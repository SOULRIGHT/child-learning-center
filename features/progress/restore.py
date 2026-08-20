"""학습과목/진도 JSON 복원. 포인트 원장 복원 경로는 변경하지 않는다."""
from __future__ import annotations

from datetime import date, datetime

from extensions import db
from feature_models import LearningProgressEntry, LearningSubject


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
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


def restore_learning_progress_from_backup_data(backup_data):
    """LearningSubject → LearningProgressEntry 순서."""
    subjects = (backup_data or {}).get('learning_subjects') or []
    restored_subjects = 0
    for item in subjects:
        if not isinstance(item, dict):
            continue
        key = (item.get('key') or '').strip()
        name = (item.get('name') or '').strip()
        if not key or not name:
            continue
        subject = None
        if item.get('id'):
            subject = LearningSubject.query.get(item.get('id'))
        if subject is None:
            subject = LearningSubject.query.filter_by(key=key).first()
        if subject is None:
            subject = LearningSubject(id=item.get('id')) if item.get('id') else LearningSubject()
            db.session.add(subject)
        subject.key = key
        subject.name = name
        if 'is_active' in item:
            subject.is_active = bool(item.get('is_active'))
        if item.get('sort_order') is not None:
            try:
                subject.sort_order = int(item.get('sort_order'))
            except (TypeError, ValueError):
                subject.sort_order = 0
        created_at = _parse_dt(item.get('created_at'))
        updated_at = _parse_dt(item.get('updated_at'))
        if created_at:
            subject.created_at = created_at
        if updated_at:
            subject.updated_at = updated_at
        restored_subjects += 1

    db.session.flush()

    entries = (backup_data or {}).get('learning_progress_entries') or []
    restored_entries = 0
    for item in entries:
        if not isinstance(item, dict):
            continue
        child_id = item.get('child_id')
        subject_id = item.get('learning_subject_id')
        recorded_on = _parse_date(item.get('recorded_on'))
        title = (item.get('textbook_title') or '').strip()
        try:
            page = int(item.get('page'))
        except (TypeError, ValueError):
            continue
        if not child_id or not subject_id or recorded_on is None or not title:
            continue
        entry_id = item.get('id')
        entry = LearningProgressEntry.query.get(entry_id) if entry_id else None
        if entry is None:
            entry = (
                LearningProgressEntry.query.filter_by(
                    child_id=child_id,
                    learning_subject_id=subject_id,
                    recorded_on=recorded_on,
                ).first()
            )
        if entry is None:
            entry = LearningProgressEntry(id=entry_id) if entry_id else LearningProgressEntry()
            db.session.add(entry)
        entry.child_id = child_id
        entry.learning_subject_id = subject_id
        entry.recorded_on = recorded_on
        entry.textbook_title = title[:120]
        entry.page = page
        entry.created_by_user_id = item.get('created_by_user_id') or entry.created_by_user_id or 1
        created_at = _parse_dt(item.get('created_at'))
        updated_at = _parse_dt(item.get('updated_at'))
        if created_at:
            entry.created_at = created_at
        if updated_at:
            entry.updated_at = updated_at
        restored_entries += 1

    db.session.commit()
    return restored_subjects, restored_entries
