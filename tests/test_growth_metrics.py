"""Growth Step 1: windows + deterministic metrics. UI/insight/LLM 없음."""
from __future__ import annotations

import inspect
import unittest
from datetime import date, timedelta

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, LearningRecord, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    POLICY_VERSION_GENERAL_V2,
    PROGRAM_TYPE_CHALLENGE,
    PROGRAM_TYPE_GENERAL,
    PROGRAM_TYPE_RECOMMENDED,
    STATUS_ABANDONED,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    Book,
    ChildReading,
    LearningProgressEntry,
    ReadingDay,
)
from features.dates import kst_today  # noqa: E402
from features.growth import metrics as growth_metrics  # noqa: E402
from features.growth.metrics import points_metrics, progress_metrics, reading_metrics  # noqa: E402
from features.growth.windows import (  # noqa: E402
    coverage_comparable,
    current_window,
    date_in_window,
    on_or_before,
    previous_window,
    resolve_as_of,
)
from features.progress.service import ensure_default_subjects  # noqa: E402
from feature_models import LearningSubject  # noqa: E402


AS_OF = date(2026, 8, 22)
CURRENT_START = date(2026, 7, 24)
CURRENT_END = date(2026, 8, 22)
PREV_START = date(2026, 6, 24)
PREV_END = date(2026, 7, 23)


class GrowthWindowsTests(unittest.TestCase):
    def test_current_and_previous_inclusive_boundaries(self):
        current = current_window(AS_OF, 30)
        previous = previous_window(AS_OF, 30)
        self.assertEqual(current['start'], CURRENT_START)
        self.assertEqual(current['end'], CURRENT_END)
        self.assertEqual(current['days'], 30)
        self.assertEqual(previous['start'], PREV_START)
        self.assertEqual(previous['end'], PREV_END)
        self.assertEqual((current['end'] - current['start']).days + 1, 30)
        self.assertEqual((previous['end'] - previous['start']).days + 1, 30)
        self.assertEqual(previous['end'], current['start'] - timedelta(days=1))

    def test_window_days_is_not_hardcoded_to_30(self):
        current = current_window(AS_OF, 7)
        self.assertEqual(current['start'], date(2026, 8, 16))
        self.assertEqual(current['end'], AS_OF)
        previous = previous_window(AS_OF, 7)
        self.assertEqual(previous['start'], date(2026, 8, 9))
        self.assertEqual(previous['end'], date(2026, 8, 15))

    def test_date_in_window_includes_ends_excludes_outside(self):
        window = current_window(AS_OF, 30)
        self.assertTrue(date_in_window(AS_OF, window))
        self.assertTrue(date_in_window(CURRENT_START, window))
        self.assertTrue(date_in_window(PREV_END, previous_window(AS_OF, 30)))
        self.assertFalse(date_in_window(PREV_END, window))
        self.assertFalse(date_in_window(date(2026, 8, 23), window))
        self.assertFalse(date_in_window(None, window))

    def test_resolve_as_of_uses_kst_today_not_utcnow(self):
        self.assertEqual(resolve_as_of(None), kst_today())
        self.assertEqual(resolve_as_of(AS_OF), AS_OF)
        source = inspect.getsource(resolve_as_of)
        self.assertNotIn('utcnow', source)

    def test_coverage_comparable(self):
        previous = previous_window(AS_OF, 30)
        self.assertFalse(coverage_comparable(None, previous))
        self.assertFalse(coverage_comparable(date(2026, 6, 25), previous))
        self.assertTrue(coverage_comparable(PREV_START, previous))
        self.assertTrue(coverage_comparable(date(2026, 6, 1), previous))

    def test_on_or_before_is_snapshot_boundary(self):
        self.assertTrue(on_or_before(AS_OF, AS_OF))
        self.assertTrue(on_or_before(CURRENT_START, AS_OF))
        self.assertFalse(on_or_before(date(2026, 8, 23), AS_OF))
        self.assertFalse(on_or_before(None, AS_OF))


class GrowthMetricsTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='growth_teacher',
            name='성장교사',
            role='돌봄선생님',
            email='growth-teacher@example.test',
            password_hash='',
        )
        self.child = Child(name='성장아동', grade=3, viewer_slug='gggggggggggggggggggggggg')
        self.other = Child(name='다른아동', grade=4, viewer_slug='hhhhhhhhhhhhhhhhhhhhhhhh')
        db.session.add_all([self.teacher, self.child, self.other])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _book(self, title):
        book = Book(title=title, normalized_key=title, is_active=True)
        db.session.add(book)
        db.session.flush()
        return book

    def _reading(
        self,
        book,
        *,
        started_on,
        status=STATUS_IN_PROGRESS,
        completed_on=None,
        ended_on=None,
        program_type=PROGRAM_TYPE_GENERAL,
        difficulty_rating=None,
        fun_rating=None,
        child=None,
    ):
        row = ChildReading(
            child_id=(child or self.child).id,
            book_id=book.id,
            started_on=started_on,
            completed_on=completed_on,
            ended_on=ended_on,
            status=status,
            program_type=program_type,
            policy_version=POLICY_VERSION_GENERAL_V2,
            difficulty_rating=difficulty_rating,
            fun_rating=fun_rating,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(row)
        db.session.flush()
        return row

    def _day(self, reading, on, child=None):
        row = ReadingDay(
            child_reading_id=reading.id,
            date=on,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        )
        db.session.add(row)
        db.session.flush()
        return row

    def _daily(self, on, *, korean=0, math=0, reading=0, manual=0, child=None, total=None):
        subject_total = korean + math + reading + manual
        row = DailyPoints(
            child_id=(child or self.child).id,
            date=on,
            korean_points=korean,
            math_points=math,
            ssen_points=0,
            reading_points=reading,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=manual,
            manual_history='[]',
            total_points=total if total is not None else subject_total,
            created_by=self.teacher.id,
        )
        db.session.add(row)
        db.session.flush()
        return row

    def _subject(self, key):
        ensure_default_subjects()
        return LearningSubject.query.filter_by(key=key).one()

    def _progress(self, subject, on, *, title='교재', page=10):
        row = LearningProgressEntry(
            child_id=self.child.id,
            learning_subject_id=subject.id,
            recorded_on=on,
            textbook_title=title,
            page=page,
            created_by_user_id=self.teacher.id,
        )
        db.session.add(row)
        db.session.flush()
        return row

    def test_metrics_module_does_not_use_legacy_or_audit_sources(self):
        source = inspect.getsource(growth_metrics)
        self.assertNotIn('LearningRecord', source)
        self.assertNotIn('PointsHistory', source)
        self.assertNotIn('ChildNote', source)
        self.assertNotIn('utcnow', source)
        self.assertNotIn('ai_difficulty', source)

    def test_reading_window_boundaries_use_reading_day_dates(self):
        book = self._book('경계책')
        reading = self._reading(book, started_on=date(2026, 6, 1))
        self._day(reading, date(2026, 8, 23))
        self._day(reading, AS_OF)
        self._day(reading, CURRENT_START)
        self._day(reading, PREV_END)
        self._day(reading, PREV_START)
        self._day(reading, date(2026, 6, 23))
        db.session.commit()

        result = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['current']['reading_days'], 2)
        self.assertEqual(result['previous']['reading_days'], 2)
        self.assertEqual(result['available_from']['reading_days'], date(2026, 6, 23))
        self.assertEqual(result['available_from']['started'], date(2026, 6, 1))
        self.assertTrue(result['comparable']['reading_days'])
        self.assertTrue(result['comparable']['started'])

    def test_started_is_not_a_reading_day(self):
        book = self._book('시작만')
        self._reading(book, started_on=AS_OF, status=STATUS_IN_PROGRESS)
        db.session.commit()

        result = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['current']['started_count'], 1)
        self.assertEqual(result['current']['reading_days'], 0)

    def test_completed_uses_completed_on_and_program_snapshot(self):
        general = self._reading(
            self._book('일반완독'),
            started_on=date(2026, 8, 1),
            completed_on=date(2026, 8, 10),
            status=STATUS_COMPLETED,
            program_type=PROGRAM_TYPE_GENERAL,
        )
        self._day(general, date(2026, 8, 1))
        self._day(general, date(2026, 8, 10))
        rec = self._reading(
            self._book('추천완독'),
            started_on=date(2026, 7, 1),
            completed_on=PREV_END,
            status=STATUS_COMPLETED,
            program_type=PROGRAM_TYPE_RECOMMENDED,
        )
        self._day(rec, date(2026, 7, 1))
        challenge = self._reading(
            self._book('도전완독'),
            started_on=date(2026, 8, 20),
            completed_on=AS_OF,
            status=STATUS_COMPLETED,
            program_type=PROGRAM_TYPE_CHALLENGE,
        )
        self._day(challenge, date(2026, 8, 20))
        self._reading(
            self._book('중단'),
            started_on=date(2026, 8, 5),
            ended_on=date(2026, 8, 8),
            status=STATUS_ABANDONED,
            program_type=PROGRAM_TYPE_GENERAL,
        )
        db.session.commit()

        result = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)
        current = result['current']
        self.assertEqual(current['completed_count'], 2)
        self.assertEqual(current['abandoned_count'], 1)
        self.assertEqual(current['completed_by_program'][PROGRAM_TYPE_GENERAL], 1)
        self.assertEqual(current['completed_by_program'][PROGRAM_TYPE_CHALLENGE], 1)
        self.assertEqual(current['completed_by_program'][PROGRAM_TYPE_RECOMMENDED], 0)
        self.assertEqual(result['previous']['completed_count'], 1)
        self.assertEqual(result['previous']['completed_by_program'][PROGRAM_TYPE_RECOMMENDED], 1)

    def test_days_and_inclusive_span_per_completed_book(self):
        reading = self._reading(
            self._book('소요'),
            started_on=date(2026, 8, 1),
            completed_on=date(2026, 8, 3),
            status=STATUS_COMPLETED,
        )
        self._day(reading, date(2026, 8, 1))
        self._day(reading, date(2026, 8, 3))
        db.session.commit()

        stats = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)['current']
        self.assertEqual(stats['days_per_completed_book']['average'], 2)
        self.assertEqual(stats['days_per_completed_book']['sample_count'], 1)
        self.assertEqual(stats['span_per_completed_book']['average'], 3)
        self.assertEqual(stats['span_per_completed_book']['sample_count'], 1)
        self.assertTrue(stats['span_per_completed_book']['inclusive'])

    def test_rating_average_none_when_empty_but_computed_for_small_n(self):
        empty = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)['current']
        self.assertIsNone(empty['difficulty_rating']['average'])
        self.assertEqual(empty['difficulty_rating']['sample_count'], 0)
        self.assertIsNone(empty['fun_rating']['average'])

        one = self._reading(
            self._book('평가1'),
            started_on=date(2026, 8, 1),
            completed_on=date(2026, 8, 2),
            status=STATUS_COMPLETED,
            difficulty_rating=5,
            fun_rating=3,
        )
        self._day(one, date(2026, 8, 1))
        db.session.commit()
        n1 = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)['current']
        self.assertEqual(n1['difficulty_rating']['sample_count'], 1)
        self.assertEqual(n1['difficulty_rating']['average'], 5)
        self.assertEqual(n1['fun_rating']['average'], 3)

        two = self._reading(
            self._book('평가2'),
            started_on=date(2026, 8, 4),
            completed_on=date(2026, 8, 5),
            status=STATUS_COMPLETED,
            difficulty_rating=3,
            fun_rating=None,
        )
        self._day(two, date(2026, 8, 4))
        db.session.commit()
        n2 = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)['current']
        self.assertEqual(n2['difficulty_rating']['sample_count'], 2)
        self.assertEqual(n2['difficulty_rating']['average'], 4)
        self.assertEqual(n2['fun_rating']['sample_count'], 1)
        self.assertEqual(n2['fun_rating']['average'], 3)

    def test_reading_comparable_false_when_ledger_starts_after_previous(self):
        book = self._book('최근시작')
        reading = self._reading(book, started_on=CURRENT_START)
        self._day(reading, CURRENT_START)
        db.session.commit()
        result = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['available_from']['reading_days'], CURRENT_START)
        self.assertEqual(result['available_from']['started'], CURRENT_START)
        self.assertFalse(result['comparable']['reading_days'])
        self.assertFalse(result['comparable']['started'])
        self.assertEqual(result['current']['reading_days'], 1)
        self.assertEqual(result['previous']['reading_days'], 0)

    def test_progress_counts_by_subject_and_latest_snapshot(self):
        korean = self._subject('korean')
        math = self._subject('math')
        self._progress(korean, PREV_END, title='국어 이전', page=5)
        self._progress(korean, AS_OF, title='국어 최근', page=12)
        self._progress(math, CURRENT_START, title='수학', page=20)
        self._progress(math, date(2026, 6, 23), title='창밖', page=1)
        db.session.commit()

        result = progress_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['current']['progress_entry_count'], 2)
        self.assertEqual(result['current']['progress_entry_count_by_subject']['korean'], 1)
        self.assertEqual(result['current']['progress_entry_count_by_subject']['math'], 1)
        self.assertEqual(result['previous']['progress_entry_count'], 1)
        self.assertEqual(result['latest_snapshot_by_subject']['korean']['page'], 12)
        self.assertEqual(result['latest_snapshot_by_subject']['korean']['textbook_title'], '국어 최근')
        self.assertEqual(result['available_from']['progress'], date(2026, 6, 23))
        self.assertTrue(result['comparable']['progress'])
        self.assertNotIn('latest_snapshot_by_subject', result['current'])

    def test_points_dedupe_and_available_from(self):
        self._daily(AS_OF, korean=100)
        older = self._daily(CURRENT_START, korean=50, total=50)
        newer = self._daily(CURRENT_START, korean=200, math=50, total=250)
        self.assertLess(older.id, newer.id)
        db.session.commit()

        result = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['available_from']['points'], CURRENT_START)
        self.assertEqual(result['current']['period_points'], 350)
        self.assertEqual(result['current']['point_activity_days'], 2)
        self.assertEqual(result['current']['subject_active_days']['korean'], 2)
        self.assertEqual(result['current']['subject_active_days']['math'], 1)
        self.assertEqual(result['current']['subject_active_days']['reading'], 0)
        self.assertFalse(result['comparable']['points'])
        self.assertNotEqual(result['current']['period_points'], 100 + 50 + 250)

    def test_points_comparable_when_previous_window_fully_covered(self):
        self._daily(PREV_START, korean=100)
        self._daily(AS_OF, korean=200)
        db.session.commit()
        result = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertTrue(result['comparable']['points'])
        self.assertEqual(result['previous']['period_points'], 100)
        self.assertEqual(result['previous']['point_activity_days'], 1)
        self.assertEqual(result['current']['period_points'], 200)
        self.assertEqual(result['current']['point_activity_days'], 1)

    def test_points_previous_zero_is_comparable_only_if_ledger_covered_window(self):
        self._daily(PREV_START, korean=100)
        db.session.commit()
        result = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertTrue(result['comparable']['points'])
        self.assertEqual(result['current']['period_points'], 0)
        self.assertEqual(result['current']['point_activity_days'], 0)
        self.assertEqual(result['previous']['period_points'], 100)
        self.assertEqual(result['previous']['point_activity_days'], 1)

    def test_points_current_cumulative_matches_ledger_not_stale_cache(self):
        self._daily(AS_OF, korean=200, math=100)
        self.child.cumulative_points = 9999
        db.session.commit()
        result = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['cumulative_as_of'], 300)
        self.assertEqual(result['current_cumulative'], 300)
        self.assertEqual(result['child_cumulative_points'], 9999)

    def test_learning_record_does_not_change_growth_metrics(self):
        before = {
            'reading': reading_metrics(self.child.id, as_of=AS_OF, window_days=30),
            'progress': progress_metrics(self.child.id, as_of=AS_OF, window_days=30),
            'points': points_metrics(self.child.id, as_of=AS_OF, window_days=30),
        }
        db.session.add(LearningRecord(
            child_id=self.child.id,
            date=AS_OF,
            korean_score=95,
            math_score=88,
            reading_score=70,
            korean_last_page=40,
            math_last_page=30,
            created_by=self.teacher.id,
        ))
        db.session.commit()
        after = {
            'reading': reading_metrics(self.child.id, as_of=AS_OF, window_days=30),
            'progress': progress_metrics(self.child.id, as_of=AS_OF, window_days=30),
            'points': points_metrics(self.child.id, as_of=AS_OF, window_days=30),
        }
        self.assertEqual(before, after)

    def test_other_child_rows_are_isolated(self):
        other_book = self._book('남의책')
        other_reading = self._reading(
            other_book,
            started_on=AS_OF,
            completed_on=AS_OF,
            status=STATUS_COMPLETED,
            child=self.other,
        )
        self._day(other_reading, AS_OF)
        self._daily(AS_OF, korean=400, child=self.other)
        db.session.commit()

        reading = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)
        points = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(reading['current']['reading_days'], 0)
        self.assertEqual(reading['current']['completed_count'], 0)
        self.assertEqual(points['current']['period_points'], 0)

    def test_same_as_of_is_deterministic(self):
        book = self._book('결정')
        reading = self._reading(book, started_on=AS_OF)
        self._day(reading, AS_OF)
        self._daily(AS_OF, korean=100)
        db.session.commit()
        first = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)
        second = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(first, second)
        self.assertEqual(
            points_metrics(self.child.id, as_of=AS_OF, window_days=30),
            points_metrics(self.child.id, as_of=AS_OF, window_days=30),
        )

    def test_latest_progress_snapshot_ignores_rows_after_as_of(self):
        korean = self._subject('korean')
        self._progress(korean, date(2026, 7, 10), title='8월22일 기준 최신', page=8)
        self._progress(korean, date(2026, 8, 25), title='미래진도', page=40)
        db.session.commit()

        result = progress_metrics(self.child.id, as_of=AS_OF, window_days=30)
        snapshot = result['latest_snapshot_by_subject']['korean']
        self.assertEqual(snapshot['page'], 8)
        self.assertEqual(snapshot['textbook_title'], '8월22일 기준 최신')
        self.assertEqual(snapshot['recorded_on'], date(2026, 7, 10))
        self.assertEqual(result['available_from']['progress'], date(2026, 7, 10))
        self.assertEqual(result['current']['progress_entry_count'], 0)

    def test_point_cumulative_as_of_ignores_future_daily_points(self):
        historical_as_of = kst_today() - timedelta(days=2)
        self._daily(historical_as_of, korean=100)
        self._daily(kst_today() + timedelta(days=3), korean=500)
        self.child.cumulative_points = 999
        db.session.commit()

        result = points_metrics(self.child.id, as_of=historical_as_of, window_days=30)
        self.assertEqual(result['current']['period_points'], 100)
        self.assertEqual(result['cumulative_as_of'], 100)
        self.assertEqual(result['current_cumulative'], 100)
        self.assertEqual(result['available_from']['points'], historical_as_of)
        self.assertEqual(result['child_cumulative_points'], 999)

    def test_historical_as_of_does_not_use_cumulative_cache(self):
        self.child.cumulative_points = 8888
        db.session.commit()
        past_as_of = kst_today() - timedelta(days=1)
        result = points_metrics(self.child.id, as_of=past_as_of, window_days=30)
        self.assertIsNone(result['cumulative_as_of'])
        self.assertIsNone(result['current_cumulative'])
        self.assertEqual(result['child_cumulative_points'], 8888)

    def test_today_empty_ledger_uses_cumulative_cache(self):
        self.child.cumulative_points = 1234
        db.session.commit()
        result = points_metrics(self.child.id, as_of=kst_today(), window_days=30)
        self.assertEqual(result['cumulative_as_of'], 1234)
        self.assertEqual(result['current_cumulative'], 1234)

    def test_started_on_does_not_advance_reading_days_coverage(self):
        book = self._book('늦게기록')
        reading = self._reading(book, started_on=date(2026, 6, 1))
        self._day(reading, date(2026, 8, 1))
        db.session.commit()

        result = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['available_from']['started'], date(2026, 6, 1))
        self.assertEqual(result['available_from']['reading_days'], date(2026, 8, 1))
        self.assertTrue(result['comparable']['started'])
        self.assertFalse(result['comparable']['reading_days'])
        self.assertEqual(result['current']['reading_days'], 1)
        self.assertEqual(result['previous']['reading_days'], 0)

    def test_rating_coverage_uses_non_null_completed_dates_only(self):
        old_null = self._reading(
            self._book('예전완독무평가'),
            started_on=date(2026, 6, 1),
            completed_on=date(2026, 6, 10),
            status=STATUS_COMPLETED,
        )
        self._day(old_null, date(2026, 6, 1))
        difficulty_only = self._reading(
            self._book('난이도만'),
            started_on=date(2026, 8, 1),
            completed_on=date(2026, 8, 4),
            status=STATUS_COMPLETED,
            difficulty_rating=4,
            fun_rating=None,
        )
        self._day(difficulty_only, date(2026, 8, 1))
        both = self._reading(
            self._book('재미도'),
            started_on=date(2026, 8, 6),
            completed_on=date(2026, 8, 8),
            status=STATUS_COMPLETED,
            difficulty_rating=2,
            fun_rating=5,
        )
        self._day(both, date(2026, 8, 6))
        db.session.commit()

        result = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['available_from']['completed'], date(2026, 6, 10))
        self.assertTrue(result['comparable']['completed'])
        self.assertEqual(result['available_from']['difficulty_rating'], date(2026, 8, 4))
        self.assertEqual(result['available_from']['fun_rating'], date(2026, 8, 8))
        self.assertFalse(result['comparable']['difficulty_rating'])
        self.assertFalse(result['comparable']['fun_rating'])
        self.assertEqual(result['current']['difficulty_rating']['sample_count'], 2)
        self.assertEqual(result['current']['difficulty_rating']['average'], 3)
        self.assertEqual(result['current']['fun_rating']['sample_count'], 1)
        self.assertEqual(result['current']['fun_rating']['average'], 5)


if __name__ == '__main__':
    unittest.main()

