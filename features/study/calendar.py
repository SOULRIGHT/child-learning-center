"""과목별 예정 요일 / 센터 비학습일 저장. 정상학습일 계산은 하지 않는다."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.exc import IntegrityError

from extensions import db
from feature_models import CenterNonStudyDay, CenterSubjectStudyWeekdays, LearningSubject
from features.planning.exclusions import PlanningError
from features.planning.weekdays import canonicalize_weekdays
from features.study.constants import NON_STUDY_SOURCE_CENTER, NON_STUDY_SOURCE_SYSTEM_HOLIDAY


class StudyCalendarError(Exception):
    def __init__(self, message, code='error'):
        super().__init__(message)
        self.message = message
        self.code = code


_ALLOWED_SOURCES = {
    NON_STUDY_SOURCE_CENTER,
    NON_STUDY_SOURCE_SYSTEM_HOLIDAY,
}


def save_subject_study_weekdays(learning_subject_id, study_weekdays):
    """과목별 예정 요일 upsert. 센터 전 과목 기본 달력은 변경하지 않는다."""
    subject = LearningSubject.query.get(learning_subject_id)
    if subject is None:
        raise StudyCalendarError('과목을 찾을 수 없습니다.', code='subject_not_found')
    try:
        days = canonicalize_weekdays(study_weekdays)
    except PlanningError as exc:
        raise StudyCalendarError(exc.message, code=getattr(exc, 'code', 'invalid_weekdays')) from exc
    row = CenterSubjectStudyWeekdays.query.filter_by(
        learning_subject_id=subject.id,
    ).first()
    if row is None:
        row = CenterSubjectStudyWeekdays(
            learning_subject_id=subject.id,
            study_weekdays=days,
        )
        db.session.add(row)
    else:
        row.study_weekdays = days
    db.session.commit()
    return row


def get_subject_study_weekdays(learning_subject_id):
    """저장된 과목별 요일. row가 없으면 None (센터 기본 fallback)."""
    row = CenterSubjectStudyWeekdays.query.filter_by(
        learning_subject_id=int(learning_subject_id),
    ).first()
    if row is None or row.study_weekdays is None:
        return None
    try:
        return canonicalize_weekdays(row.study_weekdays)
    except PlanningError as exc:
        raise StudyCalendarError(exc.message, code=getattr(exc, 'code', 'invalid_weekdays')) from exc


def delete_subject_study_weekdays(learning_subject_id):
    """과목별 요일 row를 지워 센터 기본 fallback으로 되돌린다."""
    row = CenterSubjectStudyWeekdays.query.filter_by(
        learning_subject_id=int(learning_subject_id),
    ).first()
    if row is None:
        return False
    db.session.delete(row)
    db.session.commit()
    return True


def get_center_non_study_day(day):
    if not isinstance(day, date) or isinstance(day, datetime):
        raise StudyCalendarError('날짜가 올바르지 않습니다.', code='invalid_date')
    return CenterNonStudyDay.query.filter_by(day=day).first()


def list_center_non_study_days(start_date, end_date):
    if not isinstance(start_date, date) or isinstance(start_date, datetime):
        raise StudyCalendarError('날짜가 올바르지 않습니다.', code='invalid_date')
    if not isinstance(end_date, date) or isinstance(end_date, datetime):
        raise StudyCalendarError('날짜가 올바르지 않습니다.', code='invalid_date')
    return (
        CenterNonStudyDay.query
        .filter(CenterNonStudyDay.day >= start_date)
        .filter(CenterNonStudyDay.day <= end_date)
        .order_by(CenterNonStudyDay.day.asc(), CenterNonStudyDay.id.asc())
        .all()
    )


def delete_center_non_study_day(day):
    """비학습일/공휴일 exclusion row 삭제. 해당 날짜는 학습일로 복구된다."""
    row = get_center_non_study_day(day)
    if row is None:
        return False
    db.session.delete(row)
    db.session.commit()
    return True


def save_center_non_study_day(day, *, source=NON_STUDY_SOURCE_CENTER, label=None, created_by_user_id=None):
    """비학습일 1건 저장. 공휴일 기본값을 자동 seed 하지 않는다."""
    if not isinstance(day, date) or isinstance(day, datetime):
        raise StudyCalendarError('날짜가 올바르지 않습니다.', code='invalid_date')
    if source not in _ALLOWED_SOURCES:
        raise StudyCalendarError('비학습일 구분이 올바르지 않습니다.', code='invalid_source')
    text = None if label is None else str(label).strip() or None
    if text is not None:
        text = text[:80]
    existing = CenterNonStudyDay.query.filter_by(day=day).first()
    if existing is not None:
        existing.source = source
        existing.label = text
        if created_by_user_id is not None:
            existing.created_by_user_id = created_by_user_id
        db.session.commit()
        return existing, False
    row = CenterNonStudyDay(
        day=day,
        source=source,
        label=text,
        created_by_user_id=created_by_user_id,
    )
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise StudyCalendarError('같은 날짜의 비학습일이 있습니다.', code='duplicate_day') from exc
    return row, True
