"""Growth Step 2: comparison / insight candidates / fallback copy. UI/LLM 없음."""
from __future__ import annotations

import inspect
import unittest
from datetime import date, timedelta

from features.growth.copy import (
    FALLBACK_COPY,
    FORBIDDEN_COPY_PHRASES,
    HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN,
    POINTS_PERIOD_INCREASE,
    PROGRESS_ENTRIES_DECREASE,
    PROGRESS_ENTRIES_INCREASE,
    READING_ACTIVITY_DECREASE,
    READING_ACTIVITY_INCREASE,
    READING_COMPLETIONS_INCREASE,
    all_copy_texts,
    fallback_copy,
)
from features.growth.insights import (
    generate_insight_candidates,
    top_candidates,
)
from features.growth.windows import current_window, previous_window
from features.growth import insights as growth_insights
from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    POLICY_VERSION_GENERAL_V2,
    STATUS_IN_PROGRESS,
    Book,
    ChildReading,
    ReadingDay,
)
from features.growth.metrics import metrics_bundle  # noqa: E402


AS_OF = date(2026, 8, 22)
PREV_START = date(2026, 6, 24)
CURRENT_START = date(2026, 7, 24)


def _windows():
    return current_window(AS_OF, 30), previous_window(AS_OF, 30)


def _reading_payload(
    *,
    reading_days=(0, 0),
    completed=(0, 0),
    comparable_days=True,
    comparable_completed=True,
    comparable_difficulty=False,
    comparable_fun=False,
    comparable_pair=False,
    difficulty=None,
    fun=None,
    paired=None,
):
    current_window_, previous_window_ = _windows()
    current_diff = difficulty[0] if difficulty else {'average': None, 'sample_count': 0}
    previous_diff = difficulty[1] if difficulty else {'average': None, 'sample_count': 0}
    current_fun = fun[0] if fun else {'average': None, 'sample_count': 0}
    previous_fun = fun[1] if fun else {'average': None, 'sample_count': 0}
    empty_paired = {'sample_count': 0, 'difficulty_average': None, 'fun_average': None}
    current_paired = paired[0] if paired else empty_paired
    previous_paired = paired[1] if paired else empty_paired
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current_window_,
        'previous_window': previous_window_,
        'available_from': {
            'reading_days': PREV_START if comparable_days else CURRENT_START,
            'completed': PREV_START if comparable_completed else CURRENT_START,
            'difficulty_rating': PREV_START if comparable_difficulty else None,
            'fun_rating': PREV_START if comparable_fun else None,
            'experience_rating_pair': PREV_START if comparable_pair else None,
        },
        'comparable': {
            'reading_days': comparable_days,
            'started': True,
            'completed': comparable_completed,
            'abandoned': False,
            'difficulty_rating': comparable_difficulty,
            'fun_rating': comparable_fun,
            'experience_rating_pair': comparable_pair,
        },
        'current': {
            'reading_days': reading_days[0],
            'started_count': 0,
            'completed_count': completed[0],
            'abandoned_count': 0,
            'difficulty_rating': current_diff,
            'fun_rating': current_fun,
            'paired_experience_rating': current_paired,
        },
        'previous': {
            'reading_days': reading_days[1],
            'started_count': 0,
            'completed_count': completed[1],
            'abandoned_count': 0,
            'difficulty_rating': previous_diff,
            'fun_rating': previous_fun,
            'paired_experience_rating': previous_paired,
        },
    }


def _progress_payload(current_count, previous_count, comparable=True):
    current_window_, previous_window_ = _windows()
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current_window_,
        'previous_window': previous_window_,
        'available_from': {'progress': PREV_START if comparable else CURRENT_START},
        'comparable': {'progress': comparable},
        'current': {
            'progress_entry_count': current_count,
            'progress_entry_count_by_subject': {},
        },
        'previous': {
            'progress_entry_count': previous_count,
            'progress_entry_count_by_subject': {},
        },
        'latest_snapshot_by_subject': {},
    }


def _points_payload(current_points, previous_points, *, current_days=1, previous_days=1, comparable=True):
    current_window_, previous_window_ = _windows()
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current_window_,
        'previous_window': previous_window_,
        'available_from': {'points': PREV_START if comparable else CURRENT_START},
        'comparable': {'points': comparable},
        'current': {
            'period_points': current_points,
            'point_activity_days': current_days,
            'subject_active_days': {},
            'manual_points_sum': 0,
        },
        'previous': {
            'period_points': previous_points,
            'point_activity_days': previous_days,
            'subject_active_days': {},
            'manual_points_sum': 0,
        },
        'cumulative_as_of': None,
        'current_cumulative': None,
        'child_cumulative_points': 9999,
    }


def _bundle(reading=None, progress=None, points=None):
    return {
        'reading': reading or _reading_payload(),
        'progress': progress or _progress_payload(0, 0, comparable=False),
        'points': points or _points_payload(0, 0, previous_days=0, comparable=False),
    }


def _ids(candidates):
    return [item.id for item in candidates]


class GrowthInsightFixtureTests(unittest.TestCase):
    def test_reading_activity_increase_from_5_to_8(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(reading_days=(8, 5)),
        ))
        self.assertIn(READING_ACTIVITY_INCREASE, _ids(candidates))
        item = next(row for row in candidates if row.id == READING_ACTIVITY_INCREASE)
        self.assertEqual(item.evidence['current'], 8)
        self.assertEqual(item.evidence['previous'], 5)
        self.assertEqual(item.evidence['delta'], 3)
        self.assertEqual(item.evidence['source'], 'reading_day.date')
        self.assertEqual(item.evidence['window_days'], 30)
        self.assertEqual(item.evidence['current_window']['start'], CURRENT_START)
        self.assertEqual(item.evidence['previous_window']['start'], PREV_START)
        self.assertTrue(item.evidence['comparable'])
        self.assertAlmostEqual(item.evidence['relative_change'], 0.6)

    def test_reading_activity_decrease_from_8_to_5(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(reading_days=(5, 8)),
        ))
        self.assertEqual(_ids(candidates), [READING_ACTIVITY_DECREASE])

    def test_reading_delta_plus_one_is_not_a_candidate(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(reading_days=(6, 5)),
        ))
        self.assertEqual(_ids(candidates), [])

    def test_reading_not_comparable_has_no_candidate(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(reading_days=(8, 5), comparable_days=False),
        ))
        self.assertEqual(_ids(candidates), [])

    def test_reading_previous_zero_does_not_create_increase(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(reading_days=(5, 0)),
        ))
        self.assertNotIn(READING_ACTIVITY_INCREASE, _ids(candidates))

    def test_completed_increase_from_2_to_4(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(completed=(4, 2)),
        ))
        self.assertIn(READING_COMPLETIONS_INCREASE, _ids(candidates))

    def test_progress_increase_from_3_to_7(self):
        candidates = generate_insight_candidates(_bundle(
            progress=_progress_payload(7, 3),
        ))
        self.assertEqual(_ids(candidates), [PROGRESS_ENTRIES_INCREASE])

    def test_progress_decrease_from_7_to_3(self):
        candidates = generate_insight_candidates(_bundle(
            progress=_progress_payload(3, 7),
        ))
        self.assertEqual(_ids(candidates), [PROGRESS_ENTRIES_DECREASE])

    def test_points_meaningful_increase_with_previous_activity(self):
        candidates = generate_insight_candidates(_bundle(
            points=_points_payload(300, 100, previous_days=2),
        ))
        self.assertEqual(_ids(candidates), [POINTS_PERIOD_INCREASE])
        item = candidates[0]
        self.assertEqual(item.evidence['delta'], 200)
        self.assertEqual(item.evidence['n_previous'], 2)

    def test_points_previous_activity_days_zero_has_no_increase(self):
        candidates = generate_insight_candidates(_bundle(
            points=_points_payload(400, 0, previous_days=0, comparable=True),
        ))
        self.assertNotIn(POINTS_PERIOD_INCREASE, _ids(candidates))

    def test_rating_higher_difficulty_with_stable_fun(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(
                comparable_pair=True,
                paired=(
                    {'sample_count': 3, 'difficulty_average': 3.6, 'fun_average': 4.1},
                    {'sample_count': 3, 'difficulty_average': 2.8, 'fun_average': 4.2},
                ),
            ),
        ))
        self.assertEqual(_ids(candidates), [HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN])
        item = candidates[0]
        self.assertEqual(item.evidence['n_current'], 3)
        self.assertEqual(item.evidence['source'], 'child_reading.paired_experience_rating')
        self.assertGreaterEqual(item.evidence['delta']['difficulty'], 0.5)
        self.assertGreaterEqual(item.evidence['delta']['fun'], -0.3)

    def test_unpaired_difficulty_and_fun_do_not_create_cross_candidate(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(
                comparable_difficulty=True,
                comparable_fun=True,
                comparable_pair=False,
                difficulty=(
                    {'average': 4.0, 'sample_count': 3},
                    {'average': 2.5, 'sample_count': 3},
                ),
                fun=(
                    {'average': 4.2, 'sample_count': 3},
                    {'average': 4.1, 'sample_count': 3},
                ),
                paired=(
                    {'sample_count': 0, 'difficulty_average': None, 'fun_average': None},
                    {'sample_count': 0, 'difficulty_average': None, 'fun_average': None},
                ),
            ),
        ))
        self.assertNotIn(HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN, _ids(candidates))

    def test_cross_candidate_uses_paired_averages_not_independent(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(
                comparable_difficulty=True,
                comparable_fun=True,
                comparable_pair=True,
                difficulty=(
                    {'average': 4.5, 'sample_count': 6},
                    {'average': 2.8, 'sample_count': 3},
                ),
                fun=(
                    {'average': 2.0, 'sample_count': 6},
                    {'average': 4.2, 'sample_count': 3},
                ),
                paired=(
                    {'sample_count': 3, 'difficulty_average': 3.6, 'fun_average': 4.1},
                    {'sample_count': 3, 'difficulty_average': 2.8, 'fun_average': 4.2},
                ),
            ),
        ))
        self.assertEqual(_ids(candidates), [HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN])
        item = candidates[0]
        self.assertEqual(item.evidence['current']['difficulty_average'], 3.6)
        self.assertEqual(item.evidence['current']['fun_average'], 4.1)
        self.assertNotEqual(item.evidence['current']['difficulty_average'], 4.5)
        self.assertNotEqual(item.evidence['current']['fun_average'], 2.0)

    def test_rating_n_two_has_no_cross_candidate(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(
                comparable_pair=True,
                paired=(
                    {'sample_count': 2, 'difficulty_average': 3.6, 'fun_average': 4.1},
                    {'sample_count': 2, 'difficulty_average': 2.8, 'fun_average': 4.2},
                ),
            ),
        ))
        self.assertNotIn(HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN, _ids(candidates))

    def test_rating_fun_drop_blocks_cross_candidate(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(
                comparable_pair=True,
                paired=(
                    {'sample_count': 3, 'difficulty_average': 3.6, 'fun_average': 2.5},
                    {'sample_count': 3, 'difficulty_average': 2.8, 'fun_average': 4.5},
                ),
            ),
        ))
        self.assertNotIn(HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN, _ids(candidates))

    def test_previous_zero_relative_change_is_none(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(completed=(2, 0)),
        ))
        item = next(row for row in candidates if row.id == READING_COMPLETIONS_INCREASE)
        self.assertIsNone(item.evidence['relative_change'])
        self.assertEqual(item.evidence['previous'], 0)
        self.assertEqual(item.evidence['delta'], 2)

    def test_same_input_is_deterministic(self):
        bundle = _bundle(
            reading=_reading_payload(reading_days=(11, 6), completed=(4, 2)),
            progress=_progress_payload(7, 3),
            points=_points_payload(300, 100, previous_days=2),
        )
        first = generate_insight_candidates(bundle)
        second = generate_insight_candidates(bundle)
        self.assertEqual(first, second)
        self.assertEqual([row.importance for row in first], [row.importance for row in second])
        self.assertEqual(_ids(first), _ids(second))

    def test_top_candidates_keeps_one_per_category(self):
        bundle = _bundle(
            reading=_reading_payload(reading_days=(11, 6), completed=(4, 2)),
            progress=_progress_payload(7, 3),
        )
        picked = top_candidates(generate_insight_candidates(bundle), limit=3)
        self.assertEqual(len(picked), 3)
        self.assertEqual(len({row.category for row in picked}), 3)

    def test_insights_do_not_use_live_point_cache(self):
        source = inspect.getsource(growth_insights)
        self.assertNotIn('child_cumulative_points', source)
        self.assertNotIn('cumulative_points', source)
        self.assertNotIn('HIGHER_DIFFICULTY_WITH_ENGAGEMENT', source)
        self.assertNotIn('engagement', source.lower())


class GrowthInsightCopyTests(unittest.TestCase):
    def test_fallback_copy_has_no_forbidden_phrases(self):
        joined = '\n'.join(all_copy_texts())
        for phrase in FORBIDDEN_COPY_PHRASES:
            self.assertNotIn(phrase, joined)
        self.assertNotIn('%', joined)
        self.assertNotIn('83', joined)

    def test_each_candidate_id_has_copy(self):
        for candidate_id, row in FALLBACK_COPY.items():
            rendered = fallback_copy(candidate_id)
            self.assertTrue(rendered['headline'])
            self.assertEqual(rendered['headline'], row['headline'])

    def test_unknown_id_does_not_invent_copy(self):
        self.assertEqual(fallback_copy('NOT_A_CANDIDATE'), {'headline': '', 'detail': ''})


class GrowthInsightPipelineTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='insight_teacher',
            name='통찰교사',
            role='돌봄선생님',
            email='insight-teacher@example.test',
            password_hash='',
        )
        self.child = Child(name='통찰아동', grade=3, viewer_slug='iiiiiiiiiiiiiiiiiiiiiiii')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _reading_days(self, dates):
        book = Book(title='통찰책', normalized_key='insight-book', is_active=True)
        db.session.add(book)
        db.session.flush()
        reading = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            started_on=date(2026, 6, 1),
            status=STATUS_IN_PROGRESS,
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

    def test_real_metrics_reading_5_to_8_creates_increase(self):
        previous_days = [PREV_START + timedelta(days=offset) for offset in range(5)]
        current_days = [CURRENT_START + timedelta(days=offset) for offset in range(8)]
        self._reading_days(previous_days + current_days)
        candidates = generate_insight_candidates(metrics_bundle(self.child.id, as_of=AS_OF, window_days=30))
        self.assertIn(READING_ACTIVITY_INCREASE, _ids(candidates))

    def test_real_metrics_points_without_previous_activity_has_no_increase(self):
        db.session.add(DailyPoints(
            child_id=self.child.id,
            date=date(2026, 6, 1),
            korean_points=50,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=0,
            manual_history='[]',
            total_points=50,
            created_by=self.teacher.id,
        ))
        db.session.add(DailyPoints(
            child_id=self.child.id,
            date=AS_OF,
            korean_points=300,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=0,
            manual_history='[]',
            total_points=300,
            created_by=self.teacher.id,
        ))
        db.session.commit()
        bundle = metrics_bundle(self.child.id, as_of=AS_OF, window_days=30)
        self.assertTrue(bundle['points']['comparable']['points'])
        self.assertEqual(bundle['points']['previous']['point_activity_days'], 0)
        self.assertNotIn(POINTS_PERIOD_INCREASE, _ids(generate_insight_candidates(bundle)))


if __name__ == '__main__':
    unittest.main()
