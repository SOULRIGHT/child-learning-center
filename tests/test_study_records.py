"""Growth vNext Step 1: study session / calendar domain. UI/metrics/AI 없음."""
from __future__ import annotations

import importlib.util
import inspect
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, inspect as sa_inspect, text

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    CenterNonStudyDay,
    CenterSubjectStudyWeekdays,
    LearningProgressEntry,
    LearningStudySession,
    LearningStudySessionChange,
    LearningSubject,
    LearningWorkbookPlan,
    RECORD_VERIFICATION_OBSERVED,
    RECORD_VERIFICATION_VERIFIED,
    STUDY_STATUS_EXPLICIT_NOT_STUDIED,
    STUDY_STATUS_STUDIED,
    STUDY_STATUS_UNKNOWN,
)
from features.dates import kst_today  # noqa: E402
from features.progress.service import ensure_default_subjects, save_progress_entry  # noqa: E402
from features.reading.policy import now_utc  # noqa: E402
from features.reading.session import (  # noqa: E402
    SESSION_CHILD_ID,
    SESSION_CHILD_SLUG,
    SESSION_VERIFIED_AT,
    is_write_fresh,
    set_verified_child,
)
from features.study.assignment import (  # noqa: E402
    assigned_page_count,
    permanently_excluded_ranges,
    physical_page_bounds,
)
from features.study.calendar import (  # noqa: E402
    StudyCalendarError,
    save_center_non_study_day,
    save_subject_study_weekdays,
)
from features.study.constants import (  # noqa: E402
    INPUT_CHANNEL_TEACHER,
    NON_STUDY_SOURCE_CENTER,
    NON_STUDY_SOURCE_SYSTEM_HOLIDAY,
)
from features.study.records import (  # noqa: E402
    StudyRecordError,
    create_study_session,
    delete_study_session,
    update_study_session,
)

FOUNDATION_TABLES = (
    'center_subject_study_weekdays',
    'center_non_study_day',
    'learning_study_session',
    'learning_study_session_change',
)
STUDY_FOUNDATION_MIGRATION = Path(__file__).resolve().parents[1] / (
    'migrations/versions/f7c2a19e4b80_create_growth_vnext_study_foundation.py'
)
STUDY_PLAN_FK_MIGRATION = Path(__file__).resolve().parents[1] / (
    'migrations/versions/a2b8c4d6e1f0_add_study_session_workbook_plan_fk.py'
)


def _load_migration(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_study_foundation_migration():
    return _load_migration(STUDY_FOUNDATION_MIGRATION, 'study_foundation_mig')


def _schema_invariants(engine, table):
    inspector = sa_inspect(engine)
    checks = tuple(sorted(
        (item.get('name'), ' '.join((item.get('sqltext') or '').split()))
        for item in inspector.get_check_constraints(table)
    ))
    indexes = tuple(sorted(
        (
            item.get('name'),
            tuple(item.get('column_names') or []),
            bool(item.get('unique')),
        )
        for item in inspector.get_indexes(table)
        if item.get('name') and not str(item.get('name')).startswith('sqlite_autoindex_')
    ))
    fks = tuple(sorted(
        (
            tuple(item.get('constrained_columns') or []),
            item.get('referred_table'),
            tuple(item.get('referred_columns') or []),
            (item.get('options') or {}).get('ondelete'),
        )
        for item in inspector.get_foreign_keys(table)
    ))
    defaults = {
        item['name']: item.get('default')
        for item in inspector.get_columns(table)
    }
    uniques = tuple(sorted(
        (item.get('name'), tuple(item.get('column_names') or []))
        for item in inspector.get_unique_constraints(table)
    ))
    return {
        'checks': checks,
        'indexes': indexes,
        'fks': fks,
        'defaults': defaults,
        'uniques': uniques,
    }


def _partial_unique_sql(engine, table, index_name):
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type='index' AND name=:name AND tbl_name=:table"
            ),
            {'name': index_name, 'table': table},
        ).fetchone()
    return None if row is None else row[0]


class StudyRecordTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='study_teacher',
            name='학습교사',
            role='돌봄선생님',
            email='study-teacher@example.test',
            password_hash='',
        )
        self.child = Child(name='학습세션아동', grade=3, viewer_slug='ssssssssssssssssssssssss')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        ensure_default_subjects()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.korean = LearningSubject.query.filter_by(key='korean').one()
        self.today = kst_today()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _studied(self, **kwargs):
        payload = {
            'child_id': self.child.id,
            'learning_subject_id': self.math.id,
            'study_date': self.today,
            'study_status': STUDY_STATUS_STUDIED,
            'start_page': 70,
            'end_page': 71,
            'textbook_title': '수학 3-2',
            'recorded_by_user_id': self.teacher.id,
            'actor_type': 'teacher',
            'input_channel': INPUT_CHANNEL_TEACHER,
        }
        payload.update(kwargs)
        if 'learning_workbook_plan_id' not in kwargs:
            payload['learning_workbook_plan_id'] = self._ensure_plan(
                payload['learning_subject_id'],
                payload['study_date'],
                payload.get('textbook_title') or '수학 3-2',
            ).id
        return create_study_session(**payload)

    def _ensure_plan(self, learning_subject_id, study_date, textbook_title):
        from features.planning.timeline import canonical_workbook_plan
        plan = canonical_workbook_plan(
            grade=self.child.grade,
            learning_subject_id=learning_subject_id,
            study_date=study_date,
        )
        if plan is not None:
            return plan
        return self._add_plan(
            learning_subject_id=learning_subject_id,
            textbook_title=textbook_title,
            start_date=study_date,
            start_page=1,
            end_page=200,
        )

    def _add_plan(self, **overrides):
        payload = {
            'grade': 3,
            'learning_subject_id': self.math.id,
            'textbook_title': '쎈 수학 5-2',
            'start_page': 1,
            'end_page': 200,
            'start_date': date(2026, 3, 1),
            'target_completion_date': date(2026, 12, 1),
        }
        payload.update(overrides)
        plan = LearningWorkbookPlan(**payload)
        db.session.add(plan)
        db.session.commit()
        return plan

    def _create_status(self, study_status, study_date=None, **kwargs):
        payload = {
            'child_id': self.child.id,
            'learning_subject_id': self.math.id,
            'study_date': self.today if study_date is None else study_date,
            'study_status': study_status,
            'recorded_by_user_id': self.teacher.id,
        }
        if study_status == STUDY_STATUS_STUDIED:
            payload.update(
                start_page=70,
                end_page=71,
                textbook_title='수학 3-2',
            )
        payload.update(kwargs)
        if 'learning_workbook_plan_id' not in kwargs:
            payload['learning_workbook_plan_id'] = self._ensure_plan(
                payload['learning_subject_id'],
                payload['study_date'],
                payload.get('textbook_title') or '수학 3-2',
            ).id
        return create_study_session(**payload)

    def _assert_day_status_conflict(self, first_status, second_status, study_date=None):
        day = self.today if study_date is None else study_date
        self._create_status(first_status, study_date=day)
        with self.assertRaises(StudyRecordError) as ctx:
            self._create_status(
                second_status,
                study_date=day,
                start_page=80 if second_status == STUDY_STATUS_STUDIED else None,
                end_page=81 if second_status == STUDY_STATUS_STUDIED else None,
                textbook_title='수학 3-2' if second_status == STUDY_STATUS_STUDIED else None,
            )
        self.assertEqual(ctx.exception.code, 'day_status_conflict')

    def test_studied_range_is_stored(self):
        row = self._studied()
        self.assertEqual(row.study_status, STUDY_STATUS_STUDIED)
        self.assertEqual(row.start_page, 70)
        self.assertEqual(row.end_page, 71)
        self.assertEqual(row.textbook_title, '수학 3-2')
        self.assertEqual(row.record_verification, RECORD_VERIFICATION_OBSERVED)

    def test_explicit_not_studied_has_no_pages(self):
        row = self._create_status(STUDY_STATUS_EXPLICIT_NOT_STUDIED)
        self.assertEqual(row.study_status, STUDY_STATUS_EXPLICIT_NOT_STUDIED)
        self.assertIsNone(row.start_page)
        self.assertIsNone(row.end_page)

    def test_unknown_is_stored_without_pages(self):
        row = self._create_status(STUDY_STATUS_UNKNOWN)
        self.assertEqual(row.study_status, STUDY_STATUS_UNKNOWN)
        self.assertIsNone(row.start_page)
        self.assertIsNone(row.end_page)

    def test_not_studied_rejects_pages(self):
        self._ensure_plan(self.math.id, self.today, '수학 3-2')
        with self.assertRaises(StudyRecordError) as ctx:
            create_study_session(
                child_id=self.child.id,
                learning_subject_id=self.math.id,
                study_date=self.today,
                study_status=STUDY_STATUS_EXPLICIT_NOT_STUDIED,
                start_page=10,
                end_page=12,
                recorded_by_user_id=self.teacher.id,
            )
        self.assertEqual(ctx.exception.code, 'pages_not_allowed')

    def test_observed_and_verified_are_stored(self):
        observed = self._studied(record_verification=RECORD_VERIFICATION_OBSERVED)
        verified = self._studied(
            study_date=self.today - timedelta(days=1),
            record_verification=RECORD_VERIFICATION_VERIFIED,
            start_page=80,
            end_page=81,
        )
        self.assertEqual(observed.record_verification, RECORD_VERIFICATION_OBSERVED)
        self.assertEqual(verified.record_verification, RECORD_VERIFICATION_VERIFIED)

    def test_study_status_and_record_verification_are_independent(self):
        combinations = (
            (STUDY_STATUS_STUDIED, RECORD_VERIFICATION_OBSERVED, {'start_page': 1, 'end_page': 2, 'textbook_title': '수학 3-2'}),
            (STUDY_STATUS_STUDIED, RECORD_VERIFICATION_VERIFIED, {'start_page': 3, 'end_page': 4, 'textbook_title': '수학 3-2'}),
            (STUDY_STATUS_EXPLICIT_NOT_STUDIED, RECORD_VERIFICATION_OBSERVED, {}),
            (STUDY_STATUS_EXPLICIT_NOT_STUDIED, RECORD_VERIFICATION_VERIFIED, {}),
            (STUDY_STATUS_UNKNOWN, RECORD_VERIFICATION_OBSERVED, {}),
            (STUDY_STATUS_UNKNOWN, RECORD_VERIFICATION_VERIFIED, {}),
        )
        self._add_plan(start_date=date(2026, 1, 1), textbook_title='수학 3-2')
        for offset, (status, verification, extra) in enumerate(combinations):
            row = create_study_session(
                child_id=self.child.id,
                learning_subject_id=self.math.id,
                study_date=self.today - timedelta(days=offset + 1),
                study_status=status,
                record_verification=verification,
                recorded_by_user_id=self.teacher.id,
                **extra,
            )
            self.assertEqual(row.study_status, status)
            self.assertEqual(row.record_verification, verification)

    def test_start_page_after_end_page_rejected(self):
        with self.assertRaises(StudyRecordError) as ctx:
            self._studied(start_page=20, end_page=10)
        self.assertEqual(ctx.exception.code, 'page_order')

    def test_noncontiguous_ranges_same_day_are_allowed(self):
        first = self._studied(start_page=70, end_page=71)
        second = self._studied(start_page=80, end_page=81)
        rows = LearningStudySession.query.filter_by(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            study_date=self.today,
        ).all()
        ranges = sorted((row.start_page, row.end_page) for row in rows)
        self.assertEqual(ranges, [(70, 71), (80, 81)])
        self.assertNotEqual(first.id, second.id)

    def test_earlier_page_than_previous_day_is_not_blocked(self):
        self._studied(study_date=self.today - timedelta(days=1), start_page=80, end_page=81)
        later = self._studied(start_page=70, end_page=71)
        self.assertEqual(later.start_page, 70)
        self.assertEqual(later.end_page, 71)

    def test_studied_and_explicit_not_studied_cannot_coexist(self):
        self._assert_day_status_conflict(
            STUDY_STATUS_STUDIED,
            STUDY_STATUS_EXPLICIT_NOT_STUDIED,
        )
        self._assert_day_status_conflict(
            STUDY_STATUS_EXPLICIT_NOT_STUDIED,
            STUDY_STATUS_STUDIED,
            study_date=self.today - timedelta(days=1),
        )

    def test_studied_and_unknown_cannot_coexist(self):
        self._assert_day_status_conflict(
            STUDY_STATUS_STUDIED,
            STUDY_STATUS_UNKNOWN,
        )
        self._assert_day_status_conflict(
            STUDY_STATUS_UNKNOWN,
            STUDY_STATUS_STUDIED,
            study_date=self.today - timedelta(days=1),
        )

    def test_explicit_not_studied_and_unknown_cannot_coexist(self):
        self._assert_day_status_conflict(
            STUDY_STATUS_EXPLICIT_NOT_STUDIED,
            STUDY_STATUS_UNKNOWN,
        )
        self._assert_day_status_conflict(
            STUDY_STATUS_UNKNOWN,
            STUDY_STATUS_EXPLICIT_NOT_STUDIED,
            study_date=self.today - timedelta(days=1),
        )

    def test_explicit_unknown_row_is_distinct_from_missing_row(self):
        query = LearningStudySession.query.filter_by(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            study_date=self.today,
        )
        self.assertEqual(query.count(), 0)
        row = self._create_status(STUDY_STATUS_UNKNOWN)
        self.assertEqual(query.count(), 1)
        self.assertEqual(row.study_status, STUDY_STATUS_UNKNOWN)
        self.assertIsNone(row.start_page)
        self.assertIsNone(row.end_page)

    def test_cannot_change_studied_to_unknown_when_another_studied_exists(self):
        first = self._studied(start_page=70, end_page=71)
        self._studied(start_page=80, end_page=81)
        with self.assertRaises(StudyRecordError) as ctx:
            update_study_session(
                first,
                changed_by_user_id=self.teacher.id,
                study_status=STUDY_STATUS_UNKNOWN,
            )
        self.assertEqual(ctx.exception.code, 'day_status_conflict')

    def test_create_update_delete_write_history(self):
        row = self._studied()
        created = LearningStudySessionChange.query.filter_by(
            session_id=row.id, event_type='created',
        ).one()
        self.assertIsNone(created.before_payload)
        self.assertEqual(created.after_payload['start_page'], 70)

        update_study_session(
            row,
            changed_by_user_id=self.teacher.id,
            start_page=72,
            end_page=73,
            change_reason='범위 수정',
        )
        updated = LearningStudySessionChange.query.filter_by(
            session_id=row.id, event_type='updated',
        ).one()
        self.assertEqual(updated.before_payload['start_page'], 70)
        self.assertEqual(updated.after_payload['start_page'], 72)
        self.assertEqual(updated.change_reason, '범위 수정')

        session_id = row.id
        delete_study_session(row, changed_by_user_id=self.teacher.id, change_reason='입력 오류')
        self.assertIsNone(LearningStudySession.query.get(session_id))
        deleted = LearningStudySessionChange.query.filter_by(event_type='deleted').one()
        self.assertEqual(deleted.before_payload['id'], session_id)
        self.assertEqual(deleted.change_reason, '입력 오류')
        self.assertEqual(deleted.child_id, self.child.id)

    def test_plan_id_and_title_are_kept_in_change_history(self):
        first = self._add_plan(textbook_title='쎈 수학 5-1', start_date=date(2026, 3, 1))
        self._add_plan(textbook_title='쎈 수학 5-2', start_date=date(2026, 9, 1))
        mid = date(2026, 7, 1)
        row = self._studied(
            study_date=mid,
            learning_workbook_plan_id=first.id,
            textbook_title='다른 표기',
        )
        created = LearningStudySessionChange.query.filter_by(
            session_id=row.id, event_type='created',
        ).one()
        self.assertEqual(created.after_payload['learning_workbook_plan_id'], first.id)
        self.assertEqual(created.after_payload['textbook_title'], '쎈 수학 5-1')
        updated = update_study_session(
            row,
            changed_by_user_id=self.teacher.id,
            start_page=72,
            end_page=73,
            change_reason='페이지 수정',
        )
        self.assertEqual(updated.learning_workbook_plan_id, first.id)
        change = LearningStudySessionChange.query.filter_by(
            session_id=row.id, event_type='updated',
        ).one()
        self.assertEqual(change.before_payload['learning_workbook_plan_id'], first.id)
        self.assertEqual(change.after_payload['learning_workbook_plan_id'], first.id)
        self.assertEqual(change.changed_by_user_id, self.teacher.id)

    def test_canonical_timeline_uses_latest_started_plan(self):
        from features.planning.timeline import canonical_workbook_plan
        old = self._add_plan(
            textbook_title='이전 교재',
            start_date=date(2026, 3, 1),
            target_completion_date=date(2026, 8, 20),
        )
        new = self._add_plan(
            textbook_title='새 교재',
            start_date=date(2026, 9, 1),
            target_completion_date=date(2026, 9, 5),
        )
        self.assertEqual(
            canonical_workbook_plan(
                grade=3, learning_subject_id=self.math.id, study_date=date(2026, 8, 25),
            ).id,
            old.id,
        )
        self.assertEqual(
            canonical_workbook_plan(
                grade=3, learning_subject_id=self.math.id, study_date=date(2026, 9, 8),
            ).id,
            new.id,
        )
        row = self._studied(
            study_date=date(2026, 8, 25),
            start_page=2,
            end_page=3,
        )
        self.assertEqual(row.learning_workbook_plan_id, old.id)
        later = self._studied(
            study_date=date(2026, 9, 8),
            start_page=2,
            end_page=3,
        )
        self.assertEqual(later.learning_workbook_plan_id, new.id)

    def test_new_session_requires_canonical_plan(self):
        with self.assertRaises(StudyRecordError) as ctx:
            create_study_session(
                child_id=self.child.id,
                learning_subject_id=self.math.id,
                study_date=self.today,
                study_status=STUDY_STATUS_STUDIED,
                recorded_by_user_id=self.teacher.id,
                start_page=1,
                end_page=2,
                textbook_title='직접 입력',
            )
        self.assertEqual(ctx.exception.code, 'plan_required')

    def test_legacy_null_plan_is_not_converted_on_update(self):
        now = datetime.utcnow()
        row = LearningStudySession(
            created_at=now,
            updated_at=now,
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            study_date=self.today,
            learning_workbook_plan_id=None,
            textbook_title='예전 직접입력',
            study_status=STUDY_STATUS_STUDIED,
            start_page=10,
            end_page=11,
            record_verification=RECORD_VERIFICATION_OBSERVED,
            recorded_by_user_id=self.teacher.id,
            actor_type='teacher',
            input_channel=INPUT_CHANNEL_TEACHER,
        )
        db.session.add(row)
        db.session.commit()
        self._add_plan(textbook_title='이후 등록 교재', start_date=date(2026, 3, 1))
        updated = update_study_session(
            row,
            changed_by_user_id=self.teacher.id,
            start_page=12,
            end_page=13,
        )
        self.assertIsNone(updated.learning_workbook_plan_id)
        self.assertEqual(updated.textbook_title, '예전 직접입력')
        self.assertEqual((updated.start_page, updated.end_page), (12, 13))

    def test_free_text_title_is_not_fuzzy_matched_to_plan(self):
        plan = self._add_plan(textbook_title='쎈 수학 5-2', start_date=date(2026, 3, 1))
        row = self._studied(textbook_title='쎈수학 5-2')
        self.assertEqual(row.learning_workbook_plan_id, plan.id)
        self.assertEqual(row.textbook_title, '쎈 수학 5-2')

    def test_verified_content_change_returns_to_observed(self):
        from features.study.records import mark_sessions_verified
        row = self._studied()
        mark_sessions_verified(
            [row.id],
            child_id=self.child.id,
            changed_by_user_id=self.teacher.id,
        )
        db.session.refresh(row)
        self.assertEqual(row.record_verification, RECORD_VERIFICATION_VERIFIED)
        update_study_session(
            row,
            changed_by_user_id=self.teacher.id,
            start_page=72,
            end_page=73,
        )
        db.session.refresh(row)
        self.assertEqual(row.record_verification, RECORD_VERIFICATION_OBSERVED)
        self.assertEqual((row.start_page, row.end_page), (72, 73))
        changed = LearningStudySessionChange.query.filter_by(
            session_id=row.id, event_type='updated',
        ).order_by(LearningStudySessionChange.id.desc()).first()
        self.assertEqual(changed.after_payload['record_verification'], RECORD_VERIFICATION_OBSERVED)
        self.assertEqual(changed.changed_by_user_id, self.teacher.id)

    def test_delete_requires_reason(self):
        row = self._studied()
        with self.assertRaises(StudyRecordError) as ctx:
            delete_study_session(row, changed_by_user_id=self.teacher.id, change_reason='  ')
        self.assertEqual(ctx.exception.code, 'reason_required')

    def test_progress_snapshot_is_unchanged_and_separate(self):
        save_progress_entry(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            textbook_title='수학 3-2',
            page=74,
            recorded_on=self.today,
            created_by_user_id=self.teacher.id,
        )
        self._studied()
        self.assertEqual(LearningProgressEntry.query.count(), 1)
        self.assertEqual(LearningStudySession.query.count(), 1)
        snapshot = LearningProgressEntry.query.one()
        self.assertEqual(snapshot.page, 74)
        self.assertFalse(hasattr(snapshot, 'study_status'))

    def test_workbook_plan_assigned_pages_exclude_permanent_only(self):
        plan = LearningWorkbookPlan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='수학 3-2',
            start_page=10,
            end_page=20,
            start_date=date(2026, 8, 1),
            target_completion_date=date(2026, 12, 1),
            exclusion_ranges_json=[{'start': 12, 'end': 13}],
        )
        db.session.add(plan)
        db.session.commit()
        self.assertEqual(physical_page_bounds(plan), (10, 20))
        self.assertEqual(permanently_excluded_ranges(plan), [{'start': 12, 'end': 13}])
        self.assertEqual(assigned_page_count(plan), 9)
        skipped = self._studied(start_page=10, end_page=11)
        self.assertEqual(skipped.end_page, 11)
        self.assertNotEqual(assigned_page_count(plan), 11)

    def test_selected_plan_id_ignores_title_spelling(self):
        plan = LearningWorkbookPlan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='쎈 수학 5-2',
            start_page=1,
            end_page=200,
            start_date=date(2026, 3, 1),
            target_completion_date=date(2026, 12, 1),
        )
        db.session.add(plan)
        db.session.commit()
        row = create_study_session(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            study_date=self.today,
            study_status=STUDY_STATUS_STUDIED,
            recorded_by_user_id=self.teacher.id,
            start_page=70,
            end_page=71,
            textbook_title='쎈수학 5-2',
            learning_workbook_plan_id=plan.id,
        )
        self.assertEqual(row.learning_workbook_plan_id, plan.id)
        self.assertEqual(row.textbook_title, '쎈 수학 5-2')
        other = create_study_session(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            study_date=self.today - timedelta(days=1),
            study_status=STUDY_STATUS_STUDIED,
            recorded_by_user_id=self.teacher.id,
            start_page=72,
            end_page=73,
            textbook_title='쎈  수학 5-2',
            learning_workbook_plan_id=plan.id,
        )
        self.assertEqual(other.learning_workbook_plan_id, plan.id)
        self.assertEqual(other.textbook_title, '쎈 수학 5-2')

    def test_plan_id_is_checked_against_subject_grade_and_start_date(self):
        korean_plan = self._add_plan(
            learning_subject_id=self.korean.id,
            textbook_title='국어 3-2',
        )
        grade_plan = self._add_plan(grade=4, textbook_title='수학 4-2')
        future_plan = self._add_plan(
            textbook_title='나중에 시작',
            start_date=self.today,
        )
        with self.assertRaises(StudyRecordError) as subject_ctx:
            self._studied(learning_workbook_plan_id=korean_plan.id)
        self.assertEqual(subject_ctx.exception.code, 'plan_subject_mismatch')
        with self.assertRaises(StudyRecordError) as grade_ctx:
            self._studied(learning_workbook_plan_id=grade_plan.id)
        self.assertEqual(grade_ctx.exception.code, 'plan_grade_mismatch')
        with self.assertRaises(StudyRecordError) as start_ctx:
            self._studied(
                study_date=self.today - timedelta(days=10),
                learning_workbook_plan_id=future_plan.id,
            )
        self.assertEqual(start_ctx.exception.code, 'plan_not_started')
        self.assertEqual(LearningStudySession.query.count(), 0)
        past = self.today - timedelta(days=10)
        started = self._add_plan(
            textbook_title='이미 시작',
            start_date=past - timedelta(days=1),
        )
        row = self._studied(
            study_date=past,
            learning_workbook_plan_id=started.id,
        )
        self.assertEqual(row.learning_workbook_plan_id, started.id)
        self.assertEqual(row.study_date, past)

    def test_studied_pages_must_stay_inside_selected_plan_range(self):
        plan = self._add_plan(start_page=10, end_page=100, textbook_title='범위 교재')
        ok = self._studied(
            learning_workbook_plan_id=plan.id,
            start_page=20,
            end_page=25,
        )
        self.assertEqual((ok.start_page, ok.end_page), (20, 25))
        with self.assertRaises(StudyRecordError) as before_ctx:
            self._studied(
                study_date=self.today - timedelta(days=1),
                learning_workbook_plan_id=plan.id,
                start_page=5,
                end_page=12,
            )
        self.assertEqual(before_ctx.exception.code, 'plan_page_out_of_range')
        with self.assertRaises(StudyRecordError) as after_ctx:
            self._studied(
                study_date=self.today - timedelta(days=2),
                learning_workbook_plan_id=plan.id,
                start_page=90,
                end_page=125,
            )
        self.assertEqual(after_ctx.exception.code, 'plan_page_out_of_range')
        with self.assertRaises(StudyRecordError) as update_ctx:
            update_study_session(
                ok,
                changed_by_user_id=self.teacher.id,
                start_page=120,
                end_page=125,
            )
        self.assertEqual(update_ctx.exception.code, 'plan_page_out_of_range')
        db.session.refresh(ok)
        self.assertEqual((ok.start_page, ok.end_page), (20, 25))
        with self.assertRaises(StudyRecordError) as missing_ctx:
            create_study_session(
                child_id=self.child.id,
                learning_subject_id=self.korean.id,
                study_date=self.today - timedelta(days=3),
                study_status=STUDY_STATUS_STUDIED,
                recorded_by_user_id=self.teacher.id,
                start_page=120,
                end_page=125,
                textbook_title='직접 입력',
            )
        self.assertEqual(missing_ctx.exception.code, 'plan_required')

    def test_new_write_path_does_not_call_save_progress_entry(self):
        import features.study.records as study_records
        import features.study.routes as study_routes
        import features.study.teacher_input as teacher_input
        for module in (study_records, teacher_input, study_routes):
            source = inspect.getsource(module)
            self.assertNotIn('save_progress_entry', source)
            self.assertNotIn('DailyPoints', source)
        self._studied()
        self.assertEqual(LearningStudySession.query.count(), 1)
        self.assertEqual(LearningProgressEntry.query.count(), 0)

    def test_missing_exclusions_do_not_invent_assigned_count(self):
        plan = LearningWorkbookPlan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='수학 3-2',
            start_page=1,
            end_page=50,
            start_date=date(2026, 8, 1),
            target_completion_date=date(2026, 12, 1),
            exclusion_ranges_json=None,
        )
        self.assertIsNone(assigned_page_count(plan))

    def test_subject_weekdays_and_non_study_day(self):
        row = save_subject_study_weekdays(self.math.id, [0, 2, 4])
        self.assertEqual(row.study_weekdays, [0, 2, 4])
        other = save_subject_study_weekdays(self.korean.id, [1, 3])
        self.assertEqual(other.study_weekdays, [1, 3])
        self.assertEqual(CenterSubjectStudyWeekdays.query.count(), 2)
        day, created = save_center_non_study_day(
            date(2026, 9, 8),
            source=NON_STUDY_SOURCE_CENTER,
            label='체험학습',
            created_by_user_id=self.teacher.id,
        )
        self.assertTrue(created)
        self.assertEqual(day.source, NON_STUDY_SOURCE_CENTER)
        again, created_again = save_center_non_study_day(
            date(2026, 9, 8),
            source=NON_STUDY_SOURCE_SYSTEM_HOLIDAY,
            label='임시',
        )
        self.assertFalse(created_again)
        self.assertEqual(again.id, day.id)
        self.assertEqual(CenterNonStudyDay.query.count(), 1)

    def test_invalid_weekdays_rejected(self):
        with self.assertRaises(StudyCalendarError):
            save_subject_study_weekdays(self.math.id, [9])

    def test_viewer_session_verified_is_not_record_verification(self):
        import features.study.records as study_records
        self.assertEqual(SESSION_VERIFIED_AT, 'viewer_child_verified_at')
        self.assertNotEqual(RECORD_VERIFICATION_VERIFIED, SESSION_VERIFIED_AT)
        self.assertNotIn('viewer_child_verified_at', inspect.getsource(study_records))
        self.assertNotIn('SESSION_VERIFIED_AT', inspect.getsource(study_records))
        flask_session = {}
        set_verified_child(flask_session, self.child)
        verified_at = flask_session[SESSION_VERIFIED_AT]
        self._studied(record_verification=RECORD_VERIFICATION_VERIFIED)
        self.assertEqual(flask_session[SESSION_CHILD_ID], self.child.id)
        self.assertEqual(flask_session[SESSION_CHILD_SLUG], self.child.viewer_slug)
        self.assertEqual(flask_session[SESSION_VERIFIED_AT], verified_at)
        self.assertTrue(is_write_fresh(flask_session, self.child))
        self.assertIsNotNone(now_utc())


class StudyFoundationMigrationTests(unittest.TestCase):
    def test_upgrade_and_downgrade_on_temp_sqlite(self):
        module = _load_study_foundation_migration()

        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext

        with tempfile.TemporaryDirectory(prefix='clc_study_mig_') as tmp:
            db_path = Path(tmp) / 'fresh.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text('CREATE TABLE user (id INTEGER PRIMARY KEY)'))
                    conn.execute(text('CREATE TABLE child (id INTEGER PRIMARY KEY)'))
                    conn.execute(text(
                        'CREATE TABLE learning_subject (id INTEGER PRIMARY KEY, key VARCHAR(64))'
                    ))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    tables = set(sa_inspect(conn).get_table_names())
                    self.assertIn('learning_study_session', tables)
                    self.assertIn('learning_study_session_change', tables)
                    self.assertIn('center_subject_study_weekdays', tables)
                    self.assertIn('center_non_study_day', tables)
                    session_cols = {
                        col['name'] for col in sa_inspect(conn).get_columns('learning_study_session')
                    }
                    self.assertEqual(
                        {
                            'study_status',
                            'record_verification',
                            'start_page',
                            'end_page',
                            'study_date',
                        }.issubset(session_cols),
                        True,
                    )
                    self.assertNotIn('learning_progress_entry', tables)
                    indexes = {
                        idx['name'] for idx in sa_inspect(conn).get_indexes('learning_study_session')
                    }
                    self.assertIn('uq_learning_study_session_non_range_day', indexes)
                    with Operations.context(context):
                        module.upgrade()
                    with Operations.context(context):
                        module.downgrade()
                    tables = set(sa_inspect(conn).get_table_names())
                    self.assertNotIn('learning_study_session', tables)
                    self.assertNotIn('center_non_study_day', tables)
                    self.assertIn('learning_subject', tables)
            finally:
                engine.dispose()

    def test_create_all_matches_migration_constraints(self):
        module = _load_study_foundation_migration()
        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext

        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.create_all()
            created = {
                table: _schema_invariants(db.engine, table)
                for table in FOUNDATION_TABLES
            }
            created_partial = _partial_unique_sql(
                db.engine,
                'learning_study_session',
                'uq_learning_study_session_non_range_day',
            )

        with tempfile.TemporaryDirectory(prefix='clc_study_schema_') as tmp:
            db_path = Path(tmp) / 'mig.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text('CREATE TABLE user (id INTEGER PRIMARY KEY)'))
                    conn.execute(text('CREATE TABLE child (id INTEGER PRIMARY KEY)'))
                    conn.execute(text(
                        'CREATE TABLE learning_subject (id INTEGER PRIMARY KEY, key VARCHAR(64))'
                    ))
                    conn.execute(text(
                        'CREATE TABLE learning_workbook_plan (id INTEGER PRIMARY KEY)'
                    ))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                        _load_migration(
                            STUDY_PLAN_FK_MIGRATION, 'study_plan_fk_mig'
                        ).upgrade()
                migrated = {
                    table: _schema_invariants(engine, table)
                    for table in FOUNDATION_TABLES
                }
                migrated_partial = _partial_unique_sql(
                    engine,
                    'learning_study_session',
                    'uq_learning_study_session_non_range_day',
                )
            finally:
                engine.dispose()

        for table in FOUNDATION_TABLES:
            self.assertEqual(created[table]['checks'], migrated[table]['checks'], table)
            self.assertEqual(created[table]['indexes'], migrated[table]['indexes'], table)
            self.assertEqual(created[table]['fks'], migrated[table]['fks'], table)
            self.assertEqual(created[table]['uniques'], migrated[table]['uniques'], table)
            self.assertEqual(created[table]['defaults'], migrated[table]['defaults'], table)

        self.assertIn(
            "WHERE study_status IN ('explicit_not_studied', 'unknown')",
            created_partial or '',
        )
        self.assertEqual(created_partial, migrated_partial)
        self.assertEqual(
            created['learning_study_session']['defaults']['record_verification'],
            "'observed'",
        )
        self.assertEqual(
            created['learning_study_session']['defaults']['actor_type'],
            "'teacher'",
        )
        self.assertEqual(
            created['center_non_study_day']['defaults']['source'],
            "'center'",
        )
        self.assertIn(
            'learning_workbook_plan_id',
            created['learning_study_session']['defaults'],
        )
        self.assertIn(
            (
                ('learning_workbook_plan_id',),
                'learning_workbook_plan',
                ('id',),
                None,
            ),
            created['learning_study_session']['fks'],
        )

    def test_upgrade_adds_partial_unique_when_table_already_exists(self):
        module = _load_study_foundation_migration()
        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext

        with tempfile.TemporaryDirectory(prefix='clc_study_existing_') as tmp:
            db_path = Path(tmp) / 'existing.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text('CREATE TABLE user (id INTEGER PRIMARY KEY)'))
                    conn.execute(text('CREATE TABLE child (id INTEGER PRIMARY KEY)'))
                    conn.execute(text(
                        'CREATE TABLE learning_subject (id INTEGER PRIMARY KEY, key VARCHAR(64))'
                    ))
                    conn.execute(text(
                        'CREATE TABLE learning_study_session ('
                        'id INTEGER NOT NULL PRIMARY KEY, '
                        'child_id INTEGER NOT NULL, '
                        'learning_subject_id INTEGER NOT NULL, '
                        'study_date DATE NOT NULL, '
                        'textbook_title VARCHAR(120), '
                        'study_status VARCHAR(32) NOT NULL, '
                        'start_page INTEGER, '
                        'end_page INTEGER, '
                        'record_verification VARCHAR(16) NOT NULL, '
                        'recorded_by_user_id INTEGER NOT NULL, '
                        'actor_type VARCHAR(16) NOT NULL, '
                        'input_channel VARCHAR(32), '
                        'created_at DATETIME NOT NULL, '
                        'updated_at DATETIME'
                        ')'
                    ))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    indexes = {
                        idx['name']
                        for idx in sa_inspect(conn).get_indexes('learning_study_session')
                    }
                    self.assertIn('uq_learning_study_session_non_range_day', indexes)
                    self.assertIn('ix_learning_study_session_child_subject_date', indexes)
                    partial = conn.execute(
                        text(
                            "SELECT sql FROM sqlite_master "
                            "WHERE type='index' AND name='uq_learning_study_session_non_range_day'"
                        )
                    ).fetchone()
                    self.assertIsNotNone(partial)
                    self.assertIn(
                        "WHERE study_status IN ('explicit_not_studied', 'unknown')",
                        partial[0],
                    )
                    self.assertIn('center_non_study_day', sa_inspect(conn).get_table_names())
            finally:
                engine.dispose()

    def test_migration_does_not_drop_progress_or_plan_columns(self):
        source = STUDY_FOUNDATION_MIGRATION.read_text(encoding='utf-8')
        self.assertNotIn('drop_column', source)
        self.assertNotIn('learning_progress_entry', source.split('Revises')[0] + source.split('def upgrade')[1].split('def downgrade')[0])
        upgrade = source.split('def upgrade')[1].split('def downgrade')[0]
        self.assertNotIn('op.drop_', upgrade)
        self.assertNotIn('ALTER TABLE learning_progress_entry', source)
        self.assertNotIn('ALTER TABLE learning_workbook_plan', source)


if __name__ == '__main__':
    unittest.main()
