"""Growth vNext Step 5: same-center canonical peer comparison."""
from __future__ import annotations

import inspect
import os
import statistics
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    LearningProgressEntry,
    LearningStudySession,
    LearningSubject,
    RECORD_VERIFICATION_OBSERVED,
    STUDY_STATUS_EXPLICIT_NOT_STUDIED,
    STUDY_STATUS_STUDIED,
)
from features.dates import DEV_DATE_CONTROL_ENV  # noqa: E402
from features.growth.learning_view import PEER_NONE_LABEL, PEER_REFERENCE_LABEL  # noqa: E402
from features.growth.peer import METRIC_PERIOD_POINTS, period_points_peer  # noqa: E402
from features.growth.service import build_growth_view_model  # noqa: E402
from features.growth.windows import current_window  # noqa: E402
from features.planning.service import create_workbook_plan  # noqa: E402
from features.progress.service import ensure_default_subjects  # noqa: E402
from features.study.calendar import save_subject_study_weekdays  # noqa: E402
from features.study.constants import INPUT_CHANNEL_TEACHER  # noqa: E402
from features.study.metrics import MIN_EXPECTED_DAYS_FOR_PERIOD_CHANGE, subject_period  # noqa: E402
from features.study.peer import (  # noqa: E402
    DISPLAY_LIMITED,
    DISPLAY_NONE,
    DISPLAY_PRIMARY,
    DISPLAY_REFERENCE,
    FORBIDDEN_RESULT_KEYS,
    METRIC_COVERAGE,
    METRIC_PERFORMANCE,
    REASON_CHILD_CONFIRMATION_EXCLUDED,
    REASON_CHILD_CONFIRMATION_UNAVAILABLE,
    REASON_CHILD_UNAVAILABLE,
    REASON_EXCLUDED_FROM_STATS,
    REASON_INSUFFICIENT_PEERS,
    REASON_NO_PEERS,
    REASON_TEXTBOOK_MISMATCH,
    peer_comparison_for_subject,
    peer_learning_summary,
)
from features.study.records import create_study_session  # noqa: E402
from features.study.schedule import normal_study_day  # noqa: E402
import features.study.peer as study_peer  # noqa: E402

AS_OF = date(2026, 9, 8)  # Tue
TUESDAY = 1
WINDOW_DAYS = 30


def _walk_keys(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key
            yield from _walk_keys(value)
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            yield from _walk_keys(item)


class StudyPeerTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='peer_teacher',
            name='또래교사',
            role='돌봄선생님',
            email='peer@example.test',
            password_hash='',
        )
        self.child = Child(
            name='기준아동',
            grade=3,
            viewer_slug='peerchildpeerchildpeerch',
            created_at=datetime(2020, 1, 1),
        )
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        ensure_default_subjects()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.korean = LearningSubject.query.filter_by(key='korean').one()
        self.ssen = LearningSubject.query.filter_by(key='ssen').one()
        save_subject_study_weekdays(self.math.id, [TUESDAY])
        save_subject_study_weekdays(self.korean.id, [0])
        save_subject_study_weekdays(self.ssen.id, [4])
        self.math_plan = self._plan(self.math, title='수학 3-2')
        self._plan(self.korean, title='국어 3-2')
        self._plan(self.ssen, title='쎈 3-2')
        self._slug_n = 0
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        self.patchers = [
            mock.patch('features.study.schedule.kst_today', return_value=AS_OF),
            mock.patch('features.study.records.kst_today', return_value=AS_OF),
            mock.patch('features.study.coverage.kst_today', return_value=AS_OF),
            mock.patch('features.dates.kst_today', return_value=AS_OF),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        os.environ.pop(DEV_DATE_CONTROL_ENV, None)
        db.session.remove()
        self.ctx.pop()

    def _plan(self, subject, *, title, start_date=date(2026, 1, 1), end_page=100):
        plan = create_workbook_plan(
            grade=3,
            learning_subject_id=subject.id,
            textbook_title=title,
            start_page=1,
            end_page=end_page,
            start_date=start_date,
            target_completion_date=date(2026, 12, 31),
        )
        plan.exclusion_ranges_json = []
        plan.exclusion_ranges_text = ''
        db.session.commit()
        return plan

    def _peer_child(self, name, *, grade=3, include_in_stats=True):
        self._slug_n += 1
        row = Child(
            name=name,
            grade=grade,
            include_in_stats=include_in_stats,
            viewer_slug=f'peer{self._slug_n:022d}',
            created_at=datetime(2020, 1, 1),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def _window(self, window_days=WINDOW_DAYS):
        return current_window(AS_OF, window_days)

    def _expected_days(self, child, subject, window_days=WINDOW_DAYS):
        window = self._window(window_days)
        days = []
        cursor = window['start']
        while cursor <= window['end']:
            if normal_study_day(child.id, subject.id, cursor):
                days.append(cursor)
            cursor += timedelta(days=1)
        return days

    def _session(self, child, subject, day, status=STUDY_STATUS_STUDIED, *, start=1, end=10, plan_id=None):
        payload = {
            'child_id': child.id,
            'learning_subject_id': subject.id,
            'study_date': day,
            'study_status': status,
            'recorded_by_user_id': self.teacher.id,
            'record_verification': RECORD_VERIFICATION_OBSERVED,
            'actor_type': ACTOR_TEACHER,
            'input_channel': INPUT_CHANNEL_TEACHER,
        }
        if plan_id is not None:
            payload['learning_workbook_plan_id'] = plan_id
        if status == STUDY_STATUS_STUDIED:
            payload['start_page'] = start
            payload['end_page'] = end
        return create_study_session(**payload)

    def _raw_session(self, child, subject, day, *, start, end, plan_id):
        row = LearningStudySession(
            child_id=child.id,
            learning_subject_id=subject.id,
            study_date=day,
            study_status=STUDY_STATUS_STUDIED,
            start_page=start,
            end_page=end,
            textbook_title='이전 교재',
            learning_workbook_plan_id=plan_id,
            record_verification=RECORD_VERIFICATION_OBSERVED,
            recorded_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
            input_channel=INPUT_CHANNEL_TEACHER,
            created_at=datetime(2026, 1, 1),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def _confirm(
        self,
        child,
        subject,
        *,
        confirm_count=None,
        coverage_end=10,
        window_days=WINDOW_DAYS,
        not_studied_for_zero=False,
    ):
        expected = self._expected_days(child, subject, window_days)
        if not expected:
            raise AssertionError('expected study days are required for this fixture')
        if confirm_count is None:
            confirm_count = len(expected)
        confirmed = expected[:confirm_count]
        for index, day in enumerate(confirmed):
            if not_studied_for_zero:
                self._session(child, subject, day, STUDY_STATUS_EXPLICIT_NOT_STUDIED)
            elif index == 0:
                self._session(child, subject, day, start=1, end=coverage_end)
            else:
                self._session(child, subject, day, STUDY_STATUS_EXPLICIT_NOT_STUDIED)
        return expected

    def _points(self, child, total, on=None):
        row = DailyPoints(
            child_id=child.id,
            date=on or AS_OF,
            korean_points=total,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=0,
            manual_history='[]',
            total_points=total,
            created_by=self.teacher.id,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def _perf(self, **kwargs):
        return peer_comparison_for_subject(
            self.child.id,
            self.math.id,
            METRIC_PERFORMANCE,
            as_of=AS_OF,
            window_days=kwargs.pop('window_days', WINDOW_DAYS),
            **kwargs,
        )

    def _cov(self, **kwargs):
        return peer_comparison_for_subject(
            self.child.id,
            self.math.id,
            METRIC_COVERAGE,
            as_of=AS_OF,
            window_days=kwargs.pop('window_days', WINDOW_DAYS),
            **kwargs,
        )

    def _assert_no_rank(self, payload):
        keys = set(_walk_keys(payload))
        self.assertTrue(FORBIDDEN_RESULT_KEYS.isdisjoint(keys), keys & FORBIDDEN_RESULT_KEYS)

    def test_self_exclusion(self):
        self._confirm(self.child, self.math, coverage_end=40)
        peers = []
        for name, pages in (('p1', 10), ('p2', 20), ('p3', 30)):
            peer = self._peer_child(name)
            self._confirm(peer, self.math, coverage_end=pages)
            peers.append(peer)
        result = self._cov()
        self.assertEqual(result['peer_sample_count'], 3)
        self.assertEqual(result['peer_median'], statistics.median([0.10, 0.20, 0.30]))
        self.assertNotEqual(result['peer_median'], result['child_value'])

    def test_include_in_stats_false_peer_excluded(self):
        self._confirm(self.child, self.math)
        for name in ('p1', 'p2', 'p3'):
            self._confirm(self._peer_child(name), self.math)
        hidden = self._peer_child('hidden', include_in_stats=False)
        self._confirm(hidden, self.math, coverage_end=90)
        result = self._cov()
        self.assertEqual(result['peer_sample_count'], 3)
        self.assertNotEqual(result['peer_median'], 0.90)

    def test_target_child_excluded_from_stats(self):
        self.child.include_in_stats = False
        db.session.commit()
        self._confirm(self.child, self.math)
        for name in ('p1', 'p2', 'p3'):
            self._confirm(self._peer_child(name), self.math)
        result = self._perf()
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], REASON_EXCLUDED_FROM_STATS)
        self.assertIsNone(result['peer_median'])
        self.assertEqual(result['display_tier'], DISPLAY_NONE)

    def test_odd_n3_median(self):
        self._confirm(self.child, self.math, coverage_end=50)
        for name, pages in (('a', 10), ('b', 30), ('c', 90)):
            self._confirm(self._peer_child(name), self.math, coverage_end=pages)
        result = self._cov()
        self.assertEqual(result['display_tier'], DISPLAY_PRIMARY)
        self.assertEqual(result['peer_median'], 0.30)
        self.assertEqual(result['peer_sample_count'], 3)

    def test_even_n4_median(self):
        self._confirm(self.child, self.math, coverage_end=50)
        for name, pages in (('a', 10), ('b', 20), ('c', 30), ('d', 40)):
            self._confirm(self._peer_child(name), self.math, coverage_end=pages)
        result = self._cov()
        self.assertEqual(result['peer_sample_count'], 4)
        self.assertEqual(result['peer_median'], statistics.median([0.10, 0.20, 0.30, 0.40]))

    def test_peer_none_excluded(self):
        self._confirm(self.child, self.math)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)
        self._peer_child('empty')
        result = self._cov()
        self.assertEqual(result['peer_sample_count'], 3)
        self.assertTrue(result['available'])

    def test_peer_zero_is_valid(self):
        self._confirm(self.child, self.math)
        zeros = []
        for name in ('z1', 'z2', 'z3'):
            peer = self._peer_child(name)
            self._confirm(peer, self.math, not_studied_for_zero=True)
            zeros.append(peer)
        result = self._perf()
        self.assertTrue(result['available'])
        self.assertEqual(result['peer_median'], 0.0)
        self.assertEqual(result['peer_sample_count'], 3)

    def test_n0_unavailable(self):
        self._confirm(self.child, self.math)
        result = self._perf()
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], REASON_NO_PEERS)
        self.assertIsNone(result['peer_median'])
        self.assertEqual(result['peer_sample_count'], 0)
        self.assertEqual(result['display_tier'], DISPLAY_NONE)

    def test_n1_unavailable_no_median(self):
        self._confirm(self.child, self.math)
        self._confirm(self._peer_child('only'), self.math, coverage_end=80)
        result = self._cov()
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], REASON_INSUFFICIENT_PEERS)
        self.assertIsNone(result['peer_median'])
        self.assertIsNone(result['difference'])
        self.assertEqual(result['peer_sample_count'], 1)

    def test_n2_reference_only_keeps_median(self):
        self._confirm(self.child, self.math, coverage_end=40)
        self._confirm(self._peer_child('a'), self.math, coverage_end=10)
        self._confirm(self._peer_child('b'), self.math, coverage_end=30)
        result = self._cov()
        self.assertTrue(result['available'])
        self.assertEqual(result['display_tier'], DISPLAY_REFERENCE)
        self.assertEqual(result['peer_sample_count'], 2)
        self.assertEqual(result['peer_median'], statistics.median([0.10, 0.30]))
        self.assertIsNotNone(result['difference'])
        view = build_growth_view_model(self.child, as_of=AS_OF)
        math_card = next(item for item in view['learning']['subjects'] if item['key'] == 'math')
        self.assertFalse(math_card['coverage_peer']['show_median'])
        self.assertEqual(math_card['coverage_peer']['status_label'], PEER_REFERENCE_LABEL)
        self.assertIsNone(math_card['coverage_peer']['median_display'])

    def test_n3_primary(self):
        self._confirm(self.child, self.math)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)
        result = self._perf()
        self.assertEqual(result['display_tier'], DISPLAY_PRIMARY)
        self.assertTrue(result['available'])
        self.assertEqual(result['peer_sample_count'], 3)

    def test_rank_and_percentile_keys_absent(self):
        self._confirm(self.child, self.math)
        for name in ('a', 'b', 'c'):
            peer = self._peer_child(name)
            self._confirm(peer, self.math)
            self._points(peer, 100)
        self._points(self.child, 120)
        summary = peer_learning_summary(self.child.id, as_of=AS_OF)
        points = period_points_peer(self.child.id, as_of=AS_OF)
        self._assert_no_rank(summary)
        self._assert_no_rank(points)
        self._assert_no_rank(self._perf())

    def test_same_as_of_and_period(self):
        self._confirm(self.child, self.math)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)
        result = self._perf()
        window = self._window()
        self.assertEqual(result['as_of'], AS_OF)
        self.assertEqual(result['period']['start'], window['start'])
        self.assertEqual(result['period']['end'], window['end'])
        for peer_row in peer_learning_summary(self.child.id, as_of=AS_OF)['subjects']:
            self.assertEqual(peer_row['performance']['as_of'], AS_OF)
            self.assertEqual(peer_row['performance']['period']['end'], window['end'])
            self.assertEqual(peer_row['coverage']['period']['start'], window['start'])

    def test_grade_mismatch_excluded(self):
        self._confirm(self.child, self.math)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)
        other = self._peer_child('g4', grade=4)
        result = self._cov()
        self.assertEqual(result['peer_sample_count'], 3)
        self.assertIsNotNone(other.id)

    def test_subject_mismatch_excluded(self):
        self._confirm(self.child, self.math)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)
        extra = self._peer_child('korean-only')
        self._confirm(extra, self.korean, coverage_end=90)
        result = self._perf()
        self.assertEqual(result['peer_sample_count'], 3)

    def test_coverage_different_plan_excluded(self):
        old = create_workbook_plan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='이전 교재',
            start_page=1,
            end_page=100,
            start_date=date(2025, 1, 1),
            target_completion_date=date(2026, 5, 1),
        )
        old.exclusion_ranges_json = []
        old.exclusion_ranges_text = ''
        db.session.commit()
        self._confirm(self.child, self.math, coverage_end=20)
        matching = []
        for name, pages in (('a', 10), ('b', 30), ('c', 50)):
            peer = self._peer_child(name)
            self._confirm(peer, self.math, coverage_end=pages)
            matching.append(peer)
        outsider = self._peer_child('other-book')
        expected = self._expected_days(outsider, self.math)
        for index, day in enumerate(expected):
            if index == 0:
                self._raw_session(outsider, self.math, day, start=1, end=90, plan_id=old.id)
            else:
                self._session(outsider, self.math, day, STUDY_STATUS_EXPLICIT_NOT_STUDIED)
        result = self._cov()
        self.assertEqual(result['plan_id'], self.math_plan.id)
        self.assertEqual(result['peer_sample_count'], 3)
        self.assertEqual(result['peer_median'], statistics.median([0.10, 0.30, 0.50]))

    def test_coverage_same_plan_median(self):
        self._confirm(self.child, self.math, coverage_end=25)
        for name, pages in (('a', 10), ('b', 20), ('c', 40)):
            self._confirm(self._peer_child(name), self.math, coverage_end=pages)
        result = self._cov()
        self.assertEqual(result['metric'], METRIC_COVERAGE)
        self.assertEqual(result['peer_median'], 0.20)
        self.assertAlmostEqual(result['child_value'], 0.25)
        self.assertAlmostEqual(result['difference'], 0.05)

    def test_child_coverage_unavailable(self):
        self._confirm(self.child, self.math, not_studied_for_zero=True)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)
        result = self._cov()
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], REASON_CHILD_UNAVAILABLE)
        self.assertIsNone(result['peer_median'])

    def test_performance_allows_different_textbook(self):
        old = create_workbook_plan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='다른 교재',
            start_page=1,
            end_page=100,
            start_date=date(2025, 1, 1),
            target_completion_date=date(2026, 5, 1),
        )
        old.exclusion_ranges_json = []
        db.session.commit()
        self._confirm(self.child, self.math)
        for name in ('a', 'b'):
            self._confirm(self._peer_child(name), self.math)
        outsider = self._peer_child('diff-book')
        expected = self._expected_days(outsider, self.math)
        for index, day in enumerate(expected):
            if index == 0:
                self._raw_session(outsider, self.math, day, start=1, end=10, plan_id=old.id)
            else:
                self._session(outsider, self.math, day, STUDY_STATUS_EXPLICIT_NOT_STUDIED)
        result = self._perf()
        self.assertEqual(result['peer_sample_count'], 3)
        self.assertTrue(result['available'])
        coverage = self._cov()
        self.assertEqual(coverage['peer_sample_count'], 2)

    def test_confirmation_primary_gate(self):
        self._confirm(self.child, self.math)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)
        result = self._perf()
        self.assertEqual(result['display_tier'], DISPLAY_PRIMARY)
        child_period = subject_period(
            self.child.id, self.math.id, self._window()['start'], self._window()['end'],
        )
        self.assertGreaterEqual(child_period['confirmation_rate'], 0.70)

    def test_child_confirmation_limited(self):
        expected = self._expected_days(self.child, self.math)
        self.assertGreaterEqual(len(expected), 5)
        self._confirm(self.child, self.math, confirm_count=3, coverage_end=20)
        child_period = subject_period(
            self.child.id, self.math.id, self._window()['start'], self._window()['end'],
        )
        self.assertGreaterEqual(child_period['confirmation_rate'], 0.50)
        self.assertLess(child_period['confirmation_rate'], 0.70)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)
        result = self._perf()
        self.assertTrue(result['available'])
        self.assertEqual(result['display_tier'], DISPLAY_LIMITED)
        self.assertIsNotNone(result['peer_median'])

    def test_low_confirmation_peer_excluded(self):
        self._confirm(self.child, self.math)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)
        low = self._peer_child('low')
        expected = self._expected_days(low, self.math)
        self._session(low, self.math, expected[0], start=1, end=90)
        low_period = subject_period(low.id, self.math.id, self._window()['start'], self._window()['end'])
        self.assertLess(low_period['confirmation_rate'], 0.50)
        result = self._cov()
        self.assertEqual(result['peer_sample_count'], 3)
        self.assertNotEqual(result['peer_median'], 0.90)

    def test_confirmation_unavailable(self):
        save_subject_study_weekdays(self.math.id, [])
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.korean)
        result = self._perf()
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], REASON_CHILD_CONFIRMATION_UNAVAILABLE)
        self.assertIsNone(result['peer_median'])
        self.assertIsNone(result['child_value'])

    def test_min_expected_days_not_used_as_peer_filter(self):
        source = inspect.getsource(study_peer)
        self.assertNotIn('MIN_EXPECTED_DAYS_FOR_PERIOD_CHANGE', source)
        self.assertNotIn('enough_days', source)
        window_days = 7
        self._confirm(self.child, self.math, window_days=window_days)
        child_period = subject_period(
            self.child.id, self.math.id, self._window(window_days)['start'], self._window(window_days)['end'],
        )
        self.assertLess(child_period['expected_days'], MIN_EXPECTED_DAYS_FOR_PERIOD_CHANGE)
        self.assertGreater(child_period['expected_days'], 0)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math, window_days=window_days)
        result = self._perf(window_days=window_days)
        self.assertTrue(result['available'])
        self.assertEqual(result['display_tier'], DISPLAY_PRIMARY)
        self.assertEqual(result['peer_sample_count'], 3)

    def test_points_same_grade_median_and_self_exclusion(self):
        self._points(self.child, 400)
        self._points(self._peer_child('a'), 100)
        self._points(self._peer_child('b'), 200)
        self._points(self._peer_child('c'), 300)
        result = period_points_peer(self.child.id, as_of=AS_OF)
        self.assertEqual(result['metric'], METRIC_PERIOD_POINTS)
        self.assertEqual(result['child_value'], 400)
        self.assertEqual(result['peer_median'], 200)
        self.assertEqual(result['difference'], 200)
        self.assertEqual(result['peer_sample_count'], 3)
        self.assertEqual(result['display_tier'], DISPLAY_PRIMARY)
        self._assert_no_rank(result)

    def test_points_missing_records_are_zero_not_unavailable(self):
        self._points(self.child, 50)
        self._peer_child('z1')
        self._peer_child('z2')
        self._peer_child('z3')
        result = period_points_peer(self.child.id, as_of=AS_OF)
        self.assertTrue(result['available'])
        self.assertEqual(result['peer_median'], 0)
        self.assertEqual(result['peer_sample_count'], 3)

    def test_active_inactive_subject_summary(self):
        self._confirm(self.child, self.math)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)
        self.ssen.is_active = False
        db.session.commit()
        summary = peer_learning_summary(self.child.id, as_of=AS_OF)
        keys = [row['subject_key'] for row in summary['subjects']]
        self.assertIn('math', keys)
        self.assertIn('korean', keys)
        self.assertNotIn('ssen', keys)

    def test_future_data_not_leaked(self):
        self._confirm(self.child, self.math, coverage_end=20)
        peers = []
        for name, pages in (('a', 10), ('b', 30), ('c', 50)):
            peer = self._peer_child(name)
            self._confirm(peer, self.math, coverage_end=pages)
            peers.append(peer)
        before_cov = self._cov()
        before_points = period_points_peer(self.child.id, as_of=AS_OF)
        future = AS_OF + timedelta(days=2)
        self._raw_session(self.child, self.math, future, start=1, end=100, plan_id=self.math_plan.id)
        self._points(self.child, 9999, on=future)
        self._points(peers[0], 8888, on=future)
        after_cov = self._cov()
        after_points = period_points_peer(self.child.id, as_of=AS_OF)
        self.assertEqual(after_cov['child_value'], before_cov['child_value'])
        self.assertEqual(after_cov['peer_median'], before_cov['peer_median'])
        self.assertEqual(after_points['child_value'], before_points['child_value'])
        self.assertEqual(after_points['peer_median'], before_points['peer_median'])

    def test_legacy_snapshot_page_not_used(self):
        source = inspect.getsource(study_peer)
        self.assertNotIn('LearningProgressEntry', source)
        self._confirm(self.child, self.math, coverage_end=10)
        for name, pages in (('a', 20), ('b', 30), ('c', 40)):
            peer = self._peer_child(name)
            self._confirm(peer, self.math, coverage_end=pages)
            db.session.add(LearningProgressEntry(
                child_id=peer.id,
                learning_subject_id=self.math.id,
                recorded_on=AS_OF,
                textbook_title='수학 3-2',
                page=999,
                created_by_user_id=self.teacher.id,
            ))
        db.session.add(LearningProgressEntry(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            recorded_on=AS_OF,
            textbook_title='수학 3-2',
            page=1,
            created_by_user_id=self.teacher.id,
        ))
        db.session.commit()
        result = self._cov()
        self.assertEqual(result['peer_median'], 0.30)
        self.assertNotEqual(result['peer_median'], 999)
        self.assertNotIn('current_page', result)

    def test_all_plan_mismatch_reason(self):
        self._confirm(self.child, self.math)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)

        def fake_plan_id(child, subject_id, as_of):
            if child.id == self.child.id:
                return self.math_plan.id
            return self.math_plan.id + 999

        with mock.patch('features.study.peer._canonical_plan_id', side_effect=fake_plan_id):
            result = self._cov()
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], REASON_TEXTBOOK_MISMATCH)
        self.assertIsNone(result['peer_median'])

    def test_child_confirmation_excluded(self):
        expected = self._expected_days(self.child, self.math)
        self._session(self.child, self.math, expected[0], start=1, end=10)
        child_period = subject_period(
            self.child.id, self.math.id, self._window()['start'], self._window()['end'],
        )
        self.assertLess(child_period['confirmation_rate'], 0.50)
        for name in ('a', 'b', 'c'):
            self._confirm(self._peer_child(name), self.math)
        result = self._perf()
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], REASON_CHILD_CONFIRMATION_EXCLUDED)
        self.assertIsNone(result['peer_median'])

    def test_growth_ui_hides_snapshot_peer_and_shows_canonical(self):
        self._confirm(self.child, self.math, coverage_end=20)
        self._points(self.child, 125)
        for name, pages, points in (('a', 10, 100), ('b', 30, 110), ('c', 50, 140)):
            peer = self._peer_child(name)
            self._confirm(peer, self.math, coverage_end=pages)
            self._points(peer, points)
        view = build_growth_view_model(self.child, as_of=AS_OF)
        math_card = next(item for item in view['learning']['subjects'] if item['key'] == 'math')
        self.assertTrue(math_card['performance_peer']['show_median'])
        self.assertTrue(math_card['coverage_peer']['show_median'])
        self.assertTrue(view['points']['peer']['show_median'])
        self.assertIn('비교 3명', math_card['coverage_peer']['n_display'])
        client = app.test_client()
        with client.session_transaction() as sess:
            sess['_user_id'] = str(self.teacher.id)
            sess['_fresh'] = True
        body = client.get(
            f'/children/{self.child.id}/growth',
            query_string={'as_of': AS_OF.isoformat()},
        ).get_data(as_text=True)
        self.assertIn('data-testid="canonical-peer-performance-math"', body)
        self.assertIn('data-testid="canonical-peer-coverage-math"', body)
        self.assertIn('data-testid="canonical-peer-points"', body)
        self.assertNotIn('동학년 동일 교재', body)
        self.assertNotIn('중앙값 대비', body)
        peer_perf = body.split('data-testid="canonical-peer-performance-math"', 1)[1][:800]
        for banned in ('순위', '상위권', '백분위', '우수', '열등', '평균 이상', '뒤처짐'):
            self.assertNotIn(banned, peer_perf)
        lonely = self._peer_child('lonely', grade=6)
        lonely_body = client.get(
            f'/children/{lonely.id}/growth',
            query_string={'as_of': AS_OF.isoformat()},
        ).get_data(as_text=True)
        self.assertIn(PEER_NONE_LABEL, lonely_body)
        self.assertNotIn('같은 학년 또래 중앙값 0%', lonely_body)
        self.assertNotIn('같은 학년 또래 중앙값 0점', lonely_body)
