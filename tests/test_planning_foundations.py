"""Learning Progress AX v1 planning foundation. Growth/UI/LLM 은 연결하지 않는다."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    CenterStudyCalendar,
    ChildStudyWeekdays,
    LearningSubject,
    LearningWorkbookPlan,
)
from features.planning.exclusions import PlanningError, parse_exclusion_ranges  # noqa: E402
from features.planning.weekdays import (  # noqa: E402
    DEFAULT_STUDY_WEEKDAYS,
    canonicalize_weekdays,
    count_planned_study_days,
    count_planned_study_days_inclusive,
    effective_study_weekdays,
)
from features.planning.workload import (  # noqa: E402
    DEFAULT_EXCLUDED_RATIO,
    WORKLOAD_KIND_ESTIMATED,
    WORKLOAD_KIND_EXACT,
    compute_remaining_workload,
)
from features.progress.service import normalize_textbook_title  # noqa: E402


MONDAY = date(2026, 8, 24)
FRIDAY = date(2026, 8, 28)


class ExclusionParserTests(unittest.TestCase):
    def test_parses_mixed_ranges_and_singles(self):
        ranges = parse_exclusion_ranges(
            '35-42, 67, 103-110',
            start_page=1,
            end_page=184,
        )
        self.assertEqual(
            ranges,
            [
                {'start': 35, 'end': 42},
                {'start': 67, 'end': 67},
                {'start': 103, 'end': 110},
            ],
        )

    def test_whitespace_and_single_page(self):
        ranges = parse_exclusion_ranges(
            '  10-12 ,   15  , 20-21 ',
            start_page=1,
            end_page=50,
        )
        self.assertEqual(
            ranges,
            [
                {'start': 10, 'end': 12},
                {'start': 15, 'end': 15},
                {'start': 20, 'end': 21},
            ],
        )

    def test_blank_input_preserves_missing_none(self):
        self.assertIsNone(parse_exclusion_ranges(None, start_page=1, end_page=10))
        self.assertIsNone(parse_exclusion_ranges('', start_page=1, end_page=10))
        self.assertIsNone(parse_exclusion_ranges('  ', start_page=1, end_page=10))

    def test_overlap_and_duplicate_do_not_double_count(self):
        ranges = parse_exclusion_ranges(
            '10-20, 15-25, 20',
            start_page=1,
            end_page=100,
        )
        self.assertEqual(ranges, [{'start': 10, 'end': 25}])

    def test_adjacent_ranges_merge(self):
        ranges = parse_exclusion_ranges('10-12, 13-15', start_page=1, end_page=100)
        self.assertEqual(ranges, [{'start': 10, 'end': 15}])

    def test_invalid_syntax_rejected(self):
        with self.assertRaises(PlanningError) as caught:
            parse_exclusion_ranges('35~42', start_page=1, end_page=100)
        self.assertEqual(caught.exception.code, 'invalid_range_syntax')

    def test_non_numeric_rejected(self):
        with self.assertRaises(PlanningError) as caught:
            parse_exclusion_ranges('abc', start_page=1, end_page=100)
        self.assertEqual(caught.exception.code, 'invalid_range_syntax')

    def test_zero_and_negative_rejected(self):
        with self.assertRaises(PlanningError) as caught:
            parse_exclusion_ranges('0-2', start_page=1, end_page=100)
        self.assertEqual(caught.exception.code, 'page_range')
        with self.assertRaises(PlanningError):
            parse_exclusion_ranges('-3', start_page=1, end_page=100)

    def test_reversed_range_rejected(self):
        with self.assertRaises(PlanningError) as caught:
            parse_exclusion_ranges('20-10', start_page=1, end_page=100)
        self.assertEqual(caught.exception.code, 'reversed_range')

    def test_empty_token_rejected(self):
        with self.assertRaises(PlanningError) as caught:
            parse_exclusion_ranges('35-42,,67', start_page=1, end_page=100)
        self.assertEqual(caught.exception.code, 'empty_range_token')

    def test_range_outside_plan_rejected(self):
        with self.assertRaises(PlanningError) as caught:
            parse_exclusion_ranges('90-110', start_page=10, end_page=100)
        self.assertEqual(caught.exception.code, 'range_outside_plan')
        with self.assertRaises(PlanningError) as caught:
            parse_exclusion_ranges('1-5', start_page=10, end_page=100)
        self.assertEqual(caught.exception.code, 'range_outside_plan')


class ExactWorkloadTests(unittest.TestCase):
    def test_inclusive_total_and_remaining_example(self):
        result = compute_remaining_workload(
            start_page=1,
            end_page=100,
            current_page=50,
            exclusion_ranges=[{'start': 10, 'end': 19}, {'start': 60, 'end': 69}],
        )
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_EXACT)
        self.assertEqual(result.nominal_total_pages, 100)
        self.assertEqual(result.usable_total_pages, 80)
        self.assertEqual(result.nominal_remaining_pages, 50)
        self.assertEqual(result.remaining_workload, 40)
        self.assertEqual(result.remaining_start, 51)
        self.assertEqual(result.remaining_end, 100)

    def test_exclusion_before_current_does_not_affect_remaining(self):
        result = compute_remaining_workload(
            start_page=1,
            end_page=100,
            current_page=50,
            exclusion_ranges=[{'start': 10, 'end': 19}],
        )
        self.assertEqual(result.nominal_remaining_pages, 50)
        self.assertEqual(result.remaining_workload, 50)

    def test_exclusion_after_current_is_subtracted(self):
        result = compute_remaining_workload(
            start_page=1,
            end_page=100,
            current_page=50,
            exclusion_ranges=[{'start': 60, 'end': 69}],
        )
        self.assertEqual(result.remaining_workload, 40)

    def test_current_equal_end_is_zero(self):
        result = compute_remaining_workload(
            start_page=1,
            end_page=100,
            current_page=100,
            exclusion_ranges=[{'start': 10, 'end': 19}],
        )
        self.assertEqual(result.remaining_workload, 0)
        self.assertEqual(result.nominal_remaining_pages, 0)
        self.assertIsNone(result.remaining_start)

    def test_current_after_end_is_zero_not_negative(self):
        result = compute_remaining_workload(
            start_page=1,
            end_page=100,
            current_page=120,
            exclusion_ranges=[{'start': 10, 'end': 19}],
        )
        self.assertEqual(result.remaining_workload, 0)
        self.assertGreaterEqual(result.remaining_workload, 0)

    def test_current_before_start_uses_full_plan(self):
        result = compute_remaining_workload(
            start_page=10,
            end_page=100,
            current_page=5,
            exclusion_ranges=[{'start': 20, 'end': 29}],
        )
        self.assertEqual(result.remaining_start, 10)
        self.assertEqual(result.remaining_end, 100)
        self.assertEqual(result.nominal_remaining_pages, 91)
        self.assertEqual(result.remaining_workload, 81)

    def test_exclusion_covering_current_keeps_open_interval(self):
        result = compute_remaining_workload(
            start_page=1,
            end_page=100,
            current_page=50,
            exclusion_ranges=[{'start': 48, 'end': 52}],
        )
        self.assertEqual(result.remaining_start, 51)
        self.assertEqual(result.remaining_workload, 48)


class EstimatedWorkloadTests(unittest.TestCase):
    def test_no_exclusions_uses_twenty_percent_fallback(self):
        self.assertEqual(DEFAULT_EXCLUDED_RATIO, 0.20)
        result = compute_remaining_workload(
            start_page=1,
            end_page=100,
            current_page=50,
            exclusion_ranges=None,
        )
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_ESTIMATED)
        self.assertEqual(result.nominal_remaining_pages, 50)
        self.assertEqual(result.remaining_workload, 40.0)

    def test_exact_ranges_are_not_estimated(self):
        result = compute_remaining_workload(
            start_page=1,
            end_page=100,
            current_page=50,
            exclusion_ranges=[],
        )
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_EXACT)
        self.assertEqual(result.remaining_workload, 50)

    def test_nominal_zero_estimated_is_zero(self):
        result = compute_remaining_workload(
            start_page=1,
            end_page=100,
            current_page=100,
            exclusion_ranges=None,
        )
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_ESTIMATED)
        self.assertEqual(result.remaining_workload, 0)

    def test_parser_missing_feeds_estimated_not_exact_zero(self):
        stored = parse_exclusion_ranges('', start_page=1, end_page=100)
        self.assertIsNone(stored)
        result = compute_remaining_workload(
            start_page=1,
            end_page=100,
            current_page=50,
            exclusion_ranges=stored,
        )
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_ESTIMATED)
        self.assertEqual(result.remaining_workload, 40.0)


class WeekdayHelperTests(unittest.TestCase):
    def test_monday_to_friday_open_interval(self):
        days = count_planned_study_days(MONDAY, FRIDAY, DEFAULT_STUDY_WEEKDAYS)
        self.assertEqual(days, 4)

    def test_sparse_weekdays(self):
        days = count_planned_study_days(MONDAY, FRIDAY, [0, 2, 4])
        self.assertEqual(days, 2)

    def test_weekend_included_when_configured(self):
        days = count_planned_study_days(FRIDAY, date(2026, 8, 30), [5, 6])
        self.assertEqual(days, 2)

    def test_inclusive_span_includes_start_weekday(self):
        self.assertEqual(
            count_planned_study_days_inclusive(MONDAY, FRIDAY, DEFAULT_STUDY_WEEKDAYS),
            5,
        )
        self.assertEqual(
            count_planned_study_days(MONDAY, FRIDAY, DEFAULT_STUDY_WEEKDAYS),
            4,
        )

    def test_inclusive_span_includes_target(self):
        self.assertEqual(
            count_planned_study_days_inclusive(MONDAY, MONDAY, [0]),
            1,
        )
        self.assertEqual(count_planned_study_days(MONDAY, MONDAY, [0]), 0)

    def test_inclusive_target_before_start_is_zero(self):
        self.assertEqual(
            count_planned_study_days_inclusive(FRIDAY, MONDAY, DEFAULT_STUDY_WEEKDAYS),
            0,
        )

    def test_target_equal_as_of_is_zero(self):
        self.assertEqual(count_planned_study_days(FRIDAY, FRIDAY, DEFAULT_STUDY_WEEKDAYS), 0)

    def test_target_before_as_of_is_zero(self):
        self.assertEqual(count_planned_study_days(FRIDAY, MONDAY, DEFAULT_STUDY_WEEKDAYS), 0)

    def test_empty_override_means_no_planned_days(self):
        self.assertEqual(canonicalize_weekdays([]), [])
        self.assertEqual(effective_study_weekdays(DEFAULT_STUDY_WEEKDAYS, []), [])
        self.assertEqual(count_planned_study_days(MONDAY, FRIDAY, []), 0)

    def test_missing_override_uses_center_default(self):
        self.assertEqual(
            effective_study_weekdays(DEFAULT_STUDY_WEEKDAYS, None),
            [0, 1, 2, 3, 4],
        )

    def test_duplicate_weekdays_are_canonicalized(self):
        self.assertEqual(canonicalize_weekdays([2, 0, 2, 4]), [0, 2, 4])

    def test_invalid_weekday_rejected(self):
        with self.assertRaises(PlanningError):
            canonicalize_weekdays([0, 7])
        with self.assertRaises(PlanningError):
            canonicalize_weekdays(['mon'])


class PlanningModelTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.child = Child(name='계획아동', grade=3, viewer_slug='pppppppppppppppppppppppp')
        self.subject = LearningSubject(key='math', name='수학', is_active=True, sort_order=20)
        db.session.add_all([self.child, self.subject])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _plan(self, **kwargs):
        payload = {
            'grade': 3,
            'learning_subject_id': self.subject.id,
            'textbook_title': normalize_textbook_title('우등생 수학 3-2'),
            'start_page': 10,
            'end_page': 184,
            'start_date': date(2026, 9, 1),
            'target_completion_date': date(2026, 12, 20),
        }
        payload.update(kwargs)
        row = LearningWorkbookPlan(**payload)
        db.session.add(row)
        db.session.commit()
        return row

    def test_same_logical_plan_duplicate_rejected(self):
        self._plan()
        with self.assertRaises(IntegrityError):
            self._plan()
        db.session.rollback()

    def test_same_book_different_start_date_is_kept(self):
        first = self._plan(start_date=date(2026, 9, 1))
        second = self._plan(
            start_date=date(2027, 3, 2),
            target_completion_date=date(2027, 7, 20),
        )
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(LearningWorkbookPlan.query.count(), 2)

    def test_title_uses_progress_normalization(self):
        row = self._plan(textbook_title=normalize_textbook_title('  우등생   수학  3-2  '))
        self.assertEqual(row.textbook_title, '우등생 수학 3-2')
        self.assertEqual(row.textbook_title, normalize_textbook_title('우등생   수학  3-2'))

    def test_start_page_after_end_page_rejected(self):
        with self.assertRaises(IntegrityError):
            self._plan(start_page=50, end_page=10)
        db.session.rollback()

    def test_child_weekday_override_child_id_unique(self):
        db.session.add(ChildStudyWeekdays(child_id=self.child.id, study_weekdays=[0, 2, 4]))
        db.session.commit()
        with self.assertRaises(IntegrityError):
            db.session.add(ChildStudyWeekdays(child_id=self.child.id, study_weekdays=[1, 3]))
            db.session.commit()
        db.session.rollback()

    def test_json_weekday_persistence(self):
        calendar = CenterStudyCalendar(singleton_key='default', study_weekdays=[0, 1, 2, 3, 4])
        override = ChildStudyWeekdays(child_id=self.child.id, study_weekdays=[])
        db.session.add_all([calendar, override])
        db.session.commit()
        db.session.expire_all()
        stored_calendar = CenterStudyCalendar.query.filter_by(singleton_key='default').one()
        stored_child = ChildStudyWeekdays.query.filter_by(child_id=self.child.id).one()
        self.assertEqual(stored_calendar.study_weekdays, [0, 1, 2, 3, 4])
        self.assertEqual(stored_child.study_weekdays, [])
        self.assertEqual(
            effective_study_weekdays(stored_calendar.study_weekdays, stored_child.study_weekdays),
            [],
        )

    def test_exclusion_json_persistence(self):
        ranges = parse_exclusion_ranges('35-42, 67', start_page=10, end_page=184)
        row = self._plan(
            exclusion_ranges_text='35-42, 67',
            exclusion_ranges_json=ranges,
        )
        db.session.expire_all()
        stored = db.session.get(LearningWorkbookPlan, row.id)
        self.assertEqual(stored.exclusion_ranges_text, '35-42, 67')
        self.assertEqual(stored.exclusion_ranges_json, ranges)

    def test_missing_exclusion_saves_null_and_stays_estimated(self):
        parsed = parse_exclusion_ranges(None, start_page=10, end_page=184)
        self.assertIsNone(parsed)
        row = self._plan(
            exclusion_ranges_text=None,
            exclusion_ranges_json=parsed,
        )
        db.session.expire_all()
        stored = db.session.get(LearningWorkbookPlan, row.id)
        self.assertIsNone(stored.exclusion_ranges_json)
        result = compute_remaining_workload(
            start_page=stored.start_page,
            end_page=stored.end_page,
            current_page=50,
            exclusion_ranges=stored.exclusion_ranges_json,
        )
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_ESTIMATED)

    def test_whitespace_exclusion_saves_null_not_empty_list(self):
        parsed = parse_exclusion_ranges('   ', start_page=10, end_page=184)
        self.assertIsNone(parsed)
        row = self._plan(
            exclusion_ranges_text='   ',
            exclusion_ranges_json=parsed,
        )
        db.session.expire_all()
        stored = db.session.get(LearningWorkbookPlan, row.id)
        self.assertIsNone(stored.exclusion_ranges_json)
        self.assertNotEqual(stored.exclusion_ranges_json, [])

    def test_explicit_empty_exclusion_list_stays_exact_zero(self):
        row = self._plan(
            exclusion_ranges_text=None,
            exclusion_ranges_json=[],
        )
        db.session.expire_all()
        stored = db.session.get(LearningWorkbookPlan, row.id)
        self.assertEqual(stored.exclusion_ranges_json, [])
        result = compute_remaining_workload(
            start_page=stored.start_page,
            end_page=stored.end_page,
            current_page=50,
            exclusion_ranges=stored.exclusion_ranges_json,
        )
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_EXACT)
        self.assertEqual(result.remaining_workload, stored.end_page - 50)

    def test_nonempty_exclusion_stays_exact_after_reload(self):
        ranges = parse_exclusion_ranges('35-42', start_page=10, end_page=184)
        row = self._plan(
            exclusion_ranges_text='35-42',
            exclusion_ranges_json=ranges,
        )
        db.session.expire_all()
        stored = db.session.get(LearningWorkbookPlan, row.id)
        result = compute_remaining_workload(
            start_page=stored.start_page,
            end_page=stored.end_page,
            current_page=50,
            exclusion_ranges=stored.exclusion_ranges_json,
        )
        self.assertEqual(result.workload_kind, WORKLOAD_KIND_EXACT)
        self.assertEqual(stored.exclusion_ranges_json, [{'start': 35, 'end': 42}])

    def test_target_before_start_date_rejected(self):
        with self.assertRaises(IntegrityError):
            self._plan(
                start_date=date(2026, 9, 1),
                target_completion_date=date(2026, 8, 31),
            )
        db.session.rollback()


class PlanningMigrationTests(unittest.TestCase):
    def test_upgrade_and_downgrade_on_temp_sqlite(self):
        migration_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/a1b7c93e4d20_create_learning_planning_foundations.py'
        )
        spec = importlib.util.spec_from_file_location('planning_foundation_migration', migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine, text

        with tempfile.TemporaryDirectory(prefix='clc_planning_mig_') as tmp:
            db_path = Path(tmp) / 'fresh.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text('CREATE TABLE child (id INTEGER PRIMARY KEY)'))
                    conn.execute(text(
                        'CREATE TABLE learning_subject ('
                        'id INTEGER PRIMARY KEY, key VARCHAR(64) NOT NULL'
                        ')'
                    ))
                    conn.execute(text("INSERT INTO learning_subject (id, key) VALUES (1, 'math')"))
                    conn.execute(text('INSERT INTO child (id) VALUES (1)'))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    tables = [
                        row[0] for row in conn.execute(text(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )).fetchall()
                    ]
                    calendar = conn.execute(text(
                        'SELECT singleton_key, study_weekdays FROM center_study_calendar'
                    )).fetchall()
                    conn.execute(text(
                        'INSERT INTO learning_workbook_plan ('
                        'grade, learning_subject_id, textbook_title, start_page, end_page, '
                        'start_date, target_completion_date, exclusion_ranges_json'
                        ") VALUES (3, 1, '미입력교재', 10, 184, '2026-09-01', '2026-12-20', NULL)"
                    ))
                    conn.execute(text(
                        'INSERT INTO learning_workbook_plan ('
                        'grade, learning_subject_id, textbook_title, start_page, end_page, '
                        'start_date, target_completion_date, exclusion_ranges_json'
                        ") VALUES (3, 1, '명시적0제외', 10, 184, '2026-09-01', '2026-12-20', '[]')"
                    ))
                    loaded = conn.execute(text(
                        'SELECT textbook_title, exclusion_ranges_json '
                        'FROM learning_workbook_plan ORDER BY id'
                    )).fetchall()

                date_rejected = False
                try:
                    with engine.begin() as conn:
                        conn.execute(text(
                            'INSERT INTO learning_workbook_plan ('
                            'grade, learning_subject_id, textbook_title, start_page, end_page, '
                            'start_date, target_completion_date'
                            ") VALUES (3, 1, '날짜오류', 10, 184, '2026-09-01', '2026-08-31')"
                        ))
                except Exception:
                    date_rejected = True

                with engine.begin() as conn:
                    conn.execute(text(
                        'INSERT INTO learning_workbook_plan ('
                        'grade, learning_subject_id, textbook_title, start_page, end_page, '
                        'start_date, target_completion_date'
                        ") VALUES (3, 1, '우등생 수학 3-2', 10, 184, '2026-09-01', '2026-12-20')"
                    ))

                duplicate_failed = False
                try:
                    with engine.begin() as conn:
                        conn.execute(text(
                            'INSERT INTO learning_workbook_plan ('
                            'grade, learning_subject_id, textbook_title, start_page, end_page, '
                            'start_date, target_completion_date'
                            ") VALUES (3, 1, '우등생 수학 3-2', 10, 184, '2026-09-01', '2026-12-20')"
                        ))
                except Exception:
                    duplicate_failed = True

                versioned_ok = True
                try:
                    with engine.begin() as conn:
                        conn.execute(text(
                            'INSERT INTO learning_workbook_plan ('
                            'grade, learning_subject_id, textbook_title, start_page, end_page, '
                            'start_date, target_completion_date'
                            ") VALUES (3, 1, '우등생 수학 3-2', 10, 184, '2027-03-02', '2027-07-20')"
                        ))
                except Exception:
                    versioned_ok = False

                with engine.begin() as conn:
                    conn.execute(text(
                        "INSERT INTO child_study_weekdays (child_id, study_weekdays) "
                        "VALUES (1, '[0,2,4]')"
                    ))

                child_dup_failed = False
                try:
                    with engine.begin() as conn:
                        conn.execute(text(
                            "INSERT INTO child_study_weekdays (child_id, study_weekdays) "
                            "VALUES (1, '[1,3]')"
                        ))
                except Exception:
                    child_dup_failed = True

                with engine.begin() as conn:
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.downgrade()
                    tables_after = [
                        row[0] for row in conn.execute(text(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )).fetchall()
                    ]
            finally:
                engine.dispose()

        self.assertIn('learning_workbook_plan', tables)
        self.assertIn('center_study_calendar', tables)
        self.assertIn('child_study_weekdays', tables)
        self.assertEqual(len(calendar), 1)
        self.assertEqual(calendar[0][0], 'default')
        self.assertIn('0', str(calendar[0][1]))
        by_title = {row[0]: row[1] for row in loaded}
        self.assertIsNone(by_title['미입력교재'])
        self.assertIn(by_title['명시적0제외'], ([], '[]', b'[]'))
        self.assertTrue(date_rejected)
        self.assertTrue(duplicate_failed)
        self.assertTrue(versioned_ok)
        self.assertTrue(child_dup_failed)
        self.assertNotIn('learning_workbook_plan', tables_after)
        self.assertNotIn('center_study_calendar', tables_after)
        self.assertNotIn('child_study_weekdays', tables_after)
        self.assertIn('child', tables_after)
        self.assertIn('learning_subject', tables_after)

    def test_upgrade_seeds_calendar_when_empty_table_already_exists(self):
        migration_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/a1b7c93e4d20_create_learning_planning_foundations.py'
        )
        spec = importlib.util.spec_from_file_location('planning_foundation_migration_seed', migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine, text

        with tempfile.TemporaryDirectory(prefix='clc_planning_seed_') as tmp:
            db_path = Path(tmp) / 'empty_calendar.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text('CREATE TABLE child (id INTEGER PRIMARY KEY)'))
                    conn.execute(text(
                        'CREATE TABLE learning_subject ('
                        'id INTEGER PRIMARY KEY, key VARCHAR(64) NOT NULL'
                        ')'
                    ))
                    conn.execute(text(
                        'CREATE TABLE center_study_calendar ('
                        'id INTEGER PRIMARY KEY,'
                        'singleton_key VARCHAR(16) NOT NULL UNIQUE,'
                        'study_weekdays JSON NOT NULL,'
                        'created_at DATETIME,'
                        'updated_at DATETIME'
                        ')'
                    ))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    rows = conn.execute(text(
                        'SELECT singleton_key, study_weekdays FROM center_study_calendar'
                    )).fetchall()
            finally:
                engine.dispose()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 'default')
        self.assertIn('0', str(rows[0][1]))


if __name__ == '__main__':
    unittest.main()
