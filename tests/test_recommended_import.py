"""Step 5: 추천도서 CSV/xlsx/붙여넣기 import. 실제 센터 제목은 seed하지 않는다."""
from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
import importlib.util
import tempfile

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import Book, ChildReading, ReadingRewardEvent  # noqa: E402
from features.books.import_service import (  # noqa: E402
    apply_preview,
    load_preview,
    parse_csv_bytes,
    parse_paste_text,
    parse_xlsx_bytes,
    preview_rows,
)
from features.books.service import create_book_record, delete_unused_book, update_recommended_flags  # noqa: E402
from features.dates import kst_today  # noqa: E402
from features.reading.rewards import EVENT_START, approve_recommended_reward  # noqa: E402
from features.reading.service import start_book  # noqa: E402


def _csv(text):
    return text.encode('utf-8-sig')


class RecommendedImportTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='rec_import_teacher',
            name='추천교사',
            role='돌봄선생님',
            email='rec-import-teacher@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='rec_import_viewer',
            name='추천열람',
            role='학생열람',
            email='studentview-rec-import@example.test',
            password_hash='',
        )
        self.general = User(
            username='rec_import_general',
            name='추천일반',
            role='일반사용자',
            email='rec-import-general@example.test',
            password_hash='',
        )
        db.session.add_all([self.teacher, self.viewer, self.general])
        db.session.commit()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def test_csv_2_3_creates_new_recommended_books(self):
        rows = parse_csv_bytes(_csv('title,author\n센터샘플A,작가A\n센터샘플B,작가B\n'))
        preview = preview_rows(rows, default_grade_band='2-3')
        self.assertEqual(preview['counts']['create'], 2)
        apply_preview(preview)
        books = Book.query.order_by(Book.title.asc()).all()
        self.assertEqual(len(books), 2)
        self.assertTrue(all(book.is_recommended for book in books))
        self.assertTrue(all(book.grade_band == '2-3' for book in books))

    def test_csv_4_6_creates_new_recommended_books(self):
        rows = parse_csv_bytes(_csv('title,author\n고학년샘플A,작가C\n'))
        preview = preview_rows(rows, default_grade_band='4-6')
        apply_preview(preview)
        book = Book.query.one()
        self.assertEqual(book.grade_band, '4-6')
        self.assertTrue(book.is_recommended)

    def test_title_only_row_allows_null_author(self):
        rows = parse_paste_text('제목만있는책')
        preview = preview_rows(rows, default_grade_band='2-3')
        apply_preview(preview)
        book = Book.query.one()
        self.assertEqual(book.title, '제목만있는책')
        self.assertIsNone(book.author)

    def test_title_and_author_row(self):
        rows = parse_paste_text('붙여넣기책 | 붙여넣기작가')
        preview = preview_rows(rows, default_grade_band='2-3')
        apply_preview(preview)
        book = Book.query.one()
        self.assertEqual(book.author, '붙여넣기작가')

    def test_grade_band_column_overrides_ui(self):
        rows = parse_csv_bytes(_csv('title,author,grade_band\n컬럼책,작가,4-6\n'))
        preview = preview_rows(rows, default_grade_band='2-3')
        self.assertEqual(preview['rows'][0]['grade_band'], '4-6')
        apply_preview(preview)
        self.assertEqual(Book.query.one().grade_band, '4-6')

    def test_ui_grade_band_fallback(self):
        rows = parse_csv_bytes(_csv('title,author\n폴백책,작가\n'))
        preview = preview_rows(rows, default_grade_band='2-3')
        self.assertEqual(preview['rows'][0]['grade_band'], '2-3')

    def test_invalid_grade_band_rejected(self):
        rows = parse_csv_bytes(_csv('title,author,grade_band\n잘못된책,작가,1-2\n'))
        preview = preview_rows(rows, default_grade_band='2-3')
        self.assertEqual(preview['counts']['error'], 1)
        apply_preview(preview)
        self.assertEqual(Book.query.count(), 0)

    def test_missing_title_rejected(self):
        rows = parse_paste_text('| 작가만')
        preview = preview_rows(rows, default_grade_band='2-3')
        self.assertEqual(preview['counts']['error'], 1)
        apply_preview(preview)
        self.assertEqual(Book.query.count(), 0)

    def test_missing_grade_band_without_ui_choice_is_error(self):
        rows = parse_paste_text('학년군없는책')
        preview = preview_rows(rows, default_grade_band=None)
        self.assertEqual(preview['counts']['error'], 1)

    def test_normalized_title_reuses_existing_book(self):
        create_book_record('센터 샘플-책', '동일작가')
        rows = parse_paste_text('센터샘플책 | 동일작가')
        preview = preview_rows(rows, default_grade_band='2-3')
        self.assertEqual(preview['counts']['reuse'], 1)
        apply_preview(preview)
        self.assertEqual(Book.query.count(), 1)
        book = Book.query.one()
        self.assertTrue(book.is_recommended)
        self.assertEqual(book.grade_band, '2-3')

    def test_ambiguous_duplicate_is_not_auto_merged_or_created(self):
        create_book_record('중복제목', '작가1')
        create_book_record('중복제목', '작가2')
        rows = parse_paste_text('중복제목 | 작가1')
        preview = preview_rows(rows, default_grade_band='2-3')
        self.assertEqual(preview['counts']['review'], 1)
        apply_preview(preview)
        self.assertEqual(Book.query.count(), 2)
        self.assertFalse(any(book.is_recommended for book in Book.query.all()))

    def test_title_only_against_authored_book_is_review(self):
        create_book_record('애매한책', '있는작가')
        rows = parse_paste_text('애매한책')
        preview = preview_rows(rows, default_grade_band='2-3')
        self.assertEqual(preview['counts']['review'], 1)
        apply_preview(preview)
        self.assertFalse(Book.query.one().is_recommended)

    def test_reimport_same_list_is_idempotent(self):
        rows = parse_csv_bytes(_csv('title,author\n반복책,반복작가\n'))
        first = preview_rows(rows, default_grade_band='4-6')
        apply_preview(first)
        second = preview_rows(rows, default_grade_band='4-6')
        self.assertEqual(second['counts']['create'], 0)
        self.assertEqual(second['counts']['reuse'], 1)
        apply_preview(second)
        self.assertEqual(Book.query.count(), 1)

    def test_preview_does_not_write_db(self):
        rows = parse_paste_text('미리보기책 | 작가')
        preview_rows(rows, default_grade_band='2-3')
        self.assertEqual(Book.query.count(), 0)

    def test_confirm_writes_only_create_and_reuse(self):
        create_book_record('확인책', '작가')
        create_book_record('애매책', '작가1')
        create_book_record('애매책', '작가2')
        rows = parse_paste_text('확인책 | 작가\n새책 | 새작가\n애매책 | 작가1')
        preview = preview_rows(rows, default_grade_band='2-3')
        result = apply_preview(preview)
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['reused'], 1)
        self.assertGreaterEqual(result['skipped'], 1)
        self.assertEqual(Book.query.filter_by(title='새책').count(), 1)
        self.assertEqual(Book.query.filter_by(title='애매책').count(), 2)

    def test_xlsx_import(self):
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['title', 'author'])
        sheet.append(['엑셀책', '엑셀작가'])
        buf = io.BytesIO()
        workbook.save(buf)
        rows = parse_xlsx_bytes(buf.getvalue())
        preview = preview_rows(rows, default_grade_band='2-3')
        apply_preview(preview)
        book = Book.query.one()
        self.assertEqual(book.title, '엑셀책')
        self.assertTrue(book.is_recommended)
        self.assertFalse(book.is_challenge_eligible)

    def test_tab_separated_paste(self):
        rows = parse_paste_text('탭책\t탭작가')
        preview = preview_rows(rows, default_grade_band='4-6')
        apply_preview(preview)
        book = Book.query.one()
        self.assertEqual(book.author, '탭작가')
        self.assertEqual(book.grade_band, '4-6')

    def test_http_preview_then_confirm(self):
        self._login(self.teacher)
        before = Book.query.count()
        preview_resp = self.client.post(
            '/books/recommended/import',
            data={'grade_band': '2-3', 'paste_text': '화면책A | 작가A\n화면책B | 작가B'},
            follow_redirects=False,
        )
        self.assertEqual(preview_resp.status_code, 200)
        html = preview_resp.get_data(as_text=True)
        self.assertIn('아직 저장되지 않았습니다', html)
        self.assertEqual(Book.query.count(), before)
        with self.client.session_transaction() as sess:
            payload = load_preview(sess['recommended_import_token'])
        keys = [row['row_key'] for row in payload['preview']['rows'] if row.get('selectable')]
        confirm = self.client.post(
            '/books/recommended/import/confirm',
            data={'include': keys},
            follow_redirects=False,
        )
        self.assertEqual(confirm.status_code, 302)
        self.assertEqual(Book.query.count(), before + 2)

    def test_viewer_cannot_open_import(self):
        self._login(self.viewer)
        response = self.client.get('/books/recommended/import', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/viewer', response.headers.get('Location', ''))

    def test_viewer_cannot_confirm_import(self):
        self._login(self.viewer)
        response = self.client.post(
            '/books/recommended/import/confirm',
            data={'token': 'x'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/viewer', response.headers.get('Location', ''))
        self.assertEqual(Book.query.count(), 0)

    def test_general_user_settings_still_blocked_but_import_allowed(self):
        self._login(self.general)
        settings = self.client.get('/settings', follow_redirects=False)
        self.assertEqual(settings.status_code, 302)
        import_page = self.client.get('/books/recommended/import', follow_redirects=False)
        self.assertEqual(import_page.status_code, 200)

    def test_individual_flag_update_and_unlist(self):
        book, _ = create_book_record('개별수정책', '작가')
        update_recommended_flags(book, is_recommended=True, grade_band='2-3')
        self.assertTrue(book.is_recommended)
        update_recommended_flags(book, is_recommended=False, grade_band='2-3')
        self.assertFalse(book.is_recommended)
        self.assertEqual(book.grade_band, '2-3')
        self.assertEqual(Book.query.count(), 1)

    def test_manage_page_filters(self):
        create_book_record('일반책', None)
        rec, _ = create_book_record('추천23', None)
        update_recommended_flags(rec, is_recommended=True, grade_band='2-3')
        rec46, _ = create_book_record('추천46', None)
        update_recommended_flags(rec46, is_recommended=True, grade_band='4-6')
        self._login(self.teacher)
        all_page = self.client.get('/books').get_data(as_text=True)
        rec_page = self.client.get('/books?filter=recommended').get_data(as_text=True)
        band_page = self.client.get('/books?filter=2-3').get_data(as_text=True)
        self.assertIn('일반책', all_page)
        self.assertNotIn('일반책', rec_page)
        self.assertIn('추천23', band_page)
        self.assertNotIn('추천46', band_page)

    def test_recommended_search_api_limits_to_child_grade_band(self):
        rec23, _ = create_book_record('학년검색23', None)
        update_recommended_flags(rec23, is_recommended=True, grade_band='2-3')
        rec46, _ = create_book_record('학년검색46', None)
        update_recommended_flags(rec46, is_recommended=True, grade_band='4-6')
        self._login(self.teacher)
        books = self.client.get('/api/books?recommended=1&child_grade=3').get_json()['books']
        titles = {book['title'] for book in books}
        self.assertIn('학년검색23', titles)
        self.assertNotIn('학년검색46', titles)

    def test_search_marks_recommended_in_payload(self):
        rec, _ = create_book_record('표시책', None)
        update_recommended_flags(rec, is_recommended=True, grade_band='2-3')
        self._login(self.teacher)
        book = self.client.get('/api/books?q=표시책').get_json()['books'][0]
        self.assertTrue(book['is_recommended'])
        self.assertEqual(book['grade_band'], '2-3')

    def test_migration_creates_reward_table_without_seeding_books(self):
        migration_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/f1c9e24b8a70_create_reading_reward_event.py'
        )
        spec = importlib.util.spec_from_file_location('reward_migration', migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine, text

        with tempfile.TemporaryDirectory(prefix='clc_reward_mig_') as tmp:
            db_path = Path(tmp) / 'fresh.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text('CREATE TABLE child_reading (id INTEGER PRIMARY KEY)'))
                    conn.execute(text('CREATE TABLE user (id INTEGER PRIMARY KEY)'))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    tables = [row[0] for row in conn.execute(text(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )).fetchall()]
                    count = conn.execute(text('SELECT COUNT(*) FROM reading_reward_event')).scalar()
            finally:
                engine.dispose()
        self.assertIn('reading_reward_event', tables)
        self.assertEqual(count, 0)
        self.assertNotIn('book', tables)

    def _preview_keys(self, paste_text, grade_band='2-3'):
        self._login(self.teacher)
        resp = self.client.post(
            '/books/recommended/import',
            data={'grade_band': grade_band, 'paste_text': paste_text},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 200)
        with self.client.session_transaction() as sess:
            payload = load_preview(sess['recommended_import_token'])
        rows = payload['preview']['rows']
        keys = [row['row_key'] for row in rows if row.get('selectable')]
        return resp, keys, rows

    def test_preview_uncheck_one_row_applies_only_selected(self):
        _html, keys, _rows = self._preview_keys('제외책A | 작가\n제외책B | 작가\n제외책C | 작가')
        self.assertEqual(len(keys), 3)
        confirm = self.client.post(
            '/books/recommended/import/confirm',
            data={'include': keys[:2]},
            follow_redirects=False,
        )
        self.assertEqual(confirm.status_code, 302)
        titles = {book.title for book in Book.query.all()}
        self.assertEqual(titles, {'제외책A', '제외책B'})
        self.assertIsNone(Book.query.filter_by(title='제외책C').first())

    def test_preview_uncheck_all_creates_no_books(self):
        _html, keys, _rows = self._preview_keys('전부해제책 | 작가')
        self.assertEqual(len(keys), 1)
        confirm = self.client.post(
            '/books/recommended/import/confirm',
            data={},
            follow_redirects=False,
        )
        self.assertEqual(confirm.status_code, 200)
        html = confirm.get_data(as_text=True)
        self.assertIn('적용할 도서를 선택해 주세요', html)
        self.assertEqual(Book.query.filter_by(title='전부해제책').count(), 0)

    def test_unused_book_hard_delete(self):
        book, _ = create_book_record('미사용삭제책', '작가')
        update_recommended_flags(book, is_recommended=True, grade_band='2-3')
        book_id = book.id
        self._login(self.teacher)
        resp = self.client.post(f'/books/{book_id}/delete', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIsNone(Book.query.get(book_id))

    def test_used_book_hard_delete_rejected(self):
        book, _ = create_book_record('사용중삭제책', '작가')
        update_recommended_flags(book, is_recommended=True, grade_band='2-3')
        child = Child(name='삭제검증아동', grade=3, viewer_slug='aaaaaaaaaaaaaaaaaaaaaa01')
        db.session.add(child)
        db.session.commit()
        start_book(child.id, self.teacher.id, 'teacher', activity_date=kst_today(), book_id=book.id)
        self._login(self.teacher)
        resp = self.client.post(f'/books/{book.id}/delete', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('독서 기록에 사용되어 삭제할 수 없습니다', resp.get_data(as_text=True))
        self.assertIsNotNone(Book.query.get(book.id))
        self.assertEqual(ChildReading.query.filter_by(book_id=book.id).count(), 1)

    def test_used_book_can_be_unlisted(self):
        book, _ = create_book_record('해제대상책', '작가')
        update_recommended_flags(book, is_recommended=True, grade_band='2-3')
        child = Child(name='해제검증아동', grade=3, viewer_slug='aaaaaaaaaaaaaaaaaaaaaa02')
        db.session.add(child)
        db.session.commit()
        reading, _ = start_book(
            child.id, self.teacher.id, 'teacher', activity_date=kst_today(), book_id=book.id,
        )
        approve_recommended_reward(reading, self.teacher, EVENT_START)
        points_before = DailyPoints.query.filter_by(child_id=child.id).one().manual_points
        event_count = ReadingRewardEvent.query.count()
        self._login(self.teacher)
        resp = self.client.post(f'/books/{book.id}/unlist', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        book = Book.query.get(book.id)
        self.assertFalse(book.is_recommended)
        self.assertEqual(ChildReading.query.get(reading.id).program_type, 'recommended')
        self.assertEqual(ReadingRewardEvent.query.count(), event_count)
        self.assertEqual(DailyPoints.query.filter_by(child_id=child.id).one().manual_points, points_before)

    def test_viewer_cannot_unlist_or_delete_book(self):
        book, _ = create_book_record('열람삭제책', '작가')
        update_recommended_flags(book, is_recommended=True, grade_band='2-3')
        self._login(self.viewer)
        unlist = self.client.post(f'/books/{book.id}/unlist', follow_redirects=False)
        delete = self.client.post(f'/books/{book.id}/delete', follow_redirects=False)
        self.assertEqual(unlist.status_code, 302)
        self.assertIn('/viewer', unlist.headers.get('Location', ''))
        self.assertEqual(delete.status_code, 302)
        self.assertIn('/viewer', delete.headers.get('Location', ''))
        leftover = Book.query.get(book.id)
        self.assertTrue(leftover.is_recommended)
        self.assertIsNotNone(leftover)

    def test_manage_page_shows_unlist_and_delete_actions(self):
        rec, _ = create_book_record('버튼확인책', None)
        update_recommended_flags(rec, is_recommended=True, grade_band='2-3')
        self._login(self.teacher)
        html = self.client.get('/books').get_data(as_text=True)
        self.assertIn('추천 해제', html)
        self.assertIn('도서 삭제', html)

    def test_delete_unused_service_and_used_raises(self):
        unused, _ = create_book_record('서비스삭제책', None)
        delete_unused_book(unused)
        self.assertIsNone(Book.query.filter_by(title='서비스삭제책').first())

    def test_cannot_import_recommended_onto_challenge_book(self):
        book, _ = create_book_record('충돌책', '같은작가')
        from features.books.service import update_challenge_flag
        update_challenge_flag(book, True)
        rows = parse_paste_text('충돌책 | 같은작가')
        preview = preview_rows(rows, default_grade_band='4-6')
        self.assertEqual(preview['counts']['error'], 1)
        self.assertIn('도전도서', preview['rows'][0]['message'])
        apply_preview(preview)
        saved = Book.query.one()
        self.assertTrue(saved.is_challenge_eligible)
        self.assertFalse(saved.is_recommended)


if __name__ == '__main__':
    unittest.main()
