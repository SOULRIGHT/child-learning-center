"""추천/도전 독서 교사 승인 보상. DailyPoints.reading_points는 건드리지 않는다."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from extensions import db
from feature_models import (
    EVENT_CHALLENGE_COMPLETE,
    EVENT_CHALLENGE_START,
    EVENT_RECOMMENDED_COMPLETE,
    EVENT_RECOMMENDED_START,
    POLICY_VERSION_CHALLENGE_V1,
    POLICY_VERSION_RECOMMENDED_V1,
    PROGRAM_TYPE_CHALLENGE,
    PROGRAM_TYPE_RECOMMENDED,
    ReadingRewardEvent,
    STATUS_ABANDONED,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
)
from features.reading.access import model_named
from features.dates import kst_today
from features.exemption.policy import REWARD_MODE_EXEMPTION, REWARD_MODE_POINTS, grade_supports_reward_choice
from features.reading.policy import reading_incentives_enabled

EVENT_START = EVENT_RECOMMENDED_START
EVENT_COMPLETE = EVENT_RECOMMENDED_COMPLETE
SOURCE_TYPE = 'recommended_reading'

READING_REWARD_POLICIES = {
    PROGRAM_TYPE_RECOMMENDED: {
        'start_points': {2: 100, 3: 100, 4: 100, 5: 100, 6: 100},
        'complete_points': {2: 100, 3: 100, 4: 200, 5: 200, 6: 200},
        'auto_points_grades': (2, 3, 4),
        'choice_grades': (5, 6),
        'start_event': EVENT_RECOMMENDED_START,
        'complete_event': EVENT_RECOMMENDED_COMPLETE,
        'policy_version': POLICY_VERSION_RECOMMENDED_V1,
        'source_type': 'recommended_reading',
        'start_label': ('추천독서 시작', '추천독서 시작 승인', 'start'),
        'complete_label': ('추천독서 완독', '추천독서 완독 승인', 'complete'),
        'panel_title': '추천독서 보상',
        'program_label': '추천독서',
    },
    PROGRAM_TYPE_CHALLENGE: {
        'start_points': {5: 200, 6: 200},
        'complete_points': {5: 400, 6: 400},
        'auto_points_grades': (),
        'choice_grades': (5, 6),
        'start_event': EVENT_CHALLENGE_START,
        'complete_event': EVENT_CHALLENGE_COMPLETE,
        'policy_version': POLICY_VERSION_CHALLENGE_V1,
        'source_type': 'challenge_reading',
        'start_label': ('도전독서 시작', '도전독서 시작 승인', 'start'),
        'complete_label': ('도전독서 완독', '도전독서 완독 승인', 'complete'),
        'panel_title': '도전독서 보상',
        'program_label': '도전독서',
    },
}

INCENTIVE_PROGRAM_TYPES = frozenset(READING_REWARD_POLICIES)
START_EVENT_TYPES = frozenset(
    policy['start_event'] for policy in READING_REWARD_POLICIES.values()
)
COMPLETE_EVENT_TYPES = frozenset(
    policy['complete_event'] for policy in READING_REWARD_POLICIES.values()
)
ALL_REWARD_EVENT_TYPES = START_EVENT_TYPES | COMPLETE_EVENT_TYPES


class RewardError(Exception):
    def __init__(self, message, code='error'):
        super().__init__(message)
        self.message = message
        self.code = code


def _parse_grade(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def policy_for_program(program_type):
    return READING_REWARD_POLICIES.get(program_type)


def event_types_for_program(program_type):
    policy = policy_for_program(program_type)
    if policy is None:
        return None, None
    return policy['start_event'], policy['complete_event']


def incentive_reward_points(program_type, grade, event_type, reward_mode=None):
    policy = policy_for_program(program_type)
    if policy is None:
        return None
    parsed = _parse_grade(grade)
    if event_type == policy['start_event']:
        table = policy['start_points']
    elif event_type == policy['complete_event']:
        table = policy['complete_points']
    else:
        return None
    points = table.get(parsed)
    if points is None:
        return None
    if parsed in policy['auto_points_grades']:
        return points
    if parsed in policy['choice_grades'] and reward_mode == REWARD_MODE_POINTS:
        return points
    return None


def recommended_reward_points(grade, event_type, reward_mode=None):
    """2~4학년은 기존 정책. 5~6학년은 reward_mode=points 일 때만 점수를 준다."""
    return incentive_reward_points(PROGRAM_TYPE_RECOMMENDED, grade, event_type, reward_mode)


def _load_history(daily_record):
    if not daily_record or not daily_record.manual_history:
        return []
    try:
        history = json.loads(daily_record.manual_history)
        return history if isinstance(history, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _history_sum(history):
    total = 0
    for item in history:
        try:
            total += int(item.get('points') or 0)
        except (TypeError, ValueError):
            continue
    return total


def _recalc_daily_total(daily_record):
    history = _load_history(daily_record)
    manual_total = _history_sum(history)
    daily_record.manual_history = json.dumps(history, ensure_ascii=False)
    daily_record.manual_points = manual_total
    daily_record.total_points = (
        (daily_record.korean_points or 0)
        + (daily_record.math_points or 0)
        + (daily_record.ssen_points or 0)
        + (daily_record.reading_points or 0)
        + (daily_record.piano_points or 0)
        + (daily_record.english_points or 0)
        + (daily_record.advanced_math_points or 0)
        + (daily_record.writing_points or 0)
        + manual_total
    )
    return daily_record.total_points


def _recalc_cumulative(child_id):
    Child = model_named('Child')
    DailyPoints = model_named('DailyPoints')
    child = Child.query.get(child_id)
    if child is None:
        raise RewardError('아동을 찾을 수 없습니다.', code='child_missing')
    total = (
        db.session.query(func.coalesce(func.sum(DailyPoints.total_points), 0))
        .filter(DailyPoints.child_id == child_id)
        .scalar()
    )
    child.cumulative_points = int(total or 0)
    return child


def _add_points_history(child_id, activity_date, user_id, old_total, new_total, reason, change_type):
    PointsHistory = model_named('PointsHistory')
    db.session.add(PointsHistory(
        child_id=child_id,
        date=activity_date,
        old_korean_points=0,
        old_math_points=0,
        old_ssen_points=0,
        old_reading_points=0,
        old_piano_points=0,
        old_english_points=0,
        old_advanced_math_points=0,
        old_writing_points=0,
        old_total_points=old_total,
        new_korean_points=0,
        new_math_points=0,
        new_ssen_points=0,
        new_reading_points=0,
        new_piano_points=0,
        new_english_points=0,
        new_advanced_math_points=0,
        new_writing_points=0,
        new_total_points=new_total,
        change_type=change_type,
        changed_by=user_id,
        change_reason=reason,
    ))


def _get_or_create_daily(child_id, activity_date, user_id):
    DailyPoints = model_named('DailyPoints')
    daily = DailyPoints.query.filter_by(child_id=child_id, date=activity_date).first()
    if daily is None:
        daily = DailyPoints(
            child_id=child_id,
            date=activity_date,
            korean_points=0,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=0,
            manual_history='[]',
            total_points=0,
            created_by=user_id,
        )
        db.session.add(daily)
        db.session.flush()
    return daily


def _append_manual_item(daily_record, *, event, user_name, subject, reason, source_event, source_type):
    history = _load_history(daily_record)
    next_id = (max((int(item.get('id') or 0) for item in history), default=0) + 1) if history else 1
    history.append({
        'id': next_id,
        'subject': subject,
        'points': int(event.points),
        'reason': reason,
        'created_by': user_name,
        'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'source_type': source_type,
        'source_child_reading_id': event.child_reading_id,
        'source_event': source_event,
        'source_event_id': event.id,
    })
    daily_record.manual_history = json.dumps(history, ensure_ascii=False)
    return history


def _remove_manual_item(daily_record, event, source_event, source_type):
    history = _load_history(daily_record)
    kept = []
    removed = None
    for item in history:
        if removed is None and (
            item.get('source_event_id') == event.id
            or (
                item.get('source_type') == source_type
                and item.get('source_child_reading_id') == event.child_reading_id
                and item.get('source_event') == source_event
            )
        ):
            removed = item
            continue
        kept.append(item)
    daily_record.manual_history = json.dumps(kept, ensure_ascii=False)
    return removed, kept


def get_event(child_reading_id, event_type):
    return ReadingRewardEvent.query.filter_by(
        child_reading_id=child_reading_id,
        event_type=event_type,
    ).first()


def is_active_event(event):
    return event is not None and event.revoked_at is None


def has_active_point_rewards(reading):
    if reading is None:
        return False
    start_type, complete_type = event_types_for_program(reading.program_type)
    types = [item for item in (start_type, complete_type) if item]
    if not types:
        types = list(ALL_REWARD_EVENT_TYPES)
    return any(is_active_event(get_event(reading.id, event_type)) for event_type in types)


def activity_date_for_event(reading, event_type):
    if event_type in START_EVENT_TYPES:
        return reading.started_on
    if event_type in COMPLETE_EVENT_TYPES:
        return reading.completed_on
    return None


def reward_status_for_reading(reading, child):
    if reading is None:
        return None
    grade = getattr(child, 'grade', None)
    mode = getattr(reading, 'reward_mode', None)
    policy = policy_for_program(reading.program_type)
    incentives_on = reading_incentives_enabled()
    is_recommended = reading.program_type == PROGRAM_TYPE_RECOMMENDED
    is_challenge = reading.program_type == PROGRAM_TYPE_CHALLENGE
    is_incentive = policy is not None
    auto_points = bool(policy and _parse_grade(grade) in policy['auto_points_grades'])
    can_choose_mode = bool(
        is_incentive
        and grade_supports_reward_choice(grade)
        and incentives_on
    )
    needs_mode = can_choose_mode and not mode
    is_exemption_mode = mode == REWARD_MODE_EXEMPTION
    is_points_mode = mode == REWARD_MODE_POINTS or auto_points
    start_type = policy['start_event'] if policy else EVENT_START
    complete_type = policy['complete_event'] if policy else EVENT_COMPLETE
    start_points = incentive_reward_points(reading.program_type, grade, start_type, mode) if policy else None
    complete_points = incentive_reward_points(reading.program_type, grade, complete_type, mode) if policy else None
    start_event = get_event(reading.id, start_type)
    complete_event = get_event(reading.id, complete_type)
    abandoned = reading.status == STATUS_ABANDONED
    completed = reading.status == STATUS_COMPLETED
    can_mutate = bool(is_incentive and incentives_on)
    return {
        'is_recommended': is_recommended,
        'is_challenge': is_challenge,
        'is_incentive': is_incentive,
        'show_reward_panel': is_incentive,
        'panel_title': policy['panel_title'] if policy else '',
        'program_label': policy['program_label'] if policy else '',
        'incentives_enabled': incentives_on,
        'grade_deferred': needs_mode,
        'needs_mode': needs_mode,
        'can_choose_mode': can_choose_mode,
        'reward_mode': mode,
        'is_exemption_mode': is_exemption_mode,
        'is_points_mode': is_points_mode,
        'grade': grade,
        'start': {
            'event_type': start_type,
            'points': start_points,
            'awarded': is_active_event(start_event),
            'revoked': start_event is not None and start_event.revoked_at is not None,
            'can_approve': bool(
                can_mutate
                and start_points
                and not is_active_event(start_event)
                and reading.started_on is not None
            ),
            'can_revoke': bool(is_incentive and is_active_event(start_event)),
            'awarded_on': start_event.awarded_on.isoformat() if is_active_event(start_event) and start_event.awarded_on else None,
        },
        'complete': {
            'event_type': complete_type,
            'points': complete_points,
            'awarded': is_active_event(complete_event),
            'revoked': complete_event is not None and complete_event.revoked_at is not None,
            'can_approve': bool(
                can_mutate
                and complete_points
                and completed
                and not abandoned
                and reading.completed_on is not None
                and not is_active_event(complete_event)
            ),
            'can_revoke': bool(is_incentive and is_active_event(complete_event)),
            'awarded_on': complete_event.awarded_on.isoformat() if is_active_event(complete_event) and complete_event.awarded_on else None,
        },
        'status': reading.status,
        'in_progress': reading.status == STATUS_IN_PROGRESS,
    }


def approve_recommended_reward(reading, user, event_type):
    """교사 승인 전용. 학생 POST로 호출되면 안 된다. 같은 이벤트는 한 번만 지급."""
    if reading is None:
        raise RewardError('독서 기록을 찾을 수 없습니다.', code='reading_missing')
    if not reading_incentives_enabled():
        raise RewardError('현재 추천/도전 추가 보상 프로그램이 중단되어 있습니다.', code='incentives_disabled')
    policy = policy_for_program(reading.program_type)
    if policy is None:
        raise RewardError('이 독서 기록에는 추가 보상을 지급할 수 없습니다.', code='not_recommended')
    if event_type not in {policy['start_event'], policy['complete_event']}:
        raise RewardError('알 수 없는 보상 유형입니다.', code='invalid_event')

    Child = model_named('Child')
    User = model_named('User')
    child = Child.query.get(reading.child_id)
    if child is None:
        raise RewardError('아동을 찾을 수 없습니다.', code='child_missing')
    user_id = user.id if hasattr(user, 'id') else user
    actor = user if hasattr(user, 'id') else User.query.get(user_id)
    user_name = getattr(actor, 'name', None) or getattr(actor, 'username', None) or str(user_id)
    program_label = policy['program_label']

    if event_type == policy['complete_event']:
        if reading.status == STATUS_ABANDONED:
            raise RewardError('중단한 책은 완독 보상을 줄 수 없습니다.', code='abandoned')
        if reading.status != STATUS_COMPLETED or reading.completed_on is None:
            raise RewardError('완독 후에만 완독 보상을 줄 수 있습니다.', code='not_completed')

    points = incentive_reward_points(reading.program_type, child.grade, event_type, reading.reward_mode)
    if points is None:
        if _parse_grade(child.grade) in policy['choice_grades']:
            if reading.reward_mode == REWARD_MODE_EXEMPTION:
                raise RewardError(
                    f'면제권 방식에서는 {program_label} 포인트를 지급하지 않습니다.',
                    code='exemption_mode',
                )
            raise RewardError(
                f'5~6학년 {program_label}는 먼저 보상 방식(포인트/면제권)을 선택해야 합니다.',
                code='mode_unset',
            )
        raise RewardError(f'이 학년에는 {program_label} 보상이 없습니다.', code='not_eligible')

    awarded_on = activity_date_for_event(reading, event_type)
    if awarded_on is None:
        raise RewardError('보상 기준 날짜가 없습니다.', code='missing_activity_date')
    if awarded_on > kst_today():
        raise RewardError('미래 날짜에는 보상을 줄 수 없습니다.', code='future_date')

    existing = get_event(reading.id, event_type)
    if is_active_event(existing):
        return existing, False

    if event_type == policy['start_event']:
        subject, reason, source_event = policy['start_label']
    else:
        subject, reason, source_event = policy['complete_label']
    created_new = existing is None
    if existing is None:
        existing = ReadingRewardEvent(
            child_reading_id=reading.id,
            event_type=event_type,
            points=int(points),
            awarded_on=awarded_on,
            policy_version=policy['policy_version'],
            created_by_user_id=user_id,
            revoked_at=None,
            revoked_by_user_id=None,
        )
        db.session.add(existing)
        try:
            db.session.flush()
        except IntegrityError as exc:
            db.session.rollback()
            again = get_event(reading.id, event_type)
            if is_active_event(again):
                return again, False
            raise RewardError('이미 지급된 보상입니다.', code='already_awarded') from exc
    else:
        existing.points = int(points)
        existing.awarded_on = awarded_on
        existing.policy_version = policy['policy_version']
        existing.created_by_user_id = user_id
        existing.revoked_at = None
        existing.revoked_by_user_id = None
        db.session.flush()

    daily = _get_or_create_daily(child.id, awarded_on, user_id)
    old_total = daily.total_points or 0
    _append_manual_item(
        daily,
        event=existing,
        user_name=user_name,
        subject=subject,
        reason=reason,
        source_event=source_event,
        source_type=policy['source_type'],
    )
    new_total = _recalc_daily_total(daily)
    _add_points_history(
        child.id,
        awarded_on,
        user_id,
        old_total,
        new_total,
        f'수동 추가: {subject} ({reason})',
        '추가',
    )
    _recalc_cumulative(child.id)

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        again = get_event(reading.id, event_type)
        if is_active_event(again):
            return again, False
        raise RewardError('이미 지급된 보상입니다.', code='already_awarded') from exc
    return existing, created_new


def revoke_recommended_reward(reading, user, event_type):
    if reading is None:
        raise RewardError('독서 기록을 찾을 수 없습니다.', code='reading_missing')
    policy = policy_for_program(reading.program_type)
    if policy is None or event_type not in {policy['start_event'], policy['complete_event']}:
        raise RewardError('알 수 없는 보상 유형입니다.', code='invalid_event')

    event = get_event(reading.id, event_type)
    if event is None or event.revoked_at is not None:
        raise RewardError('취소할 보상이 없습니다.', code='not_awarded')

    user_id = user.id if hasattr(user, 'id') else user
    if event_type == policy['start_event']:
        _subject, _reason, source_event = policy['start_label']
    else:
        _subject, _reason, source_event = policy['complete_label']
    DailyPoints = model_named('DailyPoints')
    daily = DailyPoints.query.filter_by(child_id=reading.child_id, date=event.awarded_on).first()
    old_total = daily.total_points if daily is not None else 0
    if daily is not None:
        _remove_manual_item(daily, event, source_event, policy['source_type'])
        new_total = _recalc_daily_total(daily)
    else:
        new_total = 0

    event.revoked_at = datetime.utcnow()
    event.revoked_by_user_id = user_id
    _add_points_history(
        reading.child_id,
        event.awarded_on,
        user_id,
        old_total,
        new_total,
        f'{policy["program_label"]} 보상 취소',
        '삭제',
    )
    _recalc_cumulative(reading.child_id)
    db.session.commit()
    return event
