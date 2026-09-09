"""교사용 학습 세션 조회 표시. 진도율/수행률/Growth 계산은 하지 않는다."""
from __future__ import annotations

from sqlalchemy.orm import joinedload

from feature_models import LearningStudySession, LearningWorkbookPlan
from features.planning.timeline import resolve_canonical_workbook_plan
from features.progress.service import list_progress_input_subjects
from features.reading.access import model_named
from features.study.constants import (
    RECORD_VERIFICATION_OBSERVED,
    RECORD_VERIFICATION_VERIFIED,
    STUDY_STATUS_EXPLICIT_NOT_STUDIED,
    STUDY_STATUS_STUDIED,
    STUDY_STATUS_UNKNOWN,
)

CHILD_NO_PLAN_MESSAGE = (
    '아직 등록된 교재가 없어요. 선생님께 교재 등록을 부탁해 주세요.'
)

STUDY_STATUS_LABELS = {
    STUDY_STATUS_STUDIED: '공부함',
    STUDY_STATUS_EXPLICIT_NOT_STUDIED: '공부하지 않음',
    STUDY_STATUS_UNKNOWN: '기억 안 남',
}
VERIFICATION_LABELS = {
    RECORD_VERIFICATION_OBSERVED: '기록만 함',
    RECORD_VERIFICATION_VERIFIED: '실제 교재 확인함',
}


def _user_display_name(user_id):
    User = model_named('User')
    if User is None or user_id is None:
        return ''
    user = User.query.get(user_id)
    if user is None:
        return ''
    return user.name or user.username or ''


def present_study_session(row):
    studied = row.study_status == STUDY_STATUS_STUDIED
    when = row.updated_at or row.created_at
    actor = row.actor_type
    if actor == 'child':
        actor_label = '아동'
    elif actor == 'teacher':
        actor_label = '교사'
    else:
        actor_label = actor or ''
    return {
        'id': row.id,
        'child_id': row.child_id,
        'study_date': row.study_date,
        'learning_subject_id': row.learning_subject_id,
        'subject_name': row.subject.name if row.subject else '-',
        'textbook_title': row.textbook_title or '',
        'learning_workbook_plan_id': row.learning_workbook_plan_id,
        'study_status': row.study_status,
        'status_label': STUDY_STATUS_LABELS.get(row.study_status, row.study_status),
        'studied': studied,
        'start_page': row.start_page,
        'end_page': row.end_page,
        'record_verification': row.record_verification,
        'verification_label': VERIFICATION_LABELS.get(
            row.record_verification,
            row.record_verification,
        ),
        'observed': row.record_verification == RECORD_VERIFICATION_OBSERVED,
        'actor_type': row.actor_type,
        'actor_label': actor_label,
        'input_channel': row.input_channel,
        'recorded_by_name': _user_display_name(row.recorded_by_user_id),
        'when': when,
    }


def list_recent_study_sessions(child_id, limit=8):
    rows = (
        LearningStudySession.query
        .options(
            joinedload(LearningStudySession.subject),
            joinedload(LearningStudySession.workbook_plan),
        )
        .filter_by(child_id=child_id)
        .order_by(
            LearningStudySession.study_date.desc(),
            LearningStudySession.id.desc(),
        )
        .limit(int(limit))
        .all()
    )
    return [present_study_session(row) for row in rows]


def list_assignment_plans(child, as_of=None):
    """학년 공유 교재 timeline. 제목 문자열로 추정하지 않으며 날짜 필터는 resolver가 한다."""
    grade = getattr(child, 'grade', None)
    if grade is None:
        return []
    allowed_ids = {subject.id for subject in list_progress_input_subjects()}
    if not allowed_ids:
        return []
    plans = (
        LearningWorkbookPlan.query
        .options(joinedload(LearningWorkbookPlan.subject))
        .filter(LearningWorkbookPlan.grade == grade)
        .filter(LearningWorkbookPlan.learning_subject_id.in_(allowed_ids))
        .order_by(
            LearningWorkbookPlan.learning_subject_id.asc(),
            LearningWorkbookPlan.start_date.asc(),
            LearningWorkbookPlan.id.asc(),
        )
        .all()
    )
    rows = []
    for plan in plans:
        subject = plan.subject
        rows.append({
            'id': plan.id,
            'learning_subject_id': plan.learning_subject_id,
            'subject_name': subject.name if subject is not None else '',
            'textbook_title': plan.textbook_title,
            'start_page': plan.start_page,
            'end_page': plan.end_page,
            'start_date': plan.start_date,
            'target_completion_date': plan.target_completion_date,
        })
    return rows


def pick_applicable_plan(child, subject, as_of):
    """child/teacher 공통 canonical plan. 요일 기반 정상학습일은 쓰지 않는다."""
    if child is None or subject is None:
        return None
    return resolve_canonical_workbook_plan(child, subject.id, as_of)


def list_child_study_rows(child, as_of):
    """활성 과목 행. 과목명은 DB에서 오며 하드코딩하지 않는다."""
    from features.study.records import find_subject_day_session

    rows = []
    for subject in list_progress_input_subjects():
        plan = pick_applicable_plan(child, subject, as_of)
        existing = None
        if plan is not None:
            existing = find_subject_day_session(
                child.id,
                subject.id,
                as_of,
                learning_workbook_plan_id=plan.id,
            )
        rows.append({
            'subject_id': subject.id,
            'subject_name': subject.name,
            'plan': None if plan is None else {
                'id': plan.id,
                'textbook_title': plan.textbook_title,
                'start_page': plan.start_page,
                'end_page': plan.end_page,
            },
            'existing': None if existing is None else present_study_session(existing),
            'can_input': plan is not None,
        })
    return rows


def list_observed_study_sessions(child_id, limit=40):
    rows = (
        LearningStudySession.query
        .options(
            joinedload(LearningStudySession.subject),
            joinedload(LearningStudySession.workbook_plan),
        )
        .filter_by(child_id=child_id, record_verification=RECORD_VERIFICATION_OBSERVED)
        .order_by(
            LearningStudySession.study_date.desc(),
            LearningStudySession.id.desc(),
        )
        .limit(int(limit))
        .all()
    )
    return [present_study_session(row) for row in rows]


def teacher_study_template_vars(child, *, recent_limit=8):
    return {
        'recent_study_sessions': list_recent_study_sessions(child.id, limit=recent_limit),
        'observed_study_sessions': list_observed_study_sessions(child.id, limit=40),
        'assignment_plans': list_assignment_plans(child),
        'study_status_labels': STUDY_STATUS_LABELS,
        'verification_labels': VERIFICATION_LABELS,
    }
