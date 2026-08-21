"""ChildReading / ReadingDay JSON 백업 복원. 포인트 복원 경로는 변경하지 않는다."""
from __future__ import annotations

from datetime import date, datetime

from extensions import db
from feature_models import ChildReading, ReadingDay, ReadingRewardEvent


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def restore_readings_from_backup_data(backup_data):
    """Book 복원 이후에 호출한다. ChildReading → ReadingDay 순서."""
    readings = (backup_data or {}).get('child_readings') or []
    restored_readings = 0
    for item in readings:
        if not isinstance(item, dict):
            continue
        child_id = item.get('child_id')
        book_id = item.get('book_id')
        started_on = _parse_date(item.get('started_on'))
        if not child_id or not book_id or started_on is None:
            continue
        reading_id = item.get('id')
        reading = ChildReading.query.get(reading_id) if reading_id else None
        if reading is None:
            reading = ChildReading(id=reading_id) if reading_id else ChildReading()
            db.session.add(reading)
        reading.child_id = child_id
        reading.book_id = book_id
        reading.started_on = started_on
        reading.completed_on = _parse_date(item.get('completed_on'))
        reading.ended_on = _parse_date(item.get('ended_on'))
        reading.status = item.get('status') or 'in_progress'
        reading.program_type = item.get('program_type') or 'general'
        reading.policy_version = item.get('policy_version') or 'general_v2'
        reading.reward_mode = item.get('reward_mode')
        reading.created_by_user_id = item.get('created_by_user_id')
        reading.actor_type = item.get('actor_type') or 'teacher'
        created_at = _parse_dt(item.get('created_at'))
        updated_at = _parse_dt(item.get('updated_at'))
        if created_at:
            reading.created_at = created_at
        if updated_at:
            reading.updated_at = updated_at
        restored_readings += 1

    db.session.flush()

    days = (backup_data or {}).get('reading_days') or []
    restored_days = 0
    for item in days:
        if not isinstance(item, dict):
            continue
        child_reading_id = item.get('child_reading_id')
        day_date = _parse_date(item.get('date'))
        if not child_reading_id or day_date is None:
            continue
        day_id = item.get('id')
        day = ReadingDay.query.get(day_id) if day_id else None
        if day is None:
            day = ReadingDay(id=day_id) if day_id else ReadingDay()
            db.session.add(day)
        day.child_reading_id = child_reading_id
        day.date = day_date
        day.review_text = item.get('review_text')
        day.created_by_user_id = item.get('created_by_user_id')
        day.actor_type = item.get('actor_type') or 'teacher'
        day.policy_version = item.get('policy_version') or 'general_v2'
        created_at = _parse_dt(item.get('created_at'))
        updated_at = _parse_dt(item.get('updated_at'))
        if created_at:
            day.created_at = created_at
        if updated_at:
            day.updated_at = updated_at
        restored_days += 1

    events = (backup_data or {}).get('reading_reward_events') or []
    restored_events = 0
    for item in events:
        if not isinstance(item, dict):
            continue
        child_reading_id = item.get('child_reading_id')
        event_type = item.get('event_type')
        awarded_on = _parse_date(item.get('awarded_on'))
        if not child_reading_id or not event_type or awarded_on is None:
            continue
        event_id = item.get('id')
        event = ReadingRewardEvent.query.get(event_id) if event_id else None
        if event is None:
            event = ReadingRewardEvent(id=event_id) if event_id else ReadingRewardEvent()
            db.session.add(event)
        event.child_reading_id = child_reading_id
        event.event_type = event_type
        event.points = int(item.get('points') or 0)
        event.awarded_on = awarded_on
        event.policy_version = item.get('policy_version') or 'recommended_v1'
        event.created_by_user_id = item.get('created_by_user_id')
        event.revoked_at = _parse_dt(item.get('revoked_at'))
        event.revoked_by_user_id = item.get('revoked_by_user_id')
        created_at = _parse_dt(item.get('created_at'))
        if created_at:
            event.created_at = created_at
        restored_events += 1

    db.session.commit()
    return restored_readings, restored_days
