"""Book JSON 백업 복원. 기존 DailyPoints 복원 경로는 변경하지 않는다."""
from __future__ import annotations

from datetime import datetime

from extensions import db
from feature_models import Book, clean_book_author, clean_book_title, normalize_book_title


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def restore_books_from_backup_data(backup_data):
    """JSON 백업의 books 목록을 Book 테이블에 반영한다.

    같은 id가 있으면 갱신, 없으면 생성한다. 다른 테이블은 건드리지 않는다.
    """
    rows = (backup_data or {}).get('books') or []
    restored = 0
    for item in rows:
        if not isinstance(item, dict):
            continue
        title = clean_book_title(item.get('title'))
        if not title:
            continue

        book_id = item.get('id')
        book = Book.query.get(book_id) if book_id else None
        if book is None:
            book = Book(id=book_id) if book_id else Book()
            db.session.add(book)

        book.title = title
        book.author = clean_book_author(item.get('author'))
        book.normalized_key = item.get('normalized_key') or normalize_book_title(title)
        if 'is_recommended' in item:
            book.is_recommended = bool(item.get('is_recommended'))
        if 'grade_band' in item:
            book.grade_band = item.get('grade_band')
        if 'is_challenge_eligible' in item:
            book.is_challenge_eligible = bool(item.get('is_challenge_eligible'))
        if 'ai_difficulty_low' in item:
            book.ai_difficulty_low = item.get('ai_difficulty_low')
        if 'ai_difficulty_high' in item:
            book.ai_difficulty_high = item.get('ai_difficulty_high')
        if 'is_active' in item:
            book.is_active = bool(item.get('is_active')) if item.get('is_active') is not None else True
        if 'sort_order' in item:
            book.sort_order = int(item.get('sort_order') or 0)
        created_at = _parse_dt(item.get('created_at'))
        updated_at = _parse_dt(item.get('updated_at'))
        if created_at:
            book.created_at = created_at
        if updated_at:
            book.updated_at = updated_at
        restored += 1

    db.session.commit()
    return restored
