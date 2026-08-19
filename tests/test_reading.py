"""Step 2: ChildReading / ReadingDay 원장, viewer 본인확인, 일반독서 100/0 정책."""
from __future__ import annotations

import json
import unittest
from datetime import date, datetime, timedelta

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, PointsHistory, User, get_backup_data  # noqa: E402
from feature_models import (  # noqa: E402
    Book,
    ChildReading,
    ReadingDay,
    STATUS_ABANDONED,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
)
from features.books.restore import restore_books_from_backup_data  # noqa: E402
from features.reading.policy import activity_today, now_utc  # noqa: E402
from features.reading.restore import restore_readings_from_backup_data  # noqa: E402
from features.reading.service import (  # noqa: E402
    ReadingError,
    abandon_current,
    get_in_progress,
    reading_days_for_child_on,
    save_today,
    start_book,
)
from features.reading.session import (  # noqa: E402
    SESSION_CHILD_ID,
    SESSION_CHILD_SLUG,
    SESSION_VERIFIED_AT,
)


PRE_POLICY_DATE = date(2026, 7, 15)


def _utc_today():
    return datetime.utcnow().date()


class ReadingLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()

        self.teacher = User(
            username='reading_teacher',
            name='독서교사',
            role='돌봄선생님',
            email='reading-teacher@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='reading_viewer',
            name='독서열람',
            role='학생열람',
            email='studentview-reading@example.test',
            password_hash='',
        )
        self.child_a = Child(name='김철수', grade=3, viewer_slug='aaaaaaaaaaaaaaaaaaaaaaaa')
        self.child_b = Child(name='이영희', grade=4, viewer_slug='bbbbbbbbbbbbbbbbbbbbbbbb')
        db.session.add_all([self.teacher, self.viewer, self.child_a, self.child_b])
        db.session.commit()
        self.teacher_id = self.teacher.id
        self.viewer_id = self.viewer.id
        self.child_a_id = self.child_a.id
        self.child_b_id = self.child_b.id
        self.slug_a = self.child_a.viewer_slug
        self.slug_b = self.child_b.viewer_slug
        self.client = app.test_client()

        self.book = Book(
            title='어린 왕자',
            author='생텍쥐페리',
            normalized_key='어린왕자',
            is_active=True,
        )
        db.session.add(self.book)
        db.session.commit()
        self.book_id = self.book.id
        self.today = activity_today()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user_id):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True

    def _verify(self, child_id, slug, verified_at=None):
        with self.client.session_transaction() as sess:
            sess[SESSION_CHILD_ID] = int(child_id)
            sess[SESSION_CHILD_SLUG] = slug
            sess[SESSION_VERIFIED_AT] = (verified_at or now_utc()).isoformat()

    def _start(self, child_id, user_id, actor='child', activity_date=None, **kwargs):
        return start_book(
            child_id,
            user_id,
            actor,
            activity_date=activity_date or self.today,
            book_id=kwargs.get('book_id', self.book_id),
            title=kwargs.get('title'),
            author=kwargs.get('author'),
            review_text=kwargs.get('review_text'),
            allow_create_book=kwargs.get('allow_create_book', False),
        )

    def _points_form(self, **overrides):
        data = {
            'date': self.today.isoformat(),
            'korean_points': '0',
            'math_points': '0',
            'ssen_points': '0',
            'reading_points': '0',
            'piano_points': '0',
            'english_points': '0',
            'advanced_math_points': '0',
            'writing_points': '0',
            'manual_entries': '[]',
        }
        data.update(overrides)
        return data

    def test_01_child_reading_create(self):
        reading, day = self._start(self.child_a_id, self.viewer_id, review_text='재미있어요')
        self.assertEqual(reading.status, STATUS_IN_PROGRESS)
        self.assertEqual(reading.started_on, self.today)
        self.assertEqual(reading.program_type, 'general')
        self.assertEqual(reading.policy_version, 'general_v2')
        self.assertEqual(day.date, self.today)
        self.assertEqual(day.review_text, '재미있어요')

    def test_02_first_reading_day_create(self):
        self._start(self.child_a_id, self.viewer_id)
        self.assertEqual(ReadingDay.query.count(), 1)

    def test_03_multiple_days_same_book(self):
        reading, _ = self._start(self.child_a_id, self.viewer_id, activity_date=self.today)
        day2_date = self.today + timedelta(days=1)
        save_today(self.child_a_id, self.viewer_id, 'child', activity_date=day2_date, review_text='둘째 날')
        days = ReadingDay.query.filter_by(child_reading_id=reading.id).all()
        self.assertEqual(len(days), 2)
        self.assertEqual(get_in_progress(self.child_a_id).id, reading.id)

    def test_04_duplicate_reading_day_prevented(self):
        reading, _ = self._start(self.child_a_id, self.viewer_id)
        dup = ReadingDay(
            child_reading_id=reading.id,
            date=self.today,
            created_by_user_id=self.viewer_id,
            actor_type='child',
            policy_version='general_v2',
        )
        db.session.add(dup)
        with self.assertRaises(Exception):
            db.session.commit()
        db.session.rollback()

    def test_05_review_text_nullable(self):
        _reading, day = self._start(self.child_a_id, self.viewer_id, review_text='')
        self.assertIsNone(day.review_text)

    def test_06_completed_sets_both_dates(self):
        self._start(self.child_a_id, self.viewer_id)
        reading, _ = save_today(
            self.child_a_id, self.viewer_id, 'child',
            activity_date=self.today, mark_completed=True,
        )
        self.assertEqual(reading.status, STATUS_COMPLETED)
        self.assertEqual(reading.completed_on, self.today)
        self.assertEqual(reading.ended_on, self.today)

    def test_07_abandoned_keeps_completed_on_null(self):
        self._start(self.child_a_id, self.viewer_id)
        reading = abandon_current(self.child_a_id, self.viewer_id, 'child', activity_date=self.today)
        self.assertEqual(reading.status, STATUS_ABANDONED)
        self.assertIsNone(reading.completed_on)
        self.assertEqual(reading.ended_on, self.today)

    def test_08_completed_and_abandoned_are_distinct(self):
        self._start(self.child_a_id, self.viewer_id)
        completed, _ = save_today(
            self.child_a_id, self.viewer_id, 'child', mark_completed=True,
        )
        self.assertNotEqual(completed.status, STATUS_ABANDONED)
        self.assertIsNotNone(completed.completed_on)

        other_book = Book(title='다른 책', author='작가', normalized_key='다른책', is_active=True)
        db.session.add(other_book)
        db.session.commit()
        self._start(
            self.child_b_id, self.viewer_id, book_id=other_book.id,
        )
        abandoned = abandon_current(self.child_b_id, self.viewer_id, 'child')
        self.assertIsNone(abandoned.completed_on)
        self.assertEqual(abandoned.status, STATUS_ABANDONED)

    def test_09_current_in_progress_lookup(self):
        reading, _ = self._start(self.child_a_id, self.viewer_id)
        self.assertEqual(get_in_progress(self.child_a_id).id, reading.id)
        self.assertIsNone(get_in_progress(self.child_b_id))

    def test_10_next_day_reuses_same_child_reading(self):
        reading, _ = self._start(self.child_a_id, self.viewer_id)
        later = self.today + timedelta(days=2)
        updated, day = save_today(self.child_a_id, self.viewer_id, 'child', activity_date=later)
        self.assertEqual(updated.id, reading.id)
        self.assertEqual(day.child_reading_id, reading.id)
        self.assertEqual(ChildReading.query.filter_by(child_id=self.child_a_id).count(), 1)

    def test_11_one_in_progress_per_child(self):
        self._start(self.child_a_id, self.viewer_id)
        other = Book(title='둘째 책', normalized_key='둘째책', is_active=True)
        db.session.add(other)
        db.session.commit()
        with self.assertRaises(ReadingError) as ctx:
            self._start(self.child_a_id, self.viewer_id, book_id=other.id)
        self.assertEqual(ctx.exception.code, 'already_in_progress')

    def test_12_unread_days_are_not_created(self):
        reading, _ = self._start(self.child_a_id, self.viewer_id, activity_date=self.today)
        later = self.today + timedelta(days=2)
        save_today(self.child_a_id, self.viewer_id, 'child', activity_date=later)
        dates = {d.date for d in ReadingDay.query.filter_by(child_reading_id=reading.id).all()}
        self.assertEqual(dates, {self.today, later})
        self.assertNotIn(self.today + timedelta(days=1), dates)

    def test_13_same_day_second_save_updates(self):
        reading, day = self._start(self.child_a_id, self.viewer_id, review_text='첫 감상')
        _, updated = save_today(
            self.child_a_id, self.viewer_id, 'child', review_text='고친 감상',
        )
        self.assertEqual(ReadingDay.query.filter_by(child_reading_id=reading.id).count(), 1)
        self.assertEqual(updated.id, day.id)
        self.assertEqual(ReadingDay.query.get(day.id).review_text, '고친 감상')

    def test_14_second_book_same_day_blocked(self):
        self._start(self.child_a_id, self.viewer_id)
        abandon_current(self.child_a_id, self.viewer_id, 'child')
        other = Book(title='새 책', normalized_key='새책', is_active=True)
        db.session.add(other)
        db.session.commit()
        with self.assertRaises(ReadingError) as ctx:
            self._start(self.child_a_id, self.viewer_id, book_id=other.id)
        self.assertEqual(ctx.exception.code, 'already_logged_today')
        self.assertEqual(len(reading_days_for_child_on(self.child_a_id, self.today)), 1)

    def test_15_viewer_report_get_still_works(self):
        self._login(self.viewer_id)
        response = self.client.get(f'/viewer/report/{self.slug_a}')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('김철수', html)
        self.assertIn('독서 기록하기', html)

    def test_16_confirm_screen_before_editor(self):
        self._login(self.viewer_id)
        confirm = self.client.get(f'/viewer/report/{self.slug_a}/reading/confirm')
        self.assertEqual(confirm.status_code, 200)
        self.assertIn('김철수 아동이 맞나요?', confirm.get_data(as_text=True))

        editor = self.client.get(f'/viewer/report/{self.slug_a}/reading', follow_redirects=False)
        self.assertEqual(editor.status_code, 302)
        self.assertIn('/reading/confirm', editor.headers.get('Location', ''))

    def test_17_confirm_yes_sets_session(self):
        self._login(self.viewer_id)
        response = self.client.post(
            f'/viewer/report/{self.slug_a}/reading/confirm',
            data={'confirm': 'yes'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertEqual(int(sess[SESSION_CHILD_ID]), self.child_a_id)
            self.assertEqual(sess[SESSION_CHILD_SLUG], self.slug_a)
            self.assertTrue(sess.get(SESSION_VERIFIED_AT))

    def test_18_unverified_viewer_post_blocked(self):
        self._login(self.viewer_id)
        response = self.client.post(
            f'/viewer/report/{self.slug_a}/reading/start',
            data={'title': '몰래 만든 책', 'review_text': '안 됨'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/reading/confirm', response.headers.get('Location', ''))
        self.assertEqual(ChildReading.query.count(), 0)

    def test_19_slug_and_session_mismatch_blocked(self):
        self._login(self.viewer_id)
        self._verify(self.child_a_id, self.slug_a)
        response = self.client.post(
            f'/viewer/report/{self.slug_b}/reading/start',
            data={'book_id': str(self.book_id), 'title': '어린 왕자'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ChildReading.query.count(), 0)

    def test_20_other_child_reading_write_blocked(self):
        self._start(self.child_b_id, self.teacher_id, actor='teacher')
        other_reading = get_in_progress(self.child_b_id)
        self._login(self.viewer_id)
        self._verify(self.child_a_id, self.slug_a)
        response = self.client.post(
            f'/viewer/report/{self.slug_a}/reading/save',
            data={
                'child_reading_id': str(other_reading.id),
                'child_id': str(self.child_b_id),
                'review_text': '가로채기',
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(ReadingDay.query.filter_by(review_text='가로채기').first())

    def test_21_ttl_allows_post(self):
        self._login(self.viewer_id)
        self._verify(self.child_a_id, self.slug_a, verified_at=now_utc() - timedelta(minutes=5))
        response = self.client.post(
            f'/viewer/report/{self.slug_a}/reading/start',
            data={'book_id': str(self.book_id), 'review_text': 'TTL 안'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ChildReading.query.filter_by(child_id=self.child_a_id).count(), 1)

    def test_22_ttl_expired_blocks_post(self):
        self._login(self.viewer_id)
        self._verify(self.child_a_id, self.slug_a, verified_at=now_utc() - timedelta(minutes=16))
        response = self.client.post(
            f'/viewer/report/{self.slug_a}/reading/start',
            data={'book_id': str(self.book_id)},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/reading/confirm', response.headers.get('Location', ''))
        self.assertEqual(ChildReading.query.count(), 0)

    def test_23_other_qr_replaces_session_child(self):
        self._login(self.viewer_id)
        self._verify(self.child_a_id, self.slug_a)
        response = self.client.post(
            f'/viewer/report/{self.slug_b}/reading/confirm',
            data={'confirm': 'yes'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertEqual(int(sess[SESSION_CHILD_ID]), self.child_b_id)
            self.assertEqual(sess[SESSION_CHILD_SLUG], self.slug_b)

    def test_24_child_reading_post_allowed(self):
        self._login(self.viewer_id)
        self._verify(self.child_a_id, self.slug_a)
        response = self.client.post(
            f'/viewer/report/{self.slug_a}/reading/start',
            data={'title': '어린 왕자', 'book_id': str(self.book_id), 'review_text': '좋아요'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ChildReading.query.filter_by(child_id=self.child_a_id).count(), 1)

    def test_25_viewer_points_input_post_still_blocked(self):
        self._login(self.viewer_id)
        self._verify(self.child_a_id, self.slug_a)
        response = self.client.post(
            f'/points/input/{self.child_a_id}',
            data=self._points_form(reading_points='100'),
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/viewer', response.headers.get('Location', ''))
        self.assertEqual(DailyPoints.query.count(), 0)

    def test_26_viewer_manual_points_still_blocked(self):
        self._login(self.viewer_id)
        self._verify(self.child_a_id, self.slug_a)
        response = self.client.post(
            '/api/manual-points',
            data=json.dumps({
                'child_id': self.child_a_id,
                'subject': '차단',
                'points': 50,
                'reason': 'reading-step2',
                'date': self.today.isoformat(),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/viewer', response.headers.get('Location', ''))
        self.assertEqual(PointsHistory.query.count(), 0)

    def test_27_teacher_proxy_without_qr_ttl(self):
        self._login(self.teacher_id)
        response = self.client.post(
            f'/children/{self.child_a_id}/reading/start',
            data={'book_id': str(self.book_id), 'review_text': '교사 대리', 'date': self.today.isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        reading = ChildReading.query.filter_by(child_id=self.child_a_id).one()
        self.assertEqual(reading.actor_type, 'teacher')
        self.assertEqual(reading.created_by_user_id, self.teacher_id)

    def test_28_existing_book_search_used(self):
        self._login(self.viewer_id)
        response = self.client.get('/api/books?q=어린')
        self.assertEqual(response.status_code, 200)
        titles = [item['title'] for item in response.get_json()['books']]
        self.assertIn('어린 왕자', titles)

    def test_29_verified_child_can_select_existing_book(self):
        self._login(self.viewer_id)
        self._verify(self.child_a_id, self.slug_a)
        before = Book.query.count()
        self.client.post(
            f'/viewer/report/{self.slug_a}/reading/start',
            data={'book_id': str(self.book_id), 'title': '어린 왕자', 'author': '생텍쥐페리'},
        )
        self.assertEqual(Book.query.count(), before)
        self.assertEqual(ChildReading.query.one().book_id, self.book_id)

    def test_30_verified_child_can_create_book_in_reading_context(self):
        self._login(self.viewer_id)
        self._verify(self.child_a_id, self.slug_a)
        self.client.post(
            f'/viewer/report/{self.slug_a}/reading/start',
            data={'title': '새로 쓴 동화', 'author': '아동작가', 'review_text': '새 책'},
        )
        created = Book.query.filter_by(title='새로 쓴 동화').one()
        self.assertEqual(created.author, '아동작가')
        self.assertEqual(ChildReading.query.one().book_id, created.id)

    def test_31_unverified_viewer_cannot_create_book(self):
        self._login(self.viewer_id)
        api = self.client.post(
            '/api/books',
            data=json.dumps({'title': 'API로 생성 금지', 'author': 'X'}),
            content_type='application/json',
            follow_redirects=False,
        )
        self.assertEqual(api.status_code, 302)
        self.assertIn('/viewer', api.headers.get('Location', ''))
        self.assertIsNone(Book.query.filter_by(title='API로 생성 금지').first())

        start = self.client.post(
            f'/viewer/report/{self.slug_a}/reading/start',
            data={'title': '컨텍스트 없는 책'},
            follow_redirects=False,
        )
        self.assertEqual(start.status_code, 302)
        self.assertIn('/reading/confirm', start.headers.get('Location', ''))
        self.assertIsNone(Book.query.filter_by(title='컨텍스트 없는 책').first())

    def test_32_33_34_reading_does_not_touch_points(self):
        self._start(self.child_a_id, self.viewer_id, review_text='포인트 없음')
        child = Child.query.get(self.child_a_id)
        self.assertEqual(DailyPoints.query.count(), 0)
        self.assertEqual(child.cumulative_points or 0, 0)
        self.assertEqual(PointsHistory.query.count(), 0)

    def test_35_teacher_can_award_100_without_digital_record(self):
        self._login(self.teacher_id)
        response = self.client.post(
            f'/points/input/{self.child_a_id}',
            data=self._points_form(reading_points='100'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ReadingDay.query.count(), 0)
        row = DailyPoints.query.filter_by(child_id=self.child_a_id).one()
        self.assertEqual(row.reading_points, 100)

    def test_36_v2_allows_100(self):
        self._login(self.teacher_id)
        self.client.post(
            f'/points/input/{self.child_a_id}',
            data=self._points_form(reading_points='100'),
        )
        self.assertEqual(DailyPoints.query.one().reading_points, 100)

    def test_37_v2_allows_0(self):
        self._login(self.teacher_id)
        self.client.post(
            f'/points/input/{self.child_a_id}',
            data=self._points_form(reading_points='0', korean_points='200'),
        )
        self.assertEqual(DailyPoints.query.one().reading_points, 0)

    def test_38_v2_rejects_200(self):
        self._login(self.teacher_id)
        response = self.client.post(
            f'/points/input/{self.child_a_id}',
            data=self._points_form(reading_points='200'),
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DailyPoints.query.count(), 0)

    def test_39_pre_policy_200_preserved_on_edit(self):
        row = DailyPoints(
            child_id=self.child_a_id,
            date=PRE_POLICY_DATE,
            korean_points=0,
            reading_points=200,
            total_points=200,
            created_by=self.teacher_id,
        )
        db.session.add(row)
        db.session.commit()
        self._login(self.teacher_id)
        self.client.post(
            f'/points/input/{self.child_a_id}',
            data=self._points_form(
                date=PRE_POLICY_DATE.isoformat(),
                korean_points='100',
                reading_points='200',
            ),
        )
        updated = DailyPoints.query.filter_by(child_id=self.child_a_id, date=PRE_POLICY_DATE).one()
        self.assertEqual(updated.reading_points, 200)
        self.assertEqual(updated.korean_points, 100)

    def test_40_past_points_are_not_converted_to_reading_days(self):
        row = DailyPoints(
            child_id=self.child_a_id,
            date=PRE_POLICY_DATE,
            reading_points=200,
            total_points=200,
            created_by=self.teacher_id,
        )
        db.session.add(row)
        db.session.commit()
        self.assertEqual(ReadingDay.query.count(), 0)
        self.assertEqual(ChildReading.query.count(), 0)

    def test_backup_restore_order(self):
        self._start(self.child_a_id, self.viewer_id, review_text='백업 감상')
        backup_data, error = get_backup_data()
        self.assertIsNone(error)
        self.assertEqual(backup_data['backup_metadata']['records_count']['child_readings'], 1)
        self.assertEqual(backup_data['backup_metadata']['records_count']['reading_days'], 1)

        ReadingDay.query.delete()
        ChildReading.query.delete()
        Book.query.delete()
        db.session.commit()

        restore_books_from_backup_data(backup_data)
        restored_readings, restored_days = restore_readings_from_backup_data(backup_data)
        self.assertEqual(restored_readings, 1)
        self.assertEqual(restored_days, 1)
        self.assertEqual(ReadingDay.query.one().review_text, '백업 감상')

    def test_confirm_no_does_not_open_write_context(self):
        self._login(self.viewer_id)
        response = self.client.post(
            f'/viewer/report/{self.slug_a}/reading/confirm',
            data={'confirm': 'no'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get(SESSION_CHILD_ID))

    def test_teacher_editor_get(self):
        self._login(self.teacher_id)
        response = self.client.get(f'/children/{self.child_a_id}/reading')
        self.assertEqual(response.status_code, 200)
        self.assertIn('오늘 읽은 책을 기록해요', response.get_data(as_text=True))

    def test_points_input_shows_digital_status(self):
        self._start(self.child_a_id, self.viewer_id)
        self._login(self.teacher_id)
        response = self.client.get(f'/points/input/{self.child_a_id}')
        html = response.get_data(as_text=True)
        self.assertIn('오늘 디지털 독서기록', html)
        self.assertIn('있음', html)
        self.assertIn('어린 왕자', html)
        self.assertIn('완료 (100점)', html)
        self.assertNotIn('id="reading_200"', html)
        self.assertIn('id="reading_100"', html)


if __name__ == '__main__':
    unittest.main()
