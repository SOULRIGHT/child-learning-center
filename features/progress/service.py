"""학습 진도 스냅샷. DailyPoints 지급 경로는 건드리지 않는다."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from extensions import db
from feature_models import LearningProgressEntry, LearningSubject

KEY_RE = re.compile(r'^[a-z][a-z0-9_]{0,62}$')
MIN_PAGE = 1
MAX_PAGE = 2000
TITLE_MAX = 120
KST = timezone(timedelta(hours=9))

DEFAULT_SUBJECTS = (
    {'key': 'korean', 'name': '국어', 'sort_order': 10},
    {'key': 'math', 'name': '수학', 'sort_order': 20},
    {'key': 'ssen', 'name': '쎈', 'sort_order': 30},
)


class ProgressError(Exception):
    def __init__(self, message, code='error'):
        super().__init__(message)
        self.message = message
        self.code = code


def kst_today():
    return datetime.now(KST).date()


def normalize_textbook_title(raw):
    text = unicodedata.normalize('NFKC', '' if raw is None else str(raw)).strip()
    return ' '.join(text.split())


def _clean_key(raw):
    key = '' if raw is None else str(raw).strip().lower()
    if not KEY_RE.match(key):
        raise ProgressError('key는 영문 소문자로 시작하고 영문/숫자/_ 만 사용할 수 있습니다.', code='invalid_key')
    return key


def _clean_name(raw):
    name = '' if raw is None else str(raw).strip()
    if not name:
        raise ProgressError('과목 이름은 필수입니다.', code='name_required')
    return name[:80]


def _clean_sort_order(raw):
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ProgressError('정렬 순서는 정수여야 합니다.', code='invalid_sort') from exc


def _clean_page(raw):
    try:
        page = int(raw)
    except (TypeError, ValueError) as exc:
        raise ProgressError('페이지는 정수여야 합니다.', code='invalid_page') from exc
    if page < MIN_PAGE:
        raise ProgressError('페이지는 1 이상이어야 합니다.', code='page_range')
    if page > MAX_PAGE:
        raise ProgressError('페이지 범위를 확인해주세요.', code='page_range')
    return page


def _clean_title(raw):
    title = normalize_textbook_title(raw)
    if not title:
        raise ProgressError('교재명은 필수입니다.', code='title_required')
    return title[:TITLE_MAX]


def _clean_recorded_on(raw):
    if isinstance(raw, date) and not isinstance(raw, datetime):
        recorded_on = raw
    else:
        text = '' if raw is None else str(raw).strip()
        try:
            recorded_on = date.fromisoformat(text[:10])
        except ValueError as exc:
            raise ProgressError('기록 날짜가 올바르지 않습니다.', code='invalid_date') from exc
    if recorded_on > kst_today():
        raise ProgressError('미래 날짜에는 진도를 기록할 수 없습니다.', code='future_date')
    return recorded_on


def ensure_default_subjects():
    """복구/초기화용. GET 조회에서는 호출하지 않는다."""
    existing = {row.key for row in LearningSubject.query.all()}
    created = 0
    for item in DEFAULT_SUBJECTS:
        if item['key'] in existing:
            continue
        db.session.add(LearningSubject(
            key=item['key'],
            name=item['name'],
            is_active=True,
            sort_order=item['sort_order'],
        ))
        created += 1
    if created:
        db.session.commit()
    return created


def list_subjects(include_inactive=True):
    query = LearningSubject.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    return query.order_by(LearningSubject.sort_order.asc(), LearningSubject.id.asc()).all()


def list_active_subjects():
    """활성 과목 SELECT만 수행한다. 누락 row를 재생성하지 않는다."""
    return list_subjects(include_inactive=False)


def get_subject(subject_id):
    return LearningSubject.query.get(subject_id)


def create_subject(key, name, is_active=True, sort_order=0):
    subject = LearningSubject(
        key=_clean_key(key),
        name=_clean_name(name),
        is_active=bool(is_active),
        sort_order=_clean_sort_order(sort_order),
    )
    db.session.add(subject)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ProgressError('이미 사용 중인 key입니다.', code='duplicate_key') from exc
    return subject


def update_subject(subject, *, name=None, is_active=None, sort_order=None):
    if name is not None:
        subject.name = _clean_name(name)
    if is_active is not None:
        subject.is_active = bool(is_active)
    if sort_order is not None:
        subject.sort_order = _clean_sort_order(sort_order)
    db.session.commit()
    return subject


def set_subject_active(subject, is_active):
    subject.is_active = bool(is_active)
    db.session.commit()
    return subject


def _model_named(name):
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        if getattr(cls, '__name__', None) == name:
            return cls
    return None


def _user_display_name(user_id):
    User = _model_named('User')
    if User is None or user_id is None:
        return ''
    user = User.query.get(user_id)
    if user is None:
        return ''
    return user.name or user.username or ''


def _comparable_previous(entry):
    title = normalize_textbook_title(entry.textbook_title)
    candidates = (
        LearningProgressEntry.query
        .filter_by(child_id=entry.child_id, learning_subject_id=entry.learning_subject_id)
        .filter(LearningProgressEntry.recorded_on < entry.recorded_on)
        .order_by(LearningProgressEntry.recorded_on.desc(), LearningProgressEntry.id.desc())
        .all()
    )
    for row in candidates:
        if normalize_textbook_title(row.textbook_title) == title:
            return row
    return None


def _has_any_previous(entry):
    return (
        LearningProgressEntry.query
        .filter_by(child_id=entry.child_id, learning_subject_id=entry.learning_subject_id)
        .filter(LearningProgressEntry.recorded_on < entry.recorded_on)
        .count()
        > 0
    )


def _delta_payload(entry):
    previous = _comparable_previous(entry)
    if previous is not None:
        return {
            'delta': entry.page - previous.page,
            'is_new_textbook': False,
            'previous_page': previous.page,
            'previous_recorded_on': previous.recorded_on,
        }
    return {
        'delta': None,
        'is_new_textbook': _has_any_previous(entry),
        'previous_page': None,
        'previous_recorded_on': None,
    }


def save_progress_entry(child_id, learning_subject_id, textbook_title, page, recorded_on, created_by_user_id):
    Child = _model_named('Child')
    if Child is None or Child.query.get(child_id) is None:
        raise ProgressError('아동을 찾을 수 없습니다.', code='child_not_found')

    try:
        subject_id = int(learning_subject_id)
    except (TypeError, ValueError) as exc:
        raise ProgressError('과목을 선택해주세요.', code='subject_required') from exc

    subject = get_subject(subject_id)
    if subject is None:
        raise ProgressError('과목을 찾을 수 없습니다.', code='subject_not_found')
    if not subject.is_active:
        raise ProgressError('비활성 과목에는 새 진도를 기록할 수 없습니다.', code='subject_inactive')

    title = _clean_title(textbook_title)
    page_value = _clean_page(page)
    day = _clean_recorded_on(recorded_on)

    existing = LearningProgressEntry.query.filter_by(
        child_id=child_id,
        learning_subject_id=subject.id,
        recorded_on=day,
    ).first()
    if existing is not None:
        existing.textbook_title = title
        existing.page = page_value
        existing.created_by_user_id = created_by_user_id
        db.session.commit()
        return existing, False

    entry = LearningProgressEntry(
        child_id=child_id,
        learning_subject_id=subject.id,
        recorded_on=day,
        textbook_title=title,
        page=page_value,
        created_by_user_id=created_by_user_id,
    )
    db.session.add(entry)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        existing = LearningProgressEntry.query.filter_by(
            child_id=child_id,
            learning_subject_id=subject.id,
            recorded_on=day,
        ).first()
        if existing is None:
            raise ProgressError('진도를 저장하지 못했습니다.', code='save_failed') from exc
        existing.textbook_title = title
        existing.page = page_value
        existing.created_by_user_id = created_by_user_id
        db.session.commit()
        return existing, False
    return entry, True


def current_progress_for_child(child_id):
    """활성 과목별 최신 스냅샷. GET 조회는 SELECT만 한다."""
    rows = []
    for subject in list_active_subjects():
        latest = (
            LearningProgressEntry.query
            .filter_by(child_id=child_id, learning_subject_id=subject.id)
            .order_by(LearningProgressEntry.recorded_on.desc(), LearningProgressEntry.id.desc())
            .first()
        )
        payload = {
            'subject': subject,
            'entry': latest,
            'delta': None,
            'is_new_textbook': False,
        }
        if latest is not None:
            payload.update(_delta_payload(latest))
        rows.append(payload)
    return rows


def history_for_child(child_id):
    entries = (
        LearningProgressEntry.query
        .filter_by(child_id=child_id)
        .order_by(LearningProgressEntry.recorded_on.desc(), LearningProgressEntry.id.desc())
        .all()
    )
    rows = []
    for entry in entries:
        delta_info = _delta_payload(entry)
        rows.append({
            'entry': entry,
            'subject': entry.subject,
            'created_by_name': _user_display_name(entry.created_by_user_id),
            **delta_info,
        })
    return rows


def delete_progress_for_child(child_id):
    """아동 삭제 시 FK 정리. 학기 reset_data에서는 호출하지 않는다."""
    LearningProgressEntry.query.filter_by(child_id=child_id).delete(synchronize_session=False)
