"""학습 세션 저장 도메인. UI/metrics/Growth AI/QR 세션과 연결하지 않는다."""
from __future__ import annotations

import unicodedata
from datetime import date, datetime

from extensions import db
from feature_models import (
    ACTOR_CHILD,
    ACTOR_TEACHER,
    LearningStudySession,
    LearningStudySessionChange,
    LearningSubject,
    STUDY_CHANGE_CREATED,
    STUDY_CHANGE_DELETED,
    STUDY_CHANGE_UPDATED,
)
from features.dates import kst_today
from features.reading.access import get_child
from features.study.constants import (
    INPUT_CHANNEL_CHILD,
    INPUT_CHANNEL_TEACHER,
    MAX_PAGE,
    MIN_PAGE,
    NON_RANGE_STUDY_STATUSES,
    RECORD_VERIFICATION_OBSERVED,
    RECORD_VERIFICATIONS,
    STUDY_STATUS_STUDIED,
    STUDY_STATUSES,
    TITLE_MAX,
)


class StudyRecordError(Exception):
    def __init__(self, message, code='error'):
        super().__init__(message)
        self.message = message
        self.code = code


_ALLOWED_ACTORS = {ACTOR_TEACHER, ACTOR_CHILD}
_ALLOWED_CHANNELS = {INPUT_CHANNEL_TEACHER, INPUT_CHANNEL_CHILD, None}


def create_study_session(
    *,
    child_id,
    learning_subject_id,
    study_date,
    study_status,
    recorded_by_user_id,
    record_verification=RECORD_VERIFICATION_OBSERVED,
    start_page=None,
    end_page=None,
    textbook_title=None,
    actor_type=ACTOR_TEACHER,
    input_channel=None,
    change_reason=None,
):
    child = get_child(child_id)
    if child is None:
        raise StudyRecordError('아동을 찾을 수 없습니다.', code='child_not_found')
    payload = _validated_payload(
        child_id=child.id,
        learning_subject_id=learning_subject_id,
        study_date=study_date,
        study_status=study_status,
        record_verification=record_verification,
        start_page=start_page,
        end_page=end_page,
        textbook_title=textbook_title,
        recorded_by_user_id=recorded_by_user_id,
        actor_type=actor_type,
        input_channel=input_channel,
    )
    _assert_day_status_compatible(
        child_id=payload['child_id'],
        learning_subject_id=payload['learning_subject_id'],
        study_date=payload['study_date'],
        study_status=payload['study_status'],
    )
    row = LearningStudySession(**payload)
    db.session.add(row)
    db.session.flush()
    _write_change(
        row,
        event_type=STUDY_CHANGE_CREATED,
        before_payload=None,
        after_payload=_session_payload(row),
        changed_by_user_id=recorded_by_user_id,
        change_reason=change_reason,
    )
    db.session.commit()
    return row


def update_study_session(
    session,
    *,
    changed_by_user_id,
    study_status=None,
    record_verification=None,
    start_page=None,
    end_page=None,
    textbook_title=None,
    change_reason=None,
):
    if session is None or getattr(session, 'id', None) is None:
        raise StudyRecordError('학습 세션을 찾을 수 없습니다.', code='session_not_found')
    before = _session_payload(session)
    next_status = session.study_status if study_status is None else study_status
    if next_status in NON_RANGE_STUDY_STATUSES:
        next_start = None if start_page is None else start_page
        next_end = None if end_page is None else end_page
    else:
        next_start = session.start_page if start_page is None else start_page
        next_end = session.end_page if end_page is None else end_page
    merged = {
        'child_id': session.child_id,
        'learning_subject_id': session.learning_subject_id,
        'study_date': session.study_date,
        'study_status': next_status,
        'record_verification': (
            session.record_verification if record_verification is None else record_verification
        ),
        'start_page': next_start,
        'end_page': next_end,
        'textbook_title': session.textbook_title if textbook_title is None else textbook_title,
        'recorded_by_user_id': session.recorded_by_user_id,
        'actor_type': session.actor_type,
        'input_channel': session.input_channel,
    }
    payload = _validated_payload(**merged)
    _assert_day_status_compatible(
        child_id=payload['child_id'],
        learning_subject_id=payload['learning_subject_id'],
        study_date=payload['study_date'],
        study_status=payload['study_status'],
        exclude_session_id=session.id,
    )
    session.study_status = payload['study_status']
    session.record_verification = payload['record_verification']
    session.start_page = payload['start_page']
    session.end_page = payload['end_page']
    session.textbook_title = payload['textbook_title']
    session.updated_at = datetime.utcnow()
    _write_change(
        session,
        event_type=STUDY_CHANGE_UPDATED,
        before_payload=before,
        after_payload=_session_payload(session),
        changed_by_user_id=changed_by_user_id,
        change_reason=change_reason,
    )
    db.session.commit()
    return session


def delete_study_session(session, *, changed_by_user_id, change_reason):
    """예외적 삭제. 사유 없이 지우지 않는다. 이력 행은 남긴다."""
    if session is None or getattr(session, 'id', None) is None:
        raise StudyRecordError('학습 세션을 찾을 수 없습니다.', code='session_not_found')
    reason = None if change_reason is None else str(change_reason).strip()
    if not reason:
        raise StudyRecordError('삭제 사유가 필요합니다.', code='reason_required')
    before = _session_payload(session)
    _write_change(
        session,
        event_type=STUDY_CHANGE_DELETED,
        before_payload=before,
        after_payload=None,
        changed_by_user_id=changed_by_user_id,
        change_reason=reason,
    )
    db.session.delete(session)
    db.session.commit()


def _validated_payload(
    *,
    child_id,
    learning_subject_id,
    study_date,
    study_status,
    record_verification,
    start_page,
    end_page,
    textbook_title,
    recorded_by_user_id,
    actor_type,
    input_channel,
):
    subject = _require_subject(learning_subject_id)
    day = _clean_study_date(study_date)
    status = _clean_choice(study_status, STUDY_STATUSES, '학습 상태', 'invalid_study_status')
    verification = _clean_choice(
        record_verification,
        RECORD_VERIFICATIONS,
        '기록 검증 상태',
        'invalid_record_verification',
    )
    actor = _clean_choice(actor_type, _ALLOWED_ACTORS, '입력자 구분', 'invalid_actor_type')
    channel = input_channel
    if channel is not None:
        channel = str(channel).strip() or None
    if channel not in _ALLOWED_CHANNELS and channel is not None:
        raise StudyRecordError('입력 출처가 올바르지 않습니다.', code='invalid_input_channel')
    try:
        user_id = int(recorded_by_user_id)
    except (TypeError, ValueError) as exc:
        raise StudyRecordError('입력자를 확인할 수 없습니다.', code='user_required') from exc

    if status == STUDY_STATUS_STUDIED:
        start = _clean_page(start_page, '시작 페이지')
        end = _clean_page(end_page, '끝 페이지')
        if start > end:
            raise StudyRecordError('시작 페이지가 끝 페이지보다 클 수 없습니다.', code='page_order')
        title = _clean_title(textbook_title)
    else:
        if start_page is not None or end_page is not None:
            raise StudyRecordError('공부하지 않은 날에는 페이지를 넣지 않습니다.', code='pages_not_allowed')
        start = None
        end = None
        title = _optional_title(textbook_title)

    return {
        'child_id': int(child_id),
        'learning_subject_id': subject.id,
        'study_date': day,
        'study_status': status,
        'record_verification': verification,
        'start_page': start,
        'end_page': end,
        'textbook_title': title,
        'recorded_by_user_id': user_id,
        'actor_type': actor,
        'input_channel': channel,
    }


def _assert_day_status_compatible(
    *,
    child_id,
    learning_subject_id,
    study_date,
    study_status,
    exclude_session_id=None,
):
    """같은 child+subject+study_date 의 모순 상태를 막는다.

    허용: studied 여러 개(비연속 페이지).
    금지: studied+explicit_not_studied, studied+unknown,
    explicit_not_studied+unknown.

    unknown row는 사후확인 후 '기억 안 남'이다.
    row가 없는 날은 아직 확인되지 않은 derived unknown이다.
    """
    query = LearningStudySession.query.filter_by(
        child_id=child_id,
        learning_subject_id=learning_subject_id,
        study_date=study_date,
    )
    if exclude_session_id is not None:
        query = query.filter(LearningStudySession.id != exclude_session_id)
    existing = query.all()
    if study_status == STUDY_STATUS_STUDIED:
        if any(row.study_status in NON_RANGE_STUDY_STATUSES for row in existing):
            raise StudyRecordError(
                '같은 날 미학습/모름 기록이 있으면 공부함을 추가할 수 없습니다.',
                code='day_status_conflict',
            )
        return
    if existing:
        raise StudyRecordError(
            '같은 날 다른 학습 기록이 있으면 미학습/모름을 저장할 수 없습니다.',
            code='day_status_conflict',
        )


def _require_subject(learning_subject_id):
    try:
        subject_id = int(learning_subject_id)
    except (TypeError, ValueError) as exc:
        raise StudyRecordError('과목을 선택해주세요.', code='subject_required') from exc
    subject = LearningSubject.query.get(subject_id)
    if subject is None:
        raise StudyRecordError('과목을 찾을 수 없습니다.', code='subject_not_found')
    return subject


def _clean_study_date(raw):
    if isinstance(raw, datetime):
        day = raw.date()
    elif isinstance(raw, date):
        day = raw
    else:
        raise StudyRecordError('기록 날짜가 올바르지 않습니다.', code='invalid_date')
    if day > kst_today():
        raise StudyRecordError('미래 날짜에는 학습을 기록할 수 없습니다.', code='future_date')
    return day


def _clean_choice(raw, allowed, label, code):
    value = None if raw is None else str(raw).strip()
    if value not in allowed:
        raise StudyRecordError(f'{label}가 올바르지 않습니다.', code=code)
    return value


def _clean_page(raw, label):
    try:
        page = int(raw)
    except (TypeError, ValueError) as exc:
        raise StudyRecordError(f'{label}는 정수여야 합니다.', code='invalid_page') from exc
    if page < MIN_PAGE or page > MAX_PAGE:
        raise StudyRecordError('페이지 범위를 확인해주세요.', code='page_range')
    return page


def _clean_title(raw):
    title = _normalize_title(raw)
    if not title:
        raise StudyRecordError('교재명은 필수입니다.', code='title_required')
    return title[:TITLE_MAX]


def _optional_title(raw):
    title = _normalize_title(raw)
    return title[:TITLE_MAX] if title else None


def _normalize_title(raw):
    text = unicodedata.normalize('NFKC', '' if raw is None else str(raw)).strip()
    return ' '.join(text.split())


def _session_payload(row):
    return {
        'id': row.id,
        'child_id': row.child_id,
        'learning_subject_id': row.learning_subject_id,
        'study_date': row.study_date.isoformat() if row.study_date else None,
        'textbook_title': row.textbook_title,
        'study_status': row.study_status,
        'start_page': row.start_page,
        'end_page': row.end_page,
        'record_verification': row.record_verification,
        'recorded_by_user_id': row.recorded_by_user_id,
        'actor_type': row.actor_type,
        'input_channel': row.input_channel,
    }


def _write_change(session, *, event_type, before_payload, after_payload, changed_by_user_id, change_reason):
    reason = None if change_reason is None else str(change_reason).strip() or None
    db.session.add(
        LearningStudySessionChange(
            session_id=session.id,
            child_id=session.child_id,
            learning_subject_id=session.learning_subject_id,
            study_date=session.study_date,
            event_type=event_type,
            before_payload=before_payload,
            after_payload=after_payload,
            change_reason=reason,
            changed_by_user_id=int(changed_by_user_id),
        )
    )
