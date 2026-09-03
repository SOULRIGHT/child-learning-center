"""PointEvent[] → current/previous window composition.

Evidence Packet / AI / current-center mapping에 의존하지 않는다.
ReadingRewardEvent 테이블을 읽거나 다시 더하지 않는다.
raw_subject / raw_reason 을 결과에 넣지 않는다.
"""
from __future__ import annotations

from collections import defaultdict

from features.growth.windows import (
    current_window,
    date_in_window,
    previous_window,
    resolve_as_of,
)
from features.points.events import (
    CATEGORY_ACTIVITY_MATERIAL,
    CATEGORY_PRAISE,
    CATEGORY_STATIONERY,
    CATEGORY_TEXTBOOK_COMPLETE,
    CATEGORY_UNCLASSIFIED,
    SOURCE_DAILY_SUBJECT,
    SOURCE_MANUAL,
)


def summarize_point_events(events, *, start_date, end_date):
    """[start_date, end_date] inclusive. activity_date만 사용한다."""
    window = {'start': start_date, 'end': end_date}
    in_window = tuple(
        event for event in (events or ())
        if date_in_window(getattr(event, 'activity_date', None), window)
    )
    return _summarize(in_window)


def point_composition_from_events(events, *, as_of=None, window_days=30):
    """기존 Growth current/previous window semantics로 양쪽 창을 집계한다."""
    as_of = resolve_as_of(as_of)
    days = int(window_days)
    current = current_window(as_of, days)
    previous = previous_window(as_of, days)
    return {
        'as_of': as_of,
        'window_days': days,
        'current_window': current,
        'previous_window': previous,
        'current': summarize_point_events(
            events, start_date=current['start'], end_date=current['end'],
        ),
        'previous': summarize_point_events(
            events, start_date=previous['start'], end_date=previous['end'],
        ),
    }


def _summarize(events):
    net = 0
    earn = 0
    spend = 0
    subject_points = defaultdict(int)
    subject_days = defaultdict(set)
    manual_earn = 0
    manual_earn_count = 0
    manual_spend = 0
    manual_spend_count = 0
    textbook_points = 0
    textbook_count = 0
    textbook_by_subject = defaultdict(lambda: {'points': 0, 'count': 0})
    praise_points = 0
    praise_count = 0
    material_points = 0
    material_count = 0
    material_by_item = defaultdict(lambda: {'points': 0, 'count': 0})
    stationery_points = 0
    stationery_count = 0
    stationery_by_item = defaultdict(lambda: {'points': 0, 'count': 0})
    unclassified_earn = 0
    unclassified_earn_count = 0
    unclassified_spend = 0
    unclassified_spend_count = 0

    for event in events:
        amount = int(event.amount)
        net += amount
        if amount > 0:
            earn += amount
        elif amount < 0:
            spend += amount

        if event.source_kind == SOURCE_DAILY_SUBJECT:
            key = event.subject_key
            if key:
                subject_points[key] += amount
                subject_days[key].add(event.activity_date)

        if event.source_kind != SOURCE_MANUAL:
            continue
        if event.is_reading_reward_mirror:
            continue

        if amount > 0:
            manual_earn += amount
            manual_earn_count += 1
        elif amount < 0:
            manual_spend += amount
            manual_spend_count += 1

        category = event.category
        if category == CATEGORY_TEXTBOOK_COMPLETE:
            textbook_points += amount
            textbook_count += 1
            subject_key = event.subject_key
            if subject_key:
                row = textbook_by_subject[subject_key]
                row['points'] += amount
                row['count'] += 1
        elif category == CATEGORY_PRAISE:
            praise_points += amount
            praise_count += 1
        elif category == CATEGORY_ACTIVITY_MATERIAL:
            material_points += amount
            material_count += 1
            item_key = event.item_key
            if item_key:
                row = material_by_item[item_key]
                row['points'] += amount
                row['count'] += 1
        elif category == CATEGORY_STATIONERY:
            stationery_points += amount
            stationery_count += 1
            item_key = event.item_key
            if item_key:
                row = stationery_by_item[item_key]
                row['points'] += amount
                row['count'] += 1
        elif category == CATEGORY_UNCLASSIFIED:
            if amount > 0:
                unclassified_earn += amount
                unclassified_earn_count += 1
            elif amount < 0:
                unclassified_spend += amount
                unclassified_spend_count += 1

    subjects = {}
    for key, points in subject_points.items():
        subjects[key] = {
            'points': points,
            'active_days': len(subject_days[key]),
        }

    return {
        'net_points': net,
        'total_earn_points': earn,
        'total_spend_points': spend,
        'subjects': subjects,
        'manual': {
            'earn_points': manual_earn,
            'earn_count': manual_earn_count,
            'spend_points': manual_spend,
            'spend_count': manual_spend_count,
        },
        'textbook': {
            'points': textbook_points,
            'count': textbook_count,
            'by_subject': dict(textbook_by_subject),
        },
        'praise': {
            'points': praise_points,
            'count': praise_count,
        },
        'material': {
            'points': material_points,
            'count': material_count,
            'by_item': dict(material_by_item),
        },
        'stationery': {
            'points': stationery_points,
            'count': stationery_count,
            'by_item': dict(stationery_by_item),
        },
        'unclassified': {
            'earn_points': unclassified_earn,
            'earn_count': unclassified_earn_count,
            'spend_points': unclassified_spend,
            'spend_count': unclassified_spend_count,
        },
    }
