"""독서 원장 lifecycle. DailyPoints/누적포인트/히스토리는 절대 건드리지 않는다."""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from extensions import db
from feature_models import (
    ACTOR_CHILD,
    ACTOR_TEACHER,
    Book,
    ChildReading,
    POLICY_VERSION_GENERAL_V2,
    ReadingDay,
    ReadingRewardEvent,
    STATUS_ABANDONED,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
)
from features.books.service import BookCreateError, create_book_record
from features.reading.access import get_child
from features.reading.classify import classify_program_type
from features.reading.policy import (
    activity_today,
    general_reading_v2_start_date,
    is_general_reading_v2,
)
from features.reading.ratings import parse_optional_rating


class ReadingError(Exception):
    def __init__(self, message, code='error'):
        super().__init__(message)
        self.message = message
        self.code = code


def get_in_progress(child_id):
    return (
        ChildReading.query.filter_by(child_id=child_id, status=STATUS_IN_PROGRESS)
        .order_by(ChildReading.id.desc())
        .first()
    )


def reading_days_for_child_on(child_id, activity_date):
    return (
        ReadingDay.query.join(ChildReading)
        .filter(
            ChildReading.child_id == child_id,
            ReadingDay.date == activity_date,
        )
        .all()
    )


def get_day(child_reading_id, activity_date):
    return ReadingDay.query.filter_by(
        child_reading_id=child_reading_id,
        date=activity_date,
    ).first()


def snapshot_for_date(child_id, activity_date):
    current = get_in_progress(child_id)
    days = reading_days_for_child_on(child_id, activity_date)
    today_day = days[0] if days else None
    today_book = None
    if today_day is not None:
        today_book = today_day.child_reading.book if today_day.child_reading else None
    current_book = current.book if current is not None else None
    return {
        'has_today_record': today_day is not None,
        'today_day': today_day,
        'today_book': today_book,
        'current_reading': current,
        'current_book': current_book,
        'current_book_title': current_book.title if current_book else None,
        'current_book_author': current_book.author if current_book else None,
    }


def list_readings_for_child(child_id):
    return (
        ChildReading.query.filter_by(child_id=child_id)
        .order_by(ChildReading.started_on.desc(), ChildReading.id.desc())
        .all()
    )


def list_days(child_reading_id):
    return (
        ReadingDay.query.filter_by(child_reading_id=child_reading_id)
        .order_by(ReadingDay.date.asc(), ReadingDay.id.asc())
        .all()
    )


def history_items_for_child(child_id):
    """한 아동의 책/일자 기록을 묶어 반환. Book은 joinedload, ReadingDay는 IN 한 번."""
    readings = (
        ChildReading.query.options(joinedload(ChildReading.book))
        .filter_by(child_id=child_id)
        .order_by(ChildReading.started_on.desc(), ChildReading.id.desc())
        .all()
    )
    if not readings:
        return []
    reading_ids = [reading.id for reading in readings]
    days = (
        ReadingDay.query.filter(ReadingDay.child_reading_id.in_(reading_ids))
        .order_by(ReadingDay.date.asc(), ReadingDay.id.asc())
        .all()
    )
    days_by_reading = {reading_id: [] for reading_id in reading_ids}
    for day in days:
        days_by_reading[day.child_reading_id].append(day)
    return [
        {
            'reading': reading,
            'book': reading.book,
            'days': days_by_reading[reading.id],
        }
        for reading in readings
    ]


def _ensure_policy_date(activity_date):
    if activity_date is None:
        activity_date = activity_today()
    if not is_general_reading_v2(activity_date):
        raise ReadingError(
            '새 독서기록은 정책 적용일 이후부터 작성할 수 있습니다.',
            code='before_policy',
        )
    return activity_date


def _clean_review(review_text):
    if review_text is None:
        return None
    text = str(review_text).strip()
    return text or None


def _resolve_book(book_id, title, author, allow_create):
    if book_id:
        book = Book.query.get(int(book_id))
        if book is None or not book.is_active:
            raise ReadingError('선택한 책을 찾을 수 없습니다.', code='book_missing')
        return book, False
    if not allow_create:
        raise ReadingError('책을 선택해 주세요.', code='book_required')
    try:
        book, _similar = create_book_record(title, author, commit=False)
    except BookCreateError as exc:
        raise ReadingError(str(exc), code='book_title_required') from exc
    return book, True


def _assert_one_in_progress(child_id, ignore_id=None):
    query = ChildReading.query.filter_by(child_id=child_id, status=STATUS_IN_PROGRESS)
    if ignore_id is not None:
        query = query.filter(ChildReading.id != ignore_id)
    if query.first() is not None:
        raise ReadingError('지금은 한 권만 읽을 수 있어요.', code='already_in_progress')


def _assert_one_day_per_child(child_id, activity_date, allowed_reading_id=None):
    days = reading_days_for_child_on(child_id, activity_date)
    for day in days:
        if allowed_reading_id is not None and day.child_reading_id == allowed_reading_id:
            continue
        raise ReadingError('오늘 독서기록은 이미 작성했어요.', code='already_logged_today')


def _touch_reading_day(child_reading, activity_date, review_text, user_id, actor_type):
    existing = get_day(child_reading.id, activity_date)
    cleaned = _clean_review(review_text)
    if existing is None:
        existing = ReadingDay(
            child_reading_id=child_reading.id,
            date=activity_date,
            review_text=cleaned,
            created_by_user_id=user_id,
            actor_type=actor_type,
            policy_version=POLICY_VERSION_GENERAL_V2,
        )
        db.session.add(existing)
    else:
        existing.review_text = cleaned
        existing.actor_type = actor_type
        existing.created_by_user_id = user_id
        existing.policy_version = POLICY_VERSION_GENERAL_V2
    return existing


def start_book(
    child_id,
    user_id,
    actor_type,
    activity_date=None,
    book_id=None,
    title=None,
    author=None,
    review_text=None,
    allow_create_book=False,
):
    activity_date = _ensure_policy_date(activity_date)
    _assert_one_in_progress(child_id)
    _assert_one_day_per_child(child_id, activity_date)

    book, _created = _resolve_book(book_id, title, author, allow_create=allow_create_book)
    child = get_child(child_id)
    program_type = classify_program_type(child, book)
    reading = ChildReading(
        child_id=child_id,
        book_id=book.id,
        started_on=activity_date,
        completed_on=None,
        ended_on=None,
        status=STATUS_IN_PROGRESS,
        program_type=program_type,
        policy_version=POLICY_VERSION_GENERAL_V2,
        created_by_user_id=user_id,
        actor_type=actor_type,
    )
    db.session.add(reading)
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise ReadingError('지금은 한 권만 읽을 수 있어요.', code='already_in_progress') from exc

    day = _touch_reading_day(reading, activity_date, review_text, user_id, actor_type)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ReadingError('오늘은 이미 이 책의 기록이 있어요.', code='duplicate_day') from exc
    return reading, day


def _parse_completion_ratings(difficulty_rating, fun_rating):
    try:
        difficulty = parse_optional_rating(difficulty_rating)
    except ValueError as exc:
        raise ReadingError('난이도는 1부터 5까지 고를 수 있어요.', code='invalid_rating') from exc
    try:
        fun = parse_optional_rating(fun_rating)
    except ValueError as exc:
        raise ReadingError('재미는 1부터 5까지 고를 수 있어요.', code='invalid_rating') from exc
    return difficulty, fun


def save_today(
    child_id,
    user_id,
    actor_type,
    activity_date=None,
    review_text=None,
    mark_completed=False,
    expected_reading_id=None,
    difficulty_rating=None,
    fun_rating=None,
):
    activity_date = _ensure_policy_date(activity_date)
    parsed_difficulty = None
    parsed_fun = None
    if mark_completed:
        parsed_difficulty, parsed_fun = _parse_completion_ratings(
            difficulty_rating, fun_rating,
        )
    reading = get_in_progress(child_id)
    if reading is None:
        raise ReadingError('지금 읽고 있는 책이 없어요.', code='no_current_book')
    if expected_reading_id is not None and int(expected_reading_id) != int(reading.id):
        raise ReadingError('다른 아동의 기록은 저장할 수 없어요.', code='reading_mismatch')
    if int(reading.child_id) != int(child_id):
        raise ReadingError('다른 아동의 기록은 저장할 수 없어요.', code='child_mismatch')

    _assert_one_day_per_child(child_id, activity_date, allowed_reading_id=reading.id)
    day = _touch_reading_day(reading, activity_date, review_text, user_id, actor_type)

    if mark_completed:
        reading.status = STATUS_COMPLETED
        reading.completed_on = activity_date
        reading.ended_on = activity_date
        reading.difficulty_rating = parsed_difficulty
        reading.fun_rating = parsed_fun

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ReadingError('오늘은 이미 이 책의 기록이 있어요.', code='duplicate_day') from exc
    return reading, day


def complete_current(
    child_id,
    user_id,
    actor_type,
    activity_date=None,
    review_text=None,
    expected_reading_id=None,
    difficulty_rating=None,
    fun_rating=None,
):
    return save_today(
        child_id,
        user_id,
        actor_type,
        activity_date=activity_date,
        review_text=review_text,
        mark_completed=True,
        expected_reading_id=expected_reading_id,
        difficulty_rating=difficulty_rating,
        fun_rating=fun_rating,
    )


def abandon_current(child_id, user_id, actor_type, activity_date=None, expected_reading_id=None):
    activity_date = _ensure_policy_date(activity_date)
    reading = get_in_progress(child_id)
    if reading is None:
        raise ReadingError('지금 읽고 있는 책이 없어요.', code='no_current_book')
    if expected_reading_id is not None and int(expected_reading_id) != int(reading.id):
        raise ReadingError('다른 아동의 기록은 저장할 수 없어요.', code='reading_mismatch')
    if int(reading.child_id) != int(child_id):
        raise ReadingError('다른 아동의 기록은 저장할 수 없어요.', code='child_mismatch')

    reading.status = STATUS_ABANDONED
    reading.completed_on = None
    reading.ended_on = activity_date
    db.session.commit()
    return reading


def delete_readings_for_child(child_id):
    """아동 hard delete용. 학기 포인트 초기화에서는 호출하지 않는다."""
    reading_ids = [
        row.id for row in ChildReading.query.filter_by(child_id=child_id).all()
    ]
    if reading_ids:
        ReadingRewardEvent.query.filter(ReadingRewardEvent.child_reading_id.in_(reading_ids)).delete(
            synchronize_session=False
        )
        ReadingDay.query.filter(ReadingDay.child_reading_id.in_(reading_ids)).delete(
            synchronize_session=False
        )
        ChildReading.query.filter(ChildReading.id.in_(reading_ids)).delete(
            synchronize_session=False
        )


def actor_type_for_user(user):
    role = getattr(user, 'role', None)
    try:
        from flask import current_app
        viewer_role = current_app.config.get('VIEWER_ROLE_NAME', '학생열람')
    except RuntimeError:
        viewer_role = '학생열람'
    if role == viewer_role:
        return ACTOR_CHILD
    return ACTOR_TEACHER


def policy_start_date():
    return general_reading_v2_start_date()
