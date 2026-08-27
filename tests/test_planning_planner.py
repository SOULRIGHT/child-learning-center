"""Deterministic rolling learning planner. Growth/UI/LLM 연결 없음."""
from __future__ import annotations

import unittest
from datetime import date

from tests.helpers import bootstrap_test_app, local_development_sqlite_path, resolved_engine_sqlite_path

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    CenterStudyCalendar,
    ChildStudyWeekdays,
    LearningProgressEntry,
    LearningSubject,
    LearningWorkbookPlan,
)
from features.planning.planner import (  # noqa: E402
    STATUS_ACTIVE,
    STATUS_BEFORE_PLAN_START,
    STATUS_COMPLETE,
    STATUS_NO_PLAN,
    STATUS_NO_REMAINING_PLANNED_DAYS,
    STATUS_NO_SNAPSHOT,
    STATUS_TARGET_ELAPSED,
    build_child_learning_plan_statuses,
    build_child_subject_plan_status,
)
from features.planning.service import (  # noqa: E402
    WEEKDAY_SOURCE_CENTER_DEFAULT,
    WEEKDAY_SOURCE_CHILD_OVERRIDE,
    create_workbook_plan,
    set_child_weekdays_override,
    update_center_weekdays,
)
from features.planning.weekdays import DEFAULT_STUDY_WEEKDAYS  # noqa: E402
from features.planning.workload import WORKLOAD_KIND_ESTIMATED, WORKLOAD_KIND_EXACT  # noqa: E402
from features.progress.service import ensure_default_subjects  # noqa: E402


PLAN_START = date(2026, 9, 1)
PLAN_TARGET = date(2026, 9, 11)
AS_OF_BEFORE = date(2026, 8, 31)
AS_OF_ACTIVE = date(2026, 9, 1)
TITLE_32 = '우등생 수학 3-2'
TITLE_31 = '우등생 수학 3-1'


class PlanningPlannerTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.assertNotEqual(resolved_engine_sqlite_path(db), local_development_sqlite_path())

        self.teacher = User(
            username='planner_teacher',
            name='플래너교사',
            role='돌봄선생님',
            email='planner-teacher@example.test',
            password_hash='',
        )
        self.child = Child(name='플래너아동', grade=3, viewer_slug='rrrrrrrrrrrrrrrrrrrrrrrr')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        self.teacher_id = self.teacher.id
        self.child_id = self.child.id
        ensure_default_subjects()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.korean = LearningSubject.query.filter_by(key='korean').one()
        self.ssen = LearningSubject.query.filter_by(key='ssen').one()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _counts(self):
        return {
            'progress': LearningProgressEntry.query.count(),
            'plans': LearningWorkbookPlan.query.count(),
            'calendar': CenterStudyCalendar.query.count(),
            'overrides': ChildStudyWeekdays.query.count(),
        }

    def _entry(self, *, recorded_on, page, title=TITLE_32, subject=None):
        subject = subject or self.math
        row = LearningProgressEntry(
            child_id=self.child_id,
            learning_subject_id=subject.id,
            recorded_on=recorded_on,
            textbook_title=title,
            page=page,
            created_by_user_id=self.teacher_id,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def _plan(self, **kwargs):
        payload = {
            'grade': 3,
            'learning_subject_id': self.math.id,
            'textbook_title': TITLE_32,
            'start_page': 10,
            'end_page': 184,
            'start_date': PLAN_START,
            'target_completion_date': PLAN_TARGET,
            'exclusion_ranges_text': None,
        }
        payload.update(kwargs)
        return create_workbook_plan(**payload)

    def _status(self, as_of, subject=None):
        db.session.expire_all()
        child = db.session.get(Child, self.child_id)
        subject = subject or self.math
        return build_child_subject_plan_status(child, subject, as_of=as_of)

    def test_engine_is_not_instance_db(self):
        self.assertNotEqual(resolved_engine_sqlite_path(db), local_development_sqlite_path())

    def test_no_snapshot(self):
        self._plan()
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.status, STATUS_NO_SNAPSHOT)
        self.assertIsNone(result.snapshot_id)
        self.assertIsNone(result.current_page)
        self.assertIsNone(result.plan_id)
        self.assertIsNone(result.remaining_workload)
        self.assertIsNone(result.required_per_planned_day)

    def test_latest_snapshot_on_or_before_as_of(self):
        self._plan()
        older = self._entry(recorded_on=date(2026, 8, 20), page=20)
        latest = self._entry(recorded_on=date(2026, 8, 31), page=84)
        self._entry(recorded_on=date(2026, 9, 2), page=90)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.snapshot_id, latest.id)
        self.assertEqual(result.current_page, 84)
        self.assertNotEqual(result.snapshot_id, older.id)

    def test_future_snapshot_is_ignored(self):
        self._plan()
        kept = self._entry(recorded_on=date(2026, 8, 30), page=40)
        self._entry(recorded_on=date(2026, 9, 10), page=120)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.snapshot_id, kept.id)
        self.assertEqual(result.current_page, 40)

    def test_plan_matches_grade_subject_normalized_title(self):
        plan = self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=84, title='  우등생   수학  3-2  ')
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.status, STATUS_ACTIVE)
        self.assertEqual(result.plan_id, plan.id)
        self.assertEqual(result.textbook_title, TITLE_32)

    def test_other_title_does_not_match(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=84, title=TITLE_31)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.status, STATUS_NO_PLAN)
        self.assertEqual(result.current_page, 84)
        self.assertIsNone(result.plan_id)
        self.assertIsNone(result.remaining_workload)
        self.assertIsNone(result.required_per_planned_day)

    def test_future_only_plan_is_before_plan_start(self):
        plan = self._plan(start_date=date(2026, 9, 15), target_completion_date=date(2026, 12, 20))
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.status, STATUS_BEFORE_PLAN_START)
        self.assertEqual(result.plan_id, plan.id)

    def test_started_plan_is_preferred_over_future_plan(self):
        started = self._plan(
            start_date=date(2025, 9, 1),
            target_completion_date=date(2025, 12, 20),
            start_page=1,
            end_page=100,
        )
        self._plan(
            start_date=date(2026, 9, 15),
            target_completion_date=date(2026, 12, 20),
        )
        self._entry(recorded_on=date(2026, 8, 31), page=40)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.plan_id, started.id)
        self.assertNotEqual(result.status, STATUS_BEFORE_PLAN_START)

    def test_yearly_plan_picks_latest_start_on_or_before_as_of(self):
        old = self._plan(
            start_date=date(2025, 9, 1),
            target_completion_date=date(2025, 12, 20),
            start_page=1,
            end_page=100,
        )
        current = self._plan(
            start_date=date(2026, 9, 1),
            target_completion_date=date(2026, 12, 20),
            start_page=10,
            end_page=184,
        )
        self._entry(recorded_on=date(2025, 9, 15), page=20)
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        result = self._status(date(2026, 10, 1))
        self.assertEqual(result.plan_id, current.id)
        self.assertNotEqual(result.plan_id, old.id)
        earlier = self._status(date(2025, 10, 1))
        self.assertEqual(earlier.plan_id, old.id)
        self.assertEqual(earlier.current_page, 20)

    def test_previous_semester_title_selects_that_plan(self):
        plan_31 = self._plan(
            textbook_title=TITLE_31,
            start_date=date(2026, 3, 2),
            target_completion_date=date(2026, 7, 17),
            start_page=1,
            end_page=160,
        )
        self._plan(
            textbook_title=TITLE_32,
            start_date=date(2026, 9, 1),
            target_completion_date=date(2026, 12, 20),
        )
        self._entry(recorded_on=date(2026, 9, 1), page=90, title=TITLE_31)
        result = self._status(date(2026, 9, 10))
        self.assertEqual(result.plan_id, plan_31.id)
        self.assertEqual(result.textbook_title, TITLE_31)

    def test_estimated_workload_when_exclusion_json_is_null(self):
        self._plan(exclusion_ranges_text=None)
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_ESTIMATED)
        self.assertEqual(result.nominal_remaining_pages, 100)
        self.assertEqual(result.remaining_workload, 80.0)
        self.assertEqual(result.status, STATUS_ACTIVE)

    def test_exact_empty_list_is_full_nominal(self):
        plan = self._plan()
        plan.exclusion_ranges_text = None
        plan.exclusion_ranges_json = []
        db.session.commit()
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_EXACT)
        self.assertEqual(result.remaining_workload, 100)
        self.assertEqual(result.nominal_remaining_pages, 100)

    def test_exact_exclusion_after_current_is_subtracted(self):
        self._plan(exclusion_ranges_text='120-129')
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_EXACT)
        self.assertEqual(result.remaining_workload, 90)

    def test_exact_exclusion_before_current_does_not_reduce_remaining(self):
        self._plan(exclusion_ranges_text='10-20')
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_EXACT)
        self.assertEqual(result.remaining_workload, 100)

    def test_current_before_start_uses_full_plan_span(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=5)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.nominal_remaining_pages, 175)
        self.assertEqual(result.remaining_workload, 140.0)
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_ESTIMATED)

    def test_current_equal_and_after_end_are_complete(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=184)
        equal = self._status(AS_OF_ACTIVE)
        self.assertEqual(equal.status, STATUS_COMPLETE)
        self.assertEqual(equal.remaining_workload, 0)
        self.assertIsNone(equal.required_per_planned_day)

        LearningProgressEntry.query.delete()
        db.session.commit()
        self._entry(recorded_on=date(2026, 8, 31), page=190)
        after = self._status(AS_OF_ACTIVE)
        self.assertEqual(after.status, STATUS_COMPLETE)
        self.assertEqual(after.remaining_workload, 0)

    def test_exact_remaining_pages_zero_is_complete(self):
        self._plan(start_page=10, end_page=20, exclusion_ranges_text='11-20')
        self._entry(recorded_on=date(2026, 8, 31), page=10)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.status, STATUS_COMPLETE)
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_EXACT)
        self.assertEqual(result.remaining_workload, 0)
        self.assertIsNone(result.required_per_planned_day)

    def test_center_default_weekdays_and_source(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.weekday_source, WEEKDAY_SOURCE_CENTER_DEFAULT)
        self.assertEqual(list(result.effective_weekdays), list(DEFAULT_STUDY_WEEKDAYS))
        self.assertEqual(result.remaining_planned_study_days, 8)
        self.assertEqual(result.required_per_planned_day, 10.0)

    def test_child_override_weekdays(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        set_child_weekdays_override(self.child_id, [0, 2, 4])
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.weekday_source, WEEKDAY_SOURCE_CHILD_OVERRIDE)
        self.assertEqual(list(result.effective_weekdays), [0, 2, 4])
        self.assertEqual(result.remaining_planned_study_days, 5)
        self.assertEqual(result.required_per_planned_day, 16.0)

    def test_empty_override_means_no_remaining_planned_days(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        set_child_weekdays_override(self.child_id, [])
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.weekday_source, WEEKDAY_SOURCE_CHILD_OVERRIDE)
        self.assertEqual(list(result.effective_weekdays), [])
        self.assertEqual(result.status, STATUS_NO_REMAINING_PLANNED_DAYS)
        self.assertEqual(result.remaining_planned_study_days, 0)
        self.assertEqual(result.remaining_workload, 80.0)
        self.assertIsNone(result.required_per_planned_day)

    def test_before_plan_start_counts_inclusive_start(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 20), page=84)
        result = self._status(AS_OF_BEFORE)
        self.assertEqual(result.status, STATUS_BEFORE_PLAN_START)
        self.assertEqual(result.remaining_planned_study_days, 9)
        self.assertEqual(result.remaining_workload, 80.0)
        self.assertAlmostEqual(result.required_per_planned_day, 80.0 / 9)

    def test_started_plan_excludes_as_of_day(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        before = self._status(AS_OF_BEFORE)
        started = self._status(AS_OF_ACTIVE)
        self.assertEqual(before.remaining_planned_study_days, 9)
        self.assertEqual(started.remaining_planned_study_days, 8)

    def test_target_date_is_included_after_as_of(self):
        self._plan(target_completion_date=date(2026, 9, 2))
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.remaining_planned_study_days, 1)
        self.assertEqual(result.status, STATUS_ACTIVE)

    def test_target_elapsed(self):
        self._plan(start_date=date(2026, 3, 2), target_completion_date=date(2026, 8, 31))
        self._entry(recorded_on=date(2026, 8, 20), page=84)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.status, STATUS_TARGET_ELAPSED)
        self.assertEqual(result.remaining_planned_study_days, 0)
        self.assertGreater(result.remaining_workload, 0)
        self.assertIsNone(result.required_per_planned_day)

    def test_required_is_none_when_complete(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=184)
        result = self._status(AS_OF_ACTIVE)
        self.assertEqual(result.status, STATUS_COMPLETE)
        self.assertEqual(result.remaining_workload, 0)
        self.assertIsNone(result.required_per_planned_day)
        self.assertGreater(result.remaining_planned_study_days, 0)

    def test_no_negative_remaining_or_required(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        result = self._status(AS_OF_ACTIVE)
        self.assertGreaterEqual(result.remaining_workload, 0)
        self.assertGreaterEqual(result.remaining_planned_study_days, 0)
        self.assertGreater(result.required_per_planned_day, 0)

    def test_aggregator_covers_active_subjects(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        child = db.session.get(Child, self.child_id)
        rows = build_child_learning_plan_statuses(child, as_of=AS_OF_ACTIVE)
        self.assertEqual([row.subject_key for row in rows], ['korean', 'math', 'ssen'])
        by_key = {row.subject_key: row for row in rows}
        self.assertEqual(by_key['math'].status, STATUS_ACTIVE)
        self.assertEqual(by_key['korean'].status, STATUS_NO_SNAPSHOT)
        self.assertEqual(by_key['ssen'].status, STATUS_NO_SNAPSHOT)

    def test_planner_is_read_only(self):
        self._plan()
        self._entry(recorded_on=date(2026, 8, 31), page=84)
        update_center_weekdays([0, 1, 2, 3, 4])
        set_child_weekdays_override(self.child_id, [0, 2, 4])
        before = self._counts()
        child = db.session.get(Child, self.child_id)
        build_child_subject_plan_status(child, self.math, as_of=AS_OF_ACTIVE)
        build_child_learning_plan_statuses(child, as_of=AS_OF_ACTIVE)
        self.assertEqual(self._counts(), before)
        self.assertFalse(db.session.dirty)
        self.assertFalse(db.session.new)
        self.assertFalse(db.session.deleted)
