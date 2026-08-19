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
