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
    LearningWorkbookPlan,
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
    RECORD_VERIFICATION_VERIFIED,
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
    learning_workbook_plan_id=None,
    actor_type=ACTOR_TEACHER,
    input_channel=None,
    change_reason=None,
    commit=True,
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
        learning_workbook_plan_id=learning_workbook_plan_id,
        recorded_by_user_id=recorded_by_user_id,
        actor_type=actor_type,
        input_channel=input_channel,
        require_plan=True,
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
    if commit:
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
    learning_workbook_plan_id=None,
    change_reason=None,
    commit=True,
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
        'learning_workbook_plan_id': (
            session.learning_workbook_plan_id
            if learning_workbook_plan_id is None
            else learning_workbook_plan_id
        ),
        'recorded_by_user_id': session.recorded_by_user_id,
        'actor_type': session.actor_type,
        'input_channel': session.input_channel,
        'require_plan': session.learning_workbook_plan_id is not None,
    }
    if session.learning_workbook_plan_id is None:
        merged['learning_workbook_plan_id'] = None
    payload = _validated_payload(**merged)
    if (
        before.get('record_verification') == RECORD_VERIFICATION_VERIFIED
        and _content_fields_changed(before, payload)
    ):
        payload['record_verification'] = RECORD_VERIFICATION_OBSERVED
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
    session.learning_workbook_plan_id = payload['learning_workbook_plan_id']
    session.updated_at = datetime.utcnow()
    _write_change(
        session,
        event_type=STUDY_CHANGE_UPDATED,
        before_payload=before,
        after_payload=_session_payload(session),
        changed_by_user_id=changed_by_user_id,
        change_reason=change_reason,
    )
    if commit:
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


_CONTENT_KEYS = (
    'study_status',
    'start_page',
    'end_page',
    'textbook_title',
    'learning_workbook_plan_id',
)


def _content_fields_changed(before, payload):
    for key in _CONTENT_KEYS:
        if before.get(key) != payload.get(key):
            return True
    return False


def find_subject_day_session(
    child_id,
    learning_subject_id,
    study_date,
    learning_workbook_plan_id=None,
):
    day = _clean_study_date(study_date)
    rows = (
        LearningStudySession.query
        .filter_by(
            child_id=int(child_id),
            learning_subject_id=int(learning_subject_id),
            study_date=day,
        )
        .order_by(LearningStudySession.id.desc())
        .all()
    )
    if not rows:
        return None
    plan_id = _blank_to_none(learning_workbook_plan_id)
    if plan_id is not None:
        plan_pk = int(plan_id)
        matched = [row for row in rows if row.learning_workbook_plan_id == plan_pk]
        if matched:
            return matched[0]
    return rows[0]


def _as_query_date(raw):
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError as exc:
        raise StudyRecordError('기록 날짜가 올바르지 않습니다.', code='invalid_date') from exc


def list_subject_day_sessions(child_id, learning_subject_id, study_date):
    """같은 child+subject+날짜의 모든 세션. I-2는 studied 여러 행을 하루로 접는다."""
    day = _as_query_date(study_date)
    return (
        LearningStudySession.query
        .filter_by(
            child_id=int(child_id),
            learning_subject_id=int(learning_subject_id),
            study_date=day,
        )
        .order_by(LearningStudySession.id.asc())
        .all()
    )


def list_child_sessions_in_range(child_id, start_date, end_date):
    start = _as_query_date(start_date)
    end = _as_query_date(end_date)
    return (
        LearningStudySession.query
        .filter(LearningStudySession.child_id == int(child_id))
        .filter(LearningStudySession.study_date >= start)
        .filter(LearningStudySession.study_date <= end)
        .order_by(
            LearningStudySession.study_date.asc(),
            LearningStudySession.learning_subject_id.asc(),
            LearningStudySession.id.asc(),
        )
        .all()
    )


def save_study_session_writes(writes, *, changed_by_user_id):
    """여러 과목 create/update를 한 트랜잭션으로 저장한다. 빈 목록은 아무 것도 쓰지 않는다."""
    if not writes:
        return []
    results = []
    try:
        for item in writes:
            existing = item.get('existing')
            fields = item['fields']
            if existing is None:
                results.append(
                    create_study_session(commit=False, **fields)
                )
            else:
                results.append(
                    update_study_session(
                        existing,
                        changed_by_user_id=changed_by_user_id,
                        commit=False,
                        **fields,
                    )
                )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return results


def mark_sessions_verified(session_ids, *, child_id, changed_by_user_id):
    ids = []
    for raw in session_ids or ():
        try:
            ids.append(int(raw))
        except (TypeError, ValueError) as exc:
            raise StudyRecordError('확인할 기록이 올바르지 않습니다.', code='verify_not_found') from exc
    unique_ids = list(dict.fromkeys(ids))
    if not unique_ids:
        raise StudyRecordError('확인할 기록을 선택해주세요.', code='verify_selection_required')
    rows = (
        LearningStudySession.query
        .filter(LearningStudySession.id.in_(unique_ids))
        .filter_by(child_id=int(child_id))
        .all()
    )
    if len(rows) != len(unique_ids):
        raise StudyRecordError('확인할 기록이 올바르지 않습니다.', code='verify_not_found')
    by_id = {row.id: row for row in rows}
    ordered = [by_id[item] for item in unique_ids]
    try:
        for row in ordered:
            update_study_session(
                row,
                changed_by_user_id=changed_by_user_id,
                record_verification=RECORD_VERIFICATION_VERIFIED,
                change_reason='실제 교재 확인',
                commit=False,
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return ordered


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
    learning_workbook_plan_id=None,
    require_plan=False,
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

    start_page = _blank_to_none(start_page)
    end_page = _blank_to_none(end_page)
    textbook_title = _blank_to_none(textbook_title)
    plan = _resolve_session_plan(
        submitted_plan_id=learning_workbook_plan_id,
        child_id=int(child_id),
        subject=subject,
        study_date=day,
        require_plan=require_plan,
    )
    if plan is not None:
        textbook_title = plan.textbook_title

    if status == STUDY_STATUS_STUDIED:
        start = _clean_page(start_page, '시작 페이지')
        end = _clean_page(end_page, '끝 페이지')
        if start > end:
            raise StudyRecordError('시작 페이지가 끝 페이지보다 클 수 없습니다.', code='page_order')
        if plan is not None and (start < plan.start_page or end > plan.end_page):
            raise StudyRecordError(
                '선택한 교재의 페이지 범위 안에서만 기록할 수 있습니다.',
                code='plan_page_out_of_range',
            )
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
        'learning_workbook_plan_id': None if plan is None else plan.id,
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


def _resolve_session_plan(*, submitted_plan_id, child_id, subject, study_date, require_plan):
    from features.planning.timeline import resolve_canonical_workbook_plan

    child = get_child(child_id)
    canonical = resolve_canonical_workbook_plan(child, subject.id, study_date)
    submitted = _blank_to_none(submitted_plan_id)
    if submitted is not None:
        plan = _resolve_workbook_plan(
            submitted,
            child_id=child_id,
            subject=subject,
            study_date=study_date,
        )
        if canonical is None or int(plan.id) != int(canonical.id):
            raise StudyRecordError(
                '해당 날짜의 등록 교재와 맞지 않습니다.',
                code='plan_not_canonical',
            )
        return plan
    if require_plan:
        if canonical is None:
            raise StudyRecordError(
                '등록된 교재가 없어 기록할 수 없습니다.',
                code='plan_required',
            )
        return canonical
    return None


def _resolve_workbook_plan(plan_id, *, child_id, subject, study_date):
    raw = _blank_to_none(plan_id)
    if raw is None:
        return None
    try:
        plan_pk = int(raw)
    except (TypeError, ValueError) as exc:
        raise StudyRecordError('배정 교재를 확인해주세요.', code='invalid_plan') from exc
    plan = LearningWorkbookPlan.query.get(plan_pk)
    if plan is None:
        raise StudyRecordError('배정 교재를 찾을 수 없습니다.', code='plan_not_found')
    if int(plan.learning_subject_id) != int(subject.id):
        raise StudyRecordError('선택한 교재가 과목과 맞지 않습니다.', code='plan_subject_mismatch')
    child = get_child(child_id)
    if child is not None and child.grade is not None and int(plan.grade) != int(child.grade):
        raise StudyRecordError('선택한 교재가 학년과 맞지 않습니다.', code='plan_grade_mismatch')
    if plan.start_date > study_date:
        raise StudyRecordError(
            '선택한 교재는 그날 아직 시작되지 않았습니다.',
            code='plan_not_started',
        )
    return plan


def _require_subject(learning_subject_id):
    try:
        subject_id = int(learning_subject_id)
    except (TypeError, ValueError) as exc:
        raise StudyRecordError('과목을 선택해주세요.', code='subject_required') from exc
    subject = LearningSubject.query.get(subject_id)
    if subject is None:
        raise StudyRecordError('과목을 찾을 수 없습니다.', code='subject_not_found')
    return subject


def _blank_to_none(raw):
    if raw is None:
        return None
    if isinstance(raw, str) and not raw.strip():
        return None
    return raw


def _clean_study_date(raw):
    if isinstance(raw, datetime):
        day = raw.date()
    elif isinstance(raw, date):
        day = raw
    else:
        text = '' if raw is None else str(raw).strip()
        try:
            day = date.fromisoformat(text)
        except ValueError as exc:
            raise StudyRecordError('기록 날짜가 올바르지 않습니다.', code='invalid_date') from exc
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
        'learning_workbook_plan_id': row.learning_workbook_plan_id,
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
