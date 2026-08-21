"""로컬 DEV 활동일 컨트롤. production 및 기본 OFF를 검증한다."""
from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import ExemptionTicket, LearningProgressEntry, LearningSubject  # noqa: E402
from features.books.service import create_book_record, update_recommended_flags  # noqa: E402
from features.dates import (  # noqa: E402
    DEV_ACTIVITY_DATE_SESSION_KEY,
    actual_kst_today,
    is_dev_date_control_enabled,
    is_production_runtime,
    kst_today,
)
from features.exemption.policy import next_issue_on, ticket_expires_on  # noqa: E402
from features.exemption.service import (  # noqa: E402
    child_exemption_snapshot,
    issue_exemption_ticket,
    set_reward_mode,
)
from features.progress.service import ensure_default_subjects, save_progress_entry  # noqa: E402
from features.reading.policy import now_utc  # noqa: E402
from features.reading.service import complete_current, start_book  # noqa: E402
from features.reading.session import (  # noqa: E402
    SESSION_CHILD_ID,
    SESSION_VERIFIED_AT,
    write_block_reason,
)
from features.subjects import CURRENT_SUBJECTS, EXEMPTION_SUBJECT_KEYS, PROGRESS_SUBJECT_KEYS  # noqa: E402


class DevDateAndSubjectRegistryTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='devdate_teacher',
            name='날짜교사',
            role='돌봄선생님',
            email='devdate-teacher@example.test',
            password_hash='',
        )
        db.session.add(self.teacher)
        db.session.commit()
        self.teacher_id = self.teacher.id
        self.client = app.test_client()
        self.child = Child(name='날짜아동', grade=5, viewer_slug='dddddddddddddddddddddddd')
        db.session.add(self.child)
        db.session.commit()
        self.child_id = self.child.id
        ensure_default_subjects()
        self._env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop('CLC_DEV_DATE_CONTROL', None)
        os.environ.pop('FLASK_ENV', None)

    def tearDown(self):
        os.environ.pop('CLC_DEV_DATE_CONTROL', None)
        os.environ.pop('FLASK_ENV', None)
        self._env_patch.stop()
        db.session.remove()
        self.ctx.pop()

    def _login(self, client=None):
        client = client or self.client
        with client.session_transaction() as sess:
            sess['_user_id'] = str(self.teacher_id)
            sess['_fresh'] = True
        return client

    def _complete_exemption(self, activity_date):
        book, _ = create_book_record(f'책{activity_date.isoformat()}', '작가')
        update_recommended_flags(book, is_recommended=True, grade_band='4-6')
        reading, _ = start_book(
            self.child_id,
            self.teacher_id,
            'teacher',
            activity_date=activity_date,
            book_id=book.id,
        )
        set_reward_mode(reading, 'exemption', self.teacher)
        complete_current(self.child_id, self.teacher_id, 'teacher', activity_date=activity_date)
        return reading

    def test_registry_matches_daily_points_and_fixed_keys(self):
        cols = {column.name for column in DailyPoints.__table__.columns}
        self.assertEqual(
            [CURRENT_SUBJECTS[key]['daily_points_field'] for key in CURRENT_SUBJECTS],
            [
                'korean_points',
                'math_points',
                'ssen_points',
                'reading_points',
                'piano_points',
                'english_points',
                'advanced_math_points',
                'writing_points',
            ],
        )
        self.assertTrue({item['daily_points_field'] for item in CURRENT_SUBJECTS.values()} <= cols)
        self.assertEqual(PROGRESS_SUBJECT_KEYS, ('korean', 'math', 'ssen'))
        self.assertEqual(EXEMPTION_SUBJECT_KEYS, ('korean', 'math', 'ssen', 'reading'))

    def test_control_off_by_default_no_ui_or_post(self):
        self.assertFalse(is_dev_date_control_enabled())
        self._login()
        html = self.client.get('/settings').get_data(as_text=True)
        self.assertNotIn('dev-date-control', html)
        self.assertNotIn('테스트 날짜', html)
        denied = self.client.post(
            '/dev/activity-date',
            data={'action': 'set', 'date': '2026-08-20'},
            follow_redirects=False,
        )
        self.assertEqual(denied.status_code, 404)

    def test_debug_true_is_not_enough(self):
        app.config['DEBUG'] = True
        self.assertFalse(is_dev_date_control_enabled())
        self._login()
        html = self.client.get('/settings').get_data(as_text=True)
        self.assertNotIn('dev-date-control', html)

    def test_enabled_local_shows_ui(self):
        os.environ['CLC_DEV_DATE_CONTROL'] = '1'
        self.assertTrue(is_dev_date_control_enabled())
        self._login()
        html = self.client.get('/settings').get_data(as_text=True)
        self.assertIn('dev-date-control', html)
        self.assertIn('DEV', html)
        self.assertNotIn('테스트 날짜', html)

    def test_production_flask_env_blocks_even_with_flag(self):
        os.environ['CLC_DEV_DATE_CONTROL'] = '1'
        os.environ['FLASK_ENV'] = 'production'
        self.assertTrue(is_production_runtime())
        self.assertFalse(is_dev_date_control_enabled())
        self._login()
        html = self.client.get('/settings').get_data(as_text=True)
        self.assertNotIn('dev-date-control', html)
        denied = self.client.post(
            '/dev/activity-date',
            data={'action': 'set', 'date': '2026-08-20'},
            follow_redirects=False,
        )
        self.assertEqual(denied.status_code, 404)

    def test_postgres_url_blocks_even_with_flag(self):
        os.environ['CLC_DEV_DATE_CONTROL'] = '1'
        os.environ['DATABASE_URL'] = 'postgresql://example.invalid/db'
        try:
            self.assertTrue(is_production_runtime())
            self.assertFalse(is_dev_date_control_enabled())
        finally:
            os.environ['DATABASE_URL'] = ''

    def test_kst_today_without_override_is_actual(self):
        self.assertEqual(kst_today(), actual_kst_today())
        os.environ['CLC_DEV_DATE_CONTROL'] = '1'
        self.assertEqual(kst_today(), actual_kst_today())

    def test_session_override_changes_kst_today(self):
        os.environ['CLC_DEV_DATE_CONTROL'] = '1'
        with app.test_request_context('/'):
            from flask import session
            session[DEV_ACTIVITY_DATE_SESSION_KEY] = '2026-08-20'
            self.assertEqual(kst_today(), date(2026, 8, 20))

    def test_http_set_next_and_today(self):
        os.environ['CLC_DEV_DATE_CONTROL'] = '1'
        self._login()
        set_resp = self.client.post(
            '/dev/activity-date',
            data={'action': 'set', 'date': '2026-08-20', 'next': '/settings'},
            follow_redirects=False,
        )
        self.assertEqual(set_resp.status_code, 302)
        html = self.client.get('/settings').get_data(as_text=True)
        self.assertIn('is-overridden', html)
        self.assertIn('테스트 날짜 2026-08-20', html)
        with self.client as client:
            client.get('/settings')
            self.assertEqual(kst_today(), date(2026, 8, 20))
        next_resp = self.client.post(
            '/dev/activity-date',
            data={'action': 'next', 'next': '/settings'},
            follow_redirects=False,
        )
        self.assertEqual(next_resp.status_code, 302)
        html = self.client.get('/settings').get_data(as_text=True)
        self.assertIn('테스트 날짜 2026-08-21', html)
        today_resp = self.client.post(
            '/dev/activity-date',
            data={'action': 'today', 'next': '/settings'},
            follow_redirects=False,
        )
        self.assertEqual(today_resp.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertNotIn(DEV_ACTIVITY_DATE_SESSION_KEY, sess)
        html = self.client.get('/settings').get_data(as_text=True)
        self.assertNotIn('is-overridden', html)
        self.assertNotIn('테스트 날짜 2026-08-21', html)

    def test_invalid_date_rejected(self):
        os.environ['CLC_DEV_DATE_CONTROL'] = '1'
        self._login()
        resp = self.client.post(
            '/dev/activity-date',
            data={'action': 'set', 'date': '2026-13-99', 'next': '/settings'},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('날짜 형식이 올바르지 않습니다', resp.get_data(as_text=True))
        with self.client.session_transaction() as sess:
            self.assertNotIn(DEV_ACTIVITY_DATE_SESSION_KEY, sess)

    def test_two_clients_have_independent_dates(self):
        os.environ['CLC_DEV_DATE_CONTROL'] = '1'
        first = app.test_client()
        second = app.test_client()
        self._login(first)
        self._login(second)
        first.post(
            '/dev/activity-date',
            data={'action': 'set', 'date': '2026-08-20', 'next': '/settings'},
        )
        second.post(
            '/dev/activity-date',
            data={'action': 'set', 'date': '2026-09-03', 'next': '/settings'},
        )
        self.assertIn('테스트 날짜 2026-08-20', first.get('/settings').get_data(as_text=True))
        self.assertIn('테스트 날짜 2026-09-03', second.get('/settings').get_data(as_text=True))

    def test_created_at_ignores_dev_date(self):
        os.environ['CLC_DEV_DATE_CONTROL'] = '1'
        before = datetime.utcnow() - timedelta(seconds=5)
        with app.test_request_context('/'):
            from flask import session
            session[DEV_ACTIVITY_DATE_SESSION_KEY] = '2026-08-20'
            self._complete_exemption(kst_today())
            ticket = issue_exemption_ticket(self.child_id, self.teacher)
            self.assertEqual(ticket.issued_on, date(2026, 8, 20))
            self.assertEqual(ticket.expires_on, date(2026, 9, 2))
            self.assertGreaterEqual(ticket.created_at, before)
            self.assertLessEqual(ticket.created_at, datetime.utcnow() + timedelta(seconds=5))
            math = LearningSubject.query.filter_by(key='math').one()
            entry, _ = save_progress_entry(
                child_id=self.child_id,
                learning_subject_id=math.id,
                textbook_title='진도교재',
                page=11,
                recorded_on=kst_today(),
                created_by_user_id=self.teacher_id,
            )
            self.assertEqual(entry.recorded_on, date(2026, 8, 20))
            self.assertGreaterEqual(entry.created_at, before)

    def test_viewer_ttl_ignores_dev_date(self):
        os.environ['CLC_DEV_DATE_CONTROL'] = '1'
        child = Child.query.get(self.child_id)
        with app.test_request_context('/'):
            from flask import session
            session[DEV_ACTIVITY_DATE_SESSION_KEY] = '2099-12-31'
            session[SESSION_CHILD_ID] = self.child_id
            session[SESSION_VERIFIED_AT] = (now_utc() - timedelta(minutes=1)).isoformat()
            self.assertEqual(kst_today(), date(2099, 12, 31))
            self.assertIsNone(write_block_reason(session, child))
            session[SESSION_VERIFIED_AT] = (now_utc() - timedelta(minutes=20)).isoformat()
            self.assertEqual(write_block_reason(session, child), 'ttl_expired')

    def test_ticket_expiry_and_cooldown_via_kst_today(self):
        os.environ['CLC_DEV_DATE_CONTROL'] = '1'
        with app.test_request_context('/'):
            from flask import session
            session[DEV_ACTIVITY_DATE_SESSION_KEY] = '2026-08-20'
            self._complete_exemption(kst_today())
            ticket = issue_exemption_ticket(self.child_id, self.teacher)
            self.assertEqual(ticket.issued_on, date(2026, 8, 20))
            self.assertEqual(ticket.expires_on, ticket_expires_on(date(2026, 8, 20)))
            self.assertEqual(ticket.expires_on, date(2026, 9, 2))
            session[DEV_ACTIVITY_DATE_SESSION_KEY] = '2026-09-03'
            snap = child_exemption_snapshot(self.child_id)
            self.assertEqual(snap['today'], date(2026, 9, 3))
            self.assertEqual(next_issue_on(ticket.issued_on), date(2026, 9, 3))
            self.assertFalse(snap['cooldown_blocks'])
            self.assertIsNone(snap['held_ticket'])
            self.assertEqual(snap['history'][0]['effective_status'], 'expired')


if __name__ == '__main__':
    unittest.main()
