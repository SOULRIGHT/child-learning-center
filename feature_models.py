"""신규 도메인 모델. 기존 app.py 모델은 이동하지 않는다."""
from __future__ import annotations

import re
import unicodedata

from extensions import db
from datetime import datetime


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
