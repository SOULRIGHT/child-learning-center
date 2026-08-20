"""Book 생성. 교사 API와 검증된 아동 독서 흐름이 공유한다."""
from extensions import db
from feature_models import (
    Book,
    clean_book_author,
    clean_book_title,
    normalize_book_title,
)


class BookCreateError(ValueError):
    pass


def create_book_record(title, author=None, commit=True):
    """제목 필수, 저자 공백은 NULL. normalized_key는 서버가 만든다.

    중복 normalized_key는 허용하고 자동 merge 하지 않는다.
    """
    cleaned_title = clean_book_title(title)
    if not cleaned_title:
        raise BookCreateError('제목은 필수입니다.')

    book = Book(
        title=cleaned_title,
        author=clean_book_author(author),
        normalized_key=normalize_book_title(cleaned_title),
        is_recommended=False,
        is_challenge_eligible=False,
        is_active=True,
        sort_order=0,
    )
    db.session.add(book)
    if commit:
        db.session.commit()
    else:
        db.session.flush()

    similar = (
        Book.query.filter(
            Book.normalized_key == book.normalized_key,
            Book.id != book.id,
        )
        .order_by(Book.id.asc())
        .limit(10)
        .all()
    )
    return book, similar


def book_has_readings(book_id):
    """운영 사용처는 ChildReading.book_id 뿐이다. ReadingDay/보상은 ChildReading을 경유한다."""
    from feature_models import ChildReading

    if book_id is None:
        return False
    return ChildReading.query.filter_by(book_id=book_id).first() is not None


def used_book_ids(book_ids):
    from feature_models import ChildReading

    ids = [int(book_id) for book_id in book_ids or [] if book_id is not None]
    if not ids:
        return set()
    rows = (
        db.session.query(ChildReading.book_id)
        .filter(ChildReading.book_id.in_(ids))
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


def unlist_recommended_book(book):
    """추천목록에서만 뺀다. 과거 ChildReading/보상/포인트는 바꾸지 않는다."""
    return update_recommended_flags(book, is_recommended=False)


def delete_unused_book(book):
    """ChildReading이 없는 Book만 hard delete. 관련 원장은 cascade하지 않는다."""
    if book is None:
        raise BookCreateError('책을 찾을 수 없습니다.')
    if book_has_readings(book.id):
        raise BookCreateError(
            '이 도서는 독서 기록에 사용되어 삭제할 수 없습니다. 대신 추천도서에서 제외할 수 있습니다.'
        )
    db.session.delete(book)
    db.session.commit()
    return True


def update_recommended_flags(book, is_recommended=None, grade_band=None):
    """추천 지정/해제와 학년군만 바꾼다. Book 자체는 삭제하지 않는다."""
    from features.reading.classify import VALID_GRADE_BANDS, normalize_grade_band

    if book is None:
        raise BookCreateError('책을 찾을 수 없습니다.')
    if is_recommended is not None:
        book.is_recommended = bool(is_recommended)
    if grade_band is not None:
        text = str(grade_band).strip()
        if text == '':
            book.grade_band = None
        else:
            parsed = normalize_grade_band(text)
            if parsed not in VALID_GRADE_BANDS:
                raise BookCreateError('학년군은 2-3 또는 4-6만 사용할 수 있습니다.')
            book.grade_band = parsed
    if book.is_recommended and not book.grade_band:
        raise BookCreateError('추천도서는 학년군(2-3 또는 4-6)이 필요합니다.')
    db.session.commit()
    return book
