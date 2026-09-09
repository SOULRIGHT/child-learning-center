"""Growth vNext Step 3: 수행률 / 데이터 확인률 / 기간 비교 eligibility."""
from __future__ import annotations

import inspect
import unittest
from datetime import date, datetime
from unittest import mock

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    LearningSubject,
    RECORD_VERIFICATION_OBSERVED,
    RECORD_VERIFICATION_VERIFIED,
    STUDY_STATUS_STUDIED,
    STUDY_STATUS_UNKNOWN,
)
from features.planning.service import create_workbook_plan  # noqa: E402
from features.progress.service import ensure_default_subjects  # noqa: E402
from features.study.calendar import save_subject_study_weekdays  # noqa: E402
from features.study.metrics import (  # noqa: E402
    INTERPRETATION_FORBIDDEN,
    INTERPRETATION_LIMITED,
    INTERPRETATION_PRIMARY,
    INTERPRETATION_UNAVAILABLE,
    compare_periods,
    confirmation_band,
    overall_period,
    subject_period,
)
from features.study.records import create_study_session  # noqa: E402
import features.study.metrics as study_metrics  # noqa: E402

TODAY = date(2026, 9, 8)
WED = date(2026, 9, 2)
SAT = date(2026, 9, 5)


class StudyMetricsTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='metrics_teacher',
            name='지표교사',
            role='돌봄선생님',
            email='metrics-teacher@example.test',
            password_hash='',
        )
        self.child = Child(
            name='지표아동',
            grade=3,
            viewer_slug='metricschildmetricschild',
            created_at=datetime(2020, 1, 1),
        )
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        ensure_default_subjects()
        self.korean = LearningSubject.query.filter_by(key='korean').one()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.ssen = LearningSubject.query.filter_by(key='ssen').one()
        save_subject_study_weekdays(self.korean.id, [0, 2])
        save_subject_study_weekdays(self.math.id, [1, 3])
        save_subject_study_weekdays(self.ssen.id, [4])
        for subject in (self.korean, self.math, self.ssen):
            create_workbook_plan(
                grade=3,
                learning_subject_id=subject.id,
                textbook_title=f'{subject.name} 교재',
                start_page=1,
                end_page=200,
                start_date=date(2026, 3, 1),
                target_completion_date=date(2026, 12, 31),
            )
        self.patchers = [
            mock.patch('features.study.schedule.kst_today', return_value=TODAY),
            mock.patch('features.study.records.kst_today', return_value=TODAY),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _session(self, subject, day, status, **kwargs):
        payload = {
            'child_id': self.child.id,
            'learning_subject_id': subject.id,
            'study_date': day,
            'study_status': status,
            'recorded_by_user_id': self.teacher.id,
            'record_verification': RECORD_VERIFICATION_OBSERVED,
            'actor_type': 'teacher',
            'input_channel': 'teacher',
        }
        if status == STUDY_STATUS_STUDIED:
            payload['start_page'] = 10
            payload['end_page'] = 11
        payload.update(kwargs)
        return create_study_session(**payload)

    def test_missing_is_unknown_not_not_studied(self):
        result = subject_period(self.child.id, self.korean.id, WED, WED)
        self.assertEqual(result['expected_days'], 1)
        self.assertEqual(result['studied_days'], 0)
        self.assertEqual(result['explicit_not_studied_days'], 0)
        self.assertEqual(result['unknown_days'], 1)
        self.assertEqual(result['missing_days'], 1)
        self.assertEqual(result['performance_rate'], 0.0)
        self.assertEqual(result['confirmation_rate'], 0.0)

    def test_explicit_unknown_is_unknown(self):
        self._session(self.korean, WED, STUDY_STATUS_UNKNOWN)
        result = subject_period(self.child.id, self.korean.id, WED, WED)
        self.assertEqual(result['unknown_days'], 1)
        self.assertEqual(result['explicit_unknown_days'], 1)
        self.assertEqual(result['confirmation_rate'], 0.0)

    def test_observed_studied_counts_as_performance(self):
        self._session(
            self.korean,
            WED,
            STUDY_STATUS_STUDIED,
            record_verification=RECORD_VERIFICATION_OBSERVED,
        )
        result = subject_period(self.child.id, self.korean.id, WED, WED)
        self.assertEqual(result['studied_days'], 1)
        self.assertEqual(result['performance_rate'], 1.0)
        self.assertEqual(result['confirmation_rate'], 1.0)

    def test_verified_studied_also_counts(self):
        self._session(
            self.math,
            TODAY,
            STUDY_STATUS_STUDIED,
            record_verification=RECORD_VERIFICATION_VERIFIED,
        )
        result = subject_period(self.child.id, self.math.id, TODAY, TODAY)
        self.assertEqual(result['studied_days'], 1)
        self.assertEqual(result['performance_rate'], 1.0)

    def test_extra_studied_on_unscheduled_day_excluded_from_rate(self):
        self._session(self.korean, SAT, STUDY_STATUS_STUDIED)
        result = subject_period(self.child.id, self.korean.id, SAT, SAT)
        self.assertEqual(result['expected_days'], 0)
        self.assertIsNone(result['performance_rate'])
        self.assertIsNone(result['confirmation_rate'])
        self.assertEqual(result['interpretation'], INTERPRETATION_UNAVAILABLE)
        self.assertEqual(result['extra_studied_days'], 1)

    def test_expected_zero_is_unavailable_not_zero_percent(self):
        result = subject_period(self.child.id, self.ssen.id, WED, WED)
        self.assertEqual(result['expected_days'], 0)
        self.assertIsNone(result['performance_rate'])
        self.assertNotEqual(result['performance_rate'], 0.0)

    def test_overall_same_day_two_subjects_denominator_two(self):
        save_subject_study_weekdays(self.math.id, [2])
        result = overall_period(self.child.id, WED, WED)
        self.assertEqual(result['expected_days'], 2)
        self._session(self.korean, WED, STUDY_STATUS_STUDIED)
        result = overall_period(self.child.id, WED, WED)
        self.assertEqual(result['expected_days'], 2)
        self.assertEqual(result['studied_days'], 1)
        self.assertEqual(result['performance_rate'], 0.5)

    def test_multiple_studied_sessions_count_as_one_day(self):
        self._session(self.korean, WED, STUDY_STATUS_STUDIED, start_page=10, end_page=11)
        self._session(self.korean, WED, STUDY_STATUS_STUDIED, start_page=12, end_page=13)
        result = subject_period(self.child.id, self.korean.id, WED, WED)
        self.assertEqual(result['studied_days'], 1)
        self.assertEqual(result['expected_days'], 1)

    def test_confirmation_band_boundaries(self):
        self.assertEqual(confirmation_band(0.49, 100), INTERPRETATION_FORBIDDEN)
        self.assertEqual(confirmation_band(0.50, 100), INTERPRETATION_LIMITED)
        self.assertEqual(confirmation_band(0.69, 100), INTERPRETATION_LIMITED)
        self.assertEqual(confirmation_band(0.70, 100), INTERPRETATION_PRIMARY)
        self.assertEqual(confirmation_band(0.70, 0), INTERPRETATION_UNAVAILABLE)

    def test_period_change_day_and_delta_boundaries(self):
        def _period(expected, rate, confirmation, band):
            return {
                'expected_days': expected,
                'performance_rate': rate,
                'confirmation_rate': confirmation,
                'interpretation': band,
            }

        seven = compare_periods(
            _period(7, 0.8, 0.8, INTERPRETATION_PRIMARY),
            _period(8, 0.6, 0.8, INTERPRETATION_PRIMARY),
        )
        self.assertFalse(seven['enough_days'])
        self.assertFalse(seven['period_change_allowed'])

        eight = compare_periods(
            _period(8, 0.8, 0.8, INTERPRETATION_PRIMARY),
            _period(8, 0.6, 0.8, INTERPRETATION_PRIMARY),
        )
        self.assertTrue(eight['enough_days'])
        self.assertTrue(eight['period_change_allowed'])
        self.assertAlmostEqual(eight['performance_delta_pp'], 20.0)
        self.assertTrue(eight['major_insight_eligible'])

        small = compare_periods(
            _period(8, 0.70, 0.80, INTERPRETATION_PRIMARY),
            _period(8, 0.601, 0.80, INTERPRETATION_PRIMARY),
        )
        self.assertLess(abs(small['performance_delta_pp']), 10.0)
        self.assertTrue(small['period_change_allowed'])
        self.assertFalse(small['major_insight_eligible'])

        ten = compare_periods(
            _period(8, 0.70, 0.80, INTERPRETATION_PRIMARY),
            _period(8, 0.60, 0.80, INTERPRETATION_PRIMARY),
        )
        self.assertGreaterEqual(abs(ten['performance_delta_pp']), 10.0)
        self.assertTrue(ten['major_insight_eligible'])

        forbidden = compare_periods(
            _period(8, 0.80, 0.49, INTERPRETATION_FORBIDDEN),
            _period(8, 0.60, 0.80, INTERPRETATION_PRIMARY),
        )
        self.assertFalse(forbidden['period_change_allowed'])
        self.assertFalse(forbidden['major_insight_eligible'])

    def test_metrics_ignore_daily_points_and_verification_axis(self):
        source = inspect.getsource(study_metrics)
        self.assertNotIn('DailyPoints', source)
        self.assertNotIn('RECORD_VERIFICATION', source)
