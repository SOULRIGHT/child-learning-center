"""Step 9: 완독 시 선택형 난이도·재미 평가."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
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
    ReadingDay,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
)
from features.books.service import create_book_record, register_challenge_book, update_recommended_flags  # noqa: E402
from features.dates import kst_today  # noqa: E402
from features.exemption.service import set_reward_mode, unconsumed_qualifying_completions  # noqa: E402
from features.reading.classify import classify_program_type  # noqa: E402
from features.reading.policy import now_utc  # noqa: E402
from features.reading.ratings import parse_optional_rating  # noqa: E402
from features.reading.restore import restore_readings_from_backup_data  # noqa: E402
from features.reading.rewards import approve_recommended_reward  # noqa: E402
from features.reading.schema import ensure_child_reading_rating_columns  # noqa: E402
from features.reading.service import ReadingError, save_today, start_book  # noqa: E402
from features.reading.session import SESSION_CHILD_ID, SESSION_CHILD_SLUG, SESSION_VERIFIED_AT  # noqa: E402


class ReadingRatingTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='rate_teacher',
            name='평가교사',
            role='돌봄선생님',
            email='rate-teacher@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='rate_viewer',
            name='평가열람',
            role='학생열람',
            email='studentview-rate@example.test',
            password_hash='',
        )
        db.session.add_all([self.teacher, self.viewer])
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

    def _general_book(self, title=None):
        self.book_n += 1
        book, _ = create_book_record(title or f'일반{self.book_n}', '일반작가')
        return book

    def _rec_book(self, title=None, grade_band='4-6'):
        self.book_n += 1
        book, _ = create_book_record(title or f'추천{self.book_n}', '추천작가')
        update_recommended_flags(book, is_recommended=True, grade_band=grade_band)
        return book

    def _challenge_book(self, title=None):
        self.book_n += 1
        book, _ = register_challenge_book(title or f'도전{self.book_n}', '도전작가')
        return book

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def _authed_client(self, user):
        client = app.test_client()
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
        return client

    def _verify_on(self, client, child):
        with client.session_transaction() as sess:
            sess[SESSION_CHILD_ID] = int(child.id)
            sess[SESSION_CHILD_SLUG] = child.viewer_slug
            sess[SESSION_VERIFIED_AT] = now_utc().isoformat()

    def _verify(self, child):
        with self.client.session_transaction() as sess:
            sess[SESSION_CHILD_ID] = int(child.id)
            sess[SESSION_CHILD_SLUG] = child.viewer_slug
            sess[SESSION_VERIFIED_AT] = now_utc().isoformat()

    def _start(self, child, book):
        return start_book(
            child.id, self.teacher.id, 'teacher',
            activity_date=self.today, book_id=book.id,
        )

    def _complete(self, child, *, difficulty=None, fun=None):
        return save_today(
            child.id, self.teacher.id, 'teacher',
            activity_date=self.today, mark_completed=True,
            difficulty_rating=difficulty, fun_rating=fun,
        )

    def test_completed_with_difficulty_1_and_fun_5(self):
        child = self._child('둘다', 3)
        self._start(child, self._general_book())
        reading, _ = self._complete(child, difficulty=1, fun=5)
        self.assertEqual(reading.status, STATUS_COMPLETED)
        self.assertEqual(reading.difficulty_rating, 1)
        self.assertEqual(reading.fun_rating, 5)

    def test_completed_with_both_null(self):
        child = self._child('생략', 3)
        self._start(child, self._general_book())
        reading, _ = self._complete(child, difficulty='', fun=None)
        self.assertEqual(reading.status, STATUS_COMPLETED)
        self.assertIsNone(reading.difficulty_rating)
        self.assertIsNone(reading.fun_rating)

    def test_completed_difficulty_only(self):
        child = self._child('난이도만', 3)
        self._start(child, self._general_book())
        reading, _ = self._complete(child, difficulty=4, fun='')
        self.assertEqual(reading.difficulty_rating, 4)
        self.assertIsNone(reading.fun_rating)

    def test_completed_fun_only(self):
        child = self._child('재미만', 3)
        self._start(child, self._general_book())
        reading, _ = self._complete(child, difficulty=None, fun=2)
        self.assertIsNone(reading.difficulty_rating)
        self.assertEqual(reading.fun_rating, 2)

    def test_rejects_out_of_range_and_garbage(self):
        cases = [
            ('difficulty', 0),
            ('difficulty', 6),
            ('fun', 0),
            ('fun', 6),
            ('difficulty', 'abc'),
            ('difficulty', '1.5'),
            ('fun', -1),
            ('fun', True),
            ('difficulty', 3.0),
        ]
        for field, value in cases:
            child = self._child(f'거절{field}{value}', 3)
            self._start(child, self._general_book())
            kwargs = {'difficulty': 3, 'fun': 3}
            kwargs['difficulty' if field == 'difficulty' else 'fun'] = value
            with self.assertRaises(ReadingError) as err:
                self._complete(child, **kwargs)
            self.assertEqual(err.exception.code, 'invalid_rating')
            reading = ChildReading.query.filter_by(child_id=child.id).one()
            self.assertEqual(reading.status, STATUS_IN_PROGRESS)
            self.assertIsNone(reading.difficulty_rating)
            self.assertIsNone(reading.fun_rating)
            db.session.rollback()

    def test_parse_optional_rating_helpers(self):
        self.assertIsNone(parse_optional_rating(None))
        self.assertIsNone(parse_optional_rating(''))
        self.assertIsNone(parse_optional_rating('  '))
        self.assertEqual(parse_optional_rating(3), 3)
        self.assertEqual(parse_optional_rating('5'), 5)
        with self.assertRaises(ValueError):
            parse_optional_rating(0)
        with self.assertRaises(ValueError):
            parse_optional_rating('nope')

    def test_program_types_all_accept_ratings(self):
        general_child = self._child('일반평가', 3)
        rec_child = self._child('추천평가', 5)
        challenge_child = self._child('도전평가', 5)
        g_book = self._general_book('일반평가책')
        r_book = self._rec_book('추천평가책')
        c_book = self._challenge_book('도전평가책')
        self.assertEqual(classify_program_type(general_child, g_book), 'general')
        self.assertEqual(classify_program_type(rec_child, r_book), 'recommended')
        self.assertEqual(classify_program_type(challenge_child, c_book), 'challenge')

        self._start(general_child, g_book)
        g, _ = self._complete(general_child, difficulty=2, fun=4)
        self._start(rec_child, r_book)
        r, _ = self._complete(rec_child, difficulty=5, fun=1)
        self._start(challenge_child, c_book)
        c, _ = self._complete(challenge_child, difficulty=3, fun=3)
        self.assertEqual(g.program_type, 'general')
        self.assertEqual(r.program_type, 'recommended')
        self.assertEqual(c.program_type, 'challenge')
        self.assertEqual((g.difficulty_rating, g.fun_rating), (2, 4))
        self.assertEqual((r.difficulty_rating, r.fun_rating), (5, 1))
        self.assertEqual((c.difficulty_rating, c.fun_rating), (3, 3))
        self.assertEqual(classify_program_type(rec_child, r_book), 'recommended')
        self.assertEqual(classify_program_type(challenge_child, c_book), 'challenge')

    def test_ratings_do_not_change_recommended_or_challenge_points(self):
        rec_child = self._child('추천포인트', 3)
        rec_book = self._rec_book(grade_band='2-3')
        rec, _ = self._start(rec_child, rec_book)
        approve_recommended_reward(rec, self.teacher, EVENT_RECOMMENDED_START)
        rec, _ = self._complete(rec_child, difficulty=5, fun=1)
        approve_recommended_reward(rec, self.teacher, EVENT_RECOMMENDED_COMPLETE)
        rec_points = DailyPoints.query.filter_by(child_id=rec_child.id).one().manual_points

        plain_child = self._child('추천비교', 3)
        plain, _ = self._start(plain_child, self._rec_book(grade_band='2-3'))
        approve_recommended_reward(plain, self.teacher, EVENT_RECOMMENDED_START)
        plain, _ = self._complete(plain_child)
        approve_recommended_reward(plain, self.teacher, EVENT_RECOMMENDED_COMPLETE)
        self.assertEqual(rec_points, DailyPoints.query.filter_by(child_id=plain_child.id).one().manual_points)
        self.assertEqual(rec.program_type, 'recommended')

        ch_child = self._child('도전파인트', 5)
        ch, _ = self._start(ch_child, self._challenge_book())
        set_reward_mode(ch, 'points', self.teacher)
        approve_recommended_reward(ch, self.teacher, EVENT_CHALLENGE_START)
        ch, _ = self._complete(ch_child, difficulty=1, fun=5)
        approve_recommended_reward(ch, self.teacher, EVENT_CHALLENGE_COMPLETE)
        ch_points = DailyPoints.query.filter_by(child_id=ch_child.id).one().manual_points

        ch_plain = self._child('도전비교', 5)
        started, _ = self._start(ch_plain, self._challenge_book())
        set_reward_mode(started, 'points', self.teacher)
        approve_recommended_reward(started, self.teacher, EVENT_CHALLENGE_START)
        started, _ = self._complete(ch_plain)
        approve_recommended_reward(started, self.teacher, EVENT_CHALLENGE_COMPLETE)
        self.assertEqual(ch_points, DailyPoints.query.filter_by(child_id=ch_plain.id).one().manual_points)

    def test_ratings_do_not_change_exemption_eligibility(self):
        rated = self._child('면제평가', 5)
        plain = self._child('면제비교', 5)
        for child, ratings in (
            (rated, {'difficulty': 5, 'fun': 1}),
            (plain, {}),
        ):
            reading, _ = self._start(child, self._rec_book())
            set_reward_mode(reading, 'exemption', self.teacher)
            self._complete(child, **ratings)
        self.assertEqual(
            len(unconsumed_qualifying_completions(rated.id, 'recommended')),
            len(unconsumed_qualifying_completions(plain.id, 'recommended')),
        )
        self.assertEqual(len(unconsumed_qualifying_completions(rated.id, 'recommended')), 1)

    def _assert_in_progress_editor_rating_ui(self, html):
        self.assertIn('이 책을 다 읽었어요', html)
        self.assertIn('id="reading-completed"', html)
        self.assertIn('name="completed"', html)
        self.assertIn('id="reading-rating-panel"', html)
        self.assertIn('이 책은 얼마나 어려웠나요?', html)
        self.assertIn('이 책은 얼마나 재미있었나요?', html)
        self.assertIn('1 쉬움', html)
        self.assertIn('5 어려움', html)
        self.assertIn('1 별로', html)
        self.assertIn('5 재미있음', html)
        self.assertIn('.reading-rating-panel { display: none; }', html)
        self.assertIn("getElementById('reading-completed')", html)
        self.assertIn("getElementById('reading-rating-panel')", html)
        self.assertIn("classList.add('is-visible')", html)
        self.assertNotRegex(html, r'id="reading-rating-panel"[^>]*\bhidden\b')
        self.assertNotIn('매우 쉬웠어요', html)
        self.assertNotIn('매우 재미있었어요', html)
        for score in range(1, 6):
            self.assertIn(f'name="difficulty_rating" id="difficulty-{score}" value="{score}"', html)
            self.assertIn(f'name="fun_rating" id="fun-{score}" value="{score}"', html)
            self.assertIn(f'for="difficulty-{score}">{score}</label>', html)
            self.assertIn(f'for="fun-{score}">{score}</label>', html)

    def test_teacher_in_progress_editor_always_shows_rating_controls(self):
        child = self._child('교사평가UI', 3)
        self._start(child, self._general_book('교사평가책'))
        self._login(self.teacher)
        resp = self.client.get(f'/children/{child.id}/reading')
        self.assertEqual(resp.status_code, 200)
        self._assert_in_progress_editor_rating_ui(resp.get_data(as_text=True))

    def test_viewer_in_progress_editor_always_shows_rating_controls(self):
        child = self._child('학생평가UI', 3)
        self._start(child, self._general_book('학생평가책'))
        self._login(self.viewer)
        self._verify(child)
        resp = self.client.get(f'/viewer/report/{child.viewer_slug}/reading')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self._assert_in_progress_editor_rating_ui(html)
        self.assertIn(f'/viewer/report/{child.viewer_slug}/reading/save', html)

    def test_ratings_ignored_when_not_completed(self):
        child = self._child('미완독평가무시', 3)
        self._start(child, self._general_book())
        reading, _ = save_today(
            child.id, self.teacher.id, 'teacher',
            activity_date=self.today, mark_completed=False,
            difficulty_rating=5, fun_rating=1,
        )
        self.assertEqual(reading.status, STATUS_IN_PROGRESS)
        self.assertIsNone(reading.difficulty_rating)
        self.assertIsNone(reading.fun_rating)

    def test_viewer_http_save_without_complete_ignores_ratings(self):
        child = self._child('미완독HTTP', 3)
        self._start(child, self._general_book())
        reading = ChildReading.query.filter_by(child_id=child.id).one()
        client = self._authed_client(self.viewer)
        self._verify_on(client, child)
        resp = client.post(
            f'/viewer/report/{child.viewer_slug}/reading/save',
            data={
                'child_reading_id': str(reading.id),
                'difficulty_rating': '5',
                'fun_rating': '1',
                'review_text': '아직 읽는 중',
            },
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        reading = ChildReading.query.get(reading.id)
        self.assertEqual(reading.status, STATUS_IN_PROGRESS)
        self.assertIsNone(reading.difficulty_rating)
        self.assertIsNone(reading.fun_rating)

    def test_teacher_history_and_editor_show_ratings(self):
        both = self._child('표시둘', 5)
        only_d = self._child('표시난이도', 3)
        none = self._child('표시없음', 3)
        self._start(both, self._rec_book('표시둘책'))
        self._complete(both, difficulty=4, fun=5)
        self._start(only_d, self._general_book('표시난이도책'))
        self._complete(only_d, difficulty=2)
        self._start(none, self._general_book('표시없음책'))
        self._complete(none)

        self._login(self.teacher)
        editor_child = self._child('평가UI', 3)
        self._start(editor_child, self._general_book())
        editor = self.client.get(f'/children/{editor_child.id}/reading').get_data(as_text=True)
        self.assertIn('이 책은 얼마나 어려웠나요?', editor)
        self.assertIn('이 책은 얼마나 재미있었나요?', editor)
        self.assertIn('1 쉬움', editor)
        self.assertIn('5 재미있음', editor)

        teacher_html = self.client.get(f'/children/{both.id}/reading/history').get_data(as_text=True)
        self.assertIn('난이도 4/5', teacher_html)
        self.assertIn('재미 5/5', teacher_html)

        none_html = self.client.get(f'/children/{none.id}/reading/history').get_data(as_text=True)
        self.assertIn('표시없음책', none_html)
        self.assertNotIn('난이도 ', none_html)
        self.assertNotIn('재미 ', none_html)

        only_html = self.client.get(f'/children/{only_d.id}/reading/history').get_data(as_text=True)
        self.assertIn('난이도 2/5', only_html)
        self.assertNotIn('재미 ', only_html)

    def test_viewer_history_shows_own_ratings_and_blocks_other_child(self):
        both = self._child('표시둘', 5)
        other = self._child('다른아동', 3)
        self._start(both, self._rec_book('표시둘책'))
        self._complete(both, difficulty=4, fun=5)
        self._start(other, self._general_book('비밀책'))
        self._complete(other, difficulty=5, fun=5)

        self._login(self.viewer)
        self._verify(both)
        viewer_html = self.client.get(
            f'/viewer/report/{both.viewer_slug}/reading/history'
        ).get_data(as_text=True)
        self.assertIn('난이도 4/5', viewer_html)
        self.assertIn('재미 5/5', viewer_html)
        self.assertNotIn('비밀책', viewer_html)
        blocked = self.client.get(
            f'/viewer/report/{other.viewer_slug}/reading/history',
            follow_redirects=False,
        )
        self.assertEqual(blocked.status_code, 403)

    def test_incentives_off_still_saves_and_shows_ratings(self):
        child = self._child('플래그오프평가', 3)
        self._start(child, self._general_book('오프평가책'))
        with mock.patch.dict(os.environ, {'CLC_READING_INCENTIVES_ENABLED': '0'}):
            reading, _ = self._complete(child, difficulty=3, fun=4)
            self.assertEqual(reading.difficulty_rating, 3)
            self.assertEqual(reading.fun_rating, 4)
            viewer = self._authed_client(self.viewer)
            self._verify_on(viewer, child)
            html = viewer.get(
                f'/viewer/report/{child.viewer_slug}/reading/history'
            ).get_data(as_text=True)
            self.assertIn('난이도 3/5', html)
            self.assertIn('재미 4/5', html)

    def test_viewer_http_complete_with_ratings(self):
        child = self._child('작성회귀', 3)
        book = self._general_book('작성회귀책')
        client = self._authed_client(self.viewer)
        self._verify_on(client, child)
        start = client.post(
            f'/viewer/report/{child.viewer_slug}/reading/start',
            data={'book_id': str(book.id), 'review_text': '읽는 중'},
            follow_redirects=False,
        )
        self.assertEqual(start.status_code, 302)
        reading = ChildReading.query.filter_by(child_id=child.id).one()
        save = client.post(
            f'/viewer/report/{child.viewer_slug}/reading/save',
            data={
                'child_reading_id': str(reading.id),
                'completed': '1',
                'difficulty_rating': '5',
                'fun_rating': '1',
                'review_text': '다 읽음',
            },
            follow_redirects=False,
        )
        self.assertEqual(save.status_code, 302)
        reading = ChildReading.query.get(reading.id)
        self.assertEqual(reading.status, STATUS_COMPLETED)
        self.assertEqual(reading.difficulty_rating, 5)
        self.assertEqual(reading.fun_rating, 1)

    def test_teacher_http_complete_without_ratings(self):
        other = self._child('교사대신', 4)
        other_book = self._general_book('대신책')
        client = self._authed_client(self.teacher)
        delegated = client.post(
            f'/children/{other.id}/reading/start',
            data={'book_id': str(other_book.id), 'date': self.today.isoformat()},
            follow_redirects=False,
        )
        self.assertEqual(delegated.status_code, 302)
        teacher_reading = ChildReading.query.filter_by(child_id=other.id).one()
        finish = client.post(
            f'/children/{other.id}/reading/save',
            data={
                'child_reading_id': str(teacher_reading.id),
                'date': self.today.isoformat(),
                'completed': '1',
            },
            follow_redirects=False,
        )
        self.assertEqual(finish.status_code, 302)
        teacher_reading = ChildReading.query.get(teacher_reading.id)
        self.assertEqual(teacher_reading.status, STATUS_COMPLETED)
        self.assertIsNone(teacher_reading.difficulty_rating)
        self.assertIsNone(teacher_reading.fun_rating)

    def test_viewer_http_rejects_invalid_rating(self):
        bad_child = self._child('잘못된값', 3)
        self._start(bad_child, self._general_book())
        reading = ChildReading.query.filter_by(child_id=bad_child.id).one()
        client = self._authed_client(self.viewer)
        self._verify_on(client, bad_child)
        bad = client.post(
            f'/viewer/report/{bad_child.viewer_slug}/reading/save',
            data={
                'child_reading_id': str(reading.id),
                'completed': '1',
                'difficulty_rating': '6',
            },
            follow_redirects=False,
        )
        self.assertEqual(bad.status_code, 302)
        reading = ChildReading.query.get(reading.id)
        self.assertEqual(reading.status, STATUS_IN_PROGRESS)
        self.assertIsNone(reading.difficulty_rating)

    def test_backup_restore_keeps_ratings(self):
        child = self._child('백업평가', 3)
        self._start(child, self._general_book('백업평가책'))
        reading, _ = self._complete(child, difficulty=2, fun=5)
        backup_data, error = get_backup_data()
        self.assertIsNone(error)
        self.assertEqual(backup_data['child_readings'][0]['difficulty_rating'], 2)
        self.assertEqual(backup_data['child_readings'][0]['fun_rating'], 5)
        ReadingDay.query.delete()
        ChildReading.query.delete()
        Book.query.delete()
        db.session.commit()
        from features.books.restore import restore_books_from_backup_data
        restore_books_from_backup_data(backup_data)
        restore_readings_from_backup_data(backup_data)
        db.session.commit()
        restored = ChildReading.query.one()
        self.assertEqual(restored.difficulty_rating, 2)
        self.assertEqual(restored.fun_rating, 5)
        self.assertEqual(restored.id, reading.id)

    def test_ensure_adds_nullable_columns_and_keeps_existing_null(self):
        from sqlalchemy import create_engine, text
        with tempfile.TemporaryDirectory(prefix='clc_rating_ensure_') as tmp:
            engine = create_engine('sqlite:///' + (Path(tmp) / 'old.db').resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text(
                        'CREATE TABLE child_reading ('
                        'id INTEGER PRIMARY KEY, child_id INTEGER, status VARCHAR(32))'
                    ))
                    conn.execute(text(
                        "INSERT INTO child_reading (id, child_id, status) "
                        "VALUES (1, 9, 'completed')"
                    ))
                self.assertTrue(ensure_child_reading_rating_columns(engine))
                self.assertFalse(ensure_child_reading_rating_columns(engine))
                with engine.connect() as conn:
                    cols = {row[1] for row in conn.execute(text('PRAGMA table_info(child_reading)'))}
                    row = conn.execute(text(
                        'SELECT difficulty_rating, fun_rating FROM child_reading WHERE id=1'
                    )).fetchone()
            finally:
                engine.dispose()
        self.assertIn('difficulty_rating', cols)
        self.assertIn('fun_rating', cols)
        self.assertIsNone(row[0])
        self.assertIsNone(row[1])

    def test_alembic_adds_rating_columns_without_backfill(self):
        migration_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/c2d9f01a7b44_add_child_reading_experience_ratings.py'
        )
        spec = importlib.util.spec_from_file_location('rating_migration', migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine, text

        with tempfile.TemporaryDirectory(prefix='clc_rating_mig_') as tmp:
            engine = create_engine('sqlite:///' + (Path(tmp) / 'fresh.db').resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text(
                        'CREATE TABLE child_reading ('
                        'id INTEGER PRIMARY KEY, status VARCHAR(32))'
                    ))
                    conn.execute(text(
                        "INSERT INTO child_reading (id, status) VALUES (1, 'completed')"
                    ))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    cols = {row[1] for row in conn.execute(text('PRAGMA table_info(child_reading)'))}
                    row = conn.execute(text(
                        'SELECT difficulty_rating, fun_rating FROM child_reading WHERE id=1'
                    )).fetchone()
            finally:
                engine.dispose()
        self.assertIn('difficulty_rating', cols)
        self.assertIn('fun_rating', cols)
        self.assertIsNone(row[0])
        self.assertIsNone(row[1])


if __name__ == '__main__':
    unittest.main()
