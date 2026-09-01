"""Deterministic teacher interpretation factual validator.

provider/LLM/DB에 의존하지 않는다. Evidence Packet + parsed_output만 본다.
자연어 전체를 이해하지 않고, 기계적으로 확실한 factual invariant만 reject한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

FACTUAL_VALIDATOR_VERSION = 'growth_teacher_factual_validator_v2'

CODE_EMPTY_EVIDENCE_IDS = 'EMPTY_EVIDENCE_IDS'
CODE_UNKNOWN_EVIDENCE_ID = 'UNKNOWN_EVIDENCE_ID'
CODE_UNSUPPORTED_NUMERIC_CLAIM = 'UNSUPPORTED_NUMERIC_CLAIM'
CODE_UNIT_MISMATCH = 'UNIT_MISMATCH'
CODE_ESTIMATED_AS_EXACT = 'ESTIMATED_AS_EXACT'
CODE_UNAVAILABLE_AS_ZERO = 'UNAVAILABLE_AS_ZERO'
CODE_NON_CONDITIONAL_SUGGESTION = 'NON_CONDITIONAL_SUGGESTION'

UNIT_DAY = 'day'
UNIT_BOOK = 'book'
UNIT_POINT = 'point'
UNIT_PAGE = 'page'
UNIT_COUNT = 'count'
UNIT_PERSON = 'person'

_UNIT_BY_TOKEN = {
    '일': UNIT_DAY,
    '권': UNIT_BOOK,
    '점': UNIT_POINT,
    '포인트': UNIT_POINT,
    '쪽': UNIT_PAGE,
    '페이지': UNIT_PAGE,
    '건': UNIT_COUNT,
    '회': UNIT_COUNT,
    '명': UNIT_PERSON,
}

_ESTIMATED_MARKERS = ('현재 추정 기준', '대략', '추정', '예상', '약')

_DATE_ISO = re.compile(r'\d{4}-\d{2}-\d{2}')
_DATE_KR = re.compile(r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일')
_YEAR_KR = re.compile(r'\d{4}년')
_MONTH_KR = re.compile(r'\d{1,2}월')
_GRADE_KR = re.compile(r'\d{1,2}학년')
_CLAIM = re.compile(
    r'(\d+(?:\.\d+)?)\s*(포인트|페이지|쪽|점|권|일|건|회|명)'
)

_ESTIMATED_ID_MARKERS = ('.plan.remaining_workload', '.plan.required_per_day')


@dataclass(frozen=True)
class EvidenceFact:
    evidence_id: str
    available: bool
    value: object
    path: str
    unit: str | None
    estimated: bool


@dataclass(frozen=True)
class Violation:
    code: str
    location: str
    evidence_id: str | None = None

    def __repr__(self):
        return f'Violation({self.code!r}, {self.location!r})'


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    violations: tuple

    def __repr__(self):
        codes = tuple(item.code for item in self.violations)
        return f'ValidationResult(valid={self.valid}, codes={codes!r})'


def collect_evidence_index(packet):
    """evidence_id -> EvidenceFact. packet field name은 id가 아니다."""
    index = {}

    def walk(node, path, estimated_plan):
        if isinstance(node, dict):
            estimated_here = estimated_plan or node.get('workload_kind') == 'estimated'
            evidence_id = node.get('evidence_id')
            if isinstance(evidence_id, str) and evidence_id and evidence_id not in index:
                available = node.get('available') is True
                index[evidence_id] = EvidenceFact(
                    evidence_id=evidence_id,
                    available=available,
                    value=node.get('value') if available else None,
                    path=path,
                    unit=_unit_for(evidence_id),
                    estimated=estimated_here and _is_estimated_numeric_id(evidence_id),
                )
            for key, value in node.items():
                child_path = f'{path}.{key}' if path else str(key)
                walk(value, child_path, estimated_here)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f'{path}[{i}]', estimated_plan)

    walk(packet if isinstance(packet, dict) else {}, '', False)
    return index


def validate_teacher_interpretation(packet, parsed_output) -> ValidationResult:
    """packet vs growth_teacher_interpretation_v2. packet/output 전문을 예외에 넣지 않는다."""
    index = collect_evidence_index(packet)
    exempt = _exempt_numbers(packet)
    violations = []
    output = parsed_output if isinstance(parsed_output, dict) else {}
    for location, text, evidence_ids, extra in _iter_items(output):
        violations.extend(_citation_violations(location, evidence_ids, index))
        if extra.get('check_conditional') and extra.get('conditional') is not True:
            violations.append(Violation(CODE_NON_CONDITIONAL_SUGGESTION, location))
        cited = tuple(
            index[eid]
            for eid in (evidence_ids if isinstance(evidence_ids, list) else [])
            if isinstance(eid, str) and eid in index
        )
        violations.extend(_numeric_violations(location, text, cited, exempt))
        violations.extend(_estimated_violations(location, text, cited))
    return ValidationResult(valid=not violations, violations=tuple(violations))


def _iter_items(output):
    for key in ('priority_insight', 'interpretation', 'next_check', 'summary'):
        item = output.get(key)
        if isinstance(item, dict):
            yield (
                key,
                item.get('text') or '',
                item.get('evidence_ids'),
                {},
            )
        elif key != 'summary':
            yield key, '', None, {}
    observations = output.get('observations')
    if isinstance(observations, list):
        for i, item in enumerate(observations):
            row = item if isinstance(item, dict) else {}
            yield (
                f'observations[{i}]',
                row.get('text') or '',
                row.get('evidence_ids'),
                {},
            )
    actions = output.get('next_actions')
    if not isinstance(actions, list):
        actions = output.get('suggestions') if isinstance(output.get('suggestions'), list) else []
    action_name = 'next_actions' if isinstance(output.get('next_actions'), list) else 'suggestions'
    for i, item in enumerate(actions):
        row = item if isinstance(item, dict) else {}
        yield (
            f'{action_name}[{i}]',
            row.get('text') or '',
            row.get('evidence_ids'),
            {'check_conditional': True, 'conditional': row.get('conditional')},
        )


def _citation_violations(location, evidence_ids, index):
    if not isinstance(evidence_ids, list) or len(evidence_ids) == 0:
        return [Violation(CODE_EMPTY_EVIDENCE_IDS, location)]
    found = []
    for item in evidence_ids:
        if not isinstance(item, str) or not item or item not in index:
            found.append(Violation(
                CODE_UNKNOWN_EVIDENCE_ID,
                location,
                evidence_id=item if isinstance(item, str) else None,
            ))
    return found


def _numeric_violations(location, text, cited, exempt):
    violations = []
    for number, unit in _numeric_claims(text):
        if _is_exempt(number, unit, exempt):
            continue
        matching = [
            fact for fact in cited
            if fact.available and _claim_matches_value(fact.value, number)
        ]
        if not matching:
            if _delta_justifies(cited, number, unit):
                continue
            unavailable_same_unit = [
                fact for fact in cited
                if (not fact.available) and fact.unit == unit
            ]
            if _numeric_equal(number, 0) and unavailable_same_unit:
                violations.append(Violation(CODE_UNAVAILABLE_AS_ZERO, location))
            else:
                violations.append(Violation(CODE_UNSUPPORTED_NUMERIC_CLAIM, location))
            continue
        typed = [fact for fact in matching if fact.unit is not None]
        if typed and not any(fact.unit == unit for fact in typed):
            violations.append(Violation(CODE_UNIT_MISMATCH, location))
    return violations


def _delta_justifies(cited, number, unit):
    facts = [
        fact for fact in cited
        if fact.available and fact.unit == unit and _is_number(fact.value)
    ]
    for i, left in enumerate(facts):
        for right in facts[i + 1:]:
            if _numeric_equal(abs(float(left.value) - float(right.value)), number):
                return True
    return False


def _estimated_violations(location, text, cited):
    if _has_estimated_marker(text):
        return []
    for fact in cited:
        if not fact.estimated or not fact.available:
            continue
        if not _mentions_estimated_value(text, fact):
            continue
        return [Violation(CODE_ESTIMATED_AS_EXACT, location)]
    return []


def _mentions_estimated_value(text, fact):
    for number, unit in _numeric_claims(text):
        if _claim_matches_value(fact.value, number) and (fact.unit is None or unit == fact.unit):
            return True
    return False


def _numeric_claims(text):
    masked = _mask_non_metric_numbers(text or '')
    claims = []
    for match in _CLAIM.finditer(masked):
        claims.append((_parse_number(match.group(1)), _UNIT_BY_TOKEN[match.group(2)]))
    return claims


def _mask_non_metric_numbers(text):
    masked = _DATE_ISO.sub(' ', text)
    masked = _DATE_KR.sub(' ', masked)
    masked = _YEAR_KR.sub(' ', masked)
    masked = _MONTH_KR.sub(' ', masked)
    masked = _GRADE_KR.sub(' ', masked)
    return masked


def _exempt_numbers(packet):
    days = set()
    other = set()
    if not isinstance(packet, dict):
        return {'day': days, 'other': other}
    scope = packet.get('scope') or {}
    window_days = scope.get('window_days')
    if _is_number(window_days):
        days.add(_as_number(window_days))
    grade = packet.get('grade')
    if _is_number(grade):
        other.add(_as_number(grade))
    return {'day': days, 'other': other}


def _is_exempt(number, unit, exempt):
    if unit == UNIT_DAY and number in exempt['day']:
        return True
    return False


def _unit_for(evidence_id):
    if '.peer.n' in evidence_id:
        return UNIT_PERSON
    if 'exemption.usage' in evidence_id and '.peer.n' not in evidence_id:
        return UNIT_COUNT
    if 'manual.event_count' in evidence_id:
        return UNIT_COUNT
    if 'observed_study_days' in evidence_id:
        return UNIT_DAY
    if 'activity_days' in evidence_id:
        return UNIT_DAY
    if 'completions' in evidence_id:
        return UNIT_BOOK
    if evidence_id.startswith('points.') or '.rwb.period' in evidence_id or 'manual.points' in evidence_id or 'reading_event.points' in evidence_id:
        return UNIT_POINT
    if 'progress_entry_count' in evidence_id:
        return UNIT_COUNT
    if '.plan.remaining_planned_days' in evidence_id:
        return UNIT_DAY
    if any(token in evidence_id for token in (
        '.page_advance',
        '.snapshot.current_page',
        '.plan.remaining_workload',
        '.plan.required_per_day',
        '.peer.median',
        '.peer.gap',
        '.peer.current_page',
        '.rwb.page_advance',
    )):
        return UNIT_PAGE
    return None


def _is_estimated_numeric_id(evidence_id):
    return any(token in evidence_id for token in _ESTIMATED_ID_MARKERS)


def _has_estimated_marker(text):
    return any(marker in (text or '') for marker in _ESTIMATED_MARKERS)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_number(value):
    return float(value) if isinstance(value, float) else int(value)


def _parse_number(raw):
    if '.' in raw:
        return float(raw)
    return int(raw)


def _claim_matches_value(value, number):
    if not _is_number(value) or not _is_number(number):
        return False
    if float(value) == float(number):
        return True
    return float(number) >= 0 and abs(float(value)) == float(number)


def _numeric_equal(left, right):
    if not _is_number(left) or not _is_number(right):
        return False
    return float(left) == float(right)
