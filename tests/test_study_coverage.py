"""Growth vNext Step 4: unique coverage / observed progress / completion forecast."""
from __future__ import annotations

import inspect
import statistics
import time
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    CenterNonStudyDay,
    CenterSystemHolidaySeed,
    LearningProgressEntry,
    LearningStudySession,
    LearningSubject,
    LearningWorkbookPlan,
    RECORD_VERIFICATION_OBSERVED,
    RECORD_VERIFICATION_VERIFIED,
    STUDY_STATUS_EXPLICIT_NOT_STUDIED,
    STUDY_STATUS_STUDIED,
    STUDY_STATUS_UNKNOWN,
)
from features.planning.service import (  # noqa: E402
    create_workbook_plan,
    set_child_weekdays_override,
    update_center_weekdays,
)
from features.progress.service import ensure_default_subjects  # noqa: E402
from features.study.calendar import (  # noqa: E402
    delete_center_non_study_day,
    save_center_non_study_day,
    save_subject_study_weekdays,
)
from features.study.constants import INPUT_CHANNEL_TEACHER, NON_STUDY_SOURCE_CENTER  # noqa: E402
from features.study.coverage import (  # noqa: E402
    FORECAST_RECENT_N,
    STATUS_ALREADY_COMPLETE,
    STATUS_EXCLUSIONS_UNCONFIRMED,
    STATUS_INSUFFICIENT_SESSIONS,
    STATUS_NO_FUTURE_STUDY_DAYS,
    STATUS_NO_STUDIED_SESSIONS,
    STATUS_PLAN_SWITCH,
    STATUS_UNSTABLE_PACE,
    VS_DELAY_2W,
    VS_ON_OR_AHEAD,
    VS_OVERLAPS,
    VS_SLIGHT_DELAY,
    VS_TARGET_PASSED,
    completion_forecast,
    learning_progress_summary,
    progress_for_plan,
    unique_page_coverage,
)
from features.study.holidays import (  # noqa: E402
    ensure_system_holidays,
    korean_public_holidays,
    year_system_holidays_initialized,
)
from features.study.records import create_study_session  # noqa: E402
from features.study.schedule import study_calendar_allows  # noqa: E402

AS_OF = date(2026, 9, 8)  # Tue


class StudyCoverageTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='cov_teacher',
            name='커버리지교사',
            role='돌봄선생님',
            email='coverage@example.test',
            password_hash='',
        )
        self.child = Child(
            name='커버리지아동',
            grade=3,
            viewer_slug='coveragechildcoveragechld',
            created_at=datetime(2020, 1, 1),
        )
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        ensure_default_subjects()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.korean = LearningSubject.query.filter_by(key='korean').one()
        self.patchers = [
            mock.patch('features.study.records.kst_today', return_value=AS_OF),
            mock.patch('features.study.coverage.kst_today', return_value=AS_OF),
            mock.patch('features.study.schedule.kst_today', return_value=AS_OF),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _plan(self, *, title='수학 3-2', subject=None, start_page=1, end_page=200,
              start_date=date(2026, 1, 1), target=date(2026, 12, 31),
              exclusions=None, confirm_empty=False):
        plan = create_workbook_plan(
            grade=3,
            learning_subject_id=(subject or self.math).id,
            textbook_title=title,
            start_page=start_page,
            end_page=end_page,
            start_date=start_date,
            target_completion_date=target,
            exclusion_ranges_text=exclusions,
        )
        if confirm_empty:
            plan.exclusion_ranges_json = []
            db.session.commit()
        return plan

    def _session(self, plan, day, start, end, *, verification=RECORD_VERIFICATION_OBSERVED,
                 created_at=None, child=None, subject_id=None):
        row = create_study_session(
            child_id=(child or self.child).id,
            learning_subject_id=subject_id or plan.learning_subject_id,
            study_date=day,
            study_status=STUDY_STATUS_STUDIED,
            start_page=start,
            end_page=end,
            recorded_by_user_id=self.teacher.id,
            record_verification=verification,
            learning_workbook_plan_id=plan.id,
            actor_type=ACTOR_TEACHER,
            input_channel=INPUT_CHANNEL_TEACHER,
        )
        if created_at is not None:
            row.created_at = created_at
            db.session.commit()
        return row

    def _raw_session(self, **kwargs):
        payload = {
            'child_id': self.child.id,
            'learning_subject_id': self.math.id,
            'study_date': AS_OF,
            'study_status': STUDY_STATUS_STUDIED,
            'start_page': 1,
            'end_page': 10,
            'record_verification': RECORD_VERIFICATION_OBSERVED,
            'recorded_by_user_id': self.teacher.id,
            'actor_type': ACTOR_TEACHER,
            'input_channel': INPUT_CHANNEL_TEACHER,
            'created_at': datetime(2026, 1, 1),
        }
        payload.update(kwargs)
        row = LearningStudySession(**payload)
        db.session.add(row)
        db.session.commit()
        return row

    def _enable_daily_calendar(self, subject=None):
        subject = subject or self.math
        update_center_weekdays(list(range(7)))
        save_subject_study_weekdays(subject.id, list(range(7)))

    def test_overlapping_ranges_unique_15(self):
        plan = self._plan(confirm_empty=True)
        self._session(plan, AS_OF - timedelta(days=2), 1, 10)
        self._session(plan, AS_OF - timedelta(days=1), 5, 15)
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(cov['observed_page_count'], 15)
        self.assertEqual(cov['assigned_covered_page_count'], 15)
        self.assertEqual(cov['observed_ranges'], [{'start': 1, 'end': 15}])

    def test_gapped_ranges_unique_21_no_interpolation(self):
        plan = self._plan(confirm_empty=True)
        self._session(plan, AS_OF - timedelta(days=2), 1, 10)
        self._session(plan, AS_OF - timedelta(days=1), 20, 30)
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(cov['observed_page_count'], 21)
        self.assertEqual(cov['assigned_covered_page_count'], 21)
        self.assertEqual(
            cov['observed_ranges'],
            [{'start': 1, 'end': 10}, {'start': 20, 'end': 30}],
        )
        self.assertNotEqual(cov['observed_page_count'], 30)
        self.assertEqual(cov['latest_observed_end_page'], 30)
        self.assertNotEqual(cov['coverage_ratio'], 30 / 200)

    def test_duplicate_review_does_not_increase_count(self):
        plan = self._plan(confirm_empty=True)
        self._session(plan, AS_OF - timedelta(days=2), 1, 10)
        self._session(plan, AS_OF - timedelta(days=1), 1, 10)
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(cov['observed_page_count'], 10)
        self.assertEqual(cov['assigned_covered_page_count'], 10)

    def test_same_day_multiple_studied_ranges(self):
        plan = self._plan(confirm_empty=True)
        self._session(plan, AS_OF, 1, 10, created_at=datetime(2026, 9, 8, 1, 0, 0))
        self._session(plan, AS_OF, 20, 25, created_at=datetime(2026, 9, 8, 2, 0, 0))
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(cov['observed_page_count'], 16)

    def test_out_of_order_input_still_unions(self):
        plan = self._plan(confirm_empty=True)
        self._session(plan, AS_OF, 20, 30)
        self._session(plan, AS_OF - timedelta(days=3), 1, 10)
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(cov['observed_page_count'], 21)

    def test_exclusions_removed_from_denominator_and_numerator(self):
        plan = self._plan(exclusions='50-60')
        self._session(plan, AS_OF - timedelta(days=1), 1, 10)
        self._session(plan, AS_OF, 45, 65)
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(cov['assigned_denominator'], 189)
        self.assertEqual(cov['observed_page_count'], 31)
        self.assertEqual(cov['assigned_covered_page_count'], 20)
        self.assertNotIn({'start': 50, 'end': 60}, cov['assigned_covered_ranges'])

    def test_exclusions_none_vs_empty_list(self):
        unknown = self._plan()
        self.assertIsNone(unknown.exclusion_ranges_json)
        self._session(unknown, AS_OF, 1, 10)
        unknown_cov = unique_page_coverage(self.child.id, unknown, as_of=AS_OF)
        self.assertEqual(unknown_cov['observed_page_count'], 10)
        self.assertIsNone(unknown_cov['assigned_denominator'])
        self.assertIsNone(unknown_cov['assigned_covered_page_count'])
        self.assertIsNone(unknown_cov['coverage_ratio'])
        self.assertFalse(unknown_cov['available'])
        self.assertEqual(unknown_cov['status'], STATUS_EXCLUSIONS_UNCONFIRMED)
        unknown_fc = completion_forecast(self.child.id, unknown, as_of=AS_OF)
        self.assertFalse(unknown_fc['available'])
        self.assertEqual(unknown_fc['reason'], STATUS_EXCLUSIONS_UNCONFIRMED)

        confirmed = self._plan(title='국어 확정', subject=self.korean, confirm_empty=True)
        self._session(confirmed, AS_OF, 1, 10)
        confirmed_cov = unique_page_coverage(self.child.id, confirmed, as_of=AS_OF)
        self.assertEqual(confirmed_cov['assigned_denominator'], 200)
        self.assertEqual(confirmed_cov['assigned_covered_page_count'], 10)
        self.assertEqual(confirmed_cov['coverage_ratio'], 10 / 200)

    def test_zero_sessions_is_na_not_zero_percent(self):
        plan = self._plan(confirm_empty=True)
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        progress = progress_for_plan(self.child.id, plan, as_of=AS_OF)
        self.assertFalse(cov['available'])
        self.assertEqual(cov['status'], STATUS_NO_STUDIED_SESSIONS)
        self.assertIsNone(cov['coverage_ratio'])
        self.assertIsNone(progress['observed_complete'])
        self.assertNotEqual(cov['coverage_ratio'], 0)
        self.assertNotEqual(cov['coverage_ratio'], 0.0)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertFalse(fc['available'])
        self.assertEqual(fc['reason'], STATUS_NO_STUDIED_SESSIONS)
        self.assertIsNone(fc['earliest_date'])

    def test_observed_and_verified_both_count(self):
        plan = self._plan(confirm_empty=True)
        self._session(plan, AS_OF - timedelta(days=1), 1, 10, verification=RECORD_VERIFICATION_OBSERVED)
        self._session(plan, AS_OF, 11, 20, verification=RECORD_VERIFICATION_VERIFIED)
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(cov['observed_page_count'], 20)

    def test_not_studied_and_unknown_excluded(self):
        plan = self._plan(confirm_empty=True)
        self._session(plan, AS_OF - timedelta(days=2), 1, 10)
        create_study_session(
            child_id=self.child.id,
            learning_subject_id=plan.learning_subject_id,
            study_date=AS_OF - timedelta(days=1),
            study_status=STUDY_STATUS_EXPLICIT_NOT_STUDIED,
            recorded_by_user_id=self.teacher.id,
            learning_workbook_plan_id=plan.id,
            actor_type=ACTOR_TEACHER,
            input_channel=INPUT_CHANNEL_TEACHER,
        )
        create_study_session(
            child_id=self.child.id,
            learning_subject_id=plan.learning_subject_id,
            study_date=AS_OF,
            study_status=STUDY_STATUS_UNKNOWN,
            recorded_by_user_id=self.teacher.id,
            learning_workbook_plan_id=plan.id,
            actor_type=ACTOR_TEACHER,
            input_channel=INPUT_CHANNEL_TEACHER,
        )
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(cov['observed_page_count'], 10)
        self.assertEqual(cov['studied_session_count'], 1)

    def test_null_plan_id_row_excluded(self):
        plan = self._plan(confirm_empty=True)
        self._session(plan, AS_OF - timedelta(days=1), 1, 10)
        self._raw_session(
            learning_workbook_plan_id=None,
            textbook_title=plan.textbook_title,
            start_page=20,
            end_page=30,
            study_date=AS_OF,
        )
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(cov['observed_page_count'], 10)

    def test_same_title_different_plans_are_separate(self):
        plan_a = self._plan(title='같은 제목', start_date=date(2026, 1, 1), confirm_empty=True)
        plan_b = self._plan(title='같은 제목', start_date=date(2026, 9, 1), confirm_empty=True)
        self._session(plan_a, date(2026, 8, 1), 1, 10)
        self._session(plan_b, AS_OF, 20, 30)
        cov_a = unique_page_coverage(self.child.id, plan_a, as_of=AS_OF)
        cov_b = unique_page_coverage(self.child.id, plan_b, as_of=AS_OF)
        self.assertEqual(cov_a['observed_page_count'], 10)
        self.assertEqual(cov_b['observed_page_count'], 11)

    def test_snapshot_page_does_not_fill_coverage(self):
        plan = self._plan(confirm_empty=True)
        db.session.add(LearningProgressEntry(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            recorded_on=AS_OF,
            textbook_title=plan.textbook_title,
            page=80,
            created_by_user_id=self.teacher.id,
        ))
        db.session.commit()
        self._session(plan, AS_OF, 1, 10)
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(cov['observed_page_count'], 10)
        self.assertNotEqual(cov['observed_page_count'], 80)

    def test_as_of_excludes_later_sessions(self):
        plan = self._plan(confirm_empty=True)
        self._session(plan, AS_OF - timedelta(days=1), 1, 10)
        self._raw_session(
            learning_workbook_plan_id=plan.id,
            learning_subject_id=plan.learning_subject_id,
            start_page=11,
            end_page=20,
            study_date=AS_OF + timedelta(days=1),
        )
        cov = unique_page_coverage(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(cov['observed_page_count'], 10)

    def _eight_pace_sessions(self, plan, *, extra_oldest=None, as_of=AS_OF):
        day = as_of - timedelta(days=FORECAST_RECENT_N)
        if extra_oldest is not None:
            start, end = extra_oldest
            self._session(plan, day - timedelta(days=1), start, end)
        start = 1
        for _ in range(FORECAST_RECENT_N):
            end = start + 9
            self._session(plan, day, start, end)
            start = end + 1
            day += timedelta(days=1)
        return start - 1

    def test_forecast_unavailable_with_seven_valid_sessions(self):
        plan = self._plan(confirm_empty=True)
        self._enable_daily_calendar()
        start = 1
        day = AS_OF - timedelta(days=7)
        for _ in range(7):
            self._session(plan, day, start, start + 9)
            start += 10
            day += timedelta(days=1)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertFalse(fc['available'])
        self.assertEqual(fc['reason'], STATUS_INSUFFICIENT_SESSIONS)
        self.assertIsNone(fc['earliest_date'])

    def test_forecast_available_at_exactly_eight_sessions(self):
        plan = self._plan(confirm_empty=True, end_page=200)
        self._enable_daily_calendar()
        self._eight_pace_sessions(plan)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertTrue(fc['available'])
        self.assertEqual(fc['median_new_pages'], 10)
        self.assertIsNotNone(fc['earliest_date'])
        self.assertIsNotNone(fc['latest_date'])

    def test_overlapping_session_new_pages_delta_and_repeat_zero(self):
        plan = self._plan(confirm_empty=True)
        self._enable_daily_calendar()
        self._session(plan, AS_OF - timedelta(days=10), 1, 10)
        self._session(plan, AS_OF - timedelta(days=9), 5, 15)
        self._session(plan, AS_OF - timedelta(days=8), 1, 10)
        from features.study.coverage import _new_pages_series, _valid_forecast_sessions
        series = _new_pages_series(_valid_forecast_sessions(self.child.id, plan, AS_OF))
        self.assertEqual([item['new_pages'] for item in series], [10, 5, 0])

    def test_recent_eight_only_for_pace(self):
        plan = self._plan(confirm_empty=True, end_page=400)
        self._enable_daily_calendar()
        self._session(plan, AS_OF - timedelta(days=9), 1, 100)
        start = 101
        day = AS_OF - timedelta(days=8)
        pages = []
        for idx in range(8):
            width = 1 if idx < 4 else 10
            end = start + width - 1
            self._session(plan, day, start, end)
            pages.append(width)
            start = end + 1
            day += timedelta(days=1)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertTrue(fc['available'])
        self.assertEqual(fc['sample_new_pages'], pages)
        self.assertEqual(fc['median_new_pages'], statistics.median(pages))
        quartiles = statistics.quantiles(pages, n=4, method='inclusive')
        self.assertEqual(fc['p25_new_pages'], quartiles[0])
        self.assertEqual(fc['p75_new_pages'], quartiles[2])
        self.assertNotEqual(fc['median_new_pages'], statistics.median([100] + pages))

    def test_p25_zero_makes_forecast_unavailable(self):
        plan = self._plan(confirm_empty=True)
        self._enable_daily_calendar()
        self._session(plan, AS_OF - timedelta(days=8), 1, 10)
        for offset in range(7):
            self._session(plan, AS_OF - timedelta(days=7 - offset), 1, 10)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertFalse(fc['available'])
        self.assertEqual(fc['reason'], STATUS_UNSTABLE_PACE)
        self.assertIsNone(fc['earliest_date'])
        self.assertLessEqual(fc['p25_new_pages'], 0)

    def test_remaining_zero_is_observed_complete(self):
        plan = self._plan(confirm_empty=True, end_page=20)
        self._session(plan, AS_OF, 1, 20)
        progress = progress_for_plan(self.child.id, plan, as_of=AS_OF)
        self.assertTrue(progress['observed_complete'])
        self.assertEqual(progress['remaining_assigned_pages'], 0)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertFalse(fc['available'])
        self.assertEqual(fc['reason'], STATUS_ALREADY_COMPLETE)
        self.assertIsNone(fc['earliest_date'])

    def test_future_dates_use_step3_schedule_and_skip_non_study_day(self):
        plan = self._plan(confirm_empty=True, end_page=200)
        update_center_weekdays([0])  # Monday
        save_subject_study_weekdays(self.math.id, [0])
        self._eight_pace_sessions(plan)
        monday = date(2026, 9, 14)
        save_center_non_study_day(monday, source=NON_STUDY_SOURCE_CENTER, label='센터휴원')
        self.assertFalse(study_calendar_allows(self.child.id, self.math.id, monday))
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertTrue(fc['available'])
        self.assertNotEqual(fc['earliest_date'], monday)
        self.assertEqual(fc['earliest_date'].weekday(), 0)
        self.assertGreater(fc['earliest_date'], monday)
        cursor = AS_OF + timedelta(days=1)
        monday_count = 0
        while cursor <= fc['earliest_date']:
            if cursor.weekday() == 0 and cursor != monday:
                monday_count += 1
            cursor += timedelta(days=1)
        self.assertGreaterEqual(monday_count, fc['earliest_sessions'])

    def test_old_plan_forecast_stops_at_next_workbook_plan(self):
        plan_a = self._plan(title='이전 교재', confirm_empty=True, end_page=400, target=date(2026, 12, 31))
        self._plan(title='다음 교재', start_date=date(2026, 9, 12), confirm_empty=True, end_page=400)
        self._enable_daily_calendar()
        self._eight_pace_sessions(plan_a)
        fc = completion_forecast(self.child.id, plan_a, as_of=AS_OF)
        self.assertFalse(fc['available'])
        self.assertEqual(fc['reason'], STATUS_PLAN_SWITCH)
        self.assertIsNone(fc['earliest_date'])

    def test_target_overlap(self):
        self._enable_daily_calendar()
        plan = self._plan(confirm_empty=True, end_page=200, target=AS_OF + timedelta(days=12))
        self._eight_pace_sessions(plan)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertTrue(fc['available'])
        self.assertEqual(fc['earliest_date'], AS_OF + timedelta(days=12))
        self.assertEqual(fc['latest_date'], AS_OF + timedelta(days=12))
        self.assertEqual(fc['vs_target'], VS_OVERLAPS)

    def test_target_on_or_ahead(self):
        self._enable_daily_calendar()
        plan = self._plan(confirm_empty=True, end_page=200, target=date(2027, 1, 1))
        self._eight_pace_sessions(plan)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertTrue(fc['available'])
        self.assertLessEqual(fc['latest_date'], plan.target_completion_date)
        self.assertEqual(fc['vs_target'], VS_ON_OR_AHEAD)

    def test_target_slight_delay(self):
        self._enable_daily_calendar()
        plan = self._plan(confirm_empty=True, end_page=210, target=AS_OF)
        self._eight_pace_sessions(plan)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertTrue(fc['available'])
        delay = (fc['earliest_date'] - plan.target_completion_date).days
        self.assertEqual(delay, 13)
        self.assertEqual(fc['vs_target'], VS_SLIGHT_DELAY)

    def test_target_14_day_boundary_is_delay_2w(self):
        self._enable_daily_calendar()
        plan = self._plan(confirm_empty=True, end_page=220, target=AS_OF)
        self._eight_pace_sessions(plan)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertTrue(fc['available'])
        delay = (fc['earliest_date'] - plan.target_completion_date).days
        self.assertEqual(delay, 14)
        self.assertEqual(fc['vs_target'], VS_DELAY_2W)

    def test_target_already_passed(self):
        plan = self._plan(confirm_empty=True, end_page=200, target=AS_OF - timedelta(days=1))
        self._session(plan, AS_OF, 1, 10)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(fc['vs_target'], VS_TARGET_PASSED)
        self.assertIsNone(fc['earliest_date'])

    def test_learning_progress_summary_keeps_availability(self):
        math_plan = self._plan(confirm_empty=True)
        self._session(math_plan, AS_OF, 1, 10)
        summary = learning_progress_summary(self.child.id, as_of=AS_OF)
        keys = [row['subject_key'] for row in summary['subjects']]
        self.assertEqual(keys, ['korean', 'math', 'ssen'])
        by_key = {row['subject_key']: row for row in summary['subjects']}
        self.assertEqual(by_key['korean']['status'], 'no_plan')
        self.assertIsNone(by_key['korean']['progress'])
        self.assertEqual(by_key['math']['progress']['observed_page_count'], 10)
        self.assertEqual(by_key['math']['progress']['plan']['textbook_title'], '수학 3-2')

    def test_canonical_module_does_not_use_legacy_sources(self):
        import features.study.coverage as coverage
        source = inspect.getsource(coverage)
        self.assertNotIn('current_progress_for_child', source)
        self.assertNotIn('from feature_models import LearningProgressEntry', source)
        self.assertNotIn('LearningProgressEntry.query', source)
        self.assertNotIn('DEFAULT_EXCLUDED_RATIO', source)
        self.assertNotIn('DailyPoints', source)
        self.assertNotIn('features.planning.planner', source)
        self.assertNotIn('features.planning.workload', source)
        self.assertNotIn('ensure_system_holidays', source)
        self.assertNotIn('db.session.commit', source)
        self.assertNotIn('db.session.add', source)

    def test_empty_effective_weekdays_is_immediately_unavailable(self):
        plan = self._plan(confirm_empty=True, end_page=200)
        self._enable_daily_calendar()
        self._eight_pace_sessions(plan)
        save_subject_study_weekdays(self.math.id, [0, 1])
        set_child_weekdays_override(self.child.id, [4, 5, 6])
        started = time.monotonic()
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0)
        self.assertFalse(fc['available'])
        self.assertEqual(fc['reason'], STATUS_NO_FUTURE_STUDY_DAYS)
        self.assertIsNone(fc['earliest_date'])

    def test_child_weekdays_empty_does_not_hang(self):
        plan = self._plan(confirm_empty=True, end_page=200)
        self._enable_daily_calendar()
        self._eight_pace_sessions(plan)
        set_child_weekdays_override(self.child.id, [])
        started = time.monotonic()
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0)
        self.assertFalse(fc['available'])
        self.assertEqual(fc['reason'], STATUS_NO_FUTURE_STUDY_DAYS)
        self.assertIsNone(fc['earliest_date'])

    def test_seeded_year_keeps_db_holiday_exclusion(self):
        hangul = date(2026, 10, 9)
        self.assertIn(hangul, korean_public_holidays(2026))
        ensure_system_holidays(2026)
        self.assertTrue(year_system_holidays_initialized(2026))
        self.assertIsNotNone(CenterNonStudyDay.query.filter_by(day=hangul).first())
        plan = self._plan(confirm_empty=True, end_page=400)
        self._enable_daily_calendar()
        self._eight_pace_sessions(plan)
        from features.study.coverage import _collect_future_study_days
        days, _ = _collect_future_study_days(self.child, plan, AS_OF, 40)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertTrue(fc['available'])
        self.assertNotIn(hangul, days)
        self.assertFalse(study_calendar_allows(self.child.id, self.math.id, hangul))

    def test_unseeded_future_year_holiday_is_not_a_study_day(self):
        as_of = date(2026, 12, 20)
        new_year = date(2027, 1, 1)
        self.assertIn(new_year, korean_public_holidays(2027))
        ensure_system_holidays(2026)
        self.assertTrue(year_system_holidays_initialized(2026))
        self.assertFalse(year_system_holidays_initialized(2027))
        plan = self._plan(confirm_empty=True, end_page=280)
        self._enable_daily_calendar()
        with mock.patch('features.study.records.kst_today', return_value=as_of):
            self._eight_pace_sessions(plan, as_of=as_of)
            holidays_2027_before = CenterNonStudyDay.query.filter(
                CenterNonStudyDay.day >= date(2027, 1, 1),
            ).count()
            seeds_before = CenterSystemHolidaySeed.query.filter_by(year=2027).count()
            fc = completion_forecast(self.child.id, plan, as_of=as_of)
        self.assertTrue(fc['available'])
        self.assertEqual(fc['earliest_sessions'], 20)
        self.assertEqual(fc['earliest_date'], date(2027, 1, 11))
        self.assertNotEqual(fc['earliest_date'], date(2027, 1, 10))
        self.assertFalse(year_system_holidays_initialized(2027))
        self.assertEqual(CenterSystemHolidaySeed.query.filter_by(year=2027).count(), seeds_before)
        self.assertEqual(
            CenterNonStudyDay.query.filter(CenterNonStudyDay.day >= date(2027, 1, 1)).count(),
            holidays_2027_before,
        )
        self.assertIsNone(CenterNonStudyDay.query.filter_by(day=new_year).first())

    def test_restored_seeded_holiday_is_not_reexcluded(self):
        hangul = date(2026, 10, 9)
        ensure_system_holidays(2026)
        self.assertTrue(delete_center_non_study_day(hangul))
        self.assertTrue(year_system_holidays_initialized(2026))
        self.assertIsNone(CenterNonStudyDay.query.filter_by(day=hangul).first())
        plan = self._plan(confirm_empty=True, end_page=400)
        self._enable_daily_calendar()
        self._eight_pace_sessions(plan)
        from features.study.coverage import _collect_future_study_days
        days, _ = _collect_future_study_days(self.child, plan, AS_OF, 40)
        fc = completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertTrue(fc['available'])
        self.assertTrue(study_calendar_allows(self.child.id, self.math.id, hangul))
        self.assertIn(hangul, days)

    def test_forecast_does_not_write_holiday_seed_or_rows(self):
        plan = self._plan(confirm_empty=True, end_page=200)
        self._enable_daily_calendar()
        self._eight_pace_sessions(plan)
        seeds_before = CenterSystemHolidaySeed.query.count()
        days_before = CenterNonStudyDay.query.count()
        completion_forecast(self.child.id, plan, as_of=AS_OF)
        self.assertEqual(CenterSystemHolidaySeed.query.count(), seeds_before)
        self.assertEqual(CenterNonStudyDay.query.count(), days_before)
