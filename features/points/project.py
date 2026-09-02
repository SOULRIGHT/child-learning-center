"""Canonical daily point records → 분석용 PointEvent. 원장/Growth/AI에 쓰지 않는다.

classify_manual을 주입하지 않으면 현재 센터 alias를 모른다.
ReadingRewardEvent 테이블은 읽지 않는다. 독서 보상 미러는
manual source_type/source_event_id만으로 식별한다.
"""
from __future__ import annotations

from datetime import date, datetime

from features.points.events import (
    CATEGORY_UNCLASSIFIED,
    PROVENANCE_DAILY_COLUMN,
    PROVENANCE_MANUAL_JSON,
    PROVENANCE_MANUAL_SUM,
    SOURCE_DAILY_SUBJECT,
    SOURCE_MANUAL,
    ManualClassification,
    PointEvent,
    UNCLASSIFIED,
)


def project_point_events(records, *, classify_manual=None):
    events = []
    for record in records or ():
        events.extend(_project_record(record, classify_manual))
    return tuple(events)


def accounting_parts(record, events=None):
    """한 canonical daily record의 T == S + M. ReadingRewardEvent는 더하지 않는다."""
    scoped = events
    if scoped is None:
        scoped = project_point_events((record,))
    activity_date = _activity_date(record)
    if activity_date is not None:
        scoped = tuple(
            event for event in scoped
            if event.activity_date == activity_date
        )
    subject_sum = sum(
        event.amount for event in scoped
        if event.source_kind == SOURCE_DAILY_SUBJECT
    )
    manual_sum = sum(
        event.amount for event in scoped
        if event.source_kind == SOURCE_MANUAL
    )
    canonical_total = _as_int((record or {}).get('total_points'))
    return {
        'canonical_total': canonical_total,
        'subject_sum': subject_sum,
        'manual_sum': manual_sum,
        'balanced': canonical_total == subject_sum + manual_sum,
    }


def _project_record(record, classify_manual):
    if not isinstance(record, dict):
        return ()
    activity_date = _activity_date(record)
    if activity_date is None:
        return ()
    events = []
    events.extend(_subject_events(activity_date, record.get('subjects') or {}))
    events.extend(_manual_events(activity_date, record, classify_manual))
    return tuple(events)


def _subject_events(activity_date, subjects):
    events = []
    if not isinstance(subjects, dict):
        return tuple(events)
    for subject_key, raw_amount in subjects.items():
        amount = _as_int(raw_amount)
        if amount == 0:
            continue
        events.append(PointEvent(
            activity_date=activity_date,
            source_kind=SOURCE_DAILY_SUBJECT,
            amount=amount,
            provenance=PROVENANCE_DAILY_COLUMN,
            subject_key=str(subject_key) if subject_key is not None else None,
        ))
    return tuple(events)


def _manual_events(activity_date, record, classify_manual):
    items = record.get('manual_items') or []
    if isinstance(items, list) and items:
        events = []
        for item in items:
            event = _manual_json_event(activity_date, item, classify_manual)
            if event is not None:
                events.append(event)
        return tuple(events)
    amount = _as_int(record.get('manual_points'))
    if amount == 0:
        return ()
    return (
        PointEvent(
            activity_date=activity_date,
            source_kind=SOURCE_MANUAL,
            amount=amount,
            provenance=PROVENANCE_MANUAL_SUM,
            category=CATEGORY_UNCLASSIFIED,
        ),
    )


def _manual_json_event(activity_date, item, classify_manual):
    if not isinstance(item, dict):
        return None
    amount = _as_int(item.get('points'))
    if amount == 0:
        return None
    classified = _classify(classify_manual, item)
    source_type = item.get('source_type')
    if source_type is not None:
        source_type = str(source_type)
    return PointEvent(
        activity_date=activity_date,
        source_kind=SOURCE_MANUAL,
        amount=amount,
        provenance=PROVENANCE_MANUAL_JSON,
        subject_key=classified.subject_key,
        category=classified.category,
        item_key=classified.item_key,
        raw_subject=_raw_text(item.get('subject')),
        raw_reason=_raw_text(item.get('reason')),
        source_type=source_type,
        source_event_id=_optional_int(item.get('source_event_id')),
    )


def _classify(classify_manual, item):
    if classify_manual is None:
        return UNCLASSIFIED
    result = classify_manual(item)
    if isinstance(result, ManualClassification):
        return result
    return UNCLASSIFIED


def _activity_date(record):
    value = (record or {}).get('date')
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional_int(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _raw_text(value):
    if value is None:
        return None
    return str(value)
