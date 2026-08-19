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
        }

    def __repr__(self):
        return f'<Book {self.id} {self.title}>'


STATUS_IN_PROGRESS = 'in_progress'
STATUS_COMPLETED = 'completed'
STATUS_ABANDONED = 'abandoned'
PROGRAM_TYPE_GENERAL = 'general'
POLICY_VERSION_GENERAL_V2 = 'general_v2'
ACTOR_CHILD = 'child'
ACTOR_TEACHER = 'teacher'


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
