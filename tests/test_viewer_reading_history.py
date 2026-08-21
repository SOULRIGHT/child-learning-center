"""Step 8: 학생열람 자기 독서기록 읽기 전용 조회."""
from __future__ import annotations

import os
import re
import unittest
from datetime import timedelta
from unittest import mock

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import ChildReading, ReadingDay, STATUS_ABANDONED  # noqa: E402
from features.books.service import create_book_record, register_challenge_book, update_recommended_flags  # noqa: E402
from features.dates import kst_today  # noqa: E402
from features.reading.classify import classify_program_type  # noqa: E402
from features.reading.policy import now_utc  # noqa: E402
from features.reading.service import (  # noqa: E402
    ReadingError,
    abandon_current,
    history_items_for_child,
    save_today,
    start_book,
)
from features.reading.session import (  # noqa: E402
    SESSION_CHILD_ID,
    SESSION_CHILD_SLUG,
    SESSION_VERIFIED_AT,
    read_block_reason,
    write_block_reason,
)


HIDDEN_ADMIN_MARKERS = (
    '교사가 대신 기록',
    '포인트 입력으로',
    '아동 상세',
    '독서 보상',
    '포인트 승인',
    '면제권 발급',
    '면제권 사용',
    '면제권 취소',
    'policy_version',
    'created_by_user_id',
    'revoked_by_user_id',
    'ExemptionTicketSource',
    'challenge_start',
    'recommended_complete',
    'manual_history',
)


class ViewerReadingHistoryTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='hist_teacher',
            name='기록교사',
            role='돌봄선생님',
            email='hist-teacher@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='hist_viewer',
            name='기록열람',
            role='학생열람',
            email='studentview-hist@example.test',
            password_hash='',
        )
        db.session.add_all([self.teacher, self.viewer])
        db.session.commit()
        self.today = kst_today()
        self.client = app.test_client()
        self._slug_n = 0
        self.book_n = 0
        self.child_a = self._child('아동A', 5)
        self.child_b = self._child('아동B', 3)

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _child(self, name, grade):
        self._slug_n += 1
        child = Child(name=name, grade=grade, viewer_slug=f'{self._slug_n:024x}')
        db.session.add(child)
        db.session.commit()
        return child

    def _general_book(self, title=None, author='일반작가'):
        self.book_n += 1
        book, _ = create_book_record(title or f'일반{self.book_n}', author)
        return book

    def _rec_book(self, title=None):
        self.book_n += 1
        book, _ = create_book_record(title or f'추천{self.book_n}', '추천작가')
        update_recommended_flags(book, is_recommended=True, grade_band='4-6')
        return book

    def _challenge_book(self, title=None):
        self.book_n += 1
        book, _ = register_challenge_book(title or f'도전{self.book_n}', '도전작가')
        return book

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def _verify(self, child, *, minutes_ago=0):
        verified_at = now_utc() - timedelta(minutes=minutes_ago)
        with self.client.session_transaction() as sess:
            sess[SESSION_CHILD_ID] = int(child.id)
            sess[SESSION_CHILD_SLUG] = child.viewer_slug
            sess[SESSION_VERIFIED_AT] = verified_at.isoformat()

    def _start(self, child, book, activity_date=None, review_text=None, actor='teacher'):
        user_id = self.teacher.id if actor == 'teacher' else self.viewer.id
        return start_book(
            child.id,
            user_id,
            actor,
            activity_date=activity_date or self.today,
            book_id=book.id,
            review_text=review_text,
        )

    def _history_url(self, child):
        return f'/viewer/report/{child.viewer_slug}/reading/history'

    def _assert_no_admin_ui(self, html):
        for marker in HIDDEN_ADMIN_MARKERS:
            self.assertNotIn(marker, html)

    def test_teacher_can_view_child_reading_history(self):
        book = self._rec_book('교사열람책')
        self._start(self.child_a, book, review_text='첫날 감상')
        self._login(self.teacher)
        resp = self.client.get(f'/children/{self.child_a.id}/reading/history')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('교사열람책', html)
        self.assertIn('추천', html)
        self.assertIn('첫날 감상', html)
        self.assertIn('교사가 대신 기록', html)

    def test_verified_viewer_can_read_own_history(self):
        book = self._general_book('내책')
        self._start(self.child_a, book, review_text='재미있었다')
        self._login(self.viewer)
        self._verify(self.child_a)
        resp = self.client.get(self._history_url(self.child_a))
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('내 독서 기록', html)
        self.assertIn('내책', html)
        self.assertIn('재미있었다', html)
        self.assertIn('내 독서 기록', html)

    def test_viewer_cannot_read_other_child_via_teacher_url(self):
        secret = self._general_book('비밀책B')
        self._start(self.child_b, secret, review_text='B만의 감상')
        self._login(self.viewer)
        self._verify(self.child_a)
        resp = self.client.get(
            f'/children/{self.child_b.id}/reading/history',
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/viewer', resp.headers.get('Location', ''))
        self.assertNotIn('비밀책B', resp.get_data(as_text=True))

    def test_viewer_a_cannot_read_child_b_history_by_slug(self):
        secret = self._general_book('B전용책')
        self._start(self.child_b, secret, review_text='다른 아동 감상')
        self._login(self.viewer)
        self._verify(self.child_a)
        resp = self.client.get(self._history_url(self.child_b), follow_redirects=False)
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn('B전용책', resp.get_data(as_text=True))
        self.assertNotIn('다른 아동 감상', resp.get_data(as_text=True))

    def test_unknown_viewer_slug_is_rejected(self):
        self._login(self.viewer)
        self._verify(self.child_a)
        missing = 'ffffffffffffffffffffffff'
        resp = self.client.get(
            f'/viewer/report/{missing}/reading/history',
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/viewer', resp.headers.get('Location', ''))

    def test_unauthenticated_history_redirects_to_login(self):
        resp = self.client.get(self._history_url(self.child_a), follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers.get('Location', ''))

        teacher_resp = self.client.get(
            f'/children/{self.child_a.id}/reading/history',
            follow_redirects=False,
        )
        self.assertEqual(teacher_resp.status_code, 302)
        self.assertIn('/login', teacher_resp.headers.get('Location', ''))

    def test_viewer_history_hides_admin_actions(self):
        book = self._rec_book('보상책')
        self._start(self.child_a, book, review_text='감상만')
        self._login(self.viewer)
        self._verify(self.child_a)
        html = self.client.get(self._history_url(self.child_a)).get_data(as_text=True)
        self._assert_no_admin_ui(html)
        self.assertNotIn('reward/approve', html)
        self.assertNotIn('exemption/issue', html)
        self.assertIn('보상책', html)
        self.assertIn('추천', html)

    def test_viewer_cannot_gain_admin_via_post(self):
        book = self._rec_book('우회책')
        reading, _ = self._start(self.child_a, book)
        self._login(self.viewer)
        self._verify(self.child_a)

        approve = self.client.post(
            f'/children/{self.child_a.id}/reading/reward/approve',
            data={'child_reading_id': str(reading.id), 'event_type': 'recommended_start'},
            follow_redirects=False,
        )
        self.assertEqual(approve.status_code, 302)
        self.assertIn('/viewer', approve.headers.get('Location', ''))

        issue = self.client.post(
            f'/children/{self.child_a.id}/exemption/issue',
            follow_redirects=False,
        )
        self.assertEqual(issue.status_code, 302)
        self.assertIn('/viewer', issue.headers.get('Location', ''))

        mode = self.client.post(
            f'/children/{self.child_a.id}/reading/reward-mode',
            data={'child_reading_id': str(reading.id), 'reward_mode': 'points'},
            follow_redirects=False,
        )
        self.assertEqual(mode.status_code, 302)
        self.assertIn('/viewer', mode.headers.get('Location', ''))

        self.assertEqual(ChildReading.query.get(reading.id).reward_mode, None)

    def test_displays_in_progress_completed_abandoned(self):
        progress_book = self._general_book('읽는중책')
        done_book = self._general_book('완독책')
        stop_book = self._general_book('중단책')
        first_day = self.today - timedelta(days=3)
        mid_day = self.today - timedelta(days=2)
        stop_day = self.today - timedelta(days=1)

        self._start(self.child_a, done_book, activity_date=first_day, review_text='완독 시작')
        save_today(
            self.child_a.id, self.teacher.id, 'teacher',
            activity_date=mid_day, review_text='다 읽었다', mark_completed=True,
        )
        stop, _ = self._start(self.child_a, stop_book, activity_date=stop_day, review_text='그만둠')
        abandon_current(self.child_a.id, self.teacher.id, 'teacher', activity_date=stop_day)
        self.assertEqual(ChildReading.query.get(stop.id).status, STATUS_ABANDONED)
        self._start(self.child_a, progress_book, activity_date=self.today, review_text='계속 읽는 중')

        self._login(self.viewer)
        self._verify(self.child_a)
        html = self.client.get(self._history_url(self.child_a)).get_data(as_text=True)
        self.assertIn('읽는중책', html)
        self.assertIn('읽는 중', html)
        self.assertIn('완독책', html)
        self.assertIn('완독', html)
        self.assertIn('중단책', html)
        self.assertIn('중단', html)
        self.assertNotIn('in_progress', html)
        self.assertNotIn('completed', html)
        self.assertNotIn('abandoned', html)

    def test_program_type_badges_and_general(self):
        rec = self._rec_book('추천표시책')
        challenge = self._challenge_book('도전표시책')
        general = self._general_book('일반표시책', author='김일반')
        rec_day = self.today - timedelta(days=2)
        ch_day = self.today - timedelta(days=1)
        self._start(self.child_a, rec, activity_date=rec_day, review_text='추천 감상')
        abandon_current(self.child_a.id, self.teacher.id, 'teacher', activity_date=rec_day)
        self._start(self.child_a, challenge, activity_date=ch_day, review_text='도전 감상')
        abandon_current(self.child_a.id, self.teacher.id, 'teacher', activity_date=ch_day)
        self._start(self.child_a, general, activity_date=self.today, review_text='일반 감상')

        self._login(self.viewer)
        self._verify(self.child_a)
        html = self.client.get(self._history_url(self.child_a)).get_data(as_text=True)
        self.assertIn('추천표시책', html)
        self.assertIn('badge bg-success">추천', html)
        self.assertIn('도전표시책', html)
        self.assertIn('badge bg-warning text-dark">도전', html)
        self.assertIn('일반표시책', html)
        self.assertIn('김일반', html)
        self.assertEqual(html.count('badge bg-success">추천'), 1)
        self.assertEqual(html.count('badge bg-warning text-dark">도전'), 1)

    def test_multiple_reading_days_and_no_other_child_days(self):
        book = self._general_book('여러날책')
        day1 = self.today - timedelta(days=1)
        self._start(self.child_a, book, activity_date=day1, review_text='첫째 날 재미있었다.')
        save_today(
            self.child_a.id, self.teacher.id, 'teacher',
            activity_date=self.today, review_text='주인공이 모험을 떠났다.',
        )
        other_book = self._general_book('B책')
        self._start(self.child_b, other_book, review_text='B아동만의 문장')

        self._login(self.viewer)
        self._verify(self.child_a)
        html = self.client.get(self._history_url(self.child_a)).get_data(as_text=True)
        self.assertIn('첫째 날 재미있었다.', html)
        self.assertIn('주인공이 모험을 떠났다.', html)
        self.assertIn(str(day1), html)
        self.assertIn(str(self.today), html)
        self.assertNotIn('B아동만의 문장', html)
        self.assertNotIn('B책', html)

        items = history_items_for_child(self.child_a.id)
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0]['days']), 2)
        self.assertEqual(items[0]['days'][0].review_text, '첫째 날 재미있었다.')

    def test_incentives_off_still_allows_viewer_history(self):
        book = self._challenge_book('플래그오프책')
        self._start(self.child_a, book, review_text='인센티브 없이도')
        self._login(self.viewer)
        self._verify(self.child_a)
        with mock.patch.dict(os.environ, {'CLC_READING_INCENTIVES_ENABLED': '0'}):
            resp = self.client.get(self._history_url(self.child_a))
            self.assertEqual(resp.status_code, 200)
            html = resp.get_data(as_text=True)
            self.assertIn('플래그오프책', html)
            self.assertIn('인센티브 없이도', html)
            self.assertIn('>도전<', html)
            self._assert_no_admin_ui(html)

    def test_expired_write_ttl_still_allows_history_read(self):
        book = self._general_book('TTL지난책')
        self._start(self.child_a, book, review_text='읽기만')
        self._login(self.viewer)
        self._verify(self.child_a, minutes_ago=20)
        with self.client.session_transaction() as sess:
            self.assertEqual(write_block_reason(sess, self.child_a), 'ttl_expired')
            self.assertIsNone(read_block_reason(sess, self.child_a))
        hist = self.client.get(self._history_url(self.child_a), follow_redirects=False)
        self.assertEqual(hist.status_code, 200)
        self.assertIn('TTL지난책', hist.get_data(as_text=True))
        editor = self.client.get(
            f'/viewer/report/{self.child_a.viewer_slug}/reading',
            follow_redirects=False,
        )
        self.assertEqual(editor.status_code, 302)
        self.assertIn('/reading/confirm', editor.headers.get('Location', ''))

    def test_unverified_history_asks_confirm_then_returns(self):
        book = self._general_book('확인후책')
        self._start(self.child_a, book, review_text='확인 후 봄')
        self._login(self.viewer)
        first = self.client.get(self._history_url(self.child_a), follow_redirects=False)
        self.assertEqual(first.status_code, 302)
        location = first.headers.get('Location', '')
        self.assertIn('/reading/confirm', location)
        self.assertIn('next=history', location)
        confirm = self.client.post(
            f'/viewer/report/{self.child_a.viewer_slug}/reading/confirm?next=history',
            data={'confirm': 'yes', 'next': 'history'},
            follow_redirects=False,
        )
        self.assertEqual(confirm.status_code, 302)
        self.assertIn('/reading/history', confirm.headers.get('Location', ''))
        html = self.client.get(self._history_url(self.child_a)).get_data(as_text=True)
        self.assertIn('확인후책', html)

    def test_teacher_report_and_history_still_render(self):
        self._login(self.teacher)
        report = self.client.get(f'/settings/print/child/{self.child_a.id}')
        self.assertEqual(report.status_code, 200)
        html = report.get_data(as_text=True)
        self.assertIn(self.child_a.name, html)
        self.assertNotIn('내 독서 기록', html)
        history = self.client.get(f'/children/{self.child_a.id}/reading/history')
        self.assertEqual(history.status_code, 200)
        self.assertIn('독서 기록 보기', history.get_data(as_text=True))

    def test_viewer_history_endpoint_is_registered(self):
        endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
        self.assertIn('reading.viewer_history', endpoints)
        with app.test_request_context():
            from flask import url_for
            built = url_for('reading.viewer_history', view_token=self.child_a.viewer_slug)
        self.assertEqual(built, self._history_url(self.child_a))

    def test_teacher_nfc_goes_to_points_input(self):
        self._login(self.teacher)
        redirect_resp = self.client.get(f'/nfc/{self.child_a.id}', follow_redirects=False)
        self.assertEqual(redirect_resp.status_code, 302)
        self.assertIn(f'/points/input/{self.child_a.id}', redirect_resp.headers.get('Location', ''))
        followed = self.client.get(f'/nfc/{self.child_a.id}', follow_redirects=True)
        self.assertEqual(followed.status_code, 200)
        self.assertTrue(followed.request.path.endswith(f'/points/input/{self.child_a.id}'))

    def test_viewer_nfc_renders_own_report_with_history_link(self):
        self._login(self.viewer)
        redirect_resp = self.client.get(f'/nfc/{self.child_a.id}', follow_redirects=False)
        self.assertEqual(redirect_resp.status_code, 302)
        self.assertIn(
            f'/viewer/report/{self.child_a.viewer_slug}',
            redirect_resp.headers.get('Location', ''),
        )
        followed = self.client.get(f'/nfc/{self.child_a.id}', follow_redirects=True)
        self.assertEqual(followed.status_code, 200)
        html = followed.get_data(as_text=True)
        self.assertIn(self.child_a.name, html)
        self.assertIn('내 독서 기록', html)
        match = re.search(r'href="([^"]*reading/history[^"]*)"', html)
        self.assertIsNotNone(match)
        history_href = match.group(1)
        self.assertEqual(history_href, self._history_url(self.child_a))

        self._verify(self.child_a)
        history = self.client.get(history_href)
        self.assertEqual(history.status_code, 200)
        self.assertIn('내 독서 기록', history.get_data(as_text=True))

    def test_report_and_editor_link_to_own_history(self):
        self._login(self.viewer)
        self._verify(self.child_a)
        report = self.client.get(f'/viewer/report/{self.child_a.viewer_slug}').get_data(as_text=True)
        self.assertIn('내 독서 기록', report)
        self.assertIn(self._history_url(self.child_a), report)
        editor = self.client.get(
            f'/viewer/report/{self.child_a.viewer_slug}/reading'
        ).get_data(as_text=True)
        self.assertIn('내 독서 기록', editor)
        self.assertIn(self._history_url(self.child_a), editor)

    def test_viewer_can_still_write_own_reading(self):
        book = self._general_book('작성유지책')
        self._login(self.viewer)
        self._verify(self.child_a)
        start = self.client.post(
            f'/viewer/report/{self.child_a.viewer_slug}/reading/start',
            data={'book_id': str(book.id), 'review_text': '오늘 씀'},
            follow_redirects=False,
        )
        self.assertEqual(start.status_code, 302)
        reading = ChildReading.query.filter_by(child_id=self.child_a.id).one()
        self.assertEqual(reading.program_type, 'general')
        save = self.client.post(
            f'/viewer/report/{self.child_a.viewer_slug}/reading/save',
            data={'child_reading_id': str(reading.id), 'review_text': '오늘 씀'},
            follow_redirects=False,
        )
        self.assertEqual(save.status_code, 302)
        self.assertEqual(ReadingDay.query.filter_by(child_reading_id=reading.id).count(), 1)

    def test_teacher_delegated_write_and_one_day_policy(self):
        book = self._general_book('대신기록책')
        self._login(self.teacher)
        start = self.client.post(
            f'/children/{self.child_b.id}/reading/start',
            data={
                'book_id': str(book.id),
                'date': self.today.isoformat(),
                'review_text': '교사가 씀',
            },
            follow_redirects=False,
        )
        self.assertEqual(start.status_code, 302)
        reading = ChildReading.query.filter_by(child_id=self.child_b.id).one()
        with self.assertRaises(ReadingError) as in_progress_err:
            start_book(
                self.child_b.id,
                self.teacher.id,
                'teacher',
                activity_date=self.today,
                book_id=self._general_book('겹침책').id,
            )
        self.assertEqual(in_progress_err.exception.code, 'already_in_progress')
        save_today(
            self.child_b.id, self.teacher.id, 'teacher',
            activity_date=self.today, review_text='교사가 씀', mark_completed=True,
        )
        with self.assertRaises(ReadingError) as err:
            start_book(
                self.child_b.id,
                self.teacher.id,
                'teacher',
                activity_date=self.today,
                book_id=self._general_book('둘째책').id,
            )
        self.assertEqual(err.exception.code, 'already_logged_today')
        self.assertEqual(ChildReading.query.get(reading.id).status, 'completed')

    def test_classify_program_type_unchanged(self):
        rec = self._rec_book()
        challenge = self._challenge_book()
        general = self._general_book()
        self.assertEqual(classify_program_type(self.child_a, rec), 'recommended')
        self.assertEqual(classify_program_type(self.child_a, challenge), 'challenge')
        self.assertEqual(classify_program_type(self.child_a, general), 'general')
        self.assertEqual(classify_program_type(self.child_b, rec), 'general')
        self.assertEqual(classify_program_type(self.child_b, challenge), 'general')


if __name__ == '__main__':
    unittest.main()
