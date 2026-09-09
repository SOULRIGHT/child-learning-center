"""Step 3~6 canonical facts for Overall Growth Evidence Packet v3.

공식 재계산 없음. features.study / reading / points peer API 결과를 projection한다.
packet builder는 이 payload만 읽는다. DB query는 이 모듈과 하위 정본 API에만 둔다.
"""
from __future__ import annotations

from datetime import date, datetime

from features.growth.peer import period_points_peer
from features.growth.reading_evidence import growth_reading_evidence
from features.growth.windows import current_window, previous_window, resolve_as_of
from features.study.coverage import learning_progress_summary
from features.study.metrics import compare_periods, subject_period
from features.study.peer import peer_learning_summary
from features.study.subjects import list_study_subjects

_PEER_DROP = frozenset(('plan_id', 'subject_id', 'child_id'))
_RATE_KEYS = (
    'expected_days',
    'studied_days',
    'explicit_not_studied_days',
    'unknown_days',
    'extra_studied_days',
    'missing_days',
    'explicit_unknown_days',
    'performance_rate',
    'confirmation_rate',
    'interpretation',
    'eligibility',
)
_COMPARE_KEYS = (
    'performance_delta_pp',
    'confirmation_delta_pp',
    'enough_days',
    'confirmation_band',
    'period_change_allowed',
    'major_insight_eligible',
)
_PROGRESS_KEYS = (
    'observed_page_count',
    'assigned_covered_page_count',
    'assigned_denominator',
    'coverage_ratio',
    'latest_observed_end_page',
    'studied_session_count',
    'available',
    'status',
    'exclusions_confirmed',
    'observed_complete',
    'remaining_assigned_pages',
)
_FORECAST_KEYS = (
    'available',
    'reason',
    'earliest_date',
    'latest_date',
    'vs_target',
    'observed_complete',
    'remaining_assigned_pages',
)
_PLAN_KEYS = (
    'textbook_title',
    'start_page',
    'end_page',
    'start_date',
    'target_completion_date',
)


def build_canonical_evidence(child_id, as_of=None, window_days=30):
    """metrics_bundle에 넣을 canonical projection. unavailable 영역을 0으로 채우지 않는다."""
    as_of = resolve_as_of(as_of)
    current = current_window(as_of, window_days)
    previous = previous_window(as_of, window_days)
    payload = {
        'as_of': as_of,
        'window_days': int(window_days),
        'current_window': current,
        'previous_window': previous,
        'subjects': {},
        'points_peer': _safe_points_peer(child_id, as_of, window_days),
        'reading': _safe_reading(child_id, as_of),
    }
    subjects = _safe_list(list_study_subjects)
    progress_rows = _index_by_key(_safe_progress(child_id, as_of))
    peer_rows = _index_by_key(_safe_peers(child_id, as_of, window_days))
    for subject in subjects:
        key = subject.key
        payload['subjects'][key] = _subject_block(
            child_id,
            subject,
            current,
            previous,
            progress_rows.get(key) or {},
            peer_rows.get(key) or {},
        )
    return payload


def _subject_block(child_id, subject, current, previous, progress_row, peer_row):
    current_metrics = _safe_subject_period(
        child_id, subject.id, current['start'], current['end'],
    )
    previous_metrics = _safe_subject_period(
        child_id, subject.id, previous['start'], previous['end'],
    )
    compare = _safe_compare(current_metrics, previous_metrics)
    progress = progress_row.get('progress') or {}
    forecast = progress_row.get('forecast') or {}
    plan = (progress.get('plan') if isinstance(progress, dict) else None) or {}
    return {
        'subject_key': subject.key,
        'subject_label': subject.name,
        'performance_current': _rate_block(current_metrics),
        'performance_previous': _rate_block(previous_metrics),
        'compare': _compare_block(compare),
        'progress': _progress_block(progress, progress_row),
        'forecast': _forecast_block(forecast, progress_row),
        'plan': _plan_block(plan, progress_row),
        'performance_peer': _peer_block(peer_row.get('performance')),
        'coverage_peer': _peer_block(peer_row.get('coverage')),
    }


def _rate_block(metrics):
    if not isinstance(metrics, dict):
        return {'available': False}
    payload = {'available': True}
    for key in _RATE_KEYS:
        if key in metrics:
            payload[key] = metrics.get(key)
    return payload


def _compare_block(compare):
    if not isinstance(compare, dict):
        return {
            'enough_days': False,
            'confirmation_band': 'unavailable',
            'period_change_allowed': False,
            'major_insight_eligible': False,
        }
    return {key: compare.get(key) for key in _COMPARE_KEYS}


def _progress_block(progress, row):
    if not isinstance(progress, dict) or not progress:
        return {
            'available': False,
            'status': row.get('status') or 'no_plan',
            'latest_observed_end_page_role': 'reference_position',
        }
    payload = {key: progress.get(key) for key in _PROGRESS_KEYS if key in progress}
    payload['available'] = progress.get('available') is True
    payload['status'] = progress.get('status') or row.get('status')
    payload['latest_observed_end_page_role'] = 'reference_position'
    return payload


def _forecast_block(forecast, row):
    if not isinstance(forecast, dict) or not forecast:
        return {
            'available': False,
            'reason': row.get('status') or 'unavailable',
            'earliest_date': None,
            'latest_date': None,
            'vs_target': row.get('vs_target') or 'unavailable',
        }
    payload = {key: forecast.get(key) for key in _FORECAST_KEYS if key in forecast}
    payload['available'] = forecast.get('available') is True
    if 'vs_target' not in payload:
        payload['vs_target'] = row.get('vs_target') or 'unavailable'
    return payload


def _plan_block(plan, row):
    if not isinstance(plan, dict) or not plan:
        return {
            'available': False,
            'status': row.get('status') or 'no_plan',
        }
    payload = {key: plan.get(key) for key in _PLAN_KEYS if key in plan}
    payload['available'] = True
    payload['status'] = row.get('status') or 'active'
    return payload


def _peer_block(peer):
    if not isinstance(peer, dict) or not peer:
        return {
            'available': False,
            'display_tier': 'none',
            'reason': 'unavailable',
            'peer_sample_count': 0,
            'child_value': None,
            'peer_median': None,
            'difference': None,
        }
    payload = {
        'available': peer.get('available') is True,
        'reason': peer.get('reason'),
        'metric': peer.get('metric'),
        'child_value': peer.get('child_value'),
        'peer_median': peer.get('peer_median'),
        'difference': peer.get('difference'),
        'peer_sample_count': peer.get('peer_sample_count') if peer.get('peer_sample_count') is not None else 0,
        'display_tier': peer.get('display_tier') or 'none',
    }
    period = peer.get('period')
    if isinstance(period, dict):
        payload['period'] = {
            'start': period.get('start'),
            'end': period.get('end'),
            'days': period.get('days'),
        }
    return payload


def _safe_subject_period(child_id, subject_id, start, end):
    try:
        return subject_period(child_id, subject_id, start, end)
    except Exception:
        return None


def _safe_compare(current, previous):
    if not isinstance(current, dict) or not isinstance(previous, dict):
        return None
    try:
        return compare_periods(current, previous)
    except Exception:
        return None


def _safe_progress(child_id, as_of):
    try:
        payload = learning_progress_summary(child_id, as_of=as_of)
    except Exception:
        return []
    return list((payload or {}).get('subjects') or [])


def _safe_peers(child_id, as_of, window_days):
    try:
        payload = peer_learning_summary(child_id, as_of=as_of, window_days=window_days)
    except Exception:
        return []
    return list((payload or {}).get('subjects') or [])


def _safe_points_peer(child_id, as_of, window_days):
    try:
        return _peer_block(period_points_peer(child_id, as_of=as_of, window_days=window_days))
    except Exception:
        return _peer_block(None)


def _safe_reading(child_id, as_of):
    try:
        return growth_reading_evidence(child_id, as_of=as_of)
    except Exception:
        return {
            'as_of': _iso(as_of),
            'facts': {'available': False, 'recent_count': 0, 'previous_count': 0},
            'ai_status': 'unavailable',
            'observations': [],
            'limitations': [],
            'allowed_evidence_refs': [],
        }


def _safe_list(fn):
    try:
        return list(fn() or [])
    except Exception:
        return []


def _index_by_key(rows):
    indexed = {}
    for row in rows:
        key = row.get('subject_key')
        if key:
            indexed[key] = row
    return indexed


def _iso(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
