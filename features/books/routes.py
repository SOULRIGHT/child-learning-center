"""Book 검색/등록/추천도서 관리. 추천 목록 일괄등록은 preview 후 confirm."""
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from feature_models import Book, normalize_book_title
from features.books.import_service import (
    RecommendedImportError,
    apply_preview,
    clear_preview,
    load_preview,
    parse_csv_bytes,
    parse_paste_text,
    parse_xlsx_bytes,
    preview_rows,
    store_preview,
)
from features.books.service import (
    BookCreateError,
    create_book_record,
    delete_unused_book,
    unlist_recommended_book,
    update_recommended_flags,
    used_book_ids,
)
from features.reading.classify import GRADE_BAND_2_3, GRADE_BAND_4_6, grade_band_for_child_grade, normalize_grade_band

books_bp = Blueprint('books', __name__)

SEARCH_LIMIT = 20
SEARCH_FETCH_LIMIT = 50
MANAGE_PAGE_SIZE = 50


def _is_viewer():
    return getattr(current_user, 'role', None) == current_app.config.get(
        'VIEWER_ROLE_NAME', '학생열람'
    )


def _forbid_viewer():
    if _is_viewer():
        return redirect(url_for('viewer_home'))
    return None


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
    blocked = _forbid_viewer()
    if blocked:
        return blocked

    filter_key = (request.args.get('filter') or 'all').strip()
    q = (request.args.get('q') or '').strip()
    try:
        page = max(int(request.args.get('page') or 1), 1)
    except (TypeError, ValueError):
        page = 1

    query = Book.query
    if filter_key == 'recommended':
        query = query.filter(Book.is_recommended.is_(True))
    elif filter_key == GRADE_BAND_2_3:
        query = query.filter(Book.is_recommended.is_(True), Book.grade_band == GRADE_BAND_2_3)
    elif filter_key == GRADE_BAND_4_6:
        query = query.filter(Book.is_recommended.is_(True), Book.grade_band == GRADE_BAND_4_6)

    if q:
        q_norm = normalize_book_title(q)
        q_lower = q.casefold()
        match_clauses = [func.lower(Book.title).contains(q_lower)]
        if q_norm:
            match_clauses.append(Book.normalized_key.contains(q_norm))
        query = query.filter(or_(*match_clauses))

    total = query.count()
    books = (
        query.order_by(Book.is_recommended.desc(), Book.grade_band.asc(), Book.id.desc())
        .offset((page - 1) * MANAGE_PAGE_SIZE)
        .limit(MANAGE_PAGE_SIZE)
        .all()
    )
    total_pages = max((total + MANAGE_PAGE_SIZE - 1) // MANAGE_PAGE_SIZE, 1)
    in_use_ids = used_book_ids([book.id for book in books])
    return render_template(
        'books/index.html',
        books=books,
        filter_key=filter_key,
        q=q,
        page=page,
        total=total,
        total_pages=total_pages,
        in_use_ids=in_use_ids,
    )


@books_bp.route('/api/books', methods=['GET'])
@login_required
def search_books():
    raw_q = request.args.get('q', '')
    q = (raw_q or '').strip()
    recommended_only = (request.args.get('recommended') or '').strip().lower() in {'1', 'true', 'yes'}
    grade_band = normalize_grade_band(request.args.get('grade_band'))
    child_grade = request.args.get('child_grade', type=int)
    if child_grade and not grade_band:
        grade_band = grade_band_for_child_grade(child_grade)

    if not q and not recommended_only:
        return jsonify({'books': []}), 200

    q_norm = normalize_book_title(q) if q else ''
    q_lower = q.casefold() if q else ''
    filters = [Book.is_active.is_(True)]
    if recommended_only:
        filters.append(Book.is_recommended.is_(True))
        if grade_band:
            filters.append(Book.grade_band == grade_band)
    if q:
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
    blocked = _forbid_viewer()
    if blocked:
        return blocked

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


@books_bp.route('/books/<int:book_id>/recommended', methods=['POST'])
@login_required
def update_book_recommended(book_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    book = Book.query.get_or_404(book_id)
    is_recommended_raw = request.form.get('is_recommended')
    grade_band = request.form.get('grade_band')
    is_recommended = None
    if is_recommended_raw is not None:
        is_recommended = is_recommended_raw in {'1', 'on', 'true', 'yes'}
    try:
        update_recommended_flags(book, is_recommended=is_recommended, grade_band=grade_band)
        flash('도서 추천 설정을 저장했습니다.', 'success')
    except BookCreateError as exc:
        flash(str(exc), 'error')
    return redirect(url_for(
        'books.books_index',
        filter=request.form.get('filter') or 'all',
        q=request.form.get('q') or '',
        page=request.form.get('page') or 1,
    ))


def _redirect_books_index():
    return redirect(url_for(
        'books.books_index',
        filter=request.form.get('filter') or 'all',
        q=request.form.get('q') or '',
        page=request.form.get('page') or 1,
    ))


@books_bp.route('/books/<int:book_id>/unlist', methods=['POST'])
@login_required
def unlist_book(book_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    book = Book.query.get_or_404(book_id)
    try:
        unlist_recommended_book(book)
        flash('추천도서에서 제외했습니다. 책은 남아 있고, 과거 독서 기록은 그대로입니다.', 'success')
    except BookCreateError as exc:
        flash(str(exc), 'error')
    return _redirect_books_index()


@books_bp.route('/books/<int:book_id>/delete', methods=['POST'])
@login_required
def delete_book(book_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    book = Book.query.get_or_404(book_id)
    try:
        delete_unused_book(book)
        flash('도서를 삭제했습니다.', 'success')
    except BookCreateError as exc:
        flash(str(exc), 'error')
    return _redirect_books_index()


@books_bp.route('/books/recommended/import', methods=['GET', 'POST'])
@login_required
def recommended_import():
    blocked = _forbid_viewer()
    if blocked:
        return blocked

    if request.method == 'GET':
        return render_template('books/import.html')

    default_grade_band = request.form.get('grade_band')
    paste_text = request.form.get('paste_text') or ''
    upload = request.files.get('file')
    try:
        if upload and upload.filename:
            filename = upload.filename.lower()
            raw = upload.read()
            if filename.endswith('.xlsx'):
                raw_rows = parse_xlsx_bytes(raw)
            elif filename.endswith('.csv') or filename.endswith('.txt'):
                raw_rows = parse_csv_bytes(raw)
            else:
                flash('CSV 또는 Excel(.xlsx) 파일만 올릴 수 있습니다.', 'error')
                return render_template('books/import.html')
        elif paste_text.strip():
            raw_rows = parse_paste_text(paste_text)
        else:
            flash('파일 또는 여러 줄 목록을 입력해 주세요.', 'error')
            return render_template('books/import.html')

        if len(raw_rows) > 400:
            flash('한 번에 400권까지만 올릴 수 있습니다.', 'error')
            return render_template('books/import.html')

        preview = preview_rows(raw_rows, default_grade_band=default_grade_band)
        token = store_preview(preview)
        session['recommended_import_token'] = token
        return render_template('books/import_preview.html', preview=preview, token=token)
    except Exception as exc:
        flash(f'목록을 읽지 못했습니다: {exc}', 'error')
        return render_template('books/import.html')


@books_bp.route('/books/recommended/import/confirm', methods=['POST'])
@login_required
def recommended_import_confirm():
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    token = request.form.get('token') or session.get('recommended_import_token')
    try:
        payload = load_preview(token)
        preview = payload.get('preview') or {}
        selected = request.form.getlist('include')
        if not selected:
            flash('적용할 도서를 선택해 주세요.', 'error')
            return render_template('books/import_preview.html', preview=preview, token=token)
        result = apply_preview(preview, selected_row_keys=selected)
        if result['created'] + result['reused'] == 0:
            flash('선택한 도서를 적용할 수 없습니다. 확인 필요/오류 행은 적용되지 않습니다.', 'error')
            return render_template('books/import_preview.html', preview=preview, token=token)
        clear_preview(token)
        session.pop('recommended_import_token', None)
        flash(
            f"추천도서 {result['created'] + result['reused']}권을 반영했습니다. "
            f"신규 {result['created']} · 기존 연결 {result['reused']} · 제외/확인 필요/오류 {result['skipped']}.",
            'success',
        )
        return redirect(url_for('books.books_index', filter='recommended'))
    except RecommendedImportError as exc:
        flash(exc.message, 'error')
        return redirect(url_for('books.recommended_import'))
    except Exception as exc:
        flash(f'등록 중 오류가 발생했습니다: {exc}', 'error')
        return redirect(url_for('books.recommended_import'))
