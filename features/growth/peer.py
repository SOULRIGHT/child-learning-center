"""분석기간 총 포인트 또래 비교.

DailyPoints 순위/백분위 코드를 재사용하지 않는다.
기간 총점은 features.growth.metrics.points_metrics 의 current.period_points 를 그대로 쓴다.
"""
from __future__ import annotations

from features.growth.metrics import points_metrics
from features.growth.windows import DEFAULT_WINDOW_DAYS, current_window, resolve_as_of
from features.reading.access import get_child
from features.study.peer import (
    DISPLAY_NONE,
    REASON_CHILD_UNAVAILABLE,
    REASON_EXCLUDED_FROM_STATS,
    base_peer_result,
    finalize_peer_sample,
    list_same_grade_stat_peers,
    unavailable_peer_result,
)

METRIC_PERIOD_POINTS = 'period_points'


def period_points_value(child_id, as_of=None, window_days=DEFAULT_WINDOW_DAYS):
    """canonical period total. 원장 구간 합이 없으면 0이다. unavailable을 0으로 바꾸지 않는다."""
    payload = points_metrics(child_id, as_of=as_of, window_days=window_days)
    current = payload.get('current') or {}
    return current.get('period_points')


def period_points_peer(child_id, as_of=None, window_days=DEFAULT_WINDOW_DAYS):
    as_of = resolve_as_of(as_of)
    period = current_window(as_of, window_days)
    base = base_peer_result(
        metric=METRIC_PERIOD_POINTS,
        as_of=as_of,
        period=period,
    )
    child = get_child(child_id)
    if child is None:
        return unavailable_peer_result(base, REASON_CHILD_UNAVAILABLE)
    child_value = period_points_value(child.id, as_of=as_of, window_days=window_days)
    base['child_value'] = child_value
    if child.include_in_stats is False:
        return unavailable_peer_result(
            base,
            REASON_EXCLUDED_FROM_STATS,
            child_value=child_value,
        )
    if child_value is None:
        return unavailable_peer_result(base, REASON_CHILD_UNAVAILABLE)

    values = []
    for peer in list_same_grade_stat_peers(child):
        value = period_points_value(peer.id, as_of=as_of, window_days=window_days)
        if value is None:
            continue
        values.append(value)
    return finalize_peer_sample(base, values, child_value=child_value, child_limited=False)
