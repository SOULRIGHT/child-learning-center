"""Teacher Growth → sanitized whitelist evidence packet.

READ-ONLY projection. metrics/insight/planner를 다시 계산하지 않는다.
DB/ORM query를 하지 않는다. LLM/prompt/validator가 아니다.
v3 canonical facts는 bundle['canonical'] projection만 사용한다.
"""
from __future__ import annotations

from datetime import date, datetime

from features.growth.center_policy import get_current_center_policy_text, normalize_center_policy_text
from features.growth.evidence_selector import (
    EvidenceCandidate,
    SELECTED_MAJOR_LIMIT,
    select_major_insights,
)
from features.growth.learning_metrics import MAX_PROGRESS_SNAPSHOT_AGE_DAYS

# Overall AI selected_insights = major only, max 4. UI INSIGHT_LIMIT(3)과 분리한다.
SELECTED_INSIGHT_LIMIT = SELECTED_MAJOR_LIMIT

SCHEMA_VERSION = 'growth_teacher_evidence_v3'
AUDIENCE_TEACHER = 'teacher'

STATUS_INSUFFICIENT_HISTORY = 'insufficient_history'
STATUS_UNAVAILABLE = 'unavailable'

_JSON_SCALARS = (str, int, float, bool, type(None))


def build_teacher_evidence_packet(bundle, selected_candidates=None, *, grade=None):
    """deterministic bundle + major candidates → teacher whitelist packet.

    selected_candidates가 없으면 canonical selector의 major(max 4)를 쓴다.
    계산/원장 조회는 하지 않는다.
    """
    bundle = bundle or {}
    canonical = bundle.get('canonical') or {}
    reading = bundle.get('reading') or {}
    points = bundle.get('points') or {}
    learning = bundle.get('learning') or {}

    scope = _scope(reading, learning, canonical)
    supporting = {
        'reading': _reading_facts(reading, canonical.get('reading') or {}),
        'points': _points_facts(
            points,
            bundle.get('point_composition'),
            canonical.get('points_peer') or {},
        ),
        'learning': _learning_facts(canonical),
        'rewards': _rewards_facts(bundle.get('rewards') or {}),
    }
    selected = _selected(supporting, selected_candidates)
    packet = {
        'schema_version': SCHEMA_VERSION,
        'audience': AUDIENCE_TEACHER,
        'as_of': _iso_date(_as_of(bundle)),
        'scope': scope,
        'center_context': _center_context(get_current_center_policy_text()),
        'selected_insights': [_insight_entry(item) for item in selected],
        'supporting_facts': supporting,
    }
    grade_value = _grade(grade)
    if grade_value is not None:
        packet['grade'] = grade_value
    return _to_jsonable(packet)


def _selected(supporting, selected_candidates):
    if selected_candidates is not None:
        return list(selected_candidates)
    return select_major_insights(supporting, limit=SELECTED_INSIGHT_LIMIT)


def _center_context(policy_text):
    """센터 운영 정책 자연어. 아동 관측 evidence가 아니므로 evidence_id를 붙이지 않는다."""
    text = normalize_center_policy_text(policy_text)
    if not text:
        return {
            'available': False,
            'policy_text': None,
        }
    return {
        'available': True,
        'policy_text': text,
    }


def _as_of(bundle):
    for key in ('canonical', 'reading', 'points', 'progress', 'learning', 'recent_window_bests'):
        value = (bundle.get(key) or {}).get('as_of')
        if value is not None:
            return value
    return None


def _scope(reading, learning, canonical):
    window_source = canonical or reading or learning or {}
    return {
        'window_days': window_source.get('window_days') or reading.get('window_days') or learning.get('window_days') or 30,
        'current_window': _window(
            window_source.get('current_window')
            or reading.get('current_window')
            or learning.get('current_window')
        ),
        'previous_window': _window(
            window_source.get('previous_window')
            or reading.get('previous_window')
            or learning.get('previous_window')
        ),
        'freshness': {
            'max_snapshot_age_days': int(
                learning.get('max_snapshot_age_days') or MAX_PROGRESS_SNAPSHOT_AGE_DAYS
            ),
        },
    }


def _reading_facts(reading, analysis_payload):
    comparable = (reading.get('comparable') or {}).get('reading_days') is True
    completed_ok = (reading.get('comparable') or {}).get('completed') is True
    current = reading.get('current') or {}
    previous = reading.get('previous') or {}
    facts = {
        'activity_days': _period_pair(
            'reading.activity_days',
            current.get('reading_days'),
            previous.get('reading_days'),
            comparable=comparable,
        ),
        'completions': _period_pair(
            'reading.completions',
            current.get('completed_count'),
            previous.get('completed_count'),
            comparable=completed_ok,
        ),
        'recommended_activity_days': _period_pair(
            'reading.recommended.activity_days',
            current.get('recommended_reading_days'),
            previous.get('recommended_reading_days'),
            comparable=comparable,
        ),
        'recommended_completions': _period_pair(
            'reading.recommended.completions',
            (current.get('completed_by_program') or {}).get('recommended'),
            (previous.get('completed_by_program') or {}).get('recommended'),
            comparable=completed_ok,
        ),
        'analysis': _reading_analysis_facts(analysis_payload),
    }
    return facts


def _reading_analysis_facts(payload):
    payload = payload or {}
    facts_in = payload.get('facts') or {}
    ai_status = payload.get('ai_status') or 'unavailable'
    recent = facts_in.get('recent_count')
    previous = facts_in.get('previous_count')
    block = {
        'ai_status': ai_status,
        'sufficiency': facts_in.get('sufficiency'),
        'recent_count': _measured(
            'reading.analysis.recent_count',
            recent,
            available=recent is not None,
        ),
        'previous_count': _measured(
            'reading.analysis.previous_count',
            previous,
            available=previous is not None,
        ),
        'text_record_count': _measured(
            'reading.analysis.text_record_count',
            facts_in.get('text_record_count'),
            available=facts_in.get('text_record_count') is not None,
        ),
        'completed_count': _measured(
            'reading.analysis.completed_count',
            facts_in.get('completed_count'),
            available=facts_in.get('completed_count') is not None,
        ),
        'completion_duration_median': _measured(
            'reading.analysis.completion_duration_median',
            facts_in.get('completion_duration_median'),
            available=facts_in.get('completion_duration_median') is not None,
            status=None if facts_in.get('completion_duration_median') is not None else STATUS_UNAVAILABLE,
        ),
        'character_count': _side_stats(
            'reading.analysis.character_count', facts_in.get('character_count') or {},
        ),
        'sentence_count': _side_stats(
            'reading.analysis.sentence_count', facts_in.get('sentence_count') or {},
        ),
        'recent_records': _meta_records(facts_in.get('recent_records') or []),
        'previous_records': _meta_records(facts_in.get('previous_records') or []),
        'ai_status_fact': _measured(
            'reading.analysis.ai_status',
            ai_status,
            available=True,
        ),
        'sufficiency_fact': _measured(
            'reading.analysis.sufficiency',
            facts_in.get('sufficiency'),
            available=facts_in.get('sufficiency') is not None,
            status=None if facts_in.get('sufficiency') is not None else STATUS_UNAVAILABLE,
        ),
        'observations': [],
        'limitations': [],
        'allowed_evidence_refs': list(payload.get('allowed_evidence_refs') or []),
    }
    if ai_status == 'current':
        block['observations'] = _observation_facts(payload.get('observations') or [])
        block['limitations'] = _limitation_facts(payload.get('limitations') or [])
    return block


def _side_stats(prefix, stats):
    return {
        'recent_median': _measured(
            f'{prefix}.recent_median',
            stats.get('recent_median'),
            available=stats.get('recent_median') is not None,
            status=None if stats.get('recent_median') is not None else STATUS_UNAVAILABLE,
        ),
        'previous_median': _measured(
            f'{prefix}.previous_median',
            stats.get('previous_median'),
            available=stats.get('previous_median') is not None,
            status=None if stats.get('previous_median') is not None else STATUS_UNAVAILABLE,
        ),
        'recent_sample_count': _measured(
            f'{prefix}.recent_sample_count',
            stats.get('recent_sample_count'),
            available=stats.get('recent_sample_count') is not None,
        ),
        'previous_sample_count': _measured(
            f'{prefix}.previous_sample_count',
            stats.get('previous_sample_count'),
            available=stats.get('previous_sample_count') is not None,
        ),
    }


def _meta_records(rows):
    found = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        found.append({
            'record_id': row.get('record_id'),
            'date': _iso_date(row.get('date')) if row.get('date') is not None else None,
            'book_title': row.get('book_title'),
            'status': row.get('status'),
            'program_type': row.get('program_type'),
        })
    return found


def _observation_facts(rows):
    found = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        found.append({
            'evidence_id': f'reading.analysis.observation.{index + 1}',
            'available': True,
            'dimension': row.get('dimension'),
            'value': row.get('observation'),
            'evidence_refs': list(row.get('evidence_refs') or []),
        })
    return found


def _limitation_facts(rows):
    found = []
    for index, row in enumerate(rows):
        if not isinstance(row, str) or not row.strip():
            continue
        found.append({
            'evidence_id': f'reading.analysis.limitation.{index + 1}',
            'available': True,
            'value': row.strip(),
        })
    return found


def _rating_pair(reading):
    current = (reading.get('current') or {}).get('paired_experience_rating') or {}
    previous = (reading.get('previous') or {}).get('paired_experience_rating') or {}
    n_current = current.get('sample_count')
    n_previous = previous.get('sample_count')
    return {
        'comparable': True,
        'n_current': _measured('reading.experience.n.current', n_current, available=n_current is not None),
        'n_previous': _measured('reading.experience.n.previous', n_previous, available=n_previous is not None),
        'difficulty': _period_pair(
            'reading.experience.difficulty',
            current.get('difficulty_average'),
            previous.get('difficulty_average'),
            comparable=True,
        ),
        'fun': _period_pair(
            'reading.experience.fun',
            current.get('fun_average'),
            previous.get('fun_average'),
            comparable=True,
        ),
    }


def _points_facts(points, composition=None, points_peer=None):
    comparable = (points.get('comparable') or {}).get('points') is True
    current = points.get('current') or {}
    previous = points.get('previous') or {}
    facts = {
        'period': _period_pair(
            'points.period',
            current.get('period_points'),
            previous.get('period_points'),
            comparable=comparable,
        ),
        'cumulative_as_of': _cumulative_fact(points.get('cumulative_as_of')),
        'peer': _canonical_peer_facts('points.peer', points_peer or {}),
    }
    if isinstance(composition, dict) and composition:
        facts['composition'] = _composition_facts(composition, comparable=comparable)
    return facts


def _composition_facts(composition, *, comparable):
    """bundle['point_composition'] whitelist. 재계산하지 않는다.

    material / stationery / unclassified / count / raw text 는 넣지 않는다.
    """
    current = composition.get('current') or {}
    previous = composition.get('previous') or {}
    extra_current = current.get('extra_learning') or {}
    extra_previous = previous.get('extra_learning') or {}
    return {
        'totals': {
            'net_points': _period_pair(
                'points.composition.totals.net_points',
                _optional_number(current.get('net_points')),
                _optional_number(previous.get('net_points')),
                comparable=comparable,
            ),
            'total_earn_points': _period_pair(
                'points.composition.totals.total_earn_points',
                _optional_number(current.get('total_earn_points')),
                _optional_number(previous.get('total_earn_points')),
                comparable=comparable,
            ),
            'total_spend_points': _period_pair(
                'points.composition.totals.total_spend_points',
                _optional_number(current.get('total_spend_points')),
                _optional_number(previous.get('total_spend_points')),
                comparable=comparable,
            ),
        },
        'subjects': _composition_subjects(
            current.get('subjects') or {},
            previous.get('subjects') or {},
            comparable=comparable,
        ),
        'textbook': _composition_category_points(
            'textbook', current, previous, comparable=comparable,
        ),
        'praise': _composition_category_points(
            'praise', current, previous, comparable=comparable,
        ),
        'help': _composition_category_points(
            'help', current, previous, comparable=comparable,
        ),
        'extra_learning': {
            'points': _period_pair(
                'points.composition.extra_learning.points',
                _composition_sum(extra_current.get('points')),
                _composition_sum(extra_previous.get('points')),
                comparable=comparable,
            ),
            'by_subject': _composition_extra_by_subject(
                extra_current.get('by_subject') or {},
                extra_previous.get('by_subject') or {},
                comparable=comparable,
            ),
        },
    }


def _composition_subjects(current_subjects, previous_subjects, *, comparable):
    subjects = {}
    for key in sorted(set(current_subjects) | set(previous_subjects)):
        if not isinstance(key, str) or not key:
            continue
        current = current_subjects.get(key) or {}
        previous = previous_subjects.get(key) or {}
        subjects[key] = {
            'points': _period_pair(
                f'points.composition.subjects.{key}.points',
                _composition_sum(current.get('points')),
                _composition_sum(previous.get('points')),
                comparable=comparable,
            ),
            'active_days': _period_pair(
                f'points.composition.subjects.{key}.active_days',
                _composition_sum(current.get('active_days')),
                _composition_sum(previous.get('active_days')),
                comparable=comparable,
            ),
        }
    return subjects


def _composition_category_points(name, current, previous, *, comparable):
    return {
        'points': _period_pair(
            f'points.composition.{name}.points',
            _composition_sum((current.get(name) or {}).get('points')),
            _composition_sum((previous.get(name) or {}).get('points')),
            comparable=comparable,
        ),
    }


def _composition_extra_by_subject(current_by, previous_by, *, comparable):
    by_subject = {}
    for key in sorted(set(current_by) | set(previous_by)):
        if not isinstance(key, str) or not key:
            continue
        current = current_by.get(key) or {}
        previous = previous_by.get(key) or {}
        by_subject[key] = {
            'points': _period_pair(
                f'points.composition.extra_learning.by_subject.{key}.points',
                _composition_sum(current.get('points')),
                _composition_sum(previous.get('points')),
                comparable=comparable,
            ),
        }
    return by_subject


def _optional_number(value):
    """unavailable/missing 은 None. 실제 합계 0만 0으로 유지한다."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def _composition_sum(value):
    """composition 기간 payload가 있을 때 빠진 카테고리는 합계 0이다."""
    number = _optional_number(value)
    return 0 if number is None else number


def _cumulative_fact(value):
    if value is None:
        return _measured('points.cumulative_as_of', None, available=False, status=STATUS_UNAVAILABLE)
    return _measured('points.cumulative_as_of', value, available=True)


def _learning_facts(canonical):
    subjects = {}
    for key, payload in ((canonical or {}).get('subjects') or {}).items():
        subjects[key] = _canonical_subject_facts(key, payload or {})
    return {'subjects': subjects}


def _canonical_subject_facts(subject_key, payload):
    current = payload.get('performance_current') or {}
    previous = payload.get('performance_previous') or {}
    compare = payload.get('compare') or {}
    prefix = f'learning.{subject_key}'
    return {
        'subject_key': subject_key,
        'subject_label': payload.get('subject_label') or subject_key,
        'performance': {
            'current': _performance_side(f'{prefix}.performance', 'current', current),
            'previous': _performance_side(f'{prefix}.performance', 'previous', previous),
        },
        'compare': {
            'enough_days': compare.get('enough_days') is True,
            'confirmation_band': compare.get('confirmation_band') or 'unavailable',
            'period_change_allowed': compare.get('period_change_allowed') is True,
            'major_insight_eligible': compare.get('major_insight_eligible') is True,
            'performance_delta_pp': _measured(
                f'{prefix}.performance.delta_pp',
                compare.get('performance_delta_pp'),
                available=compare.get('performance_delta_pp') is not None,
                status=None if compare.get('performance_delta_pp') is not None else STATUS_UNAVAILABLE,
            ),
            'confirmation_delta_pp': _measured(
                f'{prefix}.performance.confirmation_delta_pp',
                compare.get('confirmation_delta_pp'),
                available=compare.get('confirmation_delta_pp') is not None,
                status=None if compare.get('confirmation_delta_pp') is not None else STATUS_UNAVAILABLE,
            ),
            'enough_days_fact': _measured(
                f'{prefix}.performance.enough_days',
                compare.get('enough_days') is True,
                available=True,
            ),
        },
        'progress': _canonical_progress_facts(subject_key, payload.get('progress') or {}),
        'forecast': _canonical_forecast_facts(subject_key, payload.get('forecast') or {}),
        'plan': _canonical_plan_facts(subject_key, payload.get('plan') or {}),
        'performance_peer': _canonical_peer_facts(
            f'{prefix}.performance_peer', payload.get('performance_peer') or {},
        ),
        'coverage_peer': _canonical_peer_facts(
            f'{prefix}.coverage_peer', payload.get('coverage_peer') or {},
        ),
    }


def _performance_side(prefix, side, payload):
    available = payload.get('available') is not False
    expected = payload.get('expected_days')
    rate = payload.get('performance_rate')
    confirmation = payload.get('confirmation_rate')
    return {
        'expected_days': _measured(
            f'{prefix}.expected_days.{side}',
            expected,
            available=available and expected is not None,
        ),
        'studied_days': _measured(
            f'{prefix}.studied_days.{side}',
            payload.get('studied_days'),
            available=available and payload.get('studied_days') is not None,
        ),
        'explicit_not_studied_days': _measured(
            f'{prefix}.explicit_not_studied_days.{side}',
            payload.get('explicit_not_studied_days'),
            available=available and payload.get('explicit_not_studied_days') is not None,
        ),
        'unknown_days': _measured(
            f'{prefix}.unknown_days.{side}',
            payload.get('unknown_days'),
            available=available and payload.get('unknown_days') is not None,
        ),
        'extra_studied_days': _measured(
            f'{prefix}.extra_studied_days.{side}',
            payload.get('extra_studied_days'),
            available=available and payload.get('extra_studied_days') is not None,
        ),
        'performance_rate': _measured(
            f'{prefix}.rate.{side}',
            rate,
            available=available and rate is not None,
            status=None if rate is not None else STATUS_UNAVAILABLE,
        ),
        'confirmation_rate': _measured(
            f'{prefix}.confirmation.{side}',
            confirmation,
            available=available and confirmation is not None,
            status=None if confirmation is not None else STATUS_UNAVAILABLE,
        ),
        'confirmation_band': payload.get('interpretation') or 'unavailable',
        'eligibility': payload.get('eligibility') or {},
    }


def _canonical_progress_facts(subject_key, progress):
    prefix = f'learning.{subject_key}.progress'
    available = progress.get('available') is True
    status = progress.get('status') or STATUS_UNAVAILABLE
    latest = progress.get('latest_observed_end_page')
    return {
        'available': available,
        'status': status,
        'exclusions_confirmed': progress.get('exclusions_confirmed') is True,
        'observed_page_count': _measured(
            f'{prefix}.observed_page_count',
            progress.get('observed_page_count'),
            available=progress.get('observed_page_count') is not None,
            status=None if progress.get('observed_page_count') is not None else status,
        ),
        'assigned_covered_page_count': _measured(
            f'{prefix}.assigned_covered_page_count',
            progress.get('assigned_covered_page_count'),
            available=available and progress.get('assigned_covered_page_count') is not None,
            status=None if available else status,
        ),
        'assigned_denominator': _measured(
            f'{prefix}.assigned_denominator',
            progress.get('assigned_denominator'),
            available=progress.get('assigned_denominator') is not None,
            status=None if progress.get('assigned_denominator') is not None else status,
        ),
        'coverage_ratio': _measured(
            f'{prefix}.coverage_ratio',
            progress.get('coverage_ratio'),
            available=available and progress.get('coverage_ratio') is not None,
            status=None if available else status,
        ),
        'latest_observed_end_page': {
            **_measured(
                f'{prefix}.latest_observed_end_page',
                latest,
                available=latest is not None,
                status=None if latest is not None else status,
            ),
            'role': progress.get('latest_observed_end_page_role') or 'reference_position',
        },
    }


def _canonical_forecast_facts(subject_key, forecast):
    prefix = f'learning.{subject_key}.forecast'
    available = forecast.get('available') is True
    reason = forecast.get('reason') or STATUS_UNAVAILABLE
    earliest = _iso_date(forecast.get('earliest_date')) if forecast.get('earliest_date') is not None else None
    latest = _iso_date(forecast.get('latest_date')) if forecast.get('latest_date') is not None else None
    return {
        'available': available,
        'reason': reason,
        'vs_target': forecast.get('vs_target') or 'unavailable',
        'earliest_date': _measured(
            f'{prefix}.earliest_date',
            earliest,
            available=available and earliest is not None,
            status=None if available and earliest is not None else reason,
        ),
        'latest_date': _measured(
            f'{prefix}.latest_date',
            latest,
            available=available and latest is not None,
            status=None if available and latest is not None else reason,
        ),
    }


def _canonical_plan_facts(subject_key, plan):
    prefix = f'learning.{subject_key}.plan'
    available = plan.get('available') is True
    facts = {
        'available': available,
        'status': plan.get('status') or 'no_plan',
    }
    title = plan.get('textbook_title')
    if title:
        facts['textbook_title'] = title
    if plan.get('start_page') is not None:
        facts['start_page'] = _measured(
            f'{prefix}.start_page', plan.get('start_page'), available=True,
        )
    if plan.get('end_page') is not None:
        facts['end_page'] = _measured(
            f'{prefix}.end_page', plan.get('end_page'), available=True,
        )
    if plan.get('start_date') is not None:
        facts['start_date'] = _measured(
            f'{prefix}.start_date', _iso_date(plan.get('start_date')), available=True,
        )
    target = plan.get('target_completion_date')
    if target is not None:
        facts['target_completion_date'] = _measured(
            f'{prefix}.target_completion_date', _iso_date(target), available=True,
        )
    return facts


def _canonical_peer_facts(prefix, peer):
    available = peer.get('available') is True
    n = peer.get('peer_sample_count')
    if n is None:
        n = 0
    display = peer.get('display_tier') or 'none'
    child_value = peer.get('child_value')
    median = peer.get('peer_median')
    difference = peer.get('difference')
    if isinstance(difference, float):
        difference = round(difference, 6)
    if isinstance(child_value, float):
        child_value = round(child_value, 6)
    if isinstance(median, float):
        median = round(median, 6)
    return {
        'available': available,
        'display_tier': display,
        'reason': peer.get('reason') or STATUS_UNAVAILABLE,
        'child_value': _measured(
            f'{prefix}.child_value',
            child_value,
            available=child_value is not None,
            status=None if child_value is not None else STATUS_UNAVAILABLE,
        ),
        'peer_median': _measured(
            f'{prefix}.peer_median',
            median,
            available=available and median is not None,
            status=None if available else (peer.get('reason') or STATUS_UNAVAILABLE),
        ),
        'difference': _measured(
            f'{prefix}.difference',
            difference,
            available=available and difference is not None,
            status=None if available and difference is not None else STATUS_UNAVAILABLE,
        ),
        'peer_sample_count': _measured(f'{prefix}.n', n, available=True),
    }


def _observed_study_days(observed, *, comparable):
    return {
        'source': observed.get('source') or 'daily_points.date',
        'proxy': observed.get('proxy') or 'point_activity_days',
        'attendance': False,
        **_period_pair(
            'learning.observed_study_days',
            observed.get('current'),
            observed.get('previous'),
            comparable=comparable,
        ),
    }


def _subject_facts(subject_key, payload, rwb_fact):
    snapshot = payload.get('current_snapshot') or {}
    advance = payload.get('page_advance') or {}
    peer = payload.get('peer') or {}
    plan = payload.get('plan') or {}
    facts = {
        'subject_key': subject_key,
        'subject_label': payload.get('subject_name') or subject_key,
        'current_snapshot': _snapshot_facts(subject_key, snapshot),
        'page_advance': _page_advance_facts(subject_key, advance),
        'peer': _peer_facts(subject_key, peer),
        'plan': _plan_facts(subject_key, plan),
    }
    if rwb_fact:
        facts['recent_window'] = _rwb_block(
            f'learning.{subject_key}.rwb.page_advance', rwb_fact,
        )
    return facts


def _snapshot_facts(subject_key, snapshot):
    prefix = f'learning.{subject_key}.snapshot'
    available = snapshot.get('available') is True
    stale = snapshot.get('stale')
    status = 'stale' if stale else ('ok' if available else 'no_snapshot')
    facts = {
        'available': available,
        'status': status,
        'stale': bool(stale) if stale is not None else None,
        'page': _measured(
            f'{prefix}.current_page',
            snapshot.get('page'),
            available=available and snapshot.get('page') is not None,
            status=None if available else status,
        ),
        'recorded_on': _measured(
            f'{prefix}.recorded_on',
            _iso_date(snapshot.get('recorded_on')),
            available=available and snapshot.get('recorded_on') is not None,
            status=None if available else status,
        ),
    }
    title = snapshot.get('textbook_title')
    if title:
        facts['textbook_title'] = title
    return facts


def _page_advance_facts(subject_key, advance):
    prefix = f'learning.{subject_key}.page_advance'
    current = advance.get('current') or {}
    previous = advance.get('previous') or {}
    trend_ok = advance.get('comparable') is True
    return {
        'comparable': trend_ok,
        'status': advance.get('status') or STATUS_UNAVAILABLE,
        'current': _advance_side(f'{prefix}.current', current),
        'previous': _advance_side(f'{prefix}.previous', previous),
        'delta': _measured(
            f'{prefix}.delta',
            advance.get('delta'),
            available=trend_ok and advance.get('delta') is not None,
            status=None if trend_ok else (advance.get('status') or STATUS_INSUFFICIENT_HISTORY),
        ),
    }


def _advance_side(evidence_id, side):
    available = side.get('available') is True
    status = side.get('status') or (None if available else STATUS_UNAVAILABLE)
    fact = _measured(
        evidence_id,
        side.get('value'),
        available=available,
        status=None if available else status,
    )
    window = _window(side.get('window'))
    if window:
        fact['window'] = window
    title = side.get('textbook_title')
    if title:
        fact['textbook_title'] = title
    if status:
        fact['status'] = status if not available else side.get('status') or 'ok'
    return fact


def _peer_facts(subject_key, peer):
    prefix = f'learning.{subject_key}.peer'
    available = peer.get('available') is True
    status = peer.get('status') or (None if available else STATUS_UNAVAILABLE)
    n = peer.get('peer_n')
    facts = {
        'available': available,
        'status': status,
        'n': _measured(f'{prefix}.n', n if n is not None else 0, available=True),
    }
    title = peer.get('textbook_title')
    if title:
        facts['textbook_title'] = title
    if peer.get('current_page') is not None:
        facts['current_page'] = _measured(
            f'{prefix}.current_page', peer.get('current_page'), available=True,
        )
    if available:
        facts['median'] = _measured(f'{prefix}.median', peer.get('peer_median'), available=True)
        if peer.get('gap') is not None:
            facts['gap'] = _measured(f'{prefix}.gap', peer.get('gap'), available=True)
    return facts


def _plan_facts(subject_key, plan):
    prefix = f'learning.{subject_key}.plan'
    status = plan.get('status') or 'no_snapshot'
    facts = {'status': status}
    title = plan.get('textbook_title')
    if title:
        facts['textbook_title'] = title
    kind = plan.get('workload_kind')
    if kind in ('exact', 'estimated'):
        facts['workload_kind'] = kind
        facts['workload_kind_fact'] = _measured(
            f'{prefix}.workload_kind', kind, available=True,
        )
    remaining = plan.get('remaining_workload')
    if remaining is not None:
        facts['remaining_workload'] = _measured(
            f'{prefix}.remaining_workload', remaining, available=True,
        )
    days = plan.get('remaining_planned_study_days')
    if days is not None:
        facts['remaining_planned_days'] = _measured(
            f'{prefix}.remaining_planned_days', days, available=True,
        )
    required = plan.get('required_per_planned_day')
    if required is not None:
        facts['required_per_planned_day'] = _measured(
            f'{prefix}.required_per_day', required, available=True,
        )
    target = plan.get('target_completion_date')
    if target is not None:
        facts['target_completion_date'] = _measured(
            f'{prefix}.target_completion_date', _iso_date(target), available=True,
        )
    source = plan.get('weekday_source')
    if source:
        facts['weekday_source'] = source
    weekdays = plan.get('effective_weekdays')
    if weekdays is not None:
        facts['effective_weekdays'] = list(weekdays)
    return facts


def _rwb_block(prefix, fact):
    status = fact.get('status') or STATUS_INSUFFICIENT_HISTORY
    current = fact.get('current') or {}
    ok = status == 'ok' and fact.get('is_recent_window_best') is not None
    block = {
        'status': status,
        'is_recent_window_best': fact.get('is_recent_window_best'),
        'current': _rwb_side(f'{prefix}.current', current, available=ok or current.get('available') is True),
        'previous_1': _rwb_side(f'{prefix}.previous_1', fact.get('previous_1') or {}),
        'previous_2': _rwb_side(f'{prefix}.previous_2', fact.get('previous_2') or {}),
        'historical_best': _measured(
            f'{prefix}.historical_best',
            fact.get('historical_best'),
            available=fact.get('historical_best') is not None,
            status=None if fact.get('historical_best') is not None else status,
        ),
        'margin': _measured(
            f'{prefix}.margin',
            fact.get('margin'),
            available=fact.get('margin') is not None,
            status=None if fact.get('margin') is not None else status,
        ),
    }
    best_window = _window(fact.get('historical_best_window'))
    if best_window:
        block['historical_best_window'] = best_window
    title = current.get('textbook_title') or fact.get('textbook_title')
    if title:
        block['textbook_title'] = title
    return block


def _rwb_side(evidence_id, side, available=None):
    if available is None:
        available = side.get('available') is True and side.get('value') is not None
    fact = _measured(
        evidence_id,
        side.get('value'),
        available=available,
        status=None if available else (STATUS_INSUFFICIENT_HISTORY if side.get('available') is False else STATUS_UNAVAILABLE),
    )
    window = _window(side) if side.get('start') is not None else _window({
        'start': side.get('start'),
        'end': side.get('end'),
    })
    if side.get('start') is not None and side.get('end') is not None:
        fact['window'] = {'start': _iso_date(side.get('start')), 'end': _iso_date(side.get('end'))}
    elif window:
        fact['window'] = window
    return fact


def _period_pair(prefix, current, previous, *, comparable):
    current_ok = comparable and current is not None
    previous_ok = comparable and previous is not None
    delta = None
    delta_ok = current_ok and previous_ok
    if delta_ok:
        delta = current - previous
    return {
        'comparable': bool(comparable),
        'current': _measured(
            f'{prefix}.current',
            current,
            available=current_ok,
            status=None if current_ok else STATUS_INSUFFICIENT_HISTORY,
        ),
        'previous': _measured(
            f'{prefix}.previous',
            previous,
            available=previous_ok,
            status=None if previous_ok else STATUS_INSUFFICIENT_HISTORY,
        ),
        'delta': _measured(
            f'{prefix}.delta',
            delta,
            available=delta_ok,
            status=None if delta_ok else STATUS_INSUFFICIENT_HISTORY,
        ),
    }


def _rewards_facts(rewards):
    usage = rewards.get('exemption_usage') or {}
    manual = rewards.get('manual_points') or {}
    event = rewards.get('reading_reward_points') or {}
    return {
        'exemption_usage': _period_pair(
            'rewards.exemption.usage',
            usage.get('current', 0),
            usage.get('previous', 0),
            comparable=True,
        ),
        'manual_points': _period_pair(
            'rewards.manual.points',
            manual.get('current', 0),
            manual.get('previous', 0),
            comparable=True,
        ),
        'manual_event_count': _period_pair(
            'rewards.manual.event_count',
            manual.get('event_count_current', 0),
            manual.get('event_count_previous', 0),
            comparable=True,
        ),
        'reading_reward_points': _period_pair(
            'rewards.reading_event.points',
            event.get('current', 0),
            event.get('previous', 0),
            comparable=True,
        ),
        'exemption_peer': _count_peer(
            'rewards.exemption.usage.peer', usage.get('peer') or {},
        ),
        'manual_peer': _count_peer(
            'rewards.manual.points.peer', manual.get('peer') or {},
        ),
    }


def _count_peer(prefix, peer):
    available = peer.get('available') is True
    return {
        'median': _measured(
            f'{prefix}.median',
            peer.get('median'),
            available=available,
            status=None if available else STATUS_INSUFFICIENT_HISTORY,
        ),
        'n': _measured(
            f'{prefix}.n',
            peer.get('n'),
            available=peer.get('n') is not None,
        ),
    }


def _insight_entry(candidate):
    evidence = dict(getattr(candidate, 'evidence', None) or {})
    evidence.pop('relative_change', None)
    evidence_ids = getattr(candidate, 'evidence_ids', None)
    if evidence_ids is None:
        evidence_ids = _insight_evidence_ids(candidate)
    payload = {
        'id': candidate.id,
        'category': candidate.category,
        'direction': candidate.direction,
        'metric_key': candidate.metric_key,
        'tier': getattr(candidate, 'tier', None) or 'major',
        'evidence_ids': list(evidence_ids),
        'evidence': _insight_evidence(evidence),
    }
    return payload


def _insight_evidence_ids(candidate):
    metric = getattr(candidate, 'metric_key', None)
    if metric == 'reading_days':
        return _period_ids('reading.activity_days')
    if metric == 'completed_count':
        return _period_ids('reading.completions')
    if metric == 'period_points':
        return _period_ids('points.period')
    if metric == 'performance_rate':
        key = ((getattr(candidate, 'evidence', None) or {}).get('subject_key'))
        if key:
            return [
                f'learning.{key}.performance.rate.current',
                f'learning.{key}.performance.rate.previous',
                f'learning.{key}.performance.delta_pp',
            ]
    return []


def _period_ids(prefix):
    return [f'{prefix}.current', f'{prefix}.previous', f'{prefix}.delta']


def _rwb_ids(prefix):
    return [
        f'{prefix}.current',
        f'{prefix}.previous_1',
        f'{prefix}.previous_2',
        f'{prefix}.historical_best',
        f'{prefix}.margin',
    ]


def _insight_evidence(evidence):
    payload = {}
    for key in (
        'kind', 'source', 'metric_key', 'comparable',
        'window_days', 'window_count', 'lookback_days', 'comparison_window_count',
        'current', 'previous', 'delta', 'historical_best', 'margin',
        'n_current', 'n_previous',
    ):
        if key in evidence:
            payload[key] = _json_leaf(evidence.get(key))
    for key in (
        'current_window', 'previous_window', 'historical_best_window',
        'previous_1_window', 'previous_2_window',
    ):
        if key in evidence:
            payload[key] = _window(evidence.get(key)) or _json_leaf(evidence.get(key))
    subjects = evidence.get('subjects')
    if subjects:
        payload['subjects'] = [_insight_subject(row) for row in subjects]
    return payload


def _insight_subject(row):
    return {
        'subject_key': row.get('subject_key'),
        'subject_label': row.get('subject_label'),
        'textbook_title': row.get('textbook_title'),
        'current_advance': row.get('current_advance'),
        'historical_best': row.get('historical_best'),
        'margin': row.get('margin'),
        'current_window': _window(row.get('current_window')),
        'historical_best_window': _window(row.get('historical_best_window')),
    }


def _measured(evidence_id, value, *, available, status=None):
    fact = {
        'evidence_id': evidence_id,
        'available': bool(available),
    }
    if available:
        fact['value'] = value
    elif status:
        fact['status'] = status
    return fact


def _window(window):
    if not isinstance(window, dict):
        return None
    start = window.get('start')
    end = window.get('end')
    if start is None or end is None:
        return None
    return {'start': _iso_date(start), 'end': _iso_date(end)}


def _iso_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value
    raise TypeError(f'unsupported date type: {type(value)!r}')


def _grade(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    return None


def _json_leaf(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, _JSON_SCALARS):
        return value
    if isinstance(value, dict):
        return {str(key): _json_leaf(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_leaf(item) for item in value]
    return value


def _to_jsonable(value):
    if isinstance(value, _JSON_SCALARS):
        return value
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if getattr(value, '_sa_instance_state', None) is not None:
        raise TypeError('ORM object is not allowed in evidence packet')
    if isinstance(value, EvidenceCandidate):
        raise TypeError('EvidenceCandidate is not allowed in evidence packet')
    raise TypeError(f'unsupported packet type: {type(value)!r}')


def collect_evidence_ids(packet):
    """packet 안의 evidence_id 필드 값. 등장 순서를 유지한다."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            evidence_id = node.get('evidence_id')
            if isinstance(evidence_id, str):
                found.append(evidence_id)
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(packet)
    return found
