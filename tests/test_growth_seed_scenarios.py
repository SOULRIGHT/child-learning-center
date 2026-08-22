"""Growth Step 2.5: deterministic development seed contracts. UI/route 없음."""
from __future__ import annotations

import os
import unittest
from datetime import date

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints  # noqa: E402
from feature_models import Book, ChildReading, LearningProgressEntry, ReadingDay  # noqa: E402
from features.growth.copy import (  # noqa: E402
    HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN,
    POINTS_PERIOD_INCREASE,
)
from features.growth.insights import generate_insight_candidates  # noqa: E402
from features.growth.metrics import metrics_bundle  # noqa: E402
from scripts.seed.seed_growth_scenarios import (  # noqa: E402
    ALLOW_ENV,
    EXPECTED,
    SCENARIO_CATALOG,
    assert_growth_seed_target_allowed,
    seed_growth_scenarios,
)


AS_OF = date(2026, 8, 22)


class GrowthSeedSafetyTests(unittest.TestCase):
    def test_refuses_local_operating_db_without_allow_env(self):
        previous = os.environ.pop(ALLOW_ENV, None)
        try:
            with self.assertRaises(RuntimeError):
                assert_growth_seed_target_allowed('sqlite:///instance/child_center.db')
        finally:
            if previous is not None:
                os.environ[ALLOW_ENV] = previous

    def test_refuses_production_runtime(self):
        previous = os.environ.get('FLASK_ENV')
        os.environ['FLASK_ENV'] = 'production'
        try:
            with self.assertRaises(RuntimeError):
                assert_growth_seed_target_allowed('sqlite:////tmp/step.db')
        finally:
            if previous is None:
                os.environ.pop('FLASK_ENV', None)
            else:
                os.environ['FLASK_ENV'] = previous


class GrowthSeedContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = app.app_context()
        cls.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        cls.result = seed_growth_scenarios(anchor_date=AS_OF, replace_existing=True)
        cls.children = {
            key: Child.query.get(info['id'])
            for key, info in cls.result['children'].items()
        }

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        cls.ctx.pop()

    def _bundle(self, key):
        return metrics_bundle(self.children[key].id, as_of=AS_OF, window_days=30)

    def _ids(self, key):
        return [item.id for item in generate_insight_candidates(self._bundle(key))]

    def test_catalog_size_and_models_created(self):
        self.assertEqual(len(SCENARIO_CATALOG), 22)
        self.assertEqual(Child.query.count(), 22)
        self.assertGreater(Book.query.count(), 5)
        self.assertGreater(ChildReading.query.count(), 20)
        self.assertGreater(ReadingDay.query.count(), 20)
        self.assertGreater(LearningProgressEntry.query.count(), 10)
        self.assertGreater(DailyPoints.query.count(), 20)
        grades = {child.grade for child in self.children.values()}
        self.assertGreaterEqual(len(grades), 5)

    def test_seed_is_deterministic(self):
        first = {
            key: self._ids(key)
            for key in ('S1', 'S8', 'S9', 'S10', 'S13', 'S17', 'S18')
        }
        again = seed_growth_scenarios(anchor_date=AS_OF, replace_existing=True)
        self.assertEqual(again['anchor_date'], AS_OF)
        second = {
            key: [item.id for item in generate_insight_candidates(
                metrics_bundle(again['children'][key]['id'], as_of=AS_OF, window_days=30)
            )]
            for key in first
        }
        self.assertEqual(first, second)
        GrowthSeedContractTests.children = {
            key: Child.query.get(info['id'])
            for key, info in again['children'].items()
        }

    def test_s1_reading_increase(self):
        ids = self._ids('S1')
        self.assertIn('READING_ACTIVITY_INCREASE', ids)
        self.assertNotIn('READING_ACTIVITY_DECREASE', ids)

    def test_s3_no_reading_activity_insight(self):
        ids = self._ids('S3')
        self.assertNotIn('READING_ACTIVITY_INCREASE', ids)
        self.assertNotIn('READING_ACTIVITY_DECREASE', ids)

    def test_s8_no_points_increase(self):
        bundle = self._bundle('S8')
        self.assertTrue(bundle['points']['comparable']['points'])
        self.assertEqual(bundle['points']['previous']['point_activity_days'], 0)
        self.assertGreater(bundle['points']['current']['period_points'], 0)
        self.assertNotIn(POINTS_PERIOD_INCREASE, self._ids('S8'))

    def test_s9_paired_cross_insight(self):
        self.assertIn(HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN, self._ids('S9'))

    def test_s10_no_paired_cross_insight(self):
        self.assertNotIn(HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN, self._ids('S10'))

    def test_s12_paired_n_is_zero(self):
        reading = self._bundle('S12')['reading']
        self.assertEqual(reading['current']['paired_experience_rating']['sample_count'], 0)
        self.assertEqual(reading['previous']['paired_experience_rating']['sample_count'], 0)
        self.assertGreater(reading['previous']['difficulty_rating']['sample_count'], 0)
        self.assertGreater(reading['current']['fun_rating']['sample_count'], 0)
        self.assertNotIn(HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN, self._ids('S12'))

    def test_s13_insufficient_coverage_has_no_forced_growth(self):
        ids = self._ids('S13')
        for candidate_id in EXPECTED['S13']['exclude']:
            self.assertNotIn(candidate_id, ids)

    def test_expected_include_exclude_contracts(self):
        for key, spec in EXPECTED.items():
            ids = self._ids(key)
            for candidate_id in spec.get('include', []):
                self.assertIn(candidate_id, ids, msg=f'{key} missing {candidate_id}: {ids}')
            for candidate_id in spec.get('exclude', []):
                self.assertNotIn(candidate_id, ids, msg=f'{key} unexpected {candidate_id}: {ids}')

    def test_candidate_count_coverage(self):
        counts = {key: len(self._ids(key)) for key in SCENARIO_CATALOG}
        self.assertTrue(any(value == 0 for value in counts.values()), counts)
        self.assertTrue(any(value == 1 for value in counts.values()), counts)
        self.assertTrue(any(value == 2 for value in counts.values()), counts)
        self.assertTrue(any(value >= 3 for value in counts.values()), counts)


if __name__ == '__main__':
    unittest.main()
