"""학습 면제권 장부. DailyPoints / 누적포인트 / 학습진도와 독립이다."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError

from extensions import db
from feature_models import (
    ChildReading,
    ExemptionTicket,
    ExemptionTicketSource,
    ExemptionUsage,
    PROGRAM_TYPE_RECOMMENDED,
    REWARD_MODE_EXEMPTION,
    REWARD_MODE_POINTS,
    STATUS_COMPLETED,
    TICKET_STATUS_ACTIVE,
    TICKET_STATUS_EXPIRED,
    TICKET_STATUS_REVOKED,
    TICKET_STATUS_USED,
)
from features.dates import kst_today
from features.exemption.policy import (
    DEFAULT_EXEMPTION_SUBJECT_KEYS,
    EXEMPTION_FIRST_RECOMMENDED_COUNT,
    EXEMPTION_MAX_ACTIVE,
    EXEMPTION_NEXT_RECOMMENDED_COUNT,
    EXEMPTION_POLICY_VERSION,
    REWARD_MODES,
    grade_supports_reward_choice,
    next_issue_on,
    resolve_exemption_subject,
    ticket_expires_on,
)
from features.subjects import exemption_subject_choices
from features.reading.access import get_child
from features.reading.rewards import EVENT_COMPLETE, EVENT_START, get_event, is_active_event


class ExemptionError(Exception):
    def __init__(self, message, code='error'):
        super().__init__(message)
        self.message = message
        self.code = code


def _user_id(user):
    return user.id if hasattr(user, 'id') else user


def effective_ticket_status(ticket, today):
    if ticket is None:
        return None
    if ticket.status == TICKET_STATUS_ACTIVE and ticket.expires_on < today:
        return TICKET_STATUS_EXPIRED
    return ticket.status


def expire_stale_tickets(child_id, today=None):
    """발급 서비스용. GET 조회에서는 호출하지 않는다."""
    today = today or kst_today()
    rows = (
        ExemptionTicket.query
        .filter_by(child_id=child_id, status=TICKET_STATUS_ACTIVE)
        .filter(ExemptionTicket.expires_on < today)
        .all()
    )
    for ticket in rows:
        ticket.status = TICKET_STATUS_EXPIRED
    return len(rows)


def _non_revoked_tickets(child_id):
    return (
        ExemptionTicket.query
        .filter_by(child_id=child_id)
        .filter(ExemptionTicket.status != TICKET_STATUS_REVOKED)
        .order_by(ExemptionTicket.issued_on.asc(), ExemptionTicket.id.asc())
        .all()
    )


def consumed_source_reading_ids(child_id):
    """revoked ticket source는 소비되지 않은 것으로 본다. source row는 감사 이력으로 남긴다."""
    rows = (
        db.session.query(ExemptionTicketSource.child_reading_id)
        .join(ExemptionTicket, ExemptionTicketSource.exemption_ticket_id == ExemptionTicket.id)
        .filter(
            ExemptionTicket.child_id == child_id,
            ExemptionTicket.status != TICKET_STATUS_REVOKED,
        )
        .all()
    )
    return {row[0] for row in rows}


def consuming_ticket_for_reading(child_reading_id):
    return (
        ExemptionTicket.query
        .join(ExemptionTicketSource, ExemptionTicketSource.exemption_ticket_id == ExemptionTicket.id)
        .filter(
            ExemptionTicketSource.child_reading_id == child_reading_id,
            ExemptionTicket.status != TICKET_STATUS_REVOKED,
        )
        .order_by(ExemptionTicket.id.desc())
        .first()
    )


def qualifying_completions(child_id):
    return (
        ChildReading.query
        .filter_by(
            child_id=child_id,
            program_type=PROGRAM_TYPE_RECOMMENDED,
            status=STATUS_COMPLETED,
            reward_mode=REWARD_MODE_EXEMPTION,
        )
        .filter(ChildReading.completed_on.isnot(None))
        .order_by(ChildReading.completed_on.asc(), ChildReading.id.asc())
        .all()
    )


def unconsumed_qualifying_completions(child_id):
    consumed = consumed_source_reading_ids(child_id)
    return [row for row in qualifying_completions(child_id) if row.id not in consumed]


def sources_needed(non_revoked_count):
    if non_revoked_count <= 0:
        return EXEMPTION_FIRST_RECOMMENDED_COUNT
    return EXEMPTION_NEXT_RECOMMENDED_COUNT


def has_active_point_rewards(reading):
    return is_active_event(get_event(reading.id, EVENT_START)) or is_active_event(
        get_event(reading.id, EVENT_COMPLETE)
    )


def reward_mode_change_block(reading, new_mode):
    """실제 혜택이 있으면 이중보상을 막는다. 독서 중 선택 고정이 아니다."""
    if reading is None:
        return 'reading_missing', '독서 기록을 찾을 수 없습니다.'
    if new_mode not in REWARD_MODES:
        return 'invalid_mode', '보상 방식은 포인트 또는 면제권만 선택할 수 있습니다.'
    current = reading.reward_mode
    if current == new_mode:
        return None, None

    if has_active_point_rewards(reading) and new_mode == REWARD_MODE_EXEMPTION:
        return (
            'points_already_awarded',
            '이미 지급된 추천독서 포인트가 있습니다. 면제권 방식으로 변경하려면 기존 추천독서 포인트를 취소해야 합니다.',
        )

    ticket = consuming_ticket_for_reading(reading.id)
    if ticket is None:
        return None, None
    if new_mode != REWARD_MODE_POINTS:
        return None, None
    status = effective_ticket_status(ticket, kst_today())
    if status == TICKET_STATUS_USED:
        return (
            'source_used',
            '이 추천도서는 이미 면제권 발급에 반영되어 포인트 보상으로 변경할 수 없습니다.',
        )
    if status == TICKET_STATUS_EXPIRED:
        return (
            'source_expired',
            '이 추천도서는 이미 면제권 발급에 반영되어 있습니다. 만료된 면제권은 되돌릴 수 없어 포인트 보상으로 변경할 수 없습니다.',
        )
    return (
        'source_active',
        '이 추천도서는 현재 보유 중인 면제권 발급에 반영되어 있습니다. 포인트 보상으로 변경하려면 미사용 면제권을 먼저 취소해야 합니다.',
    )


def set_reward_mode(reading, new_mode, user=None):
    if reading is None:
        raise ExemptionError('독서 기록을 찾을 수 없습니다.', code='reading_missing')
    if reading.program_type != PROGRAM_TYPE_RECOMMENDED:
        raise ExemptionError('추천독서만 보상 방식을 선택할 수 있습니다.', code='not_recommended')
    child = get_child(reading.child_id)
    if child is None:
        raise ExemptionError('아동을 찾을 수 없습니다.', code='child_missing')
    if not grade_supports_reward_choice(child.grade):
        raise ExemptionError('5~6학년 추천독서만 보상 방식을 선택할 수 있습니다.', code='not_eligible')
    if new_mode not in REWARD_MODES:
        raise ExemptionError('보상 방식은 포인트 또는 면제권만 선택할 수 있습니다.', code='invalid_mode')
    code, message = reward_mode_change_block(reading, new_mode)
    if code:
        raise ExemptionError(message, code=code)
    reading.reward_mode = new_mode
    _ = user
    db.session.commit()
    return reading


def list_exemption_use_subjects():
    """Step 6 면제 과목은 LearningSubject와 무관한 고정 4개다."""
    return exemption_subject_choices()


def _usage_subject_payload(usage):
    if usage is None:
        return None
    return {'key': usage.subject_key, 'name': usage.subject_name}


def get_ticket(ticket_id):
    return ExemptionTicket.query.get(ticket_id)


def usage_for_ticket(ticket_id):
    return ExemptionUsage.query.filter_by(exemption_ticket_id=ticket_id).first()


def _last_non_revoked_ticket(child_id):
    return (
        ExemptionTicket.query
        .filter_by(child_id=child_id)
        .filter(ExemptionTicket.status != TICKET_STATUS_REVOKED)
        .order_by(ExemptionTicket.issued_on.desc(), ExemptionTicket.id.desc())
        .first()
    )


def _held_active_ticket(child_id, today):
    tickets = (
        ExemptionTicket.query
        .filter_by(child_id=child_id, status=TICKET_STATUS_ACTIVE)
        .order_by(ExemptionTicket.id.desc())
        .all()
    )
    for ticket in tickets:
        if effective_ticket_status(ticket, today) == TICKET_STATUS_ACTIVE:
            return ticket
    return None


def _usage_on_date(child_id, used_on):
    return (
        ExemptionUsage.query
        .join(ExemptionTicket, ExemptionUsage.exemption_ticket_id == ExemptionTicket.id)
        .filter(ExemptionTicket.child_id == child_id, ExemptionUsage.used_on == used_on)
        .order_by(ExemptionUsage.id.desc())
        .first()
    )


def _source_payloads(ticket):
    rows = (
        ExemptionTicketSource.query
        .filter_by(exemption_ticket_id=ticket.id)
        .order_by(ExemptionTicketSource.id.asc())
        .all()
    )
    payloads = []
    for row in rows:
        reading = row.child_reading or ChildReading.query.get(row.child_reading_id)
        book = reading.book if reading is not None else None
        payloads.append({
            'child_reading_id': row.child_reading_id,
            'title': book.title if book is not None else f'추천독서 #{row.child_reading_id}',
        })
    return payloads


def child_exemption_snapshot(child_id, today=None, *, persist_expiry=False):
    """GET은 persist_expiry=False. 발급 직전에만 True."""
    today = today or kst_today()
    child = get_child(child_id)
    if persist_expiry:
        expire_stale_tickets(child_id, today)

    eligible_grade = bool(child is not None and grade_supports_reward_choice(child.grade))
    unconsumed = unconsumed_qualifying_completions(child_id)
    non_revoked = _non_revoked_tickets(child_id)
    needed = sources_needed(len(non_revoked))
    condition_met = len(unconsumed) >= needed
    held = _held_active_ticket(child_id, today)
    last = _last_non_revoked_ticket(child_id)
    cooldown_until = next_issue_on(last.issued_on) if last is not None else None
    cooldown_blocks = cooldown_until is not None and today < cooldown_until
    holding_blocks = held is not None
    can_issue = bool(
        eligible_grade
        and condition_met
        and not holding_blocks
        and not cooldown_blocks
        and len(unconsumed) >= needed
    )
    issue_block = None
    if condition_met and holding_blocks:
        issue_block = 'holding'
    elif condition_met and cooldown_blocks:
        issue_block = 'cooldown'
    elif not condition_met:
        issue_block = 'progress'

    today_usage = _usage_on_date(child_id, today)
    today_subject = _usage_subject_payload(today_usage)

    tickets = (
        ExemptionTicket.query
        .filter_by(child_id=child_id)
        .order_by(ExemptionTicket.issued_on.desc(), ExemptionTicket.id.desc())
        .all()
    )
    history = []
    for ticket in tickets:
        usage = usage_for_ticket(ticket.id)
        history.append({
            'ticket': ticket,
            'effective_status': effective_ticket_status(ticket, today),
            'usage': usage,
            'subject': _usage_subject_payload(usage),
            'sources': _source_payloads(ticket),
            'can_revoke': ticket.status == TICKET_STATUS_ACTIVE and usage is None,
            'can_use': (
                ticket.status == TICKET_STATUS_ACTIVE
                and effective_ticket_status(ticket, today) == TICKET_STATUS_ACTIVE
                and usage is None
            ),
        })

    return {
        'eligible_grade': eligible_grade,
        'today': today,
        'held_ticket': held,
        'held_count': 1 if held is not None else 0,
        'is_first_ticket': len(non_revoked) == 0,
        'needed': needed,
        'have': min(len(unconsumed), needed),
        'unconsumed_count': len(unconsumed),
        'condition_met': condition_met,
        'can_issue': can_issue,
        'issue_block': issue_block,
        'next_issue_on': cooldown_until,
        'cooldown_blocks': cooldown_blocks,
        'holding_blocks': holding_blocks,
        'today_usage': today_usage,
        'today_subject': today_subject,
        'eligible_subjects': list_exemption_use_subjects() if eligible_grade else [],
        'history': history,
        'non_revoked_count': len(non_revoked),
        'policy_version': EXEMPTION_POLICY_VERSION,
        'max_active': EXEMPTION_MAX_ACTIVE,
        'default_subject_keys': DEFAULT_EXEMPTION_SUBJECT_KEYS,
    }


def issue_exemption_ticket(child_id, user, today=None):
    """교사 전용. 조건 충족 시에만 ticket row를 만든다. 자동 발급하지 않는다."""
    today = today or kst_today()
    child = get_child(child_id)
    if child is None:
        raise ExemptionError('아동을 찾을 수 없습니다.', code='child_missing')
    if not grade_supports_reward_choice(child.grade):
        raise ExemptionError('5~6학년만 면제권을 발급할 수 있습니다.', code='not_eligible')

    expire_stale_tickets(child_id, today)
    snapshot = child_exemption_snapshot(child_id, today, persist_expiry=False)
    if snapshot['holding_blocks']:
        raise ExemptionError('현재 사용할 수 있는 면제권을 이미 보유 중입니다.', code='already_holding')
    if snapshot['cooldown_blocks']:
        when = snapshot['next_issue_on'].isoformat()
        raise ExemptionError(f'다음 면제권은 {when}부터 발급할 수 있습니다.', code='cooldown')
    if not snapshot['condition_met']:
        raise ExemptionError('면제권 발급 조건이 아직 충족되지 않았습니다.', code='not_ready')

    sources = unconsumed_qualifying_completions(child_id)[: snapshot['needed']]
    if len(sources) < snapshot['needed']:
        raise ExemptionError('면제권 발급 조건이 아직 충족되지 않았습니다.', code='not_ready')

    user_id = _user_id(user)
    ticket = ExemptionTicket(
        child_id=child_id,
        issued_on=today,
        expires_on=ticket_expires_on(today),
        status=TICKET_STATUS_ACTIVE,
        policy_version=EXEMPTION_POLICY_VERSION,
        issued_by_user_id=user_id,
    )
    db.session.add(ticket)
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise ExemptionError('현재 사용할 수 있는 면제권을 이미 보유 중입니다.', code='already_holding') from exc

    for reading in sources:
        db.session.add(ExemptionTicketSource(
            exemption_ticket_id=ticket.id,
            child_reading_id=reading.id,
        ))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ExemptionError('현재 사용할 수 있는 면제권을 이미 보유 중입니다.', code='already_holding') from exc
    return ticket


def _parse_used_on(raw, today):
    if raw is None or raw == '':
        return today
    if hasattr(raw, 'year'):
        used_on = raw
    else:
        from datetime import date as date_cls
        try:
            used_on = date_cls.fromisoformat(str(raw)[:10])
        except ValueError as exc:
            raise ExemptionError('사용 날짜가 올바르지 않습니다.', code='invalid_date') from exc
    return used_on


def use_exemption_ticket(ticket_id, subject_key, user, used_on=None, today=None):
    """교사 전용. 포인트 원장은 변경하지 않는다."""
    today = today or kst_today()
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise ExemptionError('면제권을 찾을 수 없습니다.', code='ticket_missing')

    expire_stale_tickets(ticket.child_id, today)
    db.session.refresh(ticket)

    if ticket.status == TICKET_STATUS_REVOKED:
        raise ExemptionError('취소된 면제권은 사용할 수 없습니다.', code='revoked')
    if ticket.status == TICKET_STATUS_USED or usage_for_ticket(ticket.id) is not None:
        raise ExemptionError('이미 사용한 면제권입니다.', code='already_used')
    if ticket.status != TICKET_STATUS_ACTIVE or ticket.expires_on < today:
        if ticket.status == TICKET_STATUS_ACTIVE and ticket.expires_on < today:
            ticket.status = TICKET_STATUS_EXPIRED
            db.session.commit()
        raise ExemptionError('만료된 면제권은 사용할 수 없습니다.', code='expired')

    used_on = _parse_used_on(used_on, today)
    if used_on > today:
        raise ExemptionError('미래 날짜에는 면제권을 사용할 수 없습니다.', code='future_date')
    if used_on < ticket.issued_on or used_on > ticket.expires_on:
        raise ExemptionError('사용일은 발급일부터 유효기간 사이여야 합니다.', code='used_on_range')

    subject = resolve_exemption_subject(subject_key)
    if subject is None:
        raise ExemptionError('면제할 과목을 선택해주세요.', code='subject_not_allowed')

    usage = ExemptionUsage(
        exemption_ticket_id=ticket.id,
        subject_key=subject['key'],
        subject_name=subject['name'],
        used_on=used_on,
        recorded_by_user_id=_user_id(user),
    )
    ticket.status = TICKET_STATUS_USED
    db.session.add(usage)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ExemptionError('이미 사용한 면제권입니다.', code='already_used') from exc
    return usage


def revoke_exemption_ticket(ticket_id, user, today=None):
    """미사용 active ticket만 취소. source row는 남기고 조회에서 미소비로 되돌린다."""
    today = today or kst_today()
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise ExemptionError('면제권을 찾을 수 없습니다.', code='ticket_missing')
    if usage_for_ticket(ticket.id) is not None or ticket.status == TICKET_STATUS_USED:
        raise ExemptionError('이미 사용한 면제권은 취소할 수 없습니다.', code='already_used')
    if ticket.status == TICKET_STATUS_REVOKED:
        raise ExemptionError('이미 취소된 면제권입니다.', code='already_revoked')
    if ticket.status == TICKET_STATUS_EXPIRED or (
        ticket.status == TICKET_STATUS_ACTIVE and ticket.expires_on < today
    ):
        if ticket.status == TICKET_STATUS_ACTIVE:
            ticket.status = TICKET_STATUS_EXPIRED
            db.session.commit()
        raise ExemptionError('만료된 면제권은 취소할 수 없습니다.', code='expired')
    if ticket.status != TICKET_STATUS_ACTIVE:
        raise ExemptionError('보유 중인 면제권만 취소할 수 있습니다.', code='not_active')

    ticket.status = TICKET_STATUS_REVOKED
    ticket.revoked_at = datetime.utcnow()
    ticket.revoked_by_user_id = _user_id(user)
    db.session.commit()
    return ticket


def delete_exemptions_for_child(child_id):
    """아동 hard delete용. 학기 reset_data에서는 호출하지 않는다."""
    ticket_ids = [
        row.id for row in ExemptionTicket.query.filter_by(child_id=child_id).all()
    ]
    if not ticket_ids:
        return
    ExemptionUsage.query.filter(ExemptionUsage.exemption_ticket_id.in_(ticket_ids)).delete(
        synchronize_session=False
    )
    ExemptionTicketSource.query.filter(
        ExemptionTicketSource.exemption_ticket_id.in_(ticket_ids)
    ).delete(synchronize_session=False)
    ExemptionTicket.query.filter(ExemptionTicket.id.in_(ticket_ids)).delete(
        synchronize_session=False
    )
