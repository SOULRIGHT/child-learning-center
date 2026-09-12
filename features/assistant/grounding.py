"""Teacher assistant final-answer grounding validator.

Growth AI validator를 import하지 않는다. 철학만 맞춘다:
- LLM/DB에 의존하지 않는다
- 자연어 전체를 이해하지 않는다
- 기계적으로 확실한 factual invariant만 reject한다
- hidden LLM retry 없음
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from features.assistant.safety import RANK_MARKERS, RAW_READING_MARKERS

VALIDATOR_VERSION = 'teacher_assistant_grounding_v2'

STATUS_PASS = 'pass'
STATUS_FAIL = 'fail'
STATUS_SKIPPED = 'skipped'

SOURCE_COMPOSE = 'compose'
SOURCE_LLM = 'llm'
SOURCE_PENDING = 'pending'
SOURCE_SAFETY = 'safety'
SOURCE_NAVIGATION = 'navigation'
SOURCE_FALLBACK = 'fallback'
SOURCE_GUARDRAIL = 'guardrail'

CODE_WRONG_CHILD = 'WRONG_CHILD'
CODE_CROSS_CHILD_FACTS = 'CROSS_CHILD_FACTS'
CODE_UNSUPPORTED_NUMERIC = 'UNSUPPORTED_NUMERIC_CLAIM'
CODE_UNAVAILABLE_AS_VALUE = 'UNAVAILABLE_AS_VALUE'
CODE_DELTA_DIRECTION = 'DELTA_DIRECTION_MISMATCH'
CODE_PEER_MISMATCH = 'PEER_COMPARISON_MISMATCH'
CODE_RAW_READING = 'RAW_READING'
CODE_RANK_LANGUAGE = 'RANK_LANGUAGE'
CODE_UNSUPPORTED_CALCULATION = 'UNSUPPORTED_CALCULATION'
CODE_FACT_FAMILY_MISMATCH = 'FACT_FAMILY_MISMATCH'
CODE_INFERRED_FACT_TYPE = 'INFERRED_FACT_TYPE'

FACT_UNITS = frozenset({
    '점', '포인트', '일', '권', '페이지', '쪽', '건', '회', '명', '%', '퍼센트', '자', '문장',
})
POINT_UNITS = frozenset({'점', '포인트'})
CONVERSATIONAL_UNITS = frozenset({'분', '초', '가지', '개', '시'})
SKIP_SOURCES = frozenset({SOURCE_PENDING, SOURCE_SAFETY, SOURCE_NAVIGATION, SOURCE_GUARDRAIL})
_DATE_ISO = re.compile(r'\d{4}-\d{2}-\d{2}')
_DATE_KR = re.compile(r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일')
_DATE_KR_DAY = re.compile(r'(?:(\d{4})년\s*)?(\d{1,2})월\s*\d{1,2}일')
_YEAR_KR = re.compile(r'\d{4}년')
_MONTH_KR = re.compile(r'\d{1,2}월')
_GRADE_KR = re.compile(r'\d{1,2}학년')
_ORDINAL = re.compile(r'\d+\s*(?:번째|번(?:째)?)')
_NUMBER = re.compile(
    r'([+-]?\d{1,3}(?:,\d{3})+|[+-]?\d+(?:\.\d+)?)\s*'
    r'(포인트|페이지|쪽|점|권|일|건|회|명|%|퍼센트|자|문장|분|초|가지|개)?'
)
_DELTA_IDS = ('.delta', '.delta_pp', '.difference')
_PEER_IDS = ('.peer.median', '.peer.n', '.peer.difference', '.peer.child_value')
_PERCENT_IDS = ('.rate', 'percent', '.delta_pp', 'confirmation')
_EXTRA_RANK = ('제일 못해', '꼴찌', '하위권', '상위권', '최하위', '최상위', 'percentile')
_UNSUPPORTED_HINTS = ('평균', '예상', '예측', '적당히 계산', '추정')


@dataclass(frozen=True)
class GroundingViolation:
    code: str
    location: str = 'text'
    claim: str | None = None


@dataclass
class GroundingResult:
    ok: bool
    status: str
    violations: list = field(default_factory=list)
    used_evidence_ids: list = field(default_factory=list)
    numeric_tokens: list = field(default_factory=list)

    def codes(self):
        return [item.code for item in self.violations]

    def as_audit(self):
        return {
            'ok': self.ok,
            'status': self.status,
            'violations': self.codes(),
            'used_evidence_ids': list(self.used_evidence_ids)[:12],
            'numeric_tokens': [str(item)[:24] for item in self.numeric_tokens[:16]],
        }


def validate_grounding(
    *,
    user_text='',
    draft_text='',
    tool_results=None,
    conversation_state=None,
    page_context=None,
    answer_source=None,
):
    source = answer_source or SOURCE_LLM
    text = draft_text or ''
    facts = _collect_facts(tool_results)
    evidence_ids = [
        fact.get('evidence_id')
        for fact in facts
        if isinstance(fact.get('evidence_id'), str) and fact.get('evidence_id')
    ]
    if source in SKIP_SOURCES:
        return GroundingResult(
            ok=True,
            status=STATUS_SKIPPED,
            used_evidence_ids=evidence_ids,
        )
    violations = []
    violations.extend(_forbidden_violations(text))
    violations.extend(_child_violations(text, tool_results, conversation_state, page_context, source))
    violations.extend(_cross_child_violations(tool_results))
    if facts:
        allowlist, tokens = _numeric_allowlist(facts, tool_results)
        violations.extend(_numeric_violations(text, facts, allowlist, tokens))
        violations.extend(_unavailable_violations(text, facts))
        violations.extend(_delta_violations(text, facts))
        violations.extend(_peer_violations(text, facts, allowlist))
        violations.extend(_point_peer_basis_violations(text, facts))
        violations.extend(_unsupported_violations(text, tool_results, user_text, allowlist))
        violations.extend(_family_violations(user_text, text, facts))
        result_tokens = tokens
    else:
        result_tokens = []
    if violations:
        return GroundingResult(
            ok=False,
            status=STATUS_FAIL,
            violations=violations,
            used_evidence_ids=evidence_ids,
            numeric_tokens=result_tokens,
        )
    status = STATUS_PASS if facts or source == SOURCE_COMPOSE else STATUS_SKIPPED
    return GroundingResult(
        ok=True,
        status=status,
        used_evidence_ids=evidence_ids,
        numeric_tokens=result_tokens,
    )


def _collect_facts(tool_results):
    rows = []
    for item in tool_results or ():
        name = item.get('name')
        result = item.get('result') if isinstance(item.get('result'), dict) else {}
        if not (
            str(name or '').endswith('_facts')
            or name == 'get_subject_peer_reference'
        ):
            continue
        if result.get('skipped_unspecified_domain'):
            continue
        child = result.get('child') if isinstance(result.get('child'), dict) else {}
        for fact in result.get('facts') or ():
            if not isinstance(fact, dict):
                continue
            row = dict(fact)
            row['_child_id'] = child.get('id')
            row['_child_name'] = child.get('name')
            row['_grade'] = child.get('grade')
            row['_tool'] = name
            row['_metric_supported'] = result.get('metric_supported')
            row['_fact_family'] = fact.get('fact_family') or _family_from_evidence(fact.get('evidence_id'))
            rows.append(row)
    return rows


def _tool_children(tool_results):
    found = []
    seen = set()
    for item in tool_results or ():
        result = item.get('result') if isinstance(item.get('result'), dict) else {}
        child = result.get('child') if isinstance(result.get('child'), dict) else {}
        child_id = child.get('id')
        name = str(child.get('name') or '').strip()
        if not name or child_id in seen:
            continue
        if child_id is not None:
            seen.add(child_id)
        found.append({'id': child_id, 'name': name, 'grade': child.get('grade')})
        for match in result.get('matches') or ():
            if not isinstance(match, dict):
                continue
            match_name = str(match.get('name') or '').strip()
            match_id = match.get('id')
            if not match_name or match_id in seen:
                continue
            if match_id is not None:
                seen.add(match_id)
            found.append({'id': match_id, 'name': match_name, 'grade': match.get('grade')})
    return found


def _resolved_child(tool_results, conversation_state, page_context):
    for child in _tool_children(tool_results):
        if child.get('id') is not None and child.get('name'):
            if any(
                str(item.get('name') or '').endswith('_facts')
                or item.get('name') == 'get_subject_peer_reference'
                for item in tool_results or ()
            ):
                result = None
                for item in tool_results or ():
                    payload = item.get('result') if isinstance(item.get('result'), dict) else {}
                    bound = payload.get('child') if isinstance(payload.get('child'), dict) else {}
                    if bound.get('name'):
                        result = {
                            'id': bound.get('id'),
                            'name': bound.get('name'),
                            'grade': bound.get('grade'),
                        }
                        break
                if result:
                    return result
            break
    state = conversation_state if isinstance(conversation_state, dict) else {}
    if state.get('active_child_nickname') or state.get('active_child_id'):
        return {
            'id': state.get('active_child_id'),
            'name': state.get('active_child_nickname'),
            'grade': None,
        }
    page = page_context if isinstance(page_context, dict) else {}
    if page.get('child_name') or page.get('child_id'):
        return {
            'id': page.get('child_id'),
            'name': page.get('child_name'),
            'grade': None,
        }
    return None


def _child_violations(text, tool_results, conversation_state, page_context, source):
    if source in SKIP_SOURCES:
        return []
    allowed = set()
    for child in _tool_children(tool_results):
        name = str(child.get('name') or '').strip()
        if len(name) >= 2:
            allowed.add(name)
    resolved = _resolved_child(tool_results, conversation_state, page_context)
    resolved_name = str((resolved or {}).get('name') or '').strip()
    if len(resolved_name) >= 2:
        allowed.add(resolved_name)
    blob = text or ''
    page = page_context if isinstance(page_context, dict) else {}
    page_name = str(page.get('child_name') or '').strip()
    if (
        len(page_name) >= 2
        and page_name not in allowed
        and page_name in blob
        and page_name not in resolved_name
        and resolved_name not in page_name
    ):
        return [GroundingViolation(CODE_WRONG_CHILD, claim=page_name)]
    return []


def _cross_child_violations(_tool_results):
    """여러 아동의 각자 canonical facts를 나란히 읽는 것은 허용한다.

    서열 합성은 RANK_LANGUAGE가 막는다. child 혼선은 도구에 없는 이름을
    본문에 쓰는 경우 WRONG_CHILD로 본다.
    """
    return []


def _family_from_evidence(evidence_id):
    raw = str(evidence_id or '')
    if raw.startswith('learning.'):
        return 'learning'
    if raw.startswith('attendance.'):
        return 'attendance'
    if raw.startswith('points.') or raw.startswith('rewards.'):
        return 'points'
    if raw.startswith('reading.'):
        return 'reading'
    if 'peer' in raw:
        return 'peer'
    return 'growth'


def infer_requested_family(user_text):
    """Deterministic remainder/domain heuristic. LLM/probability 모델이 아니다.

    nickname 안의 포인트/독서 단어는 request_remainder가 제거한다.
    같은 입력이면 같은 결과다. 의미 오분류 위험은 있다.
    None이면 family mismatch를 강제하지 않는다(heuristic gap).
    """
    from features.assistant.safety import is_attendance_equivalence_request
    if is_attendance_equivalence_request(user_text):
        return 'attendance'
    from features.assistant.navigation import classify_remainder_domain, extract_child_query, request_remainder
    remainder = request_remainder(user_text, extract_child_query(user_text))
    if '출석' in (remainder or ''):
        return 'attendance'
    classified = classify_remainder_domain(remainder or user_text)
    if not classified:
        return None
    kind = classified.get('kind')
    if kind in {'learning', 'points', 'reading', 'growth', 'peer'}:
        return kind
    return None


def _used_families(facts):
    found = set()
    for fact in facts or ():
        family = fact.get('_fact_family') or _family_from_evidence(fact.get('evidence_id'))
        if family:
            found.add(family)
    return found


def _family_violations(user_text, draft_text, facts):
    requested = infer_requested_family(user_text)
    used = _used_families(facts)
    if not requested or not used:
        return []
    if requested == 'attendance':
        if used - {'attendance'}:
            return [GroundingViolation(CODE_INFERRED_FACT_TYPE, claim='attendance')]
        return []
    if requested == 'peer':
        if used <= {'peer', 'learning'}:
            return []
        return [GroundingViolation(CODE_FACT_FAMILY_MISMATCH, claim=requested)]
    if requested not in used:
        return [GroundingViolation(CODE_FACT_FAMILY_MISMATCH, claim=requested)]
    return []


def _forbidden_violations(text):
    blob = text or ''
    lowered = blob.lower()
    if any(marker.lower() in lowered for marker in RAW_READING_MARKERS):
        return [GroundingViolation(CODE_RAW_READING)]
    if 'review_text' in lowered or 'supporting_facts' in lowered:
        return [GroundingViolation(CODE_RAW_READING)]
    if any(marker in blob for marker in RANK_MARKERS + _EXTRA_RANK):
        return [GroundingViolation(CODE_RANK_LANGUAGE)]
    if '등수' in blob or '백분위' in blob or re.search(r'제일.{0,8}못해', blob):
        return [GroundingViolation(CODE_RANK_LANGUAGE)]
        return [GroundingViolation(CODE_RANK_LANGUAGE)]
    return []


def _numeric_allowlist(facts, tool_results):
    allow = set()
    tokens = []
    for fact in facts:
        if fact.get('available') is not True:
            continue
        _add_value(allow, tokens, fact.get('value'), fact.get('evidence_id'))
        display = fact.get('display_value')
        if display is not None:
            for number, _unit in _number_tokens(str(display)):
                _add_raw(allow, tokens, number)
        if fact.get('_grade') is not None:
            _add_raw(allow, tokens, fact.get('_grade'))
    for item in tool_results or ():
        result = item.get('result') if isinstance(item.get('result'), dict) else {}
        child = result.get('child') if isinstance(result.get('child'), dict) else {}
        if child.get('grade') is not None:
            _add_raw(allow, tokens, child.get('grade'))
        as_of = str(result.get('as_of') or '')
        for match in _DATE_ISO.findall(as_of):
            year, month, day = match.split('-')
            _add_raw(allow, tokens, int(year))
            _add_raw(allow, tokens, int(month))
            _add_raw(allow, tokens, int(day))
    return allow, tokens


def _add_value(allow, tokens, value, evidence_id):
    if isinstance(value, bool) or not _is_number(value):
        return
    _add_raw(allow, tokens, value)
    _add_raw(allow, tokens, abs(float(value)))
    eid = str(evidence_id or '')
    if any(marker in eid for marker in _PERCENT_IDS):
        number = float(value)
        if 0 < abs(number) <= 1:
            _add_raw(allow, tokens, abs(number) * 100)
        elif 1 < abs(number) <= 100:
            _add_raw(allow, tokens, abs(number) / 100.0)


def _add_raw(allow, tokens, value):
    if isinstance(value, bool) or not _is_number(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return
    key = _norm(value)
    allow.add(key)
    rendered = str(int(value)) if float(value).is_integer() else f'{float(value):g}'
    if rendered not in tokens:
        tokens.append(rendered)


def _numeric_violations(text, facts, allowlist, _tokens):
    violations = []
    for number, unit in _number_tokens(text):
        if unit in CONVERSATIONAL_UNITS:
            continue
        if unit in FACT_UNITS or unit is None:
            if _in_allowlist(number, allowlist):
                continue
            if unit is None and abs(number) <= 10:
                continue
            if _unavailable_zero(number, facts):
                violations.append(GroundingViolation(CODE_UNAVAILABLE_AS_VALUE, claim=str(number)))
            else:
                violations.append(GroundingViolation(CODE_UNSUPPORTED_NUMERIC, claim=str(number)))
    return violations


def _unavailable_violations(text, facts):
    blob = text or ''
    if '0으로 계산' in blob:
        if any(fact.get('available') is False for fact in facts):
            return [GroundingViolation(CODE_UNAVAILABLE_AS_VALUE, claim='0')]
    found = []
    for fact in facts:
        if fact.get('available') is not False:
            continue
        label = str(fact.get('label') or '').strip()
        if label and re.search(
            re.escape(label) + r'.{0,16}(?:0점|0일|0권|0%|0페이지|0건|\d+(?:,\d{3})*(?:\.\d+)?)',
            blob,
        ):
            found.append(GroundingViolation(CODE_UNAVAILABLE_AS_VALUE, claim=label))
    return found


def _unavailable_zero(number, facts):
    return _numeric_equal(number, 0) and any(fact.get('available') is False for fact in facts)


def _delta_violations(text, facts):
    deltas = [
        fact for fact in facts
        if fact.get('available') is True
        and _is_number(fact.get('value'))
        and any(str(fact.get('evidence_id') or '').endswith(suffix) for suffix in _DELTA_IDS)
    ]
    if not deltas:
        return []
    signs = {1 if float(fact['value']) > 0 else (-1 if float(fact['value']) < 0 else 0) for fact in deltas}
    signs.discard(0)
    if len(signs) != 1:
        return []
    sign = next(iter(signs))
    blob = text or ''
    has_up = '증가' in blob
    has_down = '감소' in blob
    if sign < 0 and has_up and not has_down:
        return [GroundingViolation(CODE_DELTA_DIRECTION, claim='증가')]
    if sign > 0 and has_down and not has_up:
        return [GroundingViolation(CODE_DELTA_DIRECTION, claim='감소')]
    return []


def _peer_violations(text, facts, allowlist):
    peers = [
        fact for fact in facts
        if fact.get('available') is True
        and any(token in str(fact.get('evidence_id') or '') for token in _PEER_IDS)
    ]
    if not peers or '중앙값' not in (text or '') and '또래' not in (text or ''):
        return []
    for number, unit in _number_tokens(text):
        if unit in CONVERSATIONAL_UNITS:
            continue
        if unit in FACT_UNITS and not _in_allowlist(number, allowlist):
            return [GroundingViolation(CODE_PEER_MISMATCH, claim=str(number))]
    return []


def _point_family(evidence_id):
    eid = str(evidence_id or '')
    if eid == 'points.cumulative_as_of':
        return 'cumulative'
    if eid in {'points.period_total.current', 'points.peer.child_value'}:
        return 'period_current'
    if eid == 'points.peer.peer_median':
        return 'peer_median'
    if eid == 'points.peer.difference':
        return 'peer_difference'
    if eid == 'points.peer.n':
        return 'peer_n'
    return None


def _point_family_values(facts):
    families = {}
    for fact in facts or ():
        if fact.get('available') is not True:
            continue
        family = _point_family(fact.get('evidence_id'))
        if not family or not _is_number(fact.get('value')):
            continue
        bucket = families.setdefault(family, set())
        bucket.add(_norm(fact.get('value')))
        bucket.add(_norm(abs(float(fact.get('value')))))
    return families


def _belongs(number, values):
    if not values:
        return False
    return _norm(number) in values or _norm(abs(float(number))) in values


def _point_peer_basis_violations(text, facts):
    """Reject mixing cumulative points into a recent-period peer comparison."""
    families = _point_family_values(facts)
    cumulative = families.get('cumulative') or set()
    period = families.get('period_current') or set()
    median = families.get('peer_median') or set()
    difference = families.get('peer_difference') or set()
    if not cumulative or not median:
        return []
    spans = _point_number_spans(text)
    if not spans:
        return []
    for index, (number, _start) in enumerate(spans):
        if not _belongs(number, median):
            continue
        if index == 0:
            continue
        previous = spans[index - 1][0]
        if _belongs(previous, cumulative) and not _belongs(previous, period):
            return [GroundingViolation(CODE_PEER_MISMATCH, claim=str(previous))]
    for line in (text or '').splitlines():
        if '중앙값' not in line and '차이' not in line:
            continue
        if not any(token in line for token in ('낮게', '높게', '낮음', '높음', '같게', '같음', '차이', '중앙값')):
            continue
        for number, unit in _number_tokens(line):
            if unit not in POINT_UNITS:
                continue
            if (
                _belongs(number, cumulative)
                and not _belongs(number, period)
                and not _belongs(number, median)
                and not _belongs(number, difference)
            ):
                return [GroundingViolation(CODE_PEER_MISMATCH, claim=str(number))]
    return []


def _point_number_spans(text):
    masked = _mask_non_metric_numbers(text or '')
    found = []
    for match in _NUMBER.finditer(masked):
        raw, unit = match.group(1), match.group(2)
        if unit not in POINT_UNITS:
            continue
        try:
            number = _parse_number(raw)
        except ValueError:
            continue
        found.append((number, match.start()))
    return found


def _unsupported_violations(text, tool_results, user_text, allowlist):
    unsupported = any(
        (item.get('result') or {}).get('metric_supported') is False
        for item in tool_results or ()
    )
    asked = any(hint in (user_text or '') for hint in _UNSUPPORTED_HINTS)
    if not unsupported and not asked:
        return []
    if unsupported:
        for number, unit in _number_tokens(text):
            if unit in FACT_UNITS and not _in_allowlist(number, allowlist):
                return [GroundingViolation(CODE_UNSUPPORTED_CALCULATION, claim=str(number))]
        return []
    if asked and not _collect_facts(tool_results):
        for number, unit in _number_tokens(text):
            if unit in FACT_UNITS:
                return [GroundingViolation(CODE_UNSUPPORTED_CALCULATION, claim=str(number))]
    return []


def _number_tokens(text):
    masked = _mask_non_metric_numbers(text or '')
    found = []
    for match in _NUMBER.finditer(masked):
        raw, unit = match.group(1), match.group(2)
        try:
            number = _parse_number(raw)
        except ValueError:
            continue
        found.append((number, unit))
    return found


def _mask_non_metric_numbers(text):
    masked = _DATE_ISO.sub(' ', text)
    masked = _DATE_KR_DAY.sub(' ', masked)
    masked = _DATE_KR.sub(' ', masked)
    masked = _YEAR_KR.sub(' ', masked)
    masked = _MONTH_KR.sub(' ', masked)
    masked = _GRADE_KR.sub(' ', masked)
    masked = _ORDINAL.sub(' ', masked)
    return masked


def _parse_number(raw):
    text = str(raw or '').strip().replace(',', '')
    if not text or text in {'+', '-'}:
        raise ValueError('empty')
    if '.' in text:
        return float(text)
    return int(text)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _norm(value):
    number = float(value)
    if number.is_integer():
        return int(number)
    return round(number, 6)


def _in_allowlist(number, allowlist):
    return _norm(number) in allowlist or _norm(abs(float(number))) in allowlist


def _numeric_equal(left, right):
    if not _is_number(left) or not _is_number(right):
        return False
    return float(left) == float(right)
