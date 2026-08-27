"""Deterministic learning Growth metrics. UI/insight/LLM 없음."""
from __future__ import annotations

import inspect
import unittest
from datetime import date

from tests.helpers import bootstrap_test_app, local_development_sqlite_path, resolved_engine_sqlite_path

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import LearningProgressEntry, LearningSubject  # noqa: E402
from features.growth.insights import generate_insight_candidates, top_candidates  # noqa: E402
from features.growth.learning_metrics import (  # noqa: E402
    MAX_PROGRESS_SNAPSHOT_AGE_DAYS,
    STATUS_BOOK_CHANGED,
    STATUS_CROSS_BOOK,
    STATUS_NO_BASELINE,
    STATUS_NO_PEERS,
    STATUS_NO_SNAPSHOT,
    STATUS_OK,
    STATUS_STALE_BASELINE,
    STATUS_STALE_ENDPOINT,
    STATUS_STALE_TARGET,
    is_stale_snapshot,
    learning_metrics,
)
from features.growth.metrics import metrics_bundle, progress_metrics  # noqa: E402
from features.planning.planner import build_child_subject_plan_status  # noqa: E402
from features.planning.service import create_workbook_plan  # noqa: E402
from features.planning.workload import WORKLOAD_KIND_ESTIMATED, WORKLOAD_KIND_EXACT  # noqa: E402
from features.progress.service import ensure_default_subjects  # noqa: E402


AS_OF = date(2026, 8, 22)
BOOK = '우등생 수학 3-2'
BOOK_OLD = '우등생 수학 3-1'


class GrowthLearningMetricsTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.assertNotEqual(resolved_engine_sqlite_path(db), local_development_sqlite_path())
        self.teacher = User(
            username='learn_growth_teacher',
            name='학습성장교사',
            role='돌봄선생님',
            email='learn-growth@example.test',
            password_hash='',
        )
        self.child = Child(name='학습성장아동', grade=3, viewer_slug='llllllllllllllllllllllll')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        ensure_default_subjects()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.korean = LearningSubject.query.filter_by(key='korean').one()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _child(self, name, *, grade=3, include_in_stats=True, slug):
        row = Child(
            name=name,
            grade=grade,
            viewer_slug=slug,
            include_in_stats=include_in_stats,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def _progress(self, on, *, page, title=BOOK, subject=None, child=None):
        row = LearningProgressEntry(
            child_id=(child or self.child).id,
            learning_subject_id=(subject or self.math).id,
            recorded_on=on,
            textbook_title=title,
            page=page,
            created_by_user_id=self.teacher.id,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def _daily(self, on, *, korean=100, child=None):
        row = DailyPoints(
            child_id=(child or self.child).id,
            date=on,
            korean_points=korean,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=0,
            manual_history='[]',
            total_points=korean,
            created_by=self.teacher.id,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def _learning(self, as_of=AS_OF):
        return learning_metrics(self.child.id, as_of=as_of, window_days=30)

    def _math(self, as_of=AS_OF):
        return self._learning(as_of)['subjects']['math']

    def test_engine_is_not_instance_db(self):
        self.assertNotEqual(resolved_engine_sqlite_path(db), local_development_sqlite_path())

    def test_freshness_constant_is_single_policy(self):
        self.assertEqual(MAX_PROGRESS_SNAPSHOT_AGE_DAYS, 21)
        self.assertEqual(is_stale_snapshot(date(2026, 7, 31), AS_OF), True)
        self.assertEqual(is_stale_snapshot(date(2026, 8, 1), AS_OF), False)

    def test_page_advance_uses_pre_window_baseline_not_first_in_window(self):
        self._progress(date(2026, 7, 20), page=80)
        self._progress(date(2026, 7, 30), page=90)
        self._progress(date(2026, 8, 15), page=120)
        current = self._math()['page_advance']['current']
        self.assertEqual(current['status'], STATUS_OK)
        self.assertEqual(current['value'], 40)
        self.assertEqual(current['baseline']['page'], 80)
        self.assertEqual(current['baseline']['recorded_on'], date(2026, 7, 20))
        self.assertEqual(current['endpoint']['page'], 120)
        self.assertTrue(current['available'])
        self.assertTrue(current['comparable'])
        progress = progress_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(progress['current']['progress_entry_count'], 2)
        self.assertEqual(progress['latest_snapshot_by_subject']['math']['page'], 120)

    def test_future_snapshot_is_excluded(self):
        self._progress(date(2026, 7, 20), page=80)
        self._progress(date(2026, 8, 15), page=120)
        self._progress(date(2026, 8, 23), page=200)
        current = self._math()['page_advance']['current']
        self.assertEqual(current['value'], 40)
        self.assertEqual(current['endpoint']['page'], 120)

    def test_cross_book_subtraction_is_forbidden(self):
        self._progress(date(2026, 7, 20), page=150, title=BOOK_OLD)
        self._progress(date(2026, 8, 15), page=20, title=BOOK)
        current = self._math()['page_advance']['current']
        self.assertEqual(current['status'], STATUS_CROSS_BOOK)
        self.assertFalse(current['available'])
        self.assertIsNone(current['value'])
        self.assertEqual(current['endpoint']['page'], 20)
        self.assertEqual(current['baseline']['page'], 150)

    def test_same_book_normalized_title_matches(self):
        self._progress(date(2026, 7, 20), page=80, title='  우등생   수학  3-2  ')
        self._progress(date(2026, 8, 15), page=100, title=BOOK)
        current = self._math()['page_advance']['current']
        self.assertEqual(current['status'], STATUS_OK)
        self.assertEqual(current['value'], 20)
        self.assertEqual(current['textbook_title'], BOOK)

    def test_missing_baseline_is_unavailable_not_zero(self):
        self._progress(date(2026, 7, 30), page=90)
        self._progress(date(2026, 8, 15), page=90)
        current = self._math()['page_advance']['current']
        self.assertEqual(current['status'], STATUS_NO_BASELINE)
        self.assertIsNone(current['value'])
        self.assertFalse(current['available'])

    def test_true_zero_advance_is_distinct_from_unavailable(self):
        self._progress(date(2026, 7, 20), page=80)
        self._progress(date(2026, 8, 15), page=80)
        current = self._math()['page_advance']['current']
        self.assertEqual(current['status'], STATUS_OK)
        self.assertEqual(current['value'], 0)
        self.assertTrue(current['available'])

    def test_negative_raw_delta_is_preserved(self):
        self._progress(date(2026, 7, 20), page=100)
        self._progress(date(2026, 8, 15), page=95)
        current = self._math()['page_advance']['current']
        self.assertEqual(current['value'], -5)
        self.assertTrue(current['available'])

    def test_stale_baseline_is_unavailable(self):
        self._progress(date(2026, 7, 2), page=80)
        self._progress(date(2026, 8, 15), page=120)
        current = self._math()['page_advance']['current']
        self.assertEqual(current['status'], STATUS_STALE_BASELINE)
        self.assertIsNone(current['value'])
        self.assertGreater(current['baseline']['age_days'], MAX_PROGRESS_SNAPSHOT_AGE_DAYS)

    def test_fresh_baseline_on_day_21_is_available(self):
        self._progress(date(2026, 7, 3), page=80)
        self._progress(date(2026, 8, 15), page=120)
        current = self._math()['page_advance']['current']
        self.assertEqual(current['baseline']['age_days'], 21)
        self.assertEqual(current['status'], STATUS_OK)
        self.assertEqual(current['value'], 40)

    def test_stale_endpoint_is_unavailable(self):
        self._progress(date(2026, 7, 20), page=80)
        self._progress(date(2026, 7, 31), page=120)
        current = self._math()['page_advance']['current']
        self.assertEqual(current['status'], STATUS_STALE_ENDPOINT)
        self.assertIsNone(current['value'])
        self.assertGreater(current['endpoint']['age_days'], MAX_PROGRESS_SNAPSHOT_AGE_DAYS)

    def test_previous_window_uses_same_rules(self):
        self._progress(date(2026, 6, 20), page=50)
        self._progress(date(2026, 7, 10), page=70)
        self._progress(date(2026, 7, 20), page=80)
        self._progress(date(2026, 8, 15), page=120)
        previous = self._math()['page_advance']['previous']
        self.assertEqual(previous['status'], STATUS_OK)
        self.assertEqual(previous['value'], 30)
        self.assertEqual(previous['baseline']['recorded_on'], date(2026, 6, 20))
        self.assertEqual(previous['endpoint']['recorded_on'], date(2026, 7, 20))
        self.assertEqual(previous['window']['start'], date(2026, 6, 24))
        self.assertEqual(previous['window']['end'], date(2026, 7, 23))

    def test_trend_comparable_when_same_book(self):
        self._progress(date(2026, 6, 20), page=50)
        self._progress(date(2026, 7, 20), page=80)
        self._progress(date(2026, 8, 15), page=120)
        advance = self._math()['page_advance']
        self.assertTrue(advance['comparable'])
        self.assertEqual(advance['status'], STATUS_OK)
        self.assertEqual(advance['delta'], 10)

    def test_trend_not_comparable_when_book_changes(self):
        self._progress(date(2026, 6, 20), page=50, title=BOOK_OLD)
        self._progress(date(2026, 7, 20), page=150, title=BOOK_OLD)
        self._progress(date(2026, 7, 10), page=10, title=BOOK)
        self._progress(date(2026, 8, 15), page=40, title=BOOK)
        advance = self._math()['page_advance']
        self.assertTrue(advance['current']['available'])
        self.assertTrue(advance['previous']['available'])
        self.assertFalse(advance['comparable'])
        self.assertEqual(advance['status'], STATUS_BOOK_CHANGED)
        self.assertIsNone(advance['delta'])

    def test_peer_self_exclusion_and_filters(self):
        self._progress(date(2026, 8, 20), page=40)
        same = self._child('동료', slug='aaaaaaaaaaaaaaaaaaaaaaaa')
        other_grade = self._child('다른학년', grade=4, slug='bbbbbbbbbbbbbbbbbbbbbbbb')
        excluded = self._child('통계제외', include_in_stats=False, slug='ccccccccccccccccccccccc1')
        self._progress(date(2026, 8, 19), page=30, child=same)
        self._progress(date(2026, 8, 19), page=90, child=other_grade)
        self._progress(date(2026, 8, 19), page=10, child=excluded)
        peer = self._math()['peer']
        self.assertEqual(peer['status'], STATUS_OK)
        self.assertEqual(peer['peer_n'], 1)
        self.assertEqual(peer['peer_median'], 30)
        self.assertEqual(peer['gap'], 10)
        self.assertNotIn('학습성장아동', str(peer))

    def test_peer_stale_target_is_unavailable(self):
        self._progress(date(2026, 7, 31), page=40)
        peer_child = self._child('동료2', slug='dddddddddddddddddddddddd')
        self._progress(date(2026, 8, 20), page=50, child=peer_child)
        peer = self._math()['peer']
        self.assertEqual(peer['status'], STATUS_STALE_TARGET)
        self.assertFalse(peer['available'])
        self.assertIsNone(peer['peer_median'])

    def test_peer_stale_latest_is_excluded(self):
        self._progress(date(2026, 8, 20), page=40)
        stale = self._child('오래된동료', slug='eeeeeeeeeeeeeeeeeeeeeeee')
        fresh = self._child('최근동료', slug='ffffffffffffffffffffffff')
        self._progress(date(2026, 7, 31), page=10, child=stale)
        self._progress(date(2026, 8, 18), page=20, child=fresh)
        peer = self._math()['peer']
        self.assertEqual(peer['peer_n'], 1)
        self.assertEqual(peer['peer_median'], 20)

    def test_peer_uses_latest_subject_snapshot_not_older_same_book(self):
        self._progress(date(2026, 8, 20), page=100, title=BOOK_OLD)
        switched = self._child('교재변경동료', slug='gggggggggggggggggggggggg')
        self._progress(date(2026, 8, 10), page=150, title=BOOK_OLD, child=switched)
        self._progress(date(2026, 8, 20), page=20, title=BOOK, child=switched)
        peer = self._math()['peer']
        self.assertEqual(peer['peer_n'], 0)
        self.assertEqual(peer['status'], STATUS_NO_PEERS)
        self.assertIsNone(peer['peer_median'])

    def test_peer_n0_n1_n2_and_even_median(self):
        self._progress(date(2026, 8, 20), page=25)
        self.assertEqual(self._math()['peer']['peer_n'], 0)
        self.assertEqual(self._math()['peer']['status'], STATUS_NO_PEERS)

        p1 = self._child('p1', slug='hhhhhhhhhhhhhhhhhhhhhhhh')
        self._progress(date(2026, 8, 19), page=10, child=p1)
        self.assertEqual(self._math()['peer']['peer_n'], 1)
        self.assertEqual(self._math()['peer']['peer_median'], 10)

        p2 = self._child('p2', slug='iiiiiiiiiiiiiiiiiiiiiiii')
        self._progress(date(2026, 8, 19), page=20, child=p2)
        two = self._math()['peer']
        self.assertEqual(two['peer_n'], 2)
        self.assertEqual(two['peer_median'], 15)
        self.assertEqual(two['gap'], 10)

        p3 = self._child('p3', slug='jjjjjjjjjjjjjjjjjjjjjjjj')
        self._progress(date(2026, 8, 19), page=30, child=p3)
        self.assertEqual(self._math()['peer']['peer_n'], 3)
        self.assertEqual(self._math()['peer']['peer_median'], 20)

        p4 = self._child('p4', slug='kkkkkkkkkkkkkkkkkkkkkkkk')
        self._progress(date(2026, 8, 19), page=40, child=p4)
        self.assertEqual(self._math()['peer']['peer_n'], 4)
        self.assertEqual(self._math()['peer']['peer_median'], 25)

    def test_peer_future_snapshot_excluded(self):
        self._progress(date(2026, 8, 20), page=40)
        peer_child = self._child('미래동료', slug='mmmmmmmmmmmmmmmmmmmmmmmm')
        self._progress(date(2026, 8, 10), page=22, child=peer_child)
        self._progress(date(2026, 8, 23), page=99, child=peer_child)
        peer = self._math()['peer']
        self.assertEqual(peer['peer_n'], 1)
        self.assertEqual(peer['peer_median'], 22)

    def test_peer_normalized_title(self):
        self._progress(date(2026, 8, 20), page=40, title='  우등생   수학  3-2  ')
        peer_child = self._child('정규화동료', slug='nnnnnnnnnnnnnnnnnnnnnnnn')
        self._progress(date(2026, 8, 19), page=18, title=BOOK, child=peer_child)
        peer = self._math()['peer']
        self.assertEqual(peer['peer_n'], 1)
        self.assertEqual(peer['textbook_title'], BOOK)

    def test_observed_study_days_uses_canonical_point_days(self):
        self._daily(date(2026, 8, 20), korean=100)
        self._daily(date(2026, 8, 20), korean=50)
        self._daily(date(2026, 7, 10), korean=100)
        payload = self._learning()['observed_study_days']
        self.assertEqual(payload['current'], 1)
        self.assertEqual(payload['previous'], 1)
        self.assertEqual(payload['source'], 'daily_points.date')
        self.assertFalse(payload['attendance'])
        self.assertEqual(payload['proxy'], 'point_activity_days')

    def test_planner_results_are_copied_not_recomputed(self):
        create_workbook_plan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title=BOOK,
            start_page=10,
            end_page=184,
            start_date=date(2026, 7, 1),
            target_completion_date=date(2026, 12, 20),
            exclusion_ranges_text=None,
        )
        self._progress(date(2026, 8, 20), page=84)
        db.session.expire_all()
        child = db.session.get(Child, self.child.id)
        canonical = build_child_subject_plan_status(child, self.math, as_of=AS_OF)
        plan = self._math()['plan']
        self.assertEqual(plan['status'], canonical.status)
        self.assertEqual(plan['remaining_workload'], canonical.remaining_workload)
        self.assertEqual(plan['required_per_planned_day'], canonical.required_per_planned_day)
        self.assertEqual(plan['workload_kind'], WORKLOAD_KIND_ESTIMATED)
        self.assertEqual(plan['weekday_source'], canonical.weekday_source)

        exact_plan = create_workbook_plan(
            grade=3,
            learning_subject_id=self.korean.id,
            textbook_title='국어 교재',
            start_page=1,
            end_page=50,
            start_date=date(2026, 7, 1),
            target_completion_date=date(2026, 12, 20),
            exclusion_ranges_text='40-42',
        )
        self._progress(date(2026, 8, 20), page=10, title='국어 교재', subject=self.korean)
        korean_plan = self._learning()['subjects']['korean']['plan']
        self.assertEqual(korean_plan['workload_kind'], WORKLOAD_KIND_EXACT)
        self.assertEqual(korean_plan['plan_id'], exact_plan.id)

    def test_planner_no_snapshot_and_no_plan_status_preserved(self):
        math_plan = self._math()['plan']
        self.assertEqual(math_plan['status'], STATUS_NO_SNAPSHOT)
        self._progress(date(2026, 8, 20), page=40)
        no_plan = self._math()['plan']
        self.assertEqual(no_plan['status'], 'no_plan')
        self.assertEqual(no_plan['current_page'], 40)
        self.assertIsNone(no_plan['required_per_planned_day'])

    def test_bundle_keeps_existing_progress_and_insight_output(self):
        self._progress(date(2026, 7, 20), page=80)
        self._progress(date(2026, 8, 15), page=120)
        self._daily(AS_OF, korean=200)
        bundle = metrics_bundle(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(bundle['progress']['current']['progress_entry_count'], 1)
        self.assertEqual(bundle['progress']['latest_snapshot_by_subject']['math']['page'], 120)
        self.assertIn('learning', bundle)
        self.assertEqual(bundle['learning']['subjects']['math']['page_advance']['current']['value'], 40)
        with_learning = [item.id for item in generate_insight_candidates(bundle)]
        without_learning = {
            key: value for key, value in bundle.items() if key != 'learning'
        }
        without = [item.id for item in generate_insight_candidates(without_learning)]
        self.assertEqual(with_learning, without)
        self.assertEqual(
            [item.id for item in top_candidates(generate_insight_candidates(bundle))],
            [item.id for item in top_candidates(generate_insight_candidates(without_learning))],
        )

    def test_learning_metrics_do_not_use_legacy_or_insight_sources(self):
        import features.growth.learning_metrics as module
        source = inspect.getsource(module)
        self.assertNotIn('LearningRecord', source)
        self.assertNotIn('generate_insight_candidates', source)
        self.assertNotIn('pages_per', source)
        self.assertIn("'attendance': False", source)
