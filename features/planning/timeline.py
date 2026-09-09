"""학년+과목 canonical WorkbookPlan timeline.

target_completion_date는 목표 완료일이며 effective period에 쓰지 않는다.
요일/정상학습일 계산은 하지 않는다.
"""
from __future__ import annotations

from collections import defaultdict

from feature_models import LearningStudySession, LearningWorkbookPlan
from features.planning.exclusions import PlanningError


PLAN_DUPLICATE_START_MESSAGE = (
    '같은 학년·과목·시작일에 교재 계획은 하나만 등록할 수 있습니다.'
)
PLAN_TIMELINE_CONFLICT_MESSAGE = (
    '이미 기록된 학습 날짜의 교재 계획이 바뀌도록 저장할 수 없습니다.'
)


def list_timeline_plans(grade, learning_subject_id):
    if grade is None or learning_subject_id is None:
        return []
    return (
        LearningWorkbookPlan.query
        .filter_by(grade=int(grade), learning_subject_id=int(learning_subject_id))
        .order_by(
            LearningWorkbookPlan.start_date.asc(),
            LearningWorkbookPlan.id.asc(),
        )
        .all()
    )


def timeline_entries_from_plans(
    plans,
    *,
    extra_start_date=None,
    override=None,
    exclude_id=None,
):
    """override={'id', 'start_date'} 는 기존 plan의 시작일 변경안."""
    entries = []
    override_id = None if override is None else override.get('id')
    skip_id = None if exclude_id is None else int(exclude_id)
    for plan in plans:
        if skip_id is not None and int(plan.id) == skip_id:
            continue
        start = plan.start_date
        if override_id is not None and int(plan.id) == int(override_id):
            start = override['start_date']
        entries.append({'id': plan.id, 'start_date': start})
    if extra_start_date is not None:
        entries.append({'id': None, 'start_date': extra_start_date})
    entries.sort(key=lambda item: (item['start_date'], item['id'] is None, item['id'] or 0))
    return entries


def proposed_timeline_entries(
    grade,
    learning_subject_id,
    *,
    extra_start_date=None,
    override=None,
    exclude_id=None,
):
    return timeline_entries_from_plans(
        list_timeline_plans(grade, learning_subject_id),
        extra_start_date=extra_start_date,
        override=override,
        exclude_id=exclude_id,
    )


def canonical_plan_from_entries(entries, study_date):
    """effective period: [start_date, next start_date). 마지막은 +infinity."""
    started = [item for item in entries if item['start_date'] <= study_date]
    if not started:
        return None
    latest = max(item['start_date'] for item in started)
    tied = [item for item in started if item['start_date'] == latest]
    if len(tied) > 1:
        return {'ambiguous': True, 'start_date': latest, 'entries': tied}
    return tied[0]


def canonical_workbook_plan(*, grade, learning_subject_id, study_date):
    """start_date <= study_date 인 plan 중 가장 최근 start_date의 정확히 하나."""
    plans = list_timeline_plans(grade, learning_subject_id)
    chosen = canonical_plan_from_entries(
        [{'id': plan.id, 'start_date': plan.start_date} for plan in plans],
        study_date,
    )
    if chosen is None or chosen.get('ambiguous'):
        return None
    plan_id = chosen.get('id')
    if plan_id is None:
        return None
    for plan in plans:
        if plan.id == plan_id:
            return plan
    return None


def resolve_canonical_workbook_plan(child, learning_subject_id, study_date):
    """child/teacher 신규·사후입력 공통 resolver."""
    if child is None or getattr(child, 'grade', None) is None:
        return None
    return canonical_workbook_plan(
        grade=child.grade,
        learning_subject_id=learning_subject_id,
        study_date=study_date,
    )


def assert_unique_plan_start_dates(entries):
    by_start = defaultdict(list)
    for item in entries:
        by_start[item['start_date']].append(item)
    for start, group in by_start.items():
        if len(group) > 1:
            raise PlanningError(
                PLAN_DUPLICATE_START_MESSAGE,
                code='duplicate_plan_start',
            )


def assert_sessions_keep_canonical_plan(entries):
    plan_ids = [item['id'] for item in entries if item['id'] is not None]
    if not plan_ids:
        return
    sessions = (
        LearningStudySession.query
        .filter(LearningStudySession.learning_workbook_plan_id.in_(plan_ids))
        .all()
    )
    for session in sessions:
        expected = canonical_plan_from_entries(entries, session.study_date)
        expected_id = None if expected is None or expected.get('ambiguous') else expected.get('id')
        if expected_id != session.learning_workbook_plan_id:
            raise PlanningError(
                PLAN_TIMELINE_CONFLICT_MESSAGE,
                code='plan_timeline_conflicts_sessions',
            )


def list_duplicate_plan_start_groups():
    """기존 DB 충돌 보고용. 자동 삭제/변환하지 않는다."""
    rows = (
        LearningWorkbookPlan.query
        .order_by(
            LearningWorkbookPlan.grade.asc(),
            LearningWorkbookPlan.learning_subject_id.asc(),
            LearningWorkbookPlan.start_date.asc(),
            LearningWorkbookPlan.id.asc(),
        )
        .all()
    )
    grouped = defaultdict(list)
    for plan in rows:
        grouped[(plan.grade, plan.learning_subject_id, plan.start_date)].append(plan)
    collisions = []
    for (grade, subject_id, start_date), plans in grouped.items():
        if len(plans) < 2:
            continue
        collisions.append({
            'grade': grade,
            'learning_subject_id': subject_id,
            'start_date': start_date,
            'plan_ids': [plan.id for plan in plans],
            'titles': [plan.textbook_title for plan in plans],
        })
    return collisions
