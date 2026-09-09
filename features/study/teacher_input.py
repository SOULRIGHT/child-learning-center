"""교사용 학습 세션 form 매핑. 상태 불변조건은 records.py 만 적용한다."""
from __future__ import annotations

from feature_models import ACTOR_TEACHER
from features.study.constants import (
    INPUT_CHANNEL_TEACHER,
    RECORD_VERIFICATION_OBSERVED,
    RECORD_VERIFICATION_VERIFIED,
    STUDY_STATUS_UNKNOWN,
)
from features.study.metrics import subject_day_state
from features.study.records import (
    create_study_session,
    find_subject_day_session,
    list_subject_day_sessions,
    save_study_session_writes,
)
from features.study.schedule import expected_subjects


def create_teacher_study_session(child_id, recorded_by_user_id, form):
    """교사 입력 form을 공통 domain service로 넘긴다.

    verified는 폼에서 명시적으로 선택한 경우에만 저장한다.
    교사 역할만으로 verified가 되지 않는다.
    교재는 폼의 교재명/plan_id를 신뢰하지 않고 canonical resolver로 정한다.
    """
    verification = '' if form.get('record_verification') is None else str(
        form.get('record_verification')
    ).strip()
    if verification != RECORD_VERIFICATION_VERIFIED:
        verification = RECORD_VERIFICATION_OBSERVED
    return create_study_session(
        child_id=child_id,
        learning_subject_id=form.get('learning_subject_id'),
        study_date=form.get('study_date'),
        study_status=form.get('study_status'),
        recorded_by_user_id=recorded_by_user_id,
        record_verification=verification,
        start_page=form.get('start_page'),
        end_page=form.get('end_page'),
        textbook_title=None,
        learning_workbook_plan_id=None,  # 서버 canonical resolver만 사용
        actor_type=ACTOR_TEACHER,
        input_channel=INPUT_CHANNEL_TEACHER,
    )


def save_teacher_post_entry_form(child_id, recorded_by_user_id, form):
    """LEARN-018 사후입력. expected+unknown 과목만 저장한다. 포인트 원장을 보지 않는다."""
    study_date = form.get('study_date')
    allowed_ids = set()
    for subject in expected_subjects(child_id, study_date):
        state = subject_day_state(
            child_id,
            subject.id,
            study_date,
            list_subject_day_sessions(child_id, subject.id, study_date),
        )
        if state['expected'] and state['outcome'] == STUDY_STATUS_UNKNOWN:
            allowed_ids.add(subject.id)
    verification = '' if form.get('record_verification') is None else str(
        form.get('record_verification')
    ).strip()
    if verification != RECORD_VERIFICATION_VERIFIED:
        verification = RECORD_VERIFICATION_OBSERVED
    writes = []
    for raw_id in form.getlist('subject_id'):
        try:
            subject_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if subject_id not in allowed_ids:
            continue
        status = '' if form.get(f'study_status_{raw_id}') is None else str(
            form.get(f'study_status_{raw_id}')
        ).strip()
        if not status:
            continue
        existing = find_subject_day_session(child_id, subject_id, study_date)
        shared = {
            'study_status': status,
            'start_page': form.get(f'start_page_{raw_id}', ''),
            'end_page': form.get(f'end_page_{raw_id}', ''),
        }
        if existing is None:
            writes.append({
                'existing': None,
                'fields': {
                    'child_id': child_id,
                    'learning_subject_id': subject_id,
                    'study_date': study_date,
                    'recorded_by_user_id': recorded_by_user_id,
                    'actor_type': ACTOR_TEACHER,
                    'input_channel': INPUT_CHANNEL_TEACHER,
                    'record_verification': verification,
                    **shared,
                },
            })
        else:
            writes.append({'existing': existing, 'fields': shared})
    return save_study_session_writes(writes, changed_by_user_id=recorded_by_user_id)
