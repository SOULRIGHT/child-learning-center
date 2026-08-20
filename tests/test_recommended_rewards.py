"""Step 5: 추천독서 판정, lifecycle, 교사 승인 보상. Step 6 면제권은 다루지 않는다."""
from __future__ import annotations

import json
import unittest
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, PointsHistory, User, get_backup_data, parse_manual_entries  # noqa: E402
from feature_models import (  # noqa: E402
    Book,
    ChildReading,
    EVENT_RECOMMENDED_COMPLETE,
    EVENT_RECOMMENDED_START,
    ReadingDay,
    ReadingRewardEvent,
    STATUS_ABANDONED,
    STATUS_COMPLETED,
)
from features.books.restore import restore_books_from_backup_data  # noqa: E402
from features.books.service import create_book_record, update_recommended_flags  # noqa: E402
from features.dates import kst_today  # noqa: E402
from features.progress.service import ensure_default_subjects, save_progress_entry  # noqa: E402
from features.reading.classify import classify_program_type  # noqa: E402
from features.reading.restore import restore_readings_from_backup_data  # noqa: E402
from features.reading.rewards import (  # noqa: E402
    RewardError,
    approve_recommended_reward,
    recommended_reward_points,
    revoke_recommended_reward,
)
from features.reading.service import (  # noqa: E402
    abandon_current,
    complete_current,
    get_in_progress,
    save_today,
    start_book,
)
from features.reading.session import SESSION_CHILD_ID, SESSION_CHILD_SLUG, SESSION_VERIFIED_AT  # noqa: E402
from features.reading.policy import now_utc  # noqa: E402


class RecommendedReadingLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='rec_life_teacher',
            name='추천생애교사',
            role='돌봄선생님',
            email='rec-life-teacher@example.test',
            password_hash='',
        )
        self.developer = User(
            username='rec_life_dev',
            name='추천개발자',
            role='개발자',
            email='rec-life-dev@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='rec_life_viewer',
            name='추천생애열람',
            role='학생열람',
            email='studentview-rec-life@example.test',
            password_hash='',
        )
        db.session.add_all([self.teacher, self.developer, self.viewer])
        db.session.commit()
        self.today = kst_today()
        self.client = app.test_client()
        self.book_23 = self._rec_book('추천23권', '2-3')
        self.book_46 = self._rec_book('추천46권', '4-6')
        self.book_general, _ = create_book_record('일반권', '일반작가')
        self._slug_n = 0

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _rec_book(self, title, band):
        book, _ = create_book_record(title, '추천작가')
        update_recommended_flags(book, is_recommended=True, grade_band=band)
        return book

    def _child(self, name, grade, slug=None):
        self._slug_n += 1
        child = Child(name=name, grade=grade, viewer_slug=f'{self._slug_n:024x}')
        db.session.add(child)
        db.session.commit()
        return child

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def _verify(self, child):
        with self.client.session_transaction() as sess:
            sess[SESSION_CHILD_ID] = int(child.id)
            sess[SESSION_CHILD_SLUG] = child.viewer_slug
            sess[SESSION_VERIFIED_AT] = now_utc().isoformat()

    def _start(self, child, book, user=None, activity_date=None):
        return start_book(
            child.id,
            (user or self.teacher).id,
            'teacher' if (user or self.teacher).role != '학생열람' else 'child',
            activity_date=activity_date or self.today,
            book_id=book.id,
        )

    def test_classify_grade_2_and_3_as_recommended(self):
        child2 = self._child('판정2', 2, 'r2aaaaaaaaaaaaaaaaaaaaaa')
        child3 = self._child('판정3', 3, 'r3aaaaaaaaaaaaaaaaaaaaaa')
        self.assertEqual(classify_program_type(child2, self.book_23), 'recommended')
        self.assertEqual(classify_program_type(child3, self.book_23), 'recommended')

    def test_classify_grade_4_5_6_as_recommended_lifecycle(self):
        child4 = self._child('판정4', 4, 'r4aaaaaaaaaaaaaaaaaaaaaa')
        child5 = self._child('판정5', 5, 'r5aaaaaaaaaaaaaaaaaaaaaa')
        child6 = self._child('판정6', 6, 'r6aaaaaaaaaaaaaaaaaaaaaa')
        self.assertEqual(classify_program_type(child4, self.book_46), 'recommended')
        self.assertEqual(classify_program_type(child5, self.book_46), 'recommended')
        self.assertEqual(classify_program_type(child6, self.book_46), 'recommended')

    def test_grade_mismatch_and_unlisted_are_general(self):
        child2 = self._child('불일치', 2, 'rmisaaaaaaaaaaaaaaaaaaaa')
        self.assertEqual(classify_program_type(child2, self.book_46), 'general')
        self.assertEqual(classify_program_type(child2, self.book_general), 'general')
        update_recommended_flags(self.book_23, is_recommended=False)
        self.assertEqual(classify_program_type(child2, self.book_23), 'general')

    def test_same_child_book_classifies_identically_from_any_path(self):
        child = self._child('경로동일', 4, 'rpathaaaaaaaaaaaaaaaaaaa')
        teacher_type = classify_program_type(child, self.book_46)
        viewer_type = classify_program_type(child, self.book_46)
        self.assertEqual(teacher_type, viewer_type)
        self.assertEqual(teacher_type, 'recommended')

    def test_start_readingday_one_current_complete_abandon(self):
        child = self._child('생애', 3, 'rlifeaaaaaaaaaaaaaaaaaaa')
        reading, day = self._start(child, self.book_23)
        self.assertEqual(reading.program_type, 'recommended')
        self.assertEqual(reading.status, 'in_progress')
        self.assertEqual(day.child_reading_id, reading.id)
        self.assertEqual(get_in_progress(child.id).id, reading.id)
        save_today(child.id, self.teacher.id, 'teacher', activity_date=self.today, review_text='읽는 중')
        self.assertEqual(ReadingDay.query.filter_by(child_reading_id=reading.id).count(), 1)
        complete_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
        self.assertEqual(ChildReading.query.get(reading.id).status, STATUS_COMPLETED)

        child2 = self._child('포기', 3, 'rabndaaaaaaaaaaaaaaaaaaa')
        reading2, _ = self._start(child2, self.book_23)
        abandon_current(child2.id, self.teacher.id, 'teacher', activity_date=self.today)
        abandoned = ChildReading.query.get(reading2.id)
        self.assertEqual(abandoned.status, STATUS_ABANDONED)
        self.assertIsNone(abandoned.completed_on)

    def test_cannot_have_general_and_recommended_in_progress(self):
        child = self._child('한방', 3, 'roneaaaaaaaaaaaaaaaaaaaa')
        self._start(child, self.book_23)
        with self.assertRaises(Exception):
            self._start(child, self.book_general)
        self.assertEqual(ChildReading.query.filter_by(child_id=child.id, status='in_progress').count(), 1)

    def test_viewer_can_start_and_complete_without_reward(self):
        child = self._child('열람생애', 3, 'rviewaaaaaaaaaaaaaaaaaaa')
        self._login(self.viewer)
        self._verify(child)
        start = self.client.post(
            f'/viewer/report/{child.viewer_slug}/reading/start',
            data={'book_id': str(self.book_23.id), 'title': self.book_23.title},
            follow_redirects=False,
        )
        self.assertEqual(start.status_code, 302)
        reading = get_in_progress(child.id)
        self.assertEqual(reading.program_type, 'recommended')
        self.assertEqual(DailyPoints.query.count(), 0)
        self.assertEqual(ReadingRewardEvent.query.count(), 0)
        complete = self.client.post(
            f'/viewer/report/{child.viewer_slug}/reading/save',
            data={'child_reading_id': str(reading.id), 'completed': '1'},
            follow_redirects=False,
        )
        self.assertEqual(complete.status_code, 302)
        self.assertEqual(ChildReading.query.get(reading.id).status, STATUS_COMPLETED)
        self.assertEqual(DailyPoints.query.count(), 0)
        self.assertEqual(ReadingRewardEvent.query.count(), 0)

    def test_viewer_reward_endpoints_blocked(self):
        child = self._child('열람차단', 3, 'rblockaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_23)
        self._login(self.viewer)
        approve = self.client.post(
            f'/children/{child.id}/reading/reward/approve',
            data={'child_reading_id': str(reading.id), 'event_type': EVENT_RECOMMENDED_START},
            follow_redirects=False,
        )
        self.assertEqual(approve.status_code, 302)
        self.assertIn('/viewer', approve.headers.get('Location', ''))
        self.assertEqual(ReadingRewardEvent.query.count(), 0)

    def test_grade_2_3_start_and_complete_points(self):
        child = self._child('저학년', 2, 'r23aaaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_23)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        complete_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
        reading = ChildReading.query.get(reading.id)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_COMPLETE)
        daily = DailyPoints.query.filter_by(child_id=child.id, date=self.today).one()
        self.assertEqual(daily.reading_points, 0)
        self.assertEqual(daily.manual_points, 200)
        self.assertEqual(daily.total_points, 200)
        self.assertEqual(Child.query.get(child.id).cumulative_points, 200)
        self.assertEqual(recommended_reward_points(3, EVENT_RECOMMENDED_COMPLETE), 100)

    def test_grade_4_start_100_complete_200(self):
        child = self._child('4학년', 4, 'r4ptaaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_46)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        complete_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
        reading = ChildReading.query.get(reading.id)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_COMPLETE)
        daily = DailyPoints.query.one()
        self.assertEqual(daily.manual_points, 300)
        history = json.loads(daily.manual_history)
        self.assertEqual({item['source_event'] for item in history}, {'start', 'complete'})

    def test_grade_5_6_lifecycle_without_point_route(self):
        for grade in (5, 6):
            child = self._child(f'{grade}학년', grade)
            reading, _ = self._start(child, self.book_46)
            self.assertEqual(reading.program_type, 'recommended')
            with self.assertRaises(RewardError) as start_err:
                approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
            self.assertEqual(start_err.exception.code, 'grade_deferred')
            complete_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
            reading = ChildReading.query.get(reading.id)
            with self.assertRaises(RewardError) as complete_err:
                approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_COMPLETE)
            self.assertEqual(complete_err.exception.code, 'grade_deferred')
        self.assertEqual(DailyPoints.query.count(), 0)
        self.assertEqual(ReadingRewardEvent.query.count(), 0)
        self.assertIsNone(recommended_reward_points(5, EVENT_RECOMMENDED_START))
        self.assertIsNone(recommended_reward_points(6, EVENT_RECOMMENDED_COMPLETE))

    def test_approve_is_idempotent_and_unique(self):
        child = self._child('중복승인', 4, 'rdupaaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_46)
        first, created = approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        second, created_again = approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.id, second.id)
        self.assertEqual(DailyPoints.query.one().manual_points, 100)
        db.session.add(ReadingRewardEvent(
            child_reading_id=reading.id,
            event_type=EVENT_RECOMMENDED_START,
            points=100,
            awarded_on=self.today,
            created_by_user_id=self.teacher.id,
        ))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_complete_approve_idempotent(self):
        child = self._child('완독중복', 3, 'rcmpaaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_23)
        complete_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
        reading = ChildReading.query.get(reading.id)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_COMPLETE)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_COMPLETE)
        self.assertEqual(DailyPoints.query.one().manual_points, 100)
        self.assertEqual(ReadingRewardEvent.query.count(), 1)

    def test_points_go_to_manual_not_reading_and_history(self):
        child = self._child('원장', 4, 'rledaaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_46)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        daily = DailyPoints.query.one()
        self.assertEqual(daily.reading_points, 0)
        self.assertEqual(daily.manual_points, 100)
        self.assertEqual(daily.total_points, 100)
        self.assertEqual(PointsHistory.query.count(), 1)
        self.assertEqual(Child.query.get(child.id).cumulative_points, 100)
        history = json.loads(daily.manual_history)
        self.assertEqual(history[0]['source_type'], 'recommended_reading')
        self.assertEqual(history[0]['source_child_reading_id'], reading.id)
        kept, _ = parse_manual_entries(daily.manual_history, '교사')
        self.assertEqual(kept[0]['source_event'], 'start')

    def test_general_reading_points_are_additive(self):
        child = self._child('가산', 4, 'raddaaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_46)
        complete_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
        db.session.add(DailyPoints(
            child_id=child.id,
            date=self.today,
            korean_points=0,
            math_points=0,
            ssen_points=0,
            reading_points=100,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=0,
            manual_history='[]',
            total_points=100,
            created_by=self.teacher.id,
        ))
        db.session.commit()
        reading = ChildReading.query.get(reading.id)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_COMPLETE)
        daily = DailyPoints.query.one()
        self.assertEqual(daily.reading_points, 100)
        self.assertEqual(daily.manual_points, 300)
        self.assertEqual(daily.total_points, 400)

    def test_reward_uses_activity_dates_not_approval_day(self):
        child = self._child('활동일', 4, 'rdateaaaaaaaaaaaaaaaaaaa')
        start_on = self.today - timedelta(days=2)
        complete_on = self.today - timedelta(days=1)
        reading, _ = self._start(child, self.book_46, activity_date=start_on)
        complete_current(child.id, self.teacher.id, 'teacher', activity_date=complete_on)
        reading = ChildReading.query.get(reading.id)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_COMPLETE)
        start_row = DailyPoints.query.filter_by(child_id=child.id, date=start_on).one()
        complete_row = DailyPoints.query.filter_by(child_id=child.id, date=complete_on).one()
        self.assertEqual(start_row.manual_points, 100)
        self.assertEqual(complete_row.manual_points, 200)
        self.assertIsNone(DailyPoints.query.filter_by(child_id=child.id, date=self.today).first())
        event = ReadingRewardEvent.query.filter_by(event_type=EVENT_RECOMMENDED_START).one()
        self.assertEqual(event.awarded_on, start_on)
        self.assertEqual(event.policy_version, 'recommended_v1')

    def test_kst_activity_today(self):
        child = self._child('KST', 3, 'rkstaaaaaaaaaaaaaaaaaaaa')
        reading, day = self._start(child, self.book_23)
        self.assertEqual(reading.started_on, kst_today())
        self.assertEqual(day.date, kst_today())

    def test_abandoned_keeps_start_reward_blocks_complete(self):
        child = self._child('중단보상', 3, 'rkeepaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_23)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        abandon_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
        reading = ChildReading.query.get(reading.id)
        with self.assertRaises(RewardError) as exc:
            approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_COMPLETE)
        self.assertEqual(exc.exception.code, 'abandoned')
        self.assertEqual(DailyPoints.query.one().manual_points, 100)
        self.assertEqual(ReadingRewardEvent.query.filter_by(event_type=EVENT_RECOMMENDED_START).count(), 1)

    def test_book_unlist_does_not_rewrite_past_reading(self):
        child = self._child('과거보존', 3, 'rpastaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_23)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        update_recommended_flags(self.book_23, is_recommended=False)
        reading = ChildReading.query.get(reading.id)
        self.assertEqual(reading.program_type, 'recommended')
        self.assertEqual(ReadingRewardEvent.query.count(), 1)
        self.assertEqual(DailyPoints.query.one().manual_points, 100)

    def test_reset_data_preserves_reading_and_progress(self):
        child = self._child('학기초기화', 3, 'rrstaaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_23)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        ensure_default_subjects()
        from feature_models import LearningSubject
        math = LearningSubject.query.filter_by(key='math').one()
        save_progress_entry(
            child_id=child.id,
            learning_subject_id=math.id,
            textbook_title='보존교재',
            page=10,
            recorded_on=self.today,
            created_by_user_id=self.teacher.id,
        )
        self._login(self.developer)
        resp = self.client.post('/settings/data', data={'action': 'reset_data'}, follow_redirects=False)
        self.assertIn(resp.status_code, (200, 302))
        self.assertEqual(ChildReading.query.count(), 1)
        self.assertEqual(ReadingDay.query.count(), 1)
        self.assertEqual(ReadingRewardEvent.query.count(), 1)
        from feature_models import LearningProgressEntry
        self.assertEqual(LearningProgressEntry.query.count(), 1)
        self.assertEqual(DailyPoints.query.count(), 0)

    def test_backup_restore_reward_events(self):
        child = self._child('백업보상', 4, 'rbakaaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_46)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        backup_data, error = get_backup_data()
        self.assertIsNone(error)
        self.assertEqual(backup_data['backup_metadata']['records_count']['reading_reward_events'], 1)
        ReadingRewardEvent.query.delete()
        ReadingDay.query.delete()
        ChildReading.query.delete()
        Book.query.delete()
        db.session.commit()
        restore_books_from_backup_data(backup_data)
        restore_readings_from_backup_data(backup_data)
        event = ReadingRewardEvent.query.one()
        self.assertEqual(event.event_type, EVENT_RECOMMENDED_START)
        self.assertEqual(event.points, 100)
        self.assertEqual(event.policy_version, 'recommended_v1')

    def test_revoke_restores_manual_and_cumulative(self):
        child = self._child('취소', 4, 'rrevaaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_46)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        revoke_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        daily = DailyPoints.query.one()
        self.assertEqual(daily.manual_points, 0)
        self.assertEqual(daily.total_points, 0)
        self.assertEqual(Child.query.get(child.id).cumulative_points, 0)
        event = ReadingRewardEvent.query.one()
        self.assertIsNotNone(event.revoked_at)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        self.assertEqual(DailyPoints.query.one().manual_points, 100)
        self.assertEqual(ReadingRewardEvent.query.count(), 1)

    def test_teacher_http_approve_and_double_click(self):
        child = self._child('화면승인', 3, 'rhttpaaaaaaaaaaaaaaaaaaa')
        reading, _ = self._start(child, self.book_23)
        self._login(self.teacher)
        url = f'/children/{child.id}/reading/reward/approve'
        data = {'child_reading_id': str(reading.id), 'event_type': EVENT_RECOMMENDED_START}
        self.assertEqual(self.client.post(url, data=data, follow_redirects=False).status_code, 302)
        self.assertEqual(self.client.post(url, data=data, follow_redirects=False).status_code, 302)
        self.assertEqual(DailyPoints.query.one().manual_points, 100)
        editor = self.client.get(f'/children/{child.id}/reading')
        self.assertIn('추천독서 보상', editor.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
