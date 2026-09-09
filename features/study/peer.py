"""Same-center peer comparison for learning metrics.

Growth AI / Evidence와 연결하지 않는다.
순위·백분위·상중하 분류를 계산하지 않는다.
"""
from __future__ import annotations

from statistics import median

from features.growth.windows import DEFAULT_WINDOW_DAYS, current_window, resolve_as_of
from features.planning.timeline import resolve_canonical_workbook_plan
from features.reading.access import get_child, model_named
from features.study.coverage import progress_for_plan
from features.study.metrics import (
    CONFIRMATION_FORBIDDEN_BELOW,
    CONFIRMATION_PRIMARY_AT,
    subject_period,
)
from features.study.subjects import list_study_subjects

METRIC_PERFORMANCE = 'performance_rate'
METRIC_COVERAGE = 'coverage_ratio'
LEARNING_METRICS = frozenset((METRIC_PERFORMANCE, METRIC_COVERAGE))

DISPLAY_PRIMARY = 'primary'
DISPLAY_LIMITED = 'limited'
DISPLAY_REFERENCE = 'reference_only'
DISPLAY_NONE = 'none'

REASON_OK = 'ok'
REASON_EXCLUDED_FROM_STATS = 'excluded_from_stats'
REASON_CHILD_UNAVAILABLE = 'child_unavailable'
REASON_CHILD_CONFIRMATION_UNAVAILABLE = 'child_confirmation_unavailable'
REASON_CHILD_CONFIRMATION_EXCLUDED = 'child_confirmation_excluded'
REASON_NO_PLAN = 'no_plan'
REASON_NO_PEERS = 'no_peers'
REASON_INSUFFICIENT_PEERS = 'insufficient_peers'
REASON_TEXTBOOK_MISMATCH = 'textbook_mismatch'
REASON_LIMITED_CONFIRMATION = 'limited_confirmation'
REASON_REFERENCE_ONLY = 'reference_only'

CONFIRM_PRIMARY = 'primary'
CONFIRM_LIMITED = 'limited'
CONFIRM_EXCLUDED = 'excluded'
CONFIRM_UNAVAILABLE = 'unavailable'

FORBIDDEN_RESULT_KEYS = frozenset((
    'rank',
    'percentile',
    'top',
    'bottom',
    'above_average',
    'below_average',
    'superior',
    'inferior',
))


def confirmation_eligibility(confirmation_rate):
    """LEARN-030. expected_days=8 규칙은 쓰지 않는다."""
    if confirmation_rate is None:
        return CONFIRM_UNAVAILABLE
    if confirmation_rate < CONFIRMATION_FORBIDDEN_BELOW:
        return CONFIRM_EXCLUDED
    if confirmation_rate < CONFIRMATION_PRIMARY_AT:
        return CONFIRM_LIMITED
    return CONFIRM_PRIMARY


def list_same_grade_stat_peers(child):
    """현재 DB = 현재 센터. self 제외, include_in_stats=False 제외, 동학년."""
    Child = model_named('Child')
    if child is None or getattr(child, 'grade', None) is None:
        return []
    return (
        Child.query
        .filter(Child.grade == child.grade)
        .filter(Child.include_in_stats.isnot(False))
        .filter(Child.id != child.id)
        .all()
    )


def peer_comparison_for_subject(
    child_id,
    learning_subject_id,
    metric,
    as_of=None,
    window_days=DEFAULT_WINDOW_DAYS,
):
    if metric not in LEARNING_METRICS:
        raise ValueError(f'unsupported peer metric: {metric}')
    as_of = resolve_as_of(as_of)
    period = current_window(as_of, window_days)
    child = get_child(child_id)
    subject_id = int(learning_subject_id)
    base = _base_result(
        metric=metric,
        as_of=as_of,
        period=period,
        subject_id=subject_id,
    )
    if child is None:
        return _unavailable(base, REASON_CHILD_UNAVAILABLE)
    if child.include_in_stats is False:
        return _unavailable(base, REASON_EXCLUDED_FROM_STATS)

    child_row = _learning_row(child, subject_id, as_of, period)
    base['child_value'] = child_row['value'] if metric == METRIC_PERFORMANCE else child_row['coverage_ratio']
    base['plan_id'] = child_row['plan_id']

    if metric == METRIC_COVERAGE and child_row['plan_id'] is None:
        return _unavailable(base, REASON_NO_PLAN, child_value=None)

    child_confirm = confirmation_eligibility(child_row['confirmation_rate'])
    if child_confirm == CONFIRM_UNAVAILABLE:
        return _unavailable(base, REASON_CHILD_CONFIRMATION_UNAVAILABLE, child_value=base['child_value'])
    if child_confirm == CONFIRM_EXCLUDED:
        return _unavailable(base, REASON_CHILD_CONFIRMATION_EXCLUDED, child_value=base['child_value'])
    if metric == METRIC_PERFORMANCE and child_row['value'] is None:
        return _unavailable(base, REASON_CHILD_UNAVAILABLE, child_value=None)
    if metric == METRIC_COVERAGE and child_row['coverage_ratio'] is None:
        return _unavailable(base, REASON_CHILD_UNAVAILABLE, child_value=None)

    peers = list_same_grade_stat_peers(child)
    if metric == METRIC_COVERAGE:
        same_plan = [
            peer for peer in peers
            if _canonical_plan_id(peer, subject_id, as_of) == child_row['plan_id']
        ]
        if peers and not same_plan:
            return _unavailable(
                base,
                REASON_TEXTBOOK_MISMATCH,
                child_value=base['child_value'],
                plan_id=child_row['plan_id'],
            )
        candidates = same_plan
    else:
        candidates = peers

    values = []
    for peer in candidates:
        row = _learning_row(peer, subject_id, as_of, period)
        if confirmation_eligibility(row['confirmation_rate']) != CONFIRM_PRIMARY:
            continue
        value = row['value'] if metric == METRIC_PERFORMANCE else row['coverage_ratio']
        if value is None:
            continue
        values.append(value)

    return _finalize_sample(
        base,
        values,
        child_value=base['child_value'],
        child_limited=(child_confirm == CONFIRM_LIMITED),
    )


def peer_learning_summary(child_id, as_of=None, window_days=DEFAULT_WINDOW_DAYS):
    as_of = resolve_as_of(as_of)
    period = current_window(as_of, window_days)
    subjects = []
    for subject in list_study_subjects():
        subjects.append({
            'subject_id': subject.id,
            'subject_key': subject.key,
            'subject_name': subject.name,
            'performance': peer_comparison_for_subject(
                child_id,
                subject.id,
                METRIC_PERFORMANCE,
                as_of=as_of,
                window_days=window_days,
            ),
            'coverage': peer_comparison_for_subject(
                child_id,
                subject.id,
                METRIC_COVERAGE,
                as_of=as_of,
                window_days=window_days,
            ),
        })
    return {
        'child_id': None if get_child(child_id) is None else int(child_id),
        'as_of': as_of,
        'period': _period_payload(period),
        'subjects': subjects,
    }


def finalize_peer_sample(base, values, *, child_value, child_limited=False):
    return _finalize_sample(base, values, child_value=child_value, child_limited=child_limited)


def base_peer_result(*, metric, as_of, period, subject_id=None, plan_id=None):
    return _base_result(
        metric=metric,
        as_of=as_of,
        period=period,
        subject_id=subject_id,
        plan_id=plan_id,
    )


def unavailable_peer_result(base, reason, **overrides):
    return _unavailable(base, reason, **overrides)


def _learning_row(child, subject_id, as_of, period):
    period_metrics = subject_period(
        child.id,
        subject_id,
        period['start'],
        period['end'],
    )
    plan = resolve_canonical_workbook_plan(child, subject_id, as_of)
    coverage_ratio = None
    plan_id = None if plan is None else plan.id
    if plan is not None:
        progress = progress_for_plan(child.id, plan, as_of=as_of)
        coverage_ratio = progress.get('coverage_ratio')
    return {
        'value': period_metrics.get('performance_rate'),
        'confirmation_rate': period_metrics.get('confirmation_rate'),
        'coverage_ratio': coverage_ratio,
        'plan_id': plan_id,
    }


def _canonical_plan_id(child, subject_id, as_of):
    plan = resolve_canonical_workbook_plan(child, subject_id, as_of)
    if plan is None:
        return None
    return plan.id


def _period_payload(period):
    return {
        'start': period['start'],
        'end': period['end'],
        'days': period['days'],
    }


def _base_result(*, metric, as_of, period, subject_id=None, plan_id=None):
    return {
        'available': False,
        'reason': REASON_NO_PEERS,
        'metric': metric,
        'child_value': None,
        'peer_median': None,
        'difference': None,
        'peer_sample_count': 0,
        'display_tier': DISPLAY_NONE,
        'as_of': as_of,
        'period': _period_payload(period),
        'subject_id': subject_id,
        'plan_id': plan_id,
    }


def _unavailable(base, reason, **overrides):
    result = dict(base)
    result.update(overrides)
    result['available'] = False
    result['reason'] = reason
    result['peer_median'] = None
    result['difference'] = None
    result['display_tier'] = DISPLAY_NONE
    if 'peer_sample_count' not in overrides:
        result['peer_sample_count'] = result.get('peer_sample_count') or 0
    return result


def _finalize_sample(base, values, *, child_value, child_limited=False):
    result = dict(base)
    result['child_value'] = child_value
    n = len(values)
    result['peer_sample_count'] = n
    if n <= 0:
        return _unavailable(result, REASON_NO_PEERS, child_value=child_value, peer_sample_count=0)
    if n == 1:
        return _unavailable(
            result,
            REASON_INSUFFICIENT_PEERS,
            child_value=child_value,
            peer_sample_count=1,
        )
    peer_median = median(values)
    difference = None if child_value is None else child_value - peer_median
    result['available'] = True
    result['peer_median'] = peer_median
    result['difference'] = difference
    if n == 2:
        result['display_tier'] = DISPLAY_REFERENCE
        result['reason'] = REASON_REFERENCE_ONLY
        return result
    if child_limited:
        result['display_tier'] = DISPLAY_LIMITED
        result['reason'] = REASON_LIMITED_CONFIRMATION
        return result
    result['display_tier'] = DISPLAY_PRIMARY
    result['reason'] = REASON_OK
    return result
