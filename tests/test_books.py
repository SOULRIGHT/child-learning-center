"""Step 1: Book 마스터 검색/등록 회귀테스트."""
from __future__ import annotations

import json
import unittest

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User, get_backup_data  # noqa: E402
from feature_models import Book, normalize_book_title  # noqa: E402
from features.books.restore import restore_books_from_backup_data  # noqa: E402


class BookMasterTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()

        self.teacher = User(
            username='book_teacher',
            name='도서교사',
            role='돌봄선생님',
            email='book-teacher@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='book_viewer',
            name='도서열람',
            role='학생열람',
            email='studentview-book@example.test',
            password_hash='',
        )
        db.session.add_all([self.teacher, self.viewer])
        db.session.commit()
        self.teacher_id = self.teacher.id
        self.viewer_id = self.viewer.id
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user_or_id):
        user_id = user_or_id if isinstance(user_or_id, int) else user_or_id.id
        with self.client.session_transaction() as sess:
            sess.clear()
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True

    def _create(self, **payload):
        return self.client.post(
            '/api/books',
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_create_book_persists_defaults(self):
        self._login(self.teacher)
        response = self._create(title=' 어린 왕자 ', author=' 생텍쥐페리 ')
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertTrue(body['created'])
        self.assertEqual(body['book']['title'], '어린 왕자')
        self.assertEqual(body['book']['author'], '생텍쥐페리')

        book = Book.query.get(body['book']['id'])
        self.assertEqual(book.title, '어린 왕자')
        self.assertEqual(book.author, '생텍쥐페리')
        self.assertEqual(book.normalized_key, normalize_book_title('어린 왕자'))
        self.assertFalse(book.is_recommended)
        self.assertFalse(book.is_challenge_eligible)
        self.assertTrue(book.is_active)
        self.assertEqual(book.sort_order, 0)
        self.assertIsNone(book.grade_band)
        self.assertIsNone(book.ai_difficulty_low)
        self.assertIsNone(book.ai_difficulty_high)

    def test_blank_title_is_rejected(self):
        self._login(self.teacher)
        empty = self._create(title='')
        whitespace = self._create(title='   ')
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(whitespace.status_code, 400)
        self.assertEqual(Book.query.count(), 0)

    def test_client_normalized_key_is_ignored(self):
        self._login(self.teacher)
        response = self._create(
            title='어린 왕자',
            normalized_key='client-forged',
            is_recommended=True,
            is_challenge_eligible=True,
            ai_difficulty_low=9,
        )
        book = Book.query.one()
        self.assertEqual(book.normalized_key, normalize_book_title('어린 왕자'))
        self.assertNotEqual(book.normalized_key, 'client-forged')
        self.assertFalse(book.is_recommended)
        self.assertFalse(book.is_challenge_eligible)
        self.assertIsNone(book.ai_difficulty_low)
        self.assertEqual(response.status_code, 201)

    def test_search_matches_punctuation_variants(self):
        self._login(self.teacher)
        self._create(title='어린 왕자', author='생텍쥐페리')
        response = self.client.get('/api/books?q=어린왕자')
        self.assertEqual(response.status_code, 200)
        books = response.get_json()['books']
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0]['title'], '어린 왕자')

        hyphen = self.client.get('/api/books?q=어린-왕자')
        bang = self.client.get('/api/books?q=어린 왕자!')
        self.assertEqual(len(hyphen.get_json()['books']), 1)
        self.assertEqual(len(bang.get_json()['books']), 1)

    def test_same_normalized_key_allows_multiple_rows(self):
        self._login(self.teacher)
        first = self._create(title='어린 왕자', author='생텍쥐페리')
        second = self._create(title='어린왕자', author='다른 번역/입력')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(Book.query.count(), 2)
        keys = {book.normalized_key for book in Book.query.all()}
        self.assertEqual(keys, {normalize_book_title('어린 왕자')})
        similar = second.get_json()['similar_books']
        self.assertEqual(len(similar), 1)
        self.assertEqual(similar[0]['author'], '생텍쥐페리')

    def test_search_returns_title_and_author_for_duplicates(self):
        self._login(self.teacher)
        self._create(title='어린 왕자', author='생텍쥐페리')
        self._create(title='어린왕자', author='다른 번역/입력')
        books = self.client.get('/api/books?q=어린').get_json()['books']
        self.assertEqual(len(books), 2)
        authors = {book['author'] for book in books}
        self.assertEqual(authors, {'생텍쥐페리', '다른 번역/입력'})
        for book in books:
            self.assertIn('id', book)
            self.assertIn('title', book)
            self.assertIn('author', book)

    def test_inactive_books_are_excluded_from_search(self):
        self._login(self.teacher)
        created = self._create(title='숨긴 책', author='작가').get_json()['book']
        book = Book.query.get(created['id'])
        book.is_active = False
        db.session.commit()
        books = self.client.get('/api/books?q=숨긴').get_json()['books']
        self.assertEqual(books, [])

    def test_empty_query_does_not_dump_all_books(self):
        self._login(self.teacher)
        self._create(title='어린 왕자')
        self._create(title='마당을 나온 암탉')
        empty = self.client.get('/api/books?q=')
        blank = self.client.get('/api/books?q=%20%20')
        missing = self.client.get('/api/books')
        self.assertEqual(empty.get_json()['books'], [])
        self.assertEqual(blank.get_json()['books'], [])
        self.assertEqual(missing.get_json()['books'], [])
        self.assertEqual(Book.query.count(), 2)

    def test_teacher_can_create_book(self):
        self._login(self.teacher_id)
        self.assertEqual(self._create(title='교사가 등록').status_code, 201)
        self.assertEqual(Book.query.filter_by(title='교사가 등록').count(), 1)

    def test_viewer_cannot_create_book(self):
        self._login(self.viewer_id)
        before = Book.query.count()
        response = self._create(title='열람계정이 등록하면 안 됨')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/viewer', response.headers.get('Location', ''))
        self.assertEqual(Book.query.count(), before)

    def test_viewer_can_search_books(self):
        db.session.add(Book(
            title='교사가 등록',
            author=None,
            normalized_key=normalize_book_title('교사가 등록'),
        ))
        db.session.commit()
        self._login(self.viewer_id)
        search = self.client.get('/api/books?q=교사')
        self.assertEqual(search.status_code, 200)
        self.assertEqual(len(search.get_json()['books']), 1)
        self.assertEqual(search.get_json()['books'][0]['title'], '교사가 등록')

    def test_backup_and_restore_roundtrip_keeps_books(self):
        self._login(self.teacher)
        self._create(title='어린 왕자', author='생텍쥐페리')
        backup_data, error = get_backup_data()
        self.assertIsNone(error)
        self.assertEqual(backup_data['backup_metadata']['records_count']['books'], 1)
        self.assertEqual(backup_data['books'][0]['title'], '어린 왕자')

        Book.query.delete()
        db.session.commit()
        self.assertEqual(Book.query.count(), 0)

        restored = restore_books_from_backup_data(backup_data)
        self.assertEqual(restored, 1)
        book = Book.query.one()
        self.assertEqual(book.title, '어린 왕자')
        self.assertEqual(book.author, '생텍쥐페리')

    def test_book_create_does_not_touch_daily_points(self):
        child = Child(name='포인트아동', grade=3, viewer_slug='cccccccccccccccccccccccc')
        db.session.add(child)
        db.session.commit()
        row = DailyPoints(
            child_id=child.id,
            date=__import__('datetime').datetime.utcnow().date(),
            korean_points=200,
            total_points=200,
            created_by=self.teacher.id,
        )
        db.session.add(row)
        db.session.commit()

        self._login(self.teacher)
        self._create(title='별책')
        self.assertEqual(DailyPoints.query.count(), 1)
        self.assertEqual(DailyPoints.query.one().korean_points, 200)


if __name__ == '__main__':
    unittest.main()
