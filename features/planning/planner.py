"""Deterministic rolling learning planner. READ only. Growth/UI/LLM 연결 없음."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from feature_models import LearningProgressEntry, LearningSubject, LearningWorkbookPlan
from features.dates import kst_today
from features.planning.exclusions import PlanningError
from features.planning.weekdays import (
    count_planned_study_days,
    count_planned_study_days_inclusive,
)
from features.planning.workload import compute_remaining_workload
from features.progress.service import list_active_subjects, normalize_textbook_title
from features.reading.access import get_child

STATUS_NO_SNAPSHOT = 'no_snapshot'
STATUS_NO_PLAN = 'no_plan'
STATUS_BEFORE_PLAN_START = 'before_plan_start'
STATUS_ACTIVE = 'active'
STATUS_COMPLETE = 'complete'
STATUS_TARGET_ELAPSED = 'target_elapsed'
STATUS_NO_REMAINING_PLANNED_DAYS = 'no_remaining_planned_days'


@dataclass(frozen=True)
class ChildSubjectPlanStatus:
    child_id: int
    learning_subject_id: int
    as_of: date
    status: str
    subject_key: str | None = None
    subject_name: str | None = None
    snapshot_id: int | None = None
    snapshot_date: date | None = None
    textbook_title: str | None = None
    current_page: int | None = None
    plan_id: int | None = None
    plan_start_date: date | None = None
    target_completion_date: date | None = None
    start_page: int | None = None
    end_page: int | None = None
    nominal_remaining_pages: int | None = None
    remaining_workload: int | float | None = None
    workload_kind: str | None = None
    effective_weekdays: tuple[int, ...] | None = None
    weekday_source: str | None = None
    remaining_planned_study_days: int | None = None
    required_per_planned_day: int | float | None = None


def resolve_planner_as_of(as_of=None):
    """Growth와 같이 kst_today()를 기본값으로 쓴다. date.today()는 쓰지 않는다."""
    if as_of is None:
        return kst_today()
    if isinstance(as_of, datetime):
        return as_of.date()
    if isinstance(as_of, date):
        return as_of
    raise PlanningError('as_of가 올바르지 않습니다.', code='invalid_as_of')


def build_child_subject_plan_status(child, learning_subject, as_of=None):
    """한 아동/과목의 as_of 계획 상태. DB write 없음."""
    as_of = resolve_planner_as_of(as_of)
    child_row = _resolve_child(child)
    subject = _resolve_subject(learning_subject)
    weekdays, weekday_source = _weekdays_for_child(child_row.id)
    snapshot = _latest_snapshot(child_row.id, subject.id, as_of)
    base = {
        'child_id': child_row.id,
        'learning_subject_id': subject.id,
        'as_of': as_of,
        'subject_key': subject.key,
        'subject_name': subject.name,
        'effective_weekdays': tuple(weekdays),
        'weekday_source': weekday_source,
    }
    if snapshot is None:
        return ChildSubjectPlanStatus(status=STATUS_NO_SNAPSHOT, **base)

    title = normalize_textbook_title(snapshot.textbook_title)
    snapshot_fields = {
        'snapshot_id': snapshot.id,
        'snapshot_date': snapshot.recorded_on,
        'textbook_title': title,
        'current_page': snapshot.page,
    }
    plan = _matching_plan(
        grade=child_row.grade,
        learning_subject_id=subject.id,
        textbook_title=title,
        as_of=as_of,
    )
    if plan is None:
        return ChildSubjectPlanStatus(status=STATUS_NO_PLAN, **base, **snapshot_fields)

    workload = compute_remaining_workload(
        start_page=plan.start_page,
        end_page=plan.end_page,
        current_page=snapshot.page,
        exclusion_ranges=plan.exclusion_ranges_json,
    )
    remaining_days = _remaining_planned_study_days(as_of, plan, weekdays)
    status = _status_for_plan(
        as_of=as_of,
        plan=plan,
        remaining_workload=workload.remaining_workload,
        remaining_days=remaining_days,
    )
    return ChildSubjectPlanStatus(
        status=status,
        plan_id=plan.id,
        plan_start_date=plan.start_date,
        target_completion_date=plan.target_completion_date,
        start_page=plan.start_page,
        end_page=plan.end_page,
        nominal_remaining_pages=workload.nominal_remaining_pages,
        remaining_workload=workload.remaining_workload,
        workload_kind=workload.workload_kind,
        remaining_planned_study_days=remaining_days,
        required_per_planned_day=_required_per_planned_day(
            workload.remaining_workload,
            remaining_days,
        ),
        **base,
        **snapshot_fields,
    )


def build_child_learning_plan_statuses(child, as_of=None):
    """활성 LearningSubject를 순회하는 얇은 aggregator. Growth 연결은 하지 않는다."""
    as_of = resolve_planner_as_of(as_of)
    child_row = _resolve_child(child)
    return [
        build_child_subject_plan_status(child_row, subject, as_of=as_of)
        for subject in list_active_subjects()
    ]


def _latest_snapshot(child_id, learning_subject_id, as_of):
    return (
        LearningProgressEntry.query
        .filter_by(child_id=child_id, learning_subject_id=learning_subject_id)
        .filter(LearningProgressEntry.recorded_on <= as_of)
        .order_by(LearningProgressEntry.recorded_on.desc(), LearningProgressEntry.id.desc())
        .first()
    )


def _matching_plan(*, grade, learning_subject_id, textbook_title, as_of):
    query = LearningWorkbookPlan.query.filter_by(
        grade=grade,
        learning_subject_id=learning_subject_id,
        textbook_title=textbook_title,
    )
    started = (
        query
        .filter(LearningWorkbookPlan.start_date <= as_of)
        .order_by(LearningWorkbookPlan.start_date.desc(), LearningWorkbookPlan.id.desc())
        .first()
    )
    if started is not None:
        return started
    return (
        query
        .filter(LearningWorkbookPlan.start_date > as_of)
        .order_by(LearningWorkbookPlan.start_date.asc(), LearningWorkbookPlan.id.asc())
        .first()
    )


def _remaining_planned_study_days(as_of, plan, weekdays):
    if as_of < plan.start_date:
        return count_planned_study_days_inclusive(
            plan.start_date,
            plan.target_completion_date,
            weekdays,
        )
    return count_planned_study_days(as_of, plan.target_completion_date, weekdays)


def _status_for_plan(*, as_of, plan, remaining_workload, remaining_days):
    if remaining_workload == 0:
        return STATUS_COMPLETE
    if as_of < plan.start_date:
        return STATUS_BEFORE_PLAN_START
    if plan.target_completion_date <= as_of:
        return STATUS_TARGET_ELAPSED
    if remaining_days == 0:
        return STATUS_NO_REMAINING_PLANNED_DAYS
    return STATUS_ACTIVE


def _required_per_planned_day(remaining_workload, remaining_days):
    if remaining_workload is None or remaining_days is None:
        return None
    if remaining_workload == 0 or remaining_days == 0:
        return None
    return remaining_workload / remaining_days


def _weekdays_for_child(child_id):
    from features.planning.service import resolve_child_study_weekdays
    days, source = resolve_child_study_weekdays(child_id)
    return days, source


def _resolve_child(child):
    if child is None:
        raise PlanningError('아동을 찾을 수 없습니다.', code='child_not_found')
    if hasattr(child, 'id') and hasattr(child, 'grade'):
        return child
    row = get_child(child)
    if row is None:
        raise PlanningError('아동을 찾을 수 없습니다.', code='child_not_found')
    return row


def _resolve_subject(learning_subject):
    if learning_subject is None:
        raise PlanningError('과목을 찾을 수 없습니다.', code='subject_not_found')
    if hasattr(learning_subject, 'id') and hasattr(learning_subject, 'key'):
        return learning_subject
    try:
        subject_id = int(learning_subject)
    except (TypeError, ValueError) as exc:
        raise PlanningError('과목을 찾을 수 없습니다.', code='subject_not_found') from exc
    subject = LearningSubject.query.get(subject_id)
    if subject is None:
        raise PlanningError('과목을 찾을 수 없습니다.', code='subject_not_found')
    return subject
