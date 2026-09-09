"""교사용 학습 세션 form 매핑. 상태 불변조건은 records.py 만 적용한다."""
from __future__ import annotations

from feature_models import ACTOR_TEACHER
from features.study.constants import (
    INPUT_CHANNEL_TEACHER,
    RECORD_VERIFICATION_OBSERVED,
    RECORD_VERIFICATION_VERIFIED,
)
from features.study.records import create_study_session


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
