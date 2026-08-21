"""신규 도메인 모델. 기존 app.py 모델은 이동하지 않는다."""
from __future__ import annotations

import re
import unicodedata

from datetime import datetime

from sqlalchemy import Index, UniqueConstraint, text

from extensions import db


_PUNCT_AND_SPACE_RE = re.compile(
    r'[\s\-–—_·•.,!?;:\'"“”‘’()\[\]{}/\\~*`]+'
)


def normalize_book_title(title):
    """제목 표기 차이를 완화한 검색 키를 만든다.

    규칙:
    - NFKC 정규화 (전각/호환 문자를 호환 형태로)
    - casefold (영문 대소문자)
    - 공백, 하이픈, 흔한 문장부호 제거
    - 한글/숫자/영문 본문은 유지
    - 저자는 포함하지 않음
    """
    if title is None:
        return ''
    text = unicodedata.normalize('NFKC', str(title)).strip()
    if not text:
        return ''
    text = text.casefold()
    text = _PUNCT_AND_SPACE_RE.sub('', text)
    return text


def clean_book_title(title):
    text = '' if title is None else str(title).strip()
    return text


def clean_book_author(author):
    if author is None:
        return None
    text = str(author).strip()
    return text or None


class Book(db.Model):
    __tablename__ = 'book'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=True)
    normalized_key = db.Column(db.String(255), nullable=False, index=True)
    is_recommended = db.Column(db.Boolean, nullable=False, default=False)
    grade_band = db.Column(db.String(16), nullable=True)
    is_challenge_eligible = db.Column(db.Boolean, nullable=False, default=False)
    ai_difficulty_low = db.Column(db.Integer, nullable=True)
    ai_difficulty_high = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_public_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'is_recommended': bool(self.is_recommended),
            'is_challenge_eligible': bool(self.is_challenge_eligible),
            'grade_band': self.grade_band,
            'is_active': bool(self.is_active),
        }

    def __repr__(self):
        return f'<Book {self.id} {self.title}>'


STATUS_IN_PROGRESS = 'in_progress'
STATUS_COMPLETED = 'completed'
STATUS_ABANDONED = 'abandoned'
PROGRAM_TYPE_GENERAL = 'general'
PROGRAM_TYPE_RECOMMENDED = 'recommended'
PROGRAM_TYPE_CHALLENGE = 'challenge'
POLICY_VERSION_GENERAL_V2 = 'general_v2'
POLICY_VERSION_RECOMMENDED_V1 = 'recommended_v1'
POLICY_VERSION_CHALLENGE_V1 = 'challenge_v1'
GRADE_BAND_2_3 = '2-3'
GRADE_BAND_4_6 = '4-6'
EVENT_RECOMMENDED_START = 'recommended_start'
EVENT_RECOMMENDED_COMPLETE = 'recommended_complete'
EVENT_CHALLENGE_START = 'challenge_start'
EVENT_CHALLENGE_COMPLETE = 'challenge_complete'
ACTOR_CHILD = 'child'
ACTOR_TEACHER = 'teacher'
REWARD_MODE_POINTS = 'points'
REWARD_MODE_EXEMPTION = 'exemption'
TICKET_STATUS_ACTIVE = 'active'
TICKET_STATUS_USED = 'used'
TICKET_STATUS_EXPIRED = 'expired'
TICKET_STATUS_REVOKED = 'revoked'


class ChildReading(db.Model):
    """한 아동이 한 권을 읽은 전체 기간."""
    __tablename__ = 'child_reading'
    __table_args__ = (
        Index(
            'uq_child_reading_one_in_progress',
            'child_id',
            unique=True,
            sqlite_where=text("status = 'in_progress'"),
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False, index=True)

    started_on = db.Column(db.Date, nullable=False)
    completed_on = db.Column(db.Date, nullable=True)
    ended_on = db.Column(db.Date, nullable=True)

    status = db.Column(db.String(32), nullable=False, default=STATUS_IN_PROGRESS, index=True)
    program_type = db.Column(db.String(32), nullable=False, default=PROGRAM_TYPE_GENERAL)
    policy_version = db.Column(db.String(32), nullable=False, default=POLICY_VERSION_GENERAL_V2)
    reward_mode = db.Column(db.String(16), nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    actor_type = db.Column(db.String(16), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    book = db.relationship('Book')
    days = db.relationship('ReadingDay', back_populates='child_reading', lazy='dynamic')

    def __repr__(self):
        return f'<ChildReading {self.id} child={self.child_id} book={self.book_id} {self.status}>'


class ReadingDay(db.Model):
    """실제로 읽은 날짜의 독서기록장 한 칸."""
    __tablename__ = 'reading_day'
    __table_args__ = (
        UniqueConstraint('child_reading_id', 'date', name='uq_reading_day_reading_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_reading_id = db.Column(
        db.Integer,
        db.ForeignKey('child_reading.id'),
        nullable=False,
        index=True,
    )
    date = db.Column(db.Date, nullable=False, index=True)
    review_text = db.Column(db.Text, nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    actor_type = db.Column(db.String(16), nullable=False)
    policy_version = db.Column(db.String(32), nullable=False, default=POLICY_VERSION_GENERAL_V2)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    child_reading = db.relationship('ChildReading', back_populates='days')

    def __repr__(self):
        return f'<ReadingDay {self.id} reading={self.child_reading_id} {self.date}>'


class ReadingRewardEvent(db.Model):
    """추천독서 시작/완독 보상 원장. 중복 지급 방지의 정본."""
    __tablename__ = 'reading_reward_event'
    __table_args__ = (
        UniqueConstraint(
            'child_reading_id',
            'event_type',
            name='uq_reading_reward_event_reading_type',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_reading_id = db.Column(
        db.Integer,
        db.ForeignKey('child_reading.id'),
        nullable=False,
        index=True,
    )
    event_type = db.Column(db.String(32), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    awarded_on = db.Column(db.Date, nullable=False, index=True)
    policy_version = db.Column(db.String(32), nullable=False, default=POLICY_VERSION_RECOMMENDED_V1)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    child_reading = db.relationship('ChildReading')

    def __repr__(self):
        return (
            f'<ReadingRewardEvent {self.id} reading={self.child_reading_id} '
            f'{self.event_type} {self.points}P>'
        )


class ManualPointPreset(db.Model):
    """자주 쓰는 수동포인트 버튼 설정. 실제 지급 원장이 아니다."""
    __tablename__ = 'manual_point_preset'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), nullable=False, unique=True)
    label = db.Column(db.String(80), nullable=False)
    default_points = db.Column(db.Integer, nullable=False)
    default_reason = db.Column(db.String(80), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_public_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'label': self.label,
            'default_points': self.default_points,
            'default_reason': self.default_reason or '',
            'is_active': bool(self.is_active),
            'sort_order': self.sort_order,
        }

    def __repr__(self):
        return f'<ManualPointPreset {self.key} {self.default_points}>'


class LearningSubject(db.Model):
    """학습진도 과목 마스터. DailyPoints 과목 컬럼 및 면제권 과목 목록과 별개다."""
    __tablename__ = 'learning_subject'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), nullable=False, unique=True)
    name = db.Column(db.String(80), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<LearningSubject {self.key}>'


class LearningProgressEntry(db.Model):
    """아동+과목+날짜 단위의 학습진도 스냅샷. 다른 날짜는 append-only."""
    __tablename__ = 'learning_progress_entry'
    __table_args__ = (
        UniqueConstraint(
            'child_id',
            'learning_subject_id',
            'recorded_on',
            name='uq_progress_child_subject_date',
        ),
        Index('ix_progress_child_recorded_on', 'child_id', 'recorded_on'),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False, index=True)
    learning_subject_id = db.Column(
        db.Integer,
        db.ForeignKey('learning_subject.id'),
        nullable=False,
        index=True,
    )
    recorded_on = db.Column(db.Date, nullable=False, index=True)
    textbook_title = db.Column(db.String(120), nullable=False)
    page = db.Column(db.Integer, nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subject = db.relationship('LearningSubject')

    def __repr__(self):
        return (
            f'<LearningProgressEntry {self.id} child={self.child_id} '
            f'{self.recorded_on} p{self.page}>'
        )


class ExemptionTicket(db.Model):
    """학습 면제권 장부. 종이 면제권의 발급/보유/만료/취소를 기록한다."""
    __tablename__ = 'exemption_ticket'
    __table_args__ = (
        Index(
            'uq_exemption_ticket_one_active',
            'child_id',
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index('ix_exemption_ticket_child_status', 'child_id', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False, index=True)
    issued_on = db.Column(db.Date, nullable=False, index=True)
    expires_on = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False, default=TICKET_STATUS_ACTIVE, index=True)
    policy_version = db.Column(db.String(32), nullable=False)
    issued_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    sources = db.relationship('ExemptionTicketSource', back_populates='ticket')
    usage = db.relationship('ExemptionUsage', back_populates='ticket', uselist=False)

    def __repr__(self):
        return f'<ExemptionTicket {self.id} child={self.child_id} {self.status}>'


class ExemptionTicketSource(db.Model):
    """면제권 발급에 소비된 추천독서 완독. revoked ticket source는 조회에서 미소비로 본다."""
    __tablename__ = 'exemption_ticket_source'
    __table_args__ = (
        UniqueConstraint(
            'exemption_ticket_id',
            'child_reading_id',
            name='uq_exemption_source_ticket_reading',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    exemption_ticket_id = db.Column(
        db.Integer,
        db.ForeignKey('exemption_ticket.id'),
        nullable=False,
        index=True,
    )
    child_reading_id = db.Column(
        db.Integer,
        db.ForeignKey('child_reading.id'),
        nullable=False,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ticket = db.relationship('ExemptionTicket', back_populates='sources')
    child_reading = db.relationship('ChildReading')

    def __repr__(self):
        return (
            f'<ExemptionTicketSource {self.id} ticket={self.exemption_ticket_id} '
            f'reading={self.child_reading_id}>'
        )


class ExemptionUsage(db.Model):
    """면제권 사용 장부. 한 ticket은 한 과목·한 날짜만 면제한다."""
    __tablename__ = 'exemption_usage'
    __table_args__ = (
        UniqueConstraint('exemption_ticket_id', name='uq_exemption_usage_ticket'),
    )

    id = db.Column(db.Integer, primary_key=True)
    exemption_ticket_id = db.Column(
        db.Integer,
        db.ForeignKey('exemption_ticket.id'),
        nullable=False,
        unique=True,
    )
    subject_key = db.Column(db.String(64), nullable=False, index=True)
    subject_name = db.Column(db.String(80), nullable=False)
    used_on = db.Column(db.Date, nullable=False, index=True)
    recorded_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ticket = db.relationship('ExemptionTicket', back_populates='usage')

    def __repr__(self):
        return (
            f'<ExemptionUsage {self.id} ticket={self.exemption_ticket_id} '
            f'{self.subject_key} {self.used_on}>'
        )
