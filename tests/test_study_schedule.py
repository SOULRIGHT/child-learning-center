"""Growth vNext Step 3: 정상학습일 / 기대 과목 / 공휴일 seed."""
from __future__ import annotations

import inspect
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import CenterNonStudyDay, CenterSystemHolidaySeed, LearningSubject  # noqa: E402
from features.planning.service import create_workbook_plan, set_child_weekdays_override  # noqa: E402
from features.progress.service import create_subject, ensure_default_subjects  # noqa: E402
from features.study.calendar import (  # noqa: E402
    delete_center_non_study_day,
    delete_subject_study_weekdays,
    save_center_non_study_day,
    save_subject_study_weekdays,
)
from features.study.constants import NON_STUDY_SOURCE_CENTER, NON_STUDY_SOURCE_SYSTEM_HOLIDAY  # noqa: E402
from features.study.holidays import (  # noqa: E402
    ensure_system_holidays,
    korean_public_holidays,
    restore_system_holidays,
    year_system_holidays_initialized,
)
from features.study.metrics import subject_period  # noqa: E402
from features.study.schedule import (  # noqa: E402
    effective_weekdays,
    expected_subjects,
    is_excluded_day,
    normal_study_day,
)
from features.study.subjects import list_study_subjects  # noqa: E402
import features.study.metrics as study_metrics  # noqa: E402
import features.study.schedule as study_schedule  # noqa: E402
import features.study.view as study_view  # noqa: E402

TODAY = date(2026, 9, 8)  # 화
WED = date(2026, 9, 2)  # 수
FRI = date(2026, 9, 4)  # 금
SAT = date(2026, 9, 5)  # 토
CHILDRENS_DAY = date(2026, 5, 5)  # 화, 어린이날


class StudyScheduleTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='sched_teacher',
            name='요일교사',
            role='돌봄선생님',
            email='sched-teacher@example.test',
            password_hash='',
        )
        self.child = Child(
            name='요일아동',
            grade=3,
            viewer_slug='schedchildschedchildschd',
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
                end_page=100,
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

    def test_subject_weekdays_and_child_intersection(self):
        self.assertEqual(effective_weekdays(self.child.id, self.korean.id), [0, 2])
        self.assertEqual(effective_weekdays(self.child.id, self.math.id), [1, 3])
        self.assertEqual(effective_weekdays(self.child.id, self.ssen.id), [4])
        set_child_weekdays_override(self.child.id, [0, 1, 2])  # 월화수
        self.assertEqual(effective_weekdays(self.child.id, self.korean.id), [0, 2])
        self.assertEqual(effective_weekdays(self.child.id, self.math.id), [1])
        self.assertEqual(effective_weekdays(self.child.id, self.ssen.id), [])
        self.assertTrue(normal_study_day(self.child.id, self.korean.id, WED))
        self.assertFalse(normal_study_day(self.child.id, self.math.id, WED))
        self.assertFalse(normal_study_day(self.child.id, self.ssen.id, FRI))

    def test_expected_subjects_follow_subject_weekdays(self):
        names = [row.name for row in expected_subjects(self.child.id, WED)]
        self.assertEqual(names, [self.korean.name])
        names = [row.name for row in expected_subjects(self.child.id, TODAY)]
        self.assertEqual(names, [self.math.name])
        names = [row.name for row in expected_subjects(self.child.id, FRI)]
        self.assertEqual(names, [self.ssen.name])
        self.assertEqual(expected_subjects(self.child.id, SAT), [])

    def test_active_subject_is_dynamic(self):
        science = create_subject('science', '과학', is_active=True, sort_order=90)
        save_subject_study_weekdays(science.id, [2])
        create_workbook_plan(
            grade=3,
            learning_subject_id=science.id,
            textbook_title='과학 교재',
            start_page=1,
            end_page=80,
            start_date=date(2026, 3, 1),
            target_completion_date=date(2026, 12, 31),
        )
        keys = [row.key for row in list_study_subjects()]
        self.assertIn('science', keys)
        names = [row.name for row in expected_subjects(self.child.id, WED)]
        self.assertIn('과학', names)
        self.assertIn(self.korean.name, names)

    def test_missing_subject_row_falls_back_to_center_calendar(self):
        delete_subject_study_weekdays(self.korean.id)
        self.assertEqual(effective_weekdays(self.child.id, self.korean.id), [0, 1, 2, 3, 4])
        self.assertTrue(normal_study_day(self.child.id, self.korean.id, TODAY))

    def test_center_non_study_day_excluded(self):
        save_center_non_study_day(WED, source=NON_STUDY_SOURCE_CENTER, label='체험학습')
        self.assertTrue(is_excluded_day(WED))
        self.assertFalse(normal_study_day(self.child.id, self.korean.id, WED))
        self.assertEqual(expected_subjects(self.child.id, WED), [])

    def test_holiday_seed_and_restore(self):
        created = ensure_system_holidays(2026)
        self.assertGreater(created, 0)
        self.assertIn(CHILDRENS_DAY, korean_public_holidays(2026))
        self.assertTrue(is_excluded_day(CHILDRENS_DAY))
        self.assertFalse(normal_study_day(self.child.id, self.math.id, CHILDRENS_DAY))
        self.assertEqual(ensure_system_holidays(2026), 0)
        self.assertTrue(delete_center_non_study_day(CHILDRENS_DAY))
        self.assertFalse(is_excluded_day(CHILDRENS_DAY))
        self.assertTrue(normal_study_day(self.child.id, self.math.id, CHILDRENS_DAY))
        self.assertEqual(ensure_system_holidays(2026), 0)
        self.assertIsNone(CenterNonStudyDay.query.filter_by(day=CHILDRENS_DAY).first())
        self.assertTrue(year_system_holidays_initialized(2026))

    def _system_holiday_count(self, year):
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        return (
            CenterNonStudyDay.query
            .filter_by(source=NON_STUDY_SOURCE_SYSTEM_HOLIDAY)
            .filter(CenterNonStudyDay.day >= start)
            .filter(CenterNonStudyDay.day <= end)
            .count()
        )

    def _delete_year_system_holidays(self, year):
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        rows = (
            CenterNonStudyDay.query
            .filter_by(source=NON_STUDY_SOURCE_SYSTEM_HOLIDAY)
            .filter(CenterNonStudyDay.day >= start)
            .filter(CenterNonStudyDay.day <= end)
            .all()
        )
        for row in rows:
            db.session.delete(row)
        db.session.commit()

    def test_ensure_same_year_is_idempotent(self):
        first = ensure_system_holidays(2026)
        count = self._system_holiday_count(2026)
        self.assertGreater(first, 0)
        self.assertEqual(ensure_system_holidays(2026), 0)
        self.assertEqual(self._system_holiday_count(2026), count)
        self.assertEqual(CenterSystemHolidaySeed.query.filter_by(year=2026).count(), 1)

    def test_restoring_one_holiday_does_not_reseed(self):
        ensure_system_holidays(2026)
        before = self._system_holiday_count(2026)
        self.assertTrue(delete_center_non_study_day(CHILDRENS_DAY))
        self.assertEqual(ensure_system_holidays(2026), 0)
        self.assertEqual(self._system_holiday_count(2026), before - 1)
        self.assertFalse(is_excluded_day(CHILDRENS_DAY))

    def test_restoring_all_system_holidays_does_not_reseed(self):
        ensure_system_holidays(2026)
        self._delete_year_system_holidays(2026)
        self.assertEqual(self._system_holiday_count(2026), 0)
        self.assertTrue(year_system_holidays_initialized(2026))
        self.assertEqual(ensure_system_holidays(2026), 0)
        self.assertEqual(self._system_holiday_count(2026), 0)
        self.assertFalse(is_excluded_day(CHILDRENS_DAY))

    def test_next_year_still_gets_first_seed(self):
        ensure_system_holidays(2026)
        self._delete_year_system_holidays(2026)
        created = ensure_system_holidays(2027)
        self.assertGreater(created, 0)
        self.assertTrue(year_system_holidays_initialized(2027))
        self.assertGreater(self._system_holiday_count(2027), 0)
        self.assertEqual(self._system_holiday_count(2026), 0)

    def test_explicit_restore_recreates_missing_holidays(self):
        ensure_system_holidays(2026)
        self._delete_year_system_holidays(2026)
        created = restore_system_holidays(2026)
        self.assertGreater(created, 0)
        self.assertTrue(is_excluded_day(CHILDRENS_DAY))

    def test_read_and_metric_paths_do_not_seed(self):
        self.assertFalse(year_system_holidays_initialized(2026))
        self.assertFalse(is_excluded_day(CHILDRENS_DAY))
        self.assertTrue(normal_study_day(self.child.id, self.math.id, CHILDRENS_DAY))
        expected_subjects(self.child.id, TODAY)
        subject_period(self.child.id, self.math.id, TODAY, TODAY)
        self.assertFalse(year_system_holidays_initialized(2026))
        self.assertEqual(self._system_holiday_count(2026), 0)
        self.assertEqual(CenterSystemHolidaySeed.query.count(), 0)
        self.assertNotIn('ensure_system_holidays', inspect.getsource(study_schedule))
        self.assertNotIn('ensure_system_holidays', inspect.getsource(study_metrics))

    def test_created_at_before_excluded(self):
        self.child.created_at = datetime(2026, 9, 8, 0, 0, 0)
        db.session.commit()
        self.assertFalse(normal_study_day(self.child.id, self.korean.id, WED))
        self.assertTrue(normal_study_day(self.child.id, self.math.id, TODAY))

    def test_no_plan_excluded(self):
        extra = create_subject('history', '역사', is_active=True, sort_order=91)
        save_subject_study_weekdays(extra.id, [2])
        self.assertFalse(normal_study_day(self.child.id, extra.id, WED))

    def test_future_date_excluded(self):
        self.assertFalse(normal_study_day(self.child.id, self.math.id, TODAY + timedelta(days=1)))

    def test_resolver_does_not_use_points_or_hardcoded_subjects(self):
        source = inspect.getsource(study_schedule)
        self.assertNotIn('from app import', source)
        self.assertNotIn('list_progress_input_subjects', source)
        self.assertNotIn('PROGRESS_SUBJECT_KEYS', source)
        view_src = inspect.getsource(study_view.list_child_study_rows)
        self.assertNotIn('list_progress_input_subjects', view_src)
        for banned in ('국어', '수학', '쎈'):
            self.assertNotIn(banned, inspect.getsource(study_schedule.expected_subjects))
            self.assertNotIn(banned, inspect.getsource(study_schedule.normal_study_day))
