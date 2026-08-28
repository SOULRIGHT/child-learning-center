"""Recent 3-window growth facts. UI/insight/threshold 없음."""
from __future__ import annotations

import inspect
import unittest
from datetime import date, timedelta
from pathlib import Path

from tests.helpers import bootstrap_test_app, local_development_sqlite_path, resolved_engine_sqlite_path

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    POLICY_VERSION_GENERAL_V2,
    STATUS_COMPLETED,
    Book,
    ChildReading,
    LearningProgressEntry,
    LearningSubject,
    ReadingDay,
)
from features.growth.copy import READING_ACTIVITY_INCREASE  # noqa: E402
from features.growth.insights import generate_insight_candidates, top_candidates  # noqa: E402
from features.growth.metrics import metrics_bundle, reading_metrics  # noqa: E402
from features.growth.recent_window_bests import (  # noqa: E402
    STATUS_BOOK_CHANGED,
    STATUS_INSUFFICIENT_HISTORY,
    STATUS_OK,
    recent_window_bests,
)
from features.growth.windows import recent_fixed_windows  # noqa: E402
from features.progress.service import ensure_default_subjects  # noqa: E402


AS_OF = date(2026, 12, 15)
CURRENT = {'start': date(2026, 11, 16), 'end': date(2026, 12, 15)}
PREV1 = {'start': date(2026, 10, 17), 'end': date(2026, 11, 15)}
PREV2 = {'start': date(2026, 9, 17), 'end': date(2026, 10, 16)}
BOOK = '우등생 수학 3-2'
BOOK_OLD = '우등생 수학 3-1'
COVERAGE_DAY = date(2026, 9, 10)


class RecentWindowBestsTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.assertNotEqual(resolved_engine_sqlite_path(db), local_development_sqlite_path())
        ensure_default_subjects()
        self.teacher = User(
            username='rwb_teacher',
            name='구간최고교사',
            role='돌봄선생님',
            email='rwb@example.test',
            password_hash='',
        )
        self.child = Child(name='구간최고아동', grade=3, viewer_slug='rwbrwbrwbrwbrwbrwbrwbrw')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        self.math = LearningSubject.query.filter_by(key='math').one()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _bests(self):
        return recent_window_bests(self.child.id, as_of=AS_OF, window_days=30)

    def _book(self, title):
        book = Book(title=title, normalized_key=title, is_active=True)
        db.session.add(book)
        db.session.flush()
        return book

    def _reading_days(self, dates, *, title='구간책'):
        book = self._book(title)
        reading = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            started_on=dates[0],
            status='in_progress',
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        for on in dates:
            db.session.add(ReadingDay(
                child_reading_id=reading.id,
                date=on,
                created_by_user_id=self.teacher.id,
                actor_type=ACTOR_TEACHER,
                policy_version=POLICY_VERSION_GENERAL_V2,
            ))
        db.session.commit()
        return reading

    def _completed(self, title, completed_on, *, started_on=None):
        book = self._book(title)
        started = started_on or (completed_on - timedelta(days=2))
        reading = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            started_on=started,
            completed_on=completed_on,
            status=STATUS_COMPLETED,
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        db.session.add(ReadingDay(
            child_reading_id=reading.id,
            date=completed_on,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        ))
        db.session.commit()
        return reading

    def _points(self, on, total, *, korean=None, stored_total=None, manual_points=0, manual_history='[]'):
        korean = total if korean is None else korean
        db.session.add(DailyPoints(
            child_id=self.child.id,
            date=on,
            korean_points=korean,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=manual_points,
            manual_history=manual_history,
            total_points=stored_total if stored_total is not None else total,
            created_by=self.teacher.id,
        ))
        db.session.commit()

    def _progress(self, on, *, page, title=BOOK):
        db.session.add(LearningProgressEntry(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            recorded_on=on,
            textbook_title=title,
            page=page,
            created_by_user_id=self.teacher.id,
        ))
        db.session.commit()

    def test_three_fixed_windows_have_no_gap_or_overlap(self):
        payload = self._bests()
        self.assertEqual(payload['window_count'], 3)
        self.assertEqual(payload['lookback_days'], 90)
        self.assertEqual(payload['current_window']['start'], CURRENT['start'])
        self.assertEqual(payload['current_window']['end'], CURRENT['end'])
        self.assertEqual(payload['previous_1_window']['start'], PREV1['start'])
        self.assertEqual(payload['previous_1_window']['end'], PREV1['end'])
        self.assertEqual(payload['previous_2_window']['start'], PREV2['start'])
        self.assertEqual(payload['previous_2_window']['end'], PREV2['end'])
        self.assertEqual(payload['previous_1_window']['end'], CURRENT['start'] - timedelta(days=1))
        self.assertEqual(payload['previous_2_window']['end'], PREV1['start'] - timedelta(days=1))
        windows = recent_fixed_windows(AS_OF, 30, count=3)
        self.assertEqual((windows[0]['end'] - windows[2]['start']).days + 1, 90)

    def test_reading_days_strict_greater_tie_lower_and_margin(self):
        self._reading_days(
            [COVERAGE_DAY]
            + [PREV2['start'] + timedelta(days=offset) for offset in range(3)]
            + [PREV1['start'] + timedelta(days=offset) for offset in range(5)]
            + [CURRENT['start'] + timedelta(days=offset) for offset in range(8)]
        )
        days = self._bests()['reading_days']
        self.assertEqual(days['status'], STATUS_OK)
        self.assertEqual(days['current']['value'], 8)
        self.assertEqual(days['previous_1']['value'], 5)
        self.assertEqual(days['previous_2']['value'], 3)
        self.assertEqual(days['historical_best'], 5)
        self.assertEqual(days['historical_best_window']['start'], PREV1['start'])
        self.assertEqual(days['margin'], 3)
        self.assertTrue(days['is_recent_window_best'])
        self.assertEqual(days['source'], 'reading_day.date')

    def test_reading_days_tie_is_not_best_and_uses_recent_historical_window(self):
        self._reading_days(
            [COVERAGE_DAY]
            + [PREV2['start'] + timedelta(days=offset) for offset in range(5)]
            + [PREV1['start'] + timedelta(days=offset) for offset in range(5)]
            + [CURRENT['start'] + timedelta(days=offset) for offset in range(5)]
        )
        days = self._bests()['reading_days']
        self.assertFalse(days['is_recent_window_best'])
        self.assertEqual(days['margin'], 0)
        self.assertEqual(days['historical_best'], 5)
        self.assertEqual(days['historical_best_window']['start'], PREV1['start'])

        db.session.query(ReadingDay).delete()
        db.session.query(ChildReading).delete()
        db.session.commit()
        self._reading_days(
            [COVERAGE_DAY]
            + [PREV2['start'] + timedelta(days=offset) for offset in range(4)]
            + [PREV1['start'] + timedelta(days=offset) for offset in range(2)]
            + [CURRENT['start'] + timedelta(days=offset) for offset in range(3)]
        )
        lower = self._bests()['reading_days']
        self.assertFalse(lower['is_recent_window_best'])
        self.assertEqual(lower['historical_best'], 4)
        self.assertEqual(lower['historical_best_window']['start'], PREV2['start'])
        self.assertEqual(lower['margin'], -1)

    def test_reading_days_unique_dates_and_future_excluded(self):
        book_a = self._book('같은날A')
        book_b = self._book('같은날B')
        for index, book in enumerate((book_a, book_b)):
            reading = ChildReading(
                child_id=self.child.id,
                book_id=book.id,
                started_on=COVERAGE_DAY,
                completed_on=CURRENT['start'] if index == 0 else None,
                status=STATUS_COMPLETED if index == 0 else 'in_progress',
                policy_version=POLICY_VERSION_GENERAL_V2,
                created_by_user_id=self.teacher.id,
                actor_type=ACTOR_TEACHER,
            )
            db.session.add(reading)
            db.session.flush()
            for on in (COVERAGE_DAY, PREV2['start'], PREV1['start'], CURRENT['start'], date(2026, 12, 20)):
                db.session.add(ReadingDay(
                    child_reading_id=reading.id,
                    date=on,
                    created_by_user_id=self.teacher.id,
                    actor_type=ACTOR_TEACHER,
                    policy_version=POLICY_VERSION_GENERAL_V2,
                ))
        db.session.commit()
        days = self._bests()['reading_days']
        self.assertEqual(days['current']['value'], 1)
        self.assertEqual(days['previous_1']['value'], 1)
        self.assertEqual(days['previous_2']['value'], 1)
        self.assertFalse(days['is_recent_window_best'])

    def test_reading_insufficient_history_is_not_fake_zero(self):
        self._reading_days([CURRENT['start'] + timedelta(days=offset) for offset in range(4)])
        days = self._bests()['reading_days']
        self.assertEqual(days['status'], STATUS_INSUFFICIENT_HISTORY)
        self.assertIsNone(days['is_recent_window_best'])
        self.assertIsNone(days['current']['value'])
        self.assertFalse(days['current']['available'])
        self.assertIsNone(days['previous_2']['value'])

        db.session.query(ReadingDay).delete()
        db.session.query(ChildReading).delete()
        db.session.commit()
        self._reading_days(
            [COVERAGE_DAY]
            + [PREV1['start'] + timedelta(days=offset) for offset in range(2)]
            + [CURRENT['start'] + timedelta(days=offset) for offset in range(4)]
        )
        zero = self._bests()['reading_days']
        self.assertEqual(zero['status'], STATUS_OK)
        self.assertEqual(zero['previous_2']['value'], 0)
        self.assertTrue(zero['previous_2']['available'])
        self.assertTrue(zero['is_recent_window_best'])
        self.assertEqual(zero['margin'], 2)

    def test_completions_use_completed_on_not_reading_days(self):
        self._completed('이전2완독', PREV2['start'])
        self._completed('이전1완독A', PREV1['start'])
        self._completed('이전1완독B', PREV1['start'] + timedelta(days=1))
        self._completed('최근완독A', CURRENT['start'])
        self._completed('최근완독B', CURRENT['start'] + timedelta(days=1))
        self._completed('최근완독C', CURRENT['start'] + timedelta(days=2))
        self._completed('미래완독', date(2026, 12, 20))
        reading = self._reading_days(
            [COVERAGE_DAY, CURRENT['start'] + timedelta(days=10)],
            title='완독아닌활동일',
        )
        completions = self._bests()['reading_completions']
        self.assertEqual(completions['current']['value'], 3)
        self.assertEqual(completions['previous_1']['value'], 2)
        self.assertEqual(completions['previous_2']['value'], 1)
        self.assertTrue(completions['is_recent_window_best'])
        self.assertEqual(completions['source'], 'child_reading.completed_on')
        self.assertEqual(reading_metrics(self.child.id, as_of=AS_OF)['current']['reading_days'], 4)

    def test_points_canonical_dedupe_and_stored_total_ignored(self):
        self._points(COVERAGE_DAY, 10)
        self._points(PREV2['start'], 20)
        self._points(PREV1['start'], 0, korean=0, stored_total=999, manual_points=80, manual_history='[{"points": 30}]')
        self._points(CURRENT['start'], 50, stored_total=9999)
        self._points(CURRENT['start'], 40, stored_total=1)
        points = self._bests()['points']
        self.assertEqual(points['previous_2']['value'], 20)
        self.assertEqual(points['previous_1']['value'], 30)
        self.assertEqual(points['current']['value'], 40)
        self.assertTrue(points['is_recent_window_best'])
        self.assertEqual(points['historical_best'], 30)
        self.assertEqual(points['margin'], 10)
        self.assertEqual(points['source'], 'daily_points.date')

    def test_points_actual_zero_vs_insufficient(self):
        self._points(CURRENT['start'], 80)
        missing = self._bests()['points']
        self.assertEqual(missing['status'], STATUS_INSUFFICIENT_HISTORY)
        self.assertIsNone(missing['current']['value'])

        self._points(COVERAGE_DAY, 0)
        self._points(PREV1['start'], 10)
        zero = self._bests()['points']
        self.assertEqual(zero['status'], STATUS_OK)
        self.assertEqual(zero['previous_2']['value'], 0)
        self.assertTrue(zero['is_recent_window_best'])

    def test_learning_same_book_strict_greater_and_tie(self):
        self._progress(date(2026, 9, 10), page=40)
        self._progress(date(2026, 10, 10), page=70)
        self._progress(date(2026, 11, 10), page=90)
        self._progress(date(2026, 12, 10), page=130)
        math = self._bests()['learning']['math']
        self.assertEqual(math['status'], STATUS_OK)
        self.assertEqual(math['previous_2']['value'], 30)
        self.assertEqual(math['previous_1']['value'], 20)
        self.assertEqual(math['current']['value'], 40)
        self.assertEqual(math['historical_best'], 30)
        self.assertEqual(math['historical_best_window']['start'], PREV2['start'])
        self.assertEqual(math['margin'], 10)
        self.assertTrue(math['is_recent_window_best'])
        self.assertEqual(math['current']['textbook_title'], BOOK)

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        self._progress(date(2026, 9, 10), page=40)
        self._progress(date(2026, 10, 10), page=70)
        self._progress(date(2026, 11, 10), page=100)
        self._progress(date(2026, 12, 10), page=130)
        tied = self._bests()['learning']['math']
        self.assertEqual(tied['current']['value'], 30)
        self.assertEqual(tied['historical_best'], 30)
        self.assertFalse(tied['is_recent_window_best'])
        self.assertEqual(tied['historical_best_window']['start'], PREV1['start'])

    def test_learning_book_change_and_stale_are_incomparable(self):
        self._progress(date(2026, 9, 10), page=40, title=BOOK_OLD)
        self._progress(date(2026, 9, 27), page=10)
        self._progress(date(2026, 10, 10), page=150, title=BOOK_OLD)
        self._progress(date(2026, 11, 10), page=40)
        self._progress(date(2026, 12, 10), page=80)
        changed = self._bests()['learning']['math']
        self.assertEqual(changed['status'], STATUS_BOOK_CHANGED)
        self.assertIsNone(changed['is_recent_window_best'])
        self.assertTrue(changed['current']['available'])
        self.assertTrue(changed['previous_2']['available'])

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        self._progress(date(2026, 8, 1), page=10)
        self._progress(date(2026, 10, 10), page=40)
        self._progress(date(2026, 11, 10), page=70)
        self._progress(date(2026, 12, 10), page=100)
        stale = self._bests()['learning']['math']
        self.assertEqual(stale['status'], STATUS_INSUFFICIENT_HISTORY)
        self.assertFalse(stale['previous_2']['available'])
        self.assertIsNone(stale['is_recent_window_best'])

    def test_learning_zero_and_negative_raw_facts(self):
        self._progress(date(2026, 9, 10), page=80)
        self._progress(date(2026, 10, 10), page=80)
        self._progress(date(2026, 11, 10), page=80)
        self._progress(date(2026, 12, 10), page=80)
        zero = self._bests()['learning']['math']
        self.assertEqual(zero['current']['value'], 0)
        self.assertEqual(zero['previous_1']['value'], 0)
        self.assertEqual(zero['previous_2']['value'], 0)
        self.assertFalse(zero['is_recent_window_best'])
        self.assertEqual(zero['margin'], 0)

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        self._progress(date(2026, 9, 10), page=100)
        self._progress(date(2026, 10, 10), page=97)
        self._progress(date(2026, 11, 10), page=94)
        self._progress(date(2026, 12, 10), page=93)
        negative = self._bests()['learning']['math']
        self.assertEqual(negative['previous_2']['value'], -3)
        self.assertEqual(negative['previous_1']['value'], -3)
        self.assertEqual(negative['current']['value'], -1)
        self.assertTrue(negative['is_recent_window_best'])
        self.assertEqual(negative['margin'], 2)

    def test_bundle_and_insights_unchanged(self):
        self._reading_days(
            [PREV1['start'] + timedelta(days=offset) for offset in range(6)]
            + [CURRENT['start'] + timedelta(days=offset) for offset in range(11)]
        )
        bundle = metrics_bundle(self.child.id, as_of=AS_OF, window_days=30)
        self.assertIn('recent_window_bests', bundle)
        self.assertEqual(bundle['reading']['current']['reading_days'], 11)
        ids = [item.id for item in generate_insight_candidates(bundle)]
        without = {
            key: value for key, value in bundle.items() if key != 'recent_window_bests'
        }
        self.assertEqual(ids, [item.id for item in generate_insight_candidates(without)])
        self.assertEqual(
            [item.id for item in top_candidates(generate_insight_candidates(bundle))],
            [item.id for item in top_candidates(generate_insight_candidates(without))],
        )
        self.assertIn(READING_ACTIVITY_INCREASE, ids)
        source = inspect.getsource(recent_window_bests)
        self.assertNotIn('generate_insight_candidates', source)
        self.assertNotIn('LearningRecord', source)
        self.assertNotIn('역대 최고', source)
        html = Path(__file__).resolve().parents[1].joinpath('templates', 'growth', 'report.html').read_text(encoding='utf-8')
        self.assertNotIn('recent_window_best', html)
        self.assertNotIn('is_recent_window_best', html)
