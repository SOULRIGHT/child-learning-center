"""면제권 사용 / 추가 포인트 / 추천도서 활동의 deterministic Growth metrics.

원장 dump를 반환하지 않는다. 인과 추론을 계산하지 않는다.
"""
from __future__ import annotations

from statistics import median

from feature_models import (
    PROGRAM_TYPE_RECOMMENDED,
    STATUS_COMPLETED,
    ChildReading,
    ExemptionTicket,
    ExemptionUsage,
    ReadingDay,
    ReadingRewardEvent,
)
from features.growth.windows import (
    coverage_comparable,
    current_window,
    date_in_window,
    on_or_before,
    previous_window,
    resolve_as_of,
)
from features.reading.access import get_child, model_named

READING_REWARD_SOURCE_TYPES = frozenset(('recommended_reading', 'challenge_reading'))
MIN_PEER_N = 2


def reward_metrics(child_id, as_of=None, window_days=30):
    as_of = resolve_as_of(as_of)
    current = current_window(as_of, window_days)
    previous = previous_window(as_of, window_days)
    child = get_child(child_id)
    usages = _child_usages(child_id, as_of)
    usage_current = _count_usages(usages, current, as_of)
    usage_previous = _count_usages(usages, previous, as_of)
    records = _point_records(child_id, as_of)
    manual_current = _manual_slice(records, current)
    manual_previous = _manual_slice(records, previous)
    events = _reward_events(child_id, as_of)
    event_current = _event_points(events, current, as_of)
    event_previous = _event_points(events, previous, as_of)
    recommended = _recommended_slices(child_id, as_of, current, previous)
    peer = _peer_payload(child, as_of, current, window_days)
    earliest_usage = min((row.used_on for row in usages), default=None)
    earliest_manual = min((row.get('date') for row in records if (row.get('manual_points') or 0)), default=None)
    return {
        'as_of': as_of,
        'window_days': window_days,
        'current_window': current,
        'previous_window': previous,
        'available_from': {
            'exemption_usage': earliest_usage,
            'manual_points': earliest_manual,
        },
        'comparable': {
            'exemption_usage': coverage_comparable(earliest_usage, previous),
            'manual_points': coverage_comparable(earliest_manual, previous),
        },
        'exemption_usage': {
            'current': usage_current,
            'previous': usage_previous,
            'delta': None if usage_current is None or usage_previous is None else usage_current - usage_previous,
            'peer': peer.get('exemption_usage') or _empty_peer(),
        },
        'manual_points': {
            'current': manual_current['points'],
            'previous': manual_previous['points'],
            'delta': manual_current['points'] - manual_previous['points'],
            'event_count_current': manual_current['events'],
            'event_count_previous': manual_previous['events'],
            'peer': peer.get('manual_points') or _empty_peer(),
        },
        'reading_reward_points': {
            'current': event_current,
            'previous': event_previous,
            'delta': event_current - event_previous,
        },
        'recommended': recommended,
    }


def _point_records(child_id, as_of):
    from features.growth.metrics import _canonical_daily_point_records, _records_as_of
    return _records_as_of(_canonical_daily_point_records(child_id), as_of)


def _child_usages(child_id, as_of):
    return (
        ExemptionUsage.query
        .join(ExemptionTicket, ExemptionUsage.exemption_ticket_id == ExemptionTicket.id)
        .filter(
            ExemptionTicket.child_id == child_id,
            ExemptionUsage.used_on <= as_of,
        )
        .all()
    )


def _count_usages(usages, window, as_of):
    return sum(
        1 for row in usages
        if on_or_before(row.used_on, as_of) and date_in_window(row.used_on, window)
    )


def _manual_slice(records, window):
    points = 0
    events = 0
    for row in records:
        if not date_in_window(row.get('date'), window):
            continue
        raw_items = [
            item for item in (row.get('manual_items') or [])
            if isinstance(item, dict)
        ]
        if raw_items:
            items = [
                item for item in raw_items
                if item.get('source_type') not in READING_REWARD_SOURCE_TYPES
            ]
            events += len(items)
            points += sum(int(item.get('points') or 0) for item in items)
            continue
        amount = int(row.get('manual_points') or 0)
        if amount:
            events += 1
            points += amount
    return {'points': points, 'events': events}


def _reward_events(child_id, as_of):
    readings = ChildReading.query.filter_by(child_id=child_id).all()
    ids = [row.id for row in readings]
    if not ids:
        return []
    return (
        ReadingRewardEvent.query
        .filter(
            ReadingRewardEvent.child_reading_id.in_(ids),
            ReadingRewardEvent.revoked_at.is_(None),
            ReadingRewardEvent.awarded_on <= as_of,
        )
        .all()
    )


def _event_points(events, window, as_of):
    return sum(
        int(row.points or 0)
        for row in events
        if on_or_before(row.awarded_on, as_of) and date_in_window(row.awarded_on, window)
    )


def _recommended_slices(child_id, as_of, current, previous):
    readings = (
        ChildReading.query
        .filter_by(child_id=child_id, program_type=PROGRAM_TYPE_RECOMMENDED)
        .all()
    )
    reading_ids = [row.id for row in readings]
    days = []
    if reading_ids:
        days = ReadingDay.query.filter(ReadingDay.child_reading_id.in_(reading_ids)).all()
    return {
        'activity_days': {
            'current': _recommended_days(days, current, as_of),
            'previous': _recommended_days(days, previous, as_of),
        },
        'completions': {
            'current': _recommended_completions(readings, current, as_of),
            'previous': _recommended_completions(readings, previous, as_of),
        },
    }


def _recommended_days(days, window, as_of):
    return len({
        day.date for day in days
        if on_or_before(day.date, as_of) and date_in_window(day.date, window)
    })


def _recommended_completions(readings, window, as_of):
    return sum(
        1 for reading in readings
        if reading.status == STATUS_COMPLETED
        and on_or_before(reading.completed_on, as_of)
        and date_in_window(reading.completed_on, window)
    )


def _peer_payload(child, as_of, current, window_days):
    empty = {
        'exemption_usage': _empty_peer(),
        'manual_points': _empty_peer(),
    }
    if child is None or child.grade is None:
        return empty
    Child = model_named('Child')
    peers = (
        Child.query
        .filter(Child.grade == child.grade, Child.id != child.id)
        .all()
    )
    usage_values = []
    manual_values = []
    for peer in peers:
        usages = _child_usages(peer.id, as_of)
        usage_values.append(_count_usages(usages, current, as_of))
        records = _point_records(peer.id, as_of)
        manual_values.append(_manual_slice(records, current)['points'])
    return {
        'exemption_usage': _peer_stats(usage_values),
        'manual_points': _peer_stats(manual_values),
    }


def _peer_stats(values):
    n = len(values)
    if n < MIN_PEER_N:
        return {'median': None, 'n': n, 'available': False}
    return {'median': int(round(median(values))), 'n': n, 'available': True}


def _empty_peer():
    return {'median': None, 'n': 0, 'available': False}
