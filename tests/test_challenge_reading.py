"""Step 7: 도전독서 v1. 추천/면제권 인프라를 재사용한다."""
from __future__ import annotations

import json
import os
import unittest
from datetime import date, timedelta
from unittest import mock

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User, get_backup_data  # noqa: E402
from feature_models import (  # noqa: E402
    Book,
    ChildReading,
    EVENT_CHALLENGE_COMPLETE,
    EVENT_CHALLENGE_START,
    EVENT_RECOMMENDED_COMPLETE,
    EVENT_RECOMMENDED_START,
    ExemptionTicket,
    ExemptionTicketSource,
    ReadingDay,
    ReadingRewardEvent,
)
from features.books.import_service import apply_preview, parse_paste_text, preview_rows  # noqa: E402
from features.books.restore import restore_books_from_backup_data  # noqa: E402
from features.books.service import (  # noqa: E402
    BookCreateError,
    create_book_record,
    register_challenge_book,
    unlist_challenge_book,
    update_challenge_flag,
    update_recommended_flags,
)
from features.dates import kst_today  # noqa: E402
from features.exemption.restore import restore_exemptions_from_backup_data  # noqa: E402
from features.exemption.service import (  # noqa: E402
    ExemptionError,
    child_exemption_snapshot,
    issue_exemption_ticket,
    next_ready_entitlement_group,
    set_reward_mode,
    unconsumed_qualifying_completions,
    use_exemption_ticket,
)
from features.reading.classify import classify_program_type  # noqa: E402
from features.reading.policy import now_utc, reading_incentives_enabled  # noqa: E402
from features.reading.restore import restore_readings_from_backup_data  # noqa: E402
from features.reading.rewards import (  # noqa: E402
    READING_REWARD_POLICIES,
    RewardError,
    approve_recommended_reward,
    recommended_reward_points,
    revoke_recommended_reward,
)
from features.reading.service import complete_current, start_book  # noqa: E402
from features.reading.session import SESSION_CHILD_ID, SESSION_CHILD_SLUG, SESSION_VERIFIED_AT  # noqa: E402


class ChallengeReadingTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='ch_teacher',
            name='도전교사',
            role='돌봄선생님',
            email='ch-teacher@example.test',
            password_hash='',
        )
        self.developer = User(
            username='ch_dev',
            name='도전개발자',
            role='개발자',
            email='ch-dev@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='ch_viewer',
            name='도전열람',
            role='학생열람',
            email='studentview-ch@example.test',
            password_hash='',
        )
        db.session.add_all([self.teacher, self.developer, self.viewer])
        db.session.commit()
        self.today = kst_today()
        self.client = app.test_client()
        self._slug_n = 0
        self.book_n = 0

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _child(self, name, grade):
        self._slug_n += 1
        child = Child(name=name, grade=grade, viewer_slug=f'{self._slug_n:024x}')
        db.session.add(child)
        db.session.commit()
        return child

    def _rec_book(self, title=None):
        self.book_n += 1
        book, _ = create_book_record(title or f'추천{self.book_n}', '추천작가')
        update_recommended_flags(book, is_recommended=True, grade_band='4-6')
        return book

    def _challenge_book(self, title=None, author='도전작가'):
        self.book_n += 1
        book, _created = register_challenge_book(title or f'도전{self.book_n}', author)
        return book

    def _general_book(self, title=None):
        self.book_n += 1
        book, _ = create_book_record(title or f'일반{self.book_n}', '일반작가')
        return book

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def _verify(self, child):
        with self.client.session_transaction() as sess:
            sess[SESSION_CHILD_ID] = int(child.id)
            sess[SESSION_CHILD_SLUG] = child.viewer_slug
            sess[SESSION_VERIFIED_AT] = now_utc().isoformat()

    def _start(self, child, book, activity_date=None):
        return start_book(
            child.id,
            self.teacher.id,
            'teacher',
            activity_date=activity_date or self.today,
            book_id=book.id,
        )

    def _complete_mode(self, child, book, mode, activity_date=None):
        day = activity_date or self.today
        reading, _ = self._start(child, book, day)
        set_reward_mode(reading, mode, self.teacher)
        complete_current(child.id, self.teacher.id, 'teacher', activity_date=day)
        return ChildReading.query.get(reading.id)

    def test_general_book_becomes_challenge(self):
        book, _ = create_book_record('기존일반', '작가')
        saved, created = register_challenge_book('기존일반', '작가')
        self.assertFalse(created)
        self.assertEqual(saved.id, book.id)
        self.assertTrue(saved.is_challenge_eligible)
        self.assertFalse(saved.is_recommended)
        self.assertEqual(Book.query.count(), 1)

    def test_new_book_created_as_challenge(self):
        book, created = register_challenge_book('새도전도서', '새작가')
        self.assertTrue(created)
        self.assertTrue(book.is_challenge_eligible)
        self.assertFalse(book.is_recommended)

    def test_recommended_cannot_become_challenge(self):
        rec = self._rec_book('추천만')
        with self.assertRaises(BookCreateError) as err:
            register_challenge_book('추천만', '추천작가')
        self.assertIn('추천도서', str(err.exception))
        self.assertTrue(Book.query.get(rec.id).is_recommended)
        self.assertFalse(Book.query.get(rec.id).is_challenge_eligible)

    def test_challenge_cannot_become_recommended(self):
        book = self._challenge_book('도전만')
        with self.assertRaises(BookCreateError):
            update_recommended_flags(book, is_recommended=True, grade_band='4-6')
        saved = Book.query.get(book.id)
        self.assertTrue(saved.is_challenge_eligible)
        self.assertFalse(saved.is_recommended)

    def test_clear_challenge_keeps_book_and_history(self):
        child = self._child('해제유지', 5)
        book = self._challenge_book('이력책')
        reading = self._complete_mode(child, book, 'exemption')
        unlist_challenge_book(book)
        saved = Book.query.get(book.id)
        self.assertFalse(saved.is_challenge_eligible)
        self.assertEqual(ChildReading.query.get(reading.id).id, reading.id)
        self.assertEqual(ChildReading.query.get(reading.id).program_type, 'challenge')
        self.assertEqual(ReadingDay.query.count(), 1)

    def test_ambiguous_duplicate_does_not_auto_merge(self):
        first, _ = create_book_record('같은제목', '작가A')
        second, _ = create_book_record('같은제목', '작가B')
        self.assertNotEqual(first.id, second.id)
        with self.assertRaises(BookCreateError) as err:
            register_challenge_book('같은제목', '작가A')
        self.assertIn('여러 권', str(err.exception))
        self.assertFalse(Book.query.get(first.id).is_challenge_eligible)
        self.assertFalse(Book.query.get(second.id).is_challenge_eligible)

    def test_recommended_xlsx_regression_does_not_set_challenge(self):
        rows = parse_paste_text('엑셀회귀 | 엑셀작가')
        preview = preview_rows(rows, default_grade_band='2-3')
        apply_preview(preview)
        book = Book.query.one()
        self.assertTrue(book.is_recommended)
        self.assertFalse(book.is_challenge_eligible)

    def test_classify_grade_5_6_challenge(self):
        book = self._challenge_book()
        for grade in (5, 6):
            child = self._child(f'분류{grade}', grade)
            self.assertEqual(classify_program_type(child, book), 'challenge')
            reading, _ = self._start(child, book)
            self.assertEqual(reading.program_type, 'challenge')

    def test_classify_general_and_recommended_unchanged(self):
        general = self._general_book()
        rec = self._rec_book()
        child = self._child('기존분류', 5)
        self.assertEqual(classify_program_type(child, general), 'general')
        self.assertEqual(classify_program_type(child, rec), 'recommended')
        younger = self._child('저학년도전', 3)
        challenge = self._challenge_book()
        self.assertEqual(classify_program_type(younger, challenge), 'general')

    def test_student_cannot_force_challenge_via_request(self):
        child = self._child('강제차단', 5)
        general = self._general_book('강제일반')
        self._login(self.viewer)
        self._verify(child)
        resp = self.client.post(
            f'/viewer/report/{child.viewer_slug}/reading/start',
            data={
                'book_id': str(general.id),
                'title': general.title,
                'program_type': 'challenge',
            },
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        reading = ChildReading.query.one()
        self.assertEqual(reading.program_type, 'general')

    def test_challenge_points_start_200_complete_400(self):
        child = self._child('포인트도전', 5)
        book = self._challenge_book()
        reading, _ = self._start(child, book)
        set_reward_mode(reading, 'points', self.teacher)
        self.assertEqual(DailyPoints.query.count(), 0)
        start_event, _ = approve_recommended_reward(reading, self.teacher, EVENT_CHALLENGE_START)
        self.assertEqual(start_event.points, 200)
        self.assertEqual(start_event.event_type, 'challenge_start')
        complete_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
        reading = ChildReading.query.get(reading.id)
        complete_event, _ = approve_recommended_reward(reading, self.teacher, EVENT_CHALLENGE_COMPLETE)
        self.assertEqual(complete_event.points, 400)
        daily = DailyPoints.query.one()
        self.assertEqual(daily.manual_points, 600)
        self.assertEqual(daily.reading_points, 0)
        self.assertEqual(ReadingRewardEvent.query.count(), 2)
        self.assertEqual(READING_REWARD_POLICIES['challenge']['start_points'][5], 200)
        self.assertEqual(READING_REWARD_POLICIES['challenge']['complete_points'][5], 400)

    def test_challenge_points_not_auto_awarded_and_revoke_works(self):
        child = self._child('자동없음', 6)
        reading = self._complete_mode(child, self._challenge_book(), 'points')
        self.assertEqual(ReadingRewardEvent.query.count(), 0)
        approve_recommended_reward(reading, self.teacher, EVENT_CHALLENGE_COMPLETE)
        self.assertEqual(DailyPoints.query.one().manual_points, 400)
        revoke_recommended_reward(reading, self.teacher, EVENT_CHALLENGE_COMPLETE)
        self.assertIsNotNone(ReadingRewardEvent.query.one().revoked_at)
        self.assertEqual(DailyPoints.query.one().manual_points, 0)

    def test_recommended_points_regression(self):
        child = self._child('추천회귀', 5)
        reading, _ = self._start(child, self._rec_book())
        set_reward_mode(reading, 'points', self.teacher)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_START)
        complete_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
        reading = ChildReading.query.get(reading.id)
        approve_recommended_reward(reading, self.teacher, EVENT_RECOMMENDED_COMPLETE)
        self.assertEqual(DailyPoints.query.one().manual_points, 300)
        self.assertEqual(recommended_reward_points(5, EVENT_RECOMMENDED_START, 'points'), 100)
        self.assertEqual(recommended_reward_points(5, EVENT_RECOMMENDED_COMPLETE, 'points'), 200)

    def test_points_challenge_not_in_exemption_eligibility(self):
        child = self._child('포인트제외', 5)
        self._complete_mode(child, self._challenge_book(), 'points')
        snap = child_exemption_snapshot(child.id, self.today)
        self.assertEqual(snap['challenge_ready_count'], 0)
        self.assertFalse(snap['condition_met'])
        self.assertEqual(unconsumed_qualifying_completions(child.id, 'challenge'), [])

    def test_challenge_exemption_one_book_one_entitlement(self):
        child = self._child('도전1권', 5)
        reading = self._complete_mode(child, self._challenge_book(), 'exemption')
        snap = child_exemption_snapshot(child.id, self.today)
        self.assertTrue(snap['condition_met'])
        self.assertTrue(snap['can_issue'])
        self.assertEqual(snap['challenge_ready_count'], 1)
        self.assertEqual(snap['next_group_program_type'], 'challenge')
        self.assertEqual(ExemptionTicket.query.count(), 0)
        ticket = issue_exemption_ticket(child.id, self.teacher, today=self.today)
        sources = ExemptionTicketSource.query.filter_by(exemption_ticket_id=ticket.id).all()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].child_reading_id, reading.id)
        self.assertEqual(ChildReading.query.get(reading.id).program_type, 'challenge')

    def test_global_active_and_cooldown(self):
        child = self._child('전역제한', 5)
        self._complete_mode(child, self._challenge_book('쿨A'), 'exemption')
        issue_exemption_ticket(child.id, self.teacher, today=self.today)
        self._complete_mode(child, self._challenge_book('쿨B'), 'exemption', self.today + timedelta(days=1))
        snap = child_exemption_snapshot(child.id, self.today)
        self.assertTrue(snap['holding_blocks'])
        self.assertFalse(snap['can_issue'])
        with self.assertRaises(ExemptionError) as held:
            issue_exemption_ticket(child.id, self.teacher, today=self.today)
        self.assertEqual(held.exception.code, 'already_holding')
        use_exemption_ticket(ExemptionTicket.query.one().id, 'math', self.teacher, today=self.today)
        with self.assertRaises(ExemptionError) as cool:
            issue_exemption_ticket(child.id, self.teacher, today=self.today + timedelta(days=1))
        self.assertEqual(cool.exception.code, 'cooldown')

    def test_ticket_origin_analysis_by_program_type(self):
        child = self._child('분석', 5)
        rec = self._complete_mode(child, self._rec_book(), 'exemption')
        rec_ticket = issue_exemption_ticket(child.id, self.teacher, today=self.today)
        rec_source = ExemptionTicketSource.query.filter_by(exemption_ticket_id=rec_ticket.id).one()
        self.assertEqual(ChildReading.query.get(rec_source.child_reading_id).program_type, 'recommended')
        use_exemption_ticket(rec_ticket.id, 'korean', self.teacher, today=self.today)
        ch = self._complete_mode(child, self._challenge_book(), 'exemption', self.today + timedelta(days=1))
        ch_ticket = issue_exemption_ticket(child.id, self.teacher, today=self.today + timedelta(days=14))
        ch_source = ExemptionTicketSource.query.filter_by(exemption_ticket_id=ch_ticket.id).one()
        self.assertEqual(ChildReading.query.get(ch_source.child_reading_id).program_type, 'challenge')
        self.assertEqual(rec.id, rec_source.child_reading_id)
        self.assertEqual(ch.id, ch_source.child_reading_id)

    def test_does_not_mix_recommended_progress_with_challenge(self):
        child = self._child('섞지않음', 5)
        first = self._complete_mode(child, self._rec_book('A'), 'exemption')
        issue_exemption_ticket(child.id, self.teacher, today=self.today)
        use_exemption_ticket(ExemptionTicket.query.one().id, 'math', self.teacher, today=self.today)
        rec_b = self._complete_mode(child, self._rec_book('B'), 'exemption', self.today + timedelta(days=1))
        ch = self._complete_mode(child, self._challenge_book('D'), 'exemption', self.today + timedelta(days=2))
        snap = child_exemption_snapshot(child.id, self.today + timedelta(days=14))
        self.assertEqual(snap['needed'], 2)
        self.assertEqual(snap['have'], 1)
        self.assertEqual(snap['challenge_ready_count'], 1)
        self.assertEqual(snap['next_group_program_type'], 'challenge')
        ticket = issue_exemption_ticket(child.id, self.teacher, today=self.today + timedelta(days=14))
        source_ids = {
            row.child_reading_id
            for row in ExemptionTicketSource.query.filter_by(exemption_ticket_id=ticket.id)
        }
        self.assertEqual(source_ids, {ch.id})
        self.assertNotIn(rec_b.id, source_ids)
        self.assertNotIn(first.id, source_ids)
        later = child_exemption_snapshot(child.id, self.today + timedelta(days=14))
        self.assertEqual(later['have'], 1)
        self.assertEqual(later['needed'], 2)
        unconsumed_rec = unconsumed_qualifying_completions(child.id, 'recommended')
        self.assertEqual([row.id for row in unconsumed_rec], [rec_b.id])

    def test_fifo_ready_groups_and_no_mixed_source_group(self):
        child = self._child('FIFO', 5)
        rec_a = self._complete_mode(child, self._rec_book('FA'), 'exemption', self.today)
        rec_b = self._complete_mode(child, self._rec_book('FB'), 'exemption', self.today + timedelta(days=1))
        rec_c = self._complete_mode(child, self._rec_book('FC'), 'exemption', self.today + timedelta(days=2))
        ch = self._complete_mode(child, self._challenge_book('FD'), 'exemption', self.today + timedelta(days=3))
        first = next_ready_entitlement_group(child.id)
        self.assertEqual(first['program_type'], 'recommended')
        self.assertEqual([row.id for row in first['readings']], [rec_a.id])
        ticket = issue_exemption_ticket(child.id, self.teacher, today=self.today + timedelta(days=3))
        self.assertEqual(
            [row.child_reading_id for row in ExemptionTicketSource.query.filter_by(exemption_ticket_id=ticket.id)],
            [rec_a.id],
        )
        second = next_ready_entitlement_group(child.id)
        self.assertEqual(second['program_type'], 'recommended')
        self.assertEqual([row.id for row in second['readings']], [rec_b.id, rec_c.id])
        use_exemption_ticket(ticket.id, 'reading', self.teacher, today=self.today + timedelta(days=3))
        ticket2 = issue_exemption_ticket(child.id, self.teacher, today=self.today + timedelta(days=17))
        ids = [
            row.child_reading_id
            for row in ExemptionTicketSource.query.filter_by(exemption_ticket_id=ticket2.id)
        ]
        self.assertEqual(ids, [rec_b.id, rec_c.id])
        self.assertNotIn(ch.id, ids)
        third = next_ready_entitlement_group(child.id)
        self.assertEqual(third['program_type'], 'challenge')
        self.assertEqual([row.id for row in third['readings']], [ch.id])

    def test_double_benefit_blocks_after_points_or_ticket(self):
        child = self._child('이중', 5)
        reading, _ = self._start(child, self._challenge_book(), self.today)
        set_reward_mode(reading, 'points', self.teacher)
        set_reward_mode(reading, 'exemption', self.teacher)
        set_reward_mode(reading, 'points', self.teacher)
        approve_recommended_reward(reading, self.teacher, EVENT_CHALLENGE_START)
        with self.assertRaises(ExemptionError) as err:
            set_reward_mode(reading, 'exemption', self.teacher)
        self.assertEqual(err.exception.code, 'points_already_awarded')
        revoke_recommended_reward(reading, self.teacher, EVENT_CHALLENGE_START)
        set_reward_mode(reading, 'exemption', self.teacher)
        complete_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
        reading = ChildReading.query.get(reading.id)
        ticket = issue_exemption_ticket(child.id, self.teacher, today=self.today)
        with self.assertRaises(ExemptionError) as active:
            set_reward_mode(reading, 'points', self.teacher)
        self.assertEqual(active.exception.code, 'source_active')
        use_exemption_ticket(ticket.id, 'ssen', self.teacher, today=self.today)
        with self.assertRaises(ExemptionError) as used:
            set_reward_mode(reading, 'points', self.teacher)
        self.assertEqual(used.exception.code, 'source_used')

    def test_books_ui_register_list_and_rename(self):
        self._login(self.teacher)
        page = self.client.get('/books').get_data(as_text=True)
        self.assertIn('독서도서 관리', page)
        self.assertIn('도전도서 추가', page)
        create = self.client.post(
            '/books/challenge',
            data={'title': 'UI도전', 'author': 'UI작가'},
            follow_redirects=False,
        )
        self.assertEqual(create.status_code, 302)
        book = Book.query.filter_by(title='UI도전').one()
        self.assertTrue(book.is_challenge_eligible)
        listed = self.client.get('/books?filter=challenge').get_data(as_text=True)
        self.assertIn('UI도전', listed)
        self.assertIn('도전도서 해제', listed)
        clear = self.client.post(
            f'/books/{book.id}/challenge',
            data={'is_challenge_eligible': '0', 'filter': 'challenge'},
            follow_redirects=False,
        )
        self.assertEqual(clear.status_code, 302)
        self.assertFalse(Book.query.get(book.id).is_challenge_eligible)

    def test_incentive_flag_on_default(self):
        self.assertTrue(reading_incentives_enabled())
        child = self._child('플래그온', 5)
        reading, _ = self._start(child, self._challenge_book())
        set_reward_mode(reading, 'points', self.teacher)
        approve_recommended_reward(reading, self.teacher, EVENT_CHALLENGE_START)
        self.assertEqual(ReadingRewardEvent.query.count(), 1)

    def test_incentive_flag_off_keeps_ledger_and_blocks_new_rewards(self):
        child = self._child('플래그오프', 5)
        book = self._challenge_book()
        reading, _ = self._start(child, book)
        set_reward_mode(reading, 'points', self.teacher)
        approve_recommended_reward(reading, self.teacher, EVENT_CHALLENGE_START)
        complete_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
        reading = ChildReading.query.get(reading.id)
        rec = self._complete_mode(self._child('오프추천', 5), self._rec_book(), 'exemption')
        ticket = issue_exemption_ticket(rec.child_id, self.teacher, today=self.today)
        self.assertEqual(ticket.status, 'active')

        with mock.patch.dict(os.environ, {'CLC_READING_INCENTIVES_ENABLED': '0'}):
            self.assertFalse(reading_incentives_enabled())
            other = self._child('오프작성', 5)
            started, day = self._start(other, self._general_book())
            self.assertEqual(started.program_type, 'general')
            self.assertEqual(day.child_reading_id, started.id)
            self._login(self.teacher)
            history = self.client.get(f'/children/{other.id}/reading/history')
            self.assertEqual(history.status_code, 200)
            points = self.client.post(
                f'/points/input/{other.id}',
                data={
                    'date': self.today.isoformat(),
                    'korean_points': '100',
                    'math_points': '0',
                    'ssen_points': '0',
                    'reading_points': '0',
                    'piano_points': '0',
                    'english_points': '0',
                    'advanced_math_points': '0',
                    'writing_points': '0',
                    'manual_entries': '[]',
                },
                follow_redirects=False,
            )
            self.assertIn(points.status_code, (200, 302))
            self.assertEqual(DailyPoints.query.filter_by(child_id=other.id).one().korean_points, 100)

            with self.assertRaises(RewardError) as reward_err:
                approve_recommended_reward(reading, self.teacher, EVENT_CHALLENGE_COMPLETE)
            self.assertEqual(reward_err.exception.code, 'incentives_disabled')
            with self.assertRaises(ExemptionError) as mode_err:
                set_reward_mode(reading, 'points', self.teacher)
            self.assertEqual(mode_err.exception.code, 'incentives_disabled')
            with self.assertRaises(ExemptionError) as issue_err:
                issue_exemption_ticket(rec.child_id, self.teacher, today=self.today)
            self.assertEqual(issue_err.exception.code, 'incentives_disabled')

            use_exemption_ticket(ticket.id, 'math', self.teacher, today=self.today)
            self.assertEqual(ExemptionTicket.query.get(ticket.id).status, 'used')
            self.assertEqual(ReadingRewardEvent.query.count(), 1)
            self.assertEqual(ExemptionTicket.query.count(), 1)
            self.assertEqual(ChildReading.query.count(), 3)

    def test_backup_restore_includes_challenge_fields(self):
        child = self._child('백업도전', 5)
        book = self._challenge_book('백업책')
        reading = self._complete_mode(child, book, 'points')
        approve_recommended_reward(reading, self.teacher, EVENT_CHALLENGE_COMPLETE)
        backup_data, error = get_backup_data()
        self.assertIsNone(error)
        self.assertTrue(backup_data['books'][0]['is_challenge_eligible'])
        self.assertEqual(backup_data['child_readings'][0]['program_type'], 'challenge')
        self.assertEqual(backup_data['reading_reward_events'][0]['event_type'], 'challenge_complete')
        ReadingRewardEvent.query.delete()
        ReadingDay.query.delete()
        ChildReading.query.delete()
        Book.query.delete()
        db.session.commit()
        restore_books_from_backup_data(backup_data)
        restore_readings_from_backup_data(backup_data)
        restore_exemptions_from_backup_data(backup_data)
        restored_book = Book.query.one()
        self.assertTrue(restored_book.is_challenge_eligible)
        restored_reading = ChildReading.query.one()
        self.assertEqual(restored_reading.program_type, 'challenge')
        self.assertEqual(ReadingRewardEvent.query.one().points, 400)

    def _panel_html(self, html, reading_id):
        token = f'data-reading-id="{reading_id}"'
        start = html.find(token)
        self.assertNotEqual(start, -1, f'reading panel {reading_id} missing')
        start = html.rfind('reading-reward-panel', 0, start)
        self.assertNotEqual(start, -1)
        nxt = html.find('reading-reward-panel', start + len('reading-reward-panel'))
        return html[start:nxt if nxt != -1 else len(html)]

    def test_unified_search_finds_general_recommended_and_challenge(self):
        general = self._general_book('검색일반책')
        rec = self._rec_book('검색추천책')
        challenge = self._challenge_book('검색도전책')
        self._login(self.teacher)
        payload = self.client.get('/api/books?q=검색').get_json()['books']
        by_title = {book['title']: book for book in payload}
        self.assertIn(general.title, by_title)
        self.assertIn(rec.title, by_title)
        self.assertIn(challenge.title, by_title)
        self.assertTrue(by_title[rec.title]['is_recommended'])
        self.assertTrue(by_title[challenge.title]['is_challenge_eligible'])
        self.assertFalse(by_title[general.title]['is_recommended'])
        self.assertFalse(by_title[general.title]['is_challenge_eligible'])

    def test_editor_has_unified_search_without_recommended_tab(self):
        child = self._child('통합검색화면', 5)
        self._login(self.teacher)
        html = self.client.get(f'/children/{child.id}/reading').get_data(as_text=True)
        self.assertNotIn('search-mode-recommended', html)
        self.assertNotIn('추천도서 전용', html)
        self.assertNotIn('학년군에 맞는 추천도서만', html)
        self.assertIn('전체 도서에서 찾습니다', html)
        self.assertIn('[추천]', html)
        self.assertIn('[도전]', html)
        rec = self._rec_book('탭없이추천')
        found = self.client.get(f'/api/books?q={rec.title}').get_json()['books']
        self.assertEqual(found[0]['id'], rec.id)
        start = self.client.post(
            f'/children/{child.id}/reading/start',
            data={'book_id': str(rec.id), 'title': rec.title, 'date': self.today.isoformat()},
            follow_redirects=False,
        )
        self.assertEqual(start.status_code, 302)
        self.assertEqual(ChildReading.query.one().program_type, 'recommended')

    def test_unified_search_start_challenge_classifies_on_server(self):
        child = self._child('검색도전시작', 5)
        book = self._challenge_book('서버분류도전')
        self._login(self.teacher)
        self.client.post(
            f'/children/{child.id}/reading/start',
            data={
                'book_id': str(book.id),
                'title': book.title,
                'program_type': 'recommended',
                'date': self.today.isoformat(),
            },
            follow_redirects=False,
        )
        self.assertEqual(ChildReading.query.one().program_type, 'challenge')

    def test_global_exemption_status_stays_off_in_progress_cards(self):
        child = self._child('카드분리', 5)
        day_a = self.today - timedelta(days=1)
        completed = self._complete_mode(child, self._rec_book('완독A'), 'exemption', day_a)
        in_progress, _ = self._start(child, self._rec_book('읽는B'), self.today)
        set_reward_mode(in_progress, 'exemption', self.teacher)
        snap = child_exemption_snapshot(child.id, self.today)
        self.assertTrue(snap['can_issue'])
        self.assertEqual(snap['have'], 1)
        self.assertEqual(snap['needed'], 1)

        self._login(self.teacher)
        history = self.client.get(f'/children/{child.id}/reading/history').get_data(as_text=True)
        editor = self.client.get(f'/children/{child.id}/reading').get_data(as_text=True)
        self.assertIn('면제권 발급 가능', history)
        self.assertIn('면제권 발급 가능', editor)
        self.assertIn('첫 보상', history)
        done_panel = self._panel_html(history, completed.id)
        open_panel = self._panel_html(history, in_progress.id)
        editor_panel = self._panel_html(editor, in_progress.id)
        for panel in (done_panel, open_panel, editor_panel):
            self.assertNotIn('면제권 발급 가능', panel)
            self.assertNotIn('1 / 1', panel)
            self.assertNotIn('0 / 2', panel)
        self.assertIn('완독은 면제권 진행에 포함됩니다', done_panel)
        self.assertIn('완독하면 면제권 진행에 포함됩니다', open_panel)
        self.assertIn('완독하면 면제권 진행에 포함됩니다', editor_panel)
        self.assertNotIn('이미 면제권 발급에 반영되었습니다', done_panel)
        self.assertNotIn('이미 면제권 발급에 반영되었습니다', open_panel)

        issue_exemption_ticket(child.id, self.teacher, today=self.today)
        after = child_exemption_snapshot(child.id, self.today)
        self.assertEqual(after['needed'], 2)
        self.assertEqual(after['have'], 0)
        history2 = self.client.get(f'/children/{child.id}/reading/history').get_data(as_text=True)
        self.assertIn('추천도서 0 / 2권', history2)
        applied = self._panel_html(history2, completed.id)
        still_open = self._panel_html(history2, in_progress.id)
        self.assertIn('이미 면제권 발급에 반영되었습니다', applied)
        self.assertNotIn('이미 면제권 발급에 반영되었습니다', still_open)
        self.assertNotIn('면제권 발급 가능', still_open)
        self.assertNotIn('0 / 2', still_open)

        complete_current(child.id, self.teacher.id, 'teacher', activity_date=self.today)
        later = child_exemption_snapshot(child.id, self.today)
        self.assertEqual(later['needed'], 2)
        self.assertEqual(later['have'], 1)
        history3 = self.client.get(f'/children/{child.id}/reading/history').get_data(as_text=True)
        self.assertIn('추천도서 1 / 2권', history3)
        finished_b = self._panel_html(history3, in_progress.id)
        self.assertNotIn('1 / 2', finished_b)
        self.assertNotIn('면제권 발급 가능', finished_b)
        self.assertIn('완독은 면제권 진행에 포함됩니다', finished_b)


if __name__ == '__main__':
    unittest.main()
