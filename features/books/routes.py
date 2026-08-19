"""Book 검색/등록 API. Step 1에서는 마스터만 다룬다."""
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from feature_models import Book, normalize_book_title
from features.books.service import BookCreateError, create_book_record

books_bp = Blueprint('books', __name__)

SEARCH_LIMIT = 20
SEARCH_FETCH_LIMIT = 50


def _search_rank(book, q_norm, q_lower):
    key = book.normalized_key or ''
    title_l = (book.title or '').casefold()
    if q_norm and key == q_norm:
        return (0, book.sort_order or 0, book.id or 0)
    if q_norm and key.startswith(q_norm):
        return (1, book.sort_order or 0, book.id or 0)
    if q_norm and q_norm in key:
        return (2, book.sort_order or 0, book.id or 0)
    if q_lower and title_l.startswith(q_lower):
        return (3, book.sort_order or 0, book.id or 0)
    return (4, book.sort_order or 0, book.id or 0)


@books_bp.route('/books')
@login_required
def books_index():
    """개발/교사 확인용 최소 검색·등록 화면."""
    return render_template('books/index.html')


@books_bp.route('/api/books', methods=['GET'])
@login_required
def search_books():
    raw_q = request.args.get('q', '')
    q = (raw_q or '').strip()
    if not q:
        return jsonify({'books': []}), 200

    q_norm = normalize_book_title(q)
    q_lower = q.casefold()
    filters = [Book.is_active.is_(True)]
    match_clauses = [func.lower(Book.title).contains(q_lower)]
    if q_norm:
        match_clauses.append(Book.normalized_key.contains(q_norm))
    filters.append(or_(*match_clauses))

    candidates = (
        Book.query.filter(*filters)
        .limit(SEARCH_FETCH_LIMIT)
        .all()
    )
    candidates.sort(key=lambda book: _search_rank(book, q_norm, q_lower))
    books = [book.to_public_dict() for book in candidates[:SEARCH_LIMIT]]
    return jsonify({'books': books})


@books_bp.route('/api/books', methods=['POST'])
@login_required
def create_book():
    if getattr(current_user, 'role', None) == current_app.config.get('VIEWER_ROLE_NAME', '학생열람'):
        return redirect(url_for('viewer_home'))

    payload = request.get_json(silent=True) or {}
    try:
        book, similar = create_book_record(payload.get('title'), payload.get('author'))
    except BookCreateError as exc:
        return jsonify({'created': False, 'error': str(exc)}), 400

    return jsonify({
        'created': True,
        'book': book.to_public_dict(),
        'similar_books': [item.to_public_dict() for item in similar],
    }), 201
