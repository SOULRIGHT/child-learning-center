"""아동 viewer 학습 세션 form 매핑. 상태 불변조건은 records.py 만 적용한다."""
from __future__ import annotations

from feature_models import ACTOR_CHILD
from features.study.constants import (
    INPUT_CHANNEL_CHILD,
    RECORD_VERIFICATION_OBSERVED,
)
from features.study.records import (
    find_subject_day_session,
    save_study_session_writes,
)


def save_child_study_form(child_id, recorded_by_user_id, form):
    """한 화면의 여러 과목 입력을 한 트랜잭션으로 저장한다.

    선택하지 않은 과목은 row를 만들지 않는다.
    아동 입력은 항상 observed이며 canonical WorkbookPlan resolver를 쓴다.
    """
    study_date = form.get('study_date')
    writes = []
    for raw_id in form.getlist('subject_id'):
        status = '' if form.get(f'study_status_{raw_id}') is None else str(
            form.get(f'study_status_{raw_id}')
        ).strip()
        if not status:
            continue
        existing = find_subject_day_session(child_id, raw_id, study_date)
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
                    'learning_subject_id': raw_id,
                    'study_date': study_date,
                    'recorded_by_user_id': recorded_by_user_id,
                    'actor_type': ACTOR_CHILD,
                    'input_channel': INPUT_CHANNEL_CHILD,
                    'record_verification': RECORD_VERIFICATION_OBSERVED,
                    **shared,
                },
            })
        else:
            writes.append({'existing': existing, 'fields': shared})
    return save_study_session_writes(writes, changed_by_user_id=recorded_by_user_id)
