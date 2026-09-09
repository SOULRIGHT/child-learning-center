"""정상학습일 / 기대 과목 canonical resolver.

출석·포인트 원장은 쓰지 않는다. 공휴일 라이브러리 결과를 실시간 union하지 않는다.
비학습일 정본은 CenterNonStudyDay row다.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from feature_models import CenterNonStudyDay, LearningSubject
from features.dates import KST, kst_today
from features.planning.service import (
    effective_child_study_weekdays,
    get_center_weekdays,
)
from features.planning.timeline import resolve_canonical_workbook_plan
from features.planning.weekdays import canonicalize_weekdays
from features.reading.access import get_child
from features.study.calendar import get_subject_study_weekdays
from features.study.subjects import list_study_subjects


def _as_date(raw):
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError as exc:
        raise TypeError('date가 필요합니다.') from exc


def child_available_from(child):
    """Child.created_at의 KST 달력일. 이 날짜 이전은 분모에 넣지 않는다."""
    created = getattr(child, 'created_at', None)
    if created is None:
        return kst_today()
    if isinstance(created, datetime):
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return created.astimezone(KST).date()
    if isinstance(created, date):
        return created
    return kst_today()


def subject_weekdays(subject_id):
    """과목별 예정 요일. row가 없으면 센터 기본 달력."""
    stored = get_subject_study_weekdays(subject_id)
    if stored is None:
        return list(get_center_weekdays())
    return list(stored)


def child_weekdays(child_id):
    """아동 전 과목 공통 예정 등원/학습 가능 요일. row가 없으면 센터 기본 달력."""
    return list(effective_child_study_weekdays(child_id))


def effective_weekdays(child_id, subject_id):
    """subject_weekdays ∩ child_weekdays."""
    subject_days = set(canonicalize_weekdays(subject_weekdays(subject_id)))
    child_days = set(canonicalize_weekdays(child_weekdays(child_id)))
    return sorted(subject_days & child_days)


def is_excluded_day(day):
    """CenterNonStudyDay에 있으면 제외. 라이브러리 결과를 실시간 union하지 않는다.

    공휴일 seed/commit을 하지 않는다. 계산 경로는 read-only다.
    """
    day = _as_date(day)
    return CenterNonStudyDay.query.filter_by(day=day).first() is not None


def study_calendar_allows(child_id, subject_id, day):
    """과목 예정요일 ∩ 아동 예정요일 ∩ 센터 비학습일.

    미래 cutoff와 교재 존재 여부는 보지 않는다.
    완료예상 달력은 이 함수와 canonical WorkbookPlan identity를 함께 쓴다.
    """
    day = _as_date(day)
    child = get_child(child_id)
    if child is None:
        return False
    if day < child_available_from(child):
        return False
    if is_excluded_day(day):
        return False
    if day.weekday() not in set(effective_weekdays(child.id, subject_id)):
        return False
    subject = LearningSubject.query.get(int(subject_id))
    if subject is None or not subject.is_active:
        return False
    return True


def normal_study_day(child_id, subject_id, day):
    """해당 아동·과목의 정상학습일 여부."""
    day = _as_date(day)
    if day > kst_today():
        return False
    if not study_calendar_allows(child_id, subject_id, day):
        return False
    child = get_child(child_id)
    if child is None:
        return False
    subject = LearningSubject.query.get(int(subject_id))
    if subject is None:
        return False
    plan = resolve_canonical_workbook_plan(child, subject.id, day)
    if plan is None:
        return False
    return True


def expected_subjects(child_id, day):
    """그날 정상학습일인 활성 과목. 고정 3-key 목록을 쓰지 않는다."""
    day = _as_date(day)
    child = get_child(child_id)
    if child is None:
        return []
    rows = []
    for subject in list_study_subjects():
        if normal_study_day(child.id, subject.id, day):
            rows.append(subject)
    return rows
