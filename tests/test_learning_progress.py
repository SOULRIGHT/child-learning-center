"""Step 4: LearningSubject / LearningProgressEntry. DailyPoints 경로와 분리한다."""
from __future__ import annotations

import json
import unittest
from datetime import timedelta
from pathlib import Path
import importlib.util
import tempfile

from sqlalchemy.exc import IntegrityError

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, PointsHistory, User, get_backup_data  # noqa: E402
from feature_models import LearningProgressEntry, LearningSubject  # noqa: E402
from features.progress.restore import restore_learning_progress_from_backup_data  # noqa: E402
from features.progress.service import (  # noqa: E402
    DEFAULT_SUBJECTS,
    ProgressError,
    create_subject,
    current_progress_for_child,
    ensure_default_subjects,
    history_for_child,
    kst_today,
    list_active_subjects,
    list_progress_input_subjects,
    save_progress_entry,
    set_subject_active,
    update_subject,
)


class LearningProgressTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()

        self.teacher = User(
            username='progress_teacher',
            name='진도교사',
            role='돌봄선생님',
            email='progress-teacher@example.test',
            password_hash='',
        )
        self.developer = User(
            username='progress_dev',
            name='진도개발자',
            role='개발자',
            email='progress-dev@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='progress_viewer',
            name='진도열람',
            role='학생열람',
            email='studentview-progress@example.test',
            password_hash='',
        )
        self.child = Child(name='진도아동', grade=3, viewer_slug='eeeeeeeeeeeeeeeeeeeeeeee')
        db.session.add_all([self.teacher, self.developer, self.viewer, self.child])
        db.session.commit()
        self.teacher_id = self.teacher.id
        self.developer_id = self.developer.id
        self.viewer_id = self.viewer.id
        self.child_id = self.child.id
        self.client = app.test_client()
        self.today = kst_today()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user_id):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True

    def _math(self):
        ensure_default_subjects()
        return LearningSubject.query.filter_by(key='math').one()

    def _ssen(self):
        ensure_default_subjects()
        return LearningSubject.query.filter_by(key='ssen').one()

    def _save(self, **kwargs):
        math = self._math()
        payload = {
            'child_id': self.child_id,
            'learning_subject_id': math.id,
            'textbook_title': '쎈 수학 5-2',
            'page': 74,
            'recorded_on': self.today,
            'created_by_user_id': self.teacher_id,
        }
        payload.update(kwargs)
        return save_progress_entry(**payload)

    def test_01_subject_create(self):
        subject = create_subject('korean_wb', '국어', sort_order=30)
        self.assertEqual(subject.key, 'korean_wb')
        self.assertEqual(subject.name, '국어')
        self.assertTrue(subject.is_active)

    def test_02_subject_key_unique(self):
        create_subject('math_extra', '수학추가')
        with self.assertRaises(ProgressError):
            create_subject('math_extra', '다른이름')
        db.session.add(LearningSubject(key='math_extra', name='중복', is_active=True, sort_order=0))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_03_subject_active_inactive(self):
        subject = create_subject('temp', '임시')
        set_subject_active(subject, False)
        self.assertFalse(subject.is_active)
        self.assertNotIn('temp', [row.key for row in list_active_subjects()])

    def test_04_subject_sort_order(self):
        create_subject('zeta', 'Z', sort_order=30)
        create_subject('alpha', 'A', sort_order=10)
        keys = [row.key for row in list_active_subjects()]
        self.assertEqual(keys, ['alpha', 'zeta'])

    def test_05_inactive_subject_hidden_from_input(self):
        math = self._math()
        set_subject_active(math, False)
        self._login(self.teacher_id)
        html = self.client.get(f'/points/input/{self.child_id}').get_data(as_text=True)
        self.assertNotIn(f'<option value="{math.id}">수학</option>', html)
        self.assertIn('>쎈</option>', html)

    def test_06_inactive_subject_keeps_past_entry(self):
        entry, _ = self._save()
        math = self._math()
        set_subject_active(math, False)
        kept = LearningProgressEntry.query.get(entry.id)
        self.assertEqual(kept.page, 74)
        history = history_for_child(self.child_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['entry'].id, entry.id)

    def test_07_first_snapshot(self):
        entry, created = self._save()
        self.assertTrue(created)
        self.assertEqual(LearningProgressEntry.query.count(), 1)
        self.assertEqual(entry.page, 74)
        self.assertEqual(entry.textbook_title, '쎈 수학 5-2')

    def test_08_other_date_appends(self):
        first, _ = self._save(page=74, recorded_on=self.today - timedelta(days=7))
        second, created = self._save(page=91, recorded_on=self.today)
        self.assertTrue(created)
        self.assertEqual(LearningProgressEntry.query.count(), 2)
        self.assertNotEqual(first.id, second.id)

    def test_09_same_date_updates_same_row(self):
        first, _ = self._save(page=74)
        second, created = self._save(page=76)
        self.assertFalse(created)
        self.assertEqual(first.id, second.id)
        self.assertEqual(LearningProgressEntry.query.count(), 1)
        self.assertEqual(LearningProgressEntry.query.one().page, 76)

    def test_10_past_rows_preserved(self):
        old, _ = self._save(page=74, recorded_on=self.today - timedelta(days=7))
        self._save(page=91, recorded_on=self.today)
        self.assertEqual(LearningProgressEntry.query.get(old.id).page, 74)
        self.assertEqual(LearningProgressEntry.query.count(), 2)

    def test_11_latest_snapshot(self):
        self._save(page=74, recorded_on=self.today - timedelta(days=7))
        self._save(page=91, recorded_on=self.today)
        current = current_progress_for_child(self.child_id)
        math_row = next(row for row in current if row['subject'].key == 'math')
        self.assertEqual(math_row['entry'].page, 91)

    def test_12_page_zero_and_negative_rejected(self):
        with self.assertRaises(ProgressError):
            self._save(page=0)
        with self.assertRaises(ProgressError):
            self._save(page=-3)
        self.assertEqual(LearningProgressEntry.query.count(), 0)

    def test_13_textbook_title_saved(self):
        entry, _ = self._save(textbook_title='  쎈   수학  3-2  ')
        self.assertEqual(entry.textbook_title, '쎈 수학 3-2')

    def test_14_same_book_delta(self):
        self._save(page=74, recorded_on=self.today - timedelta(days=7))
        self._save(page=91, recorded_on=self.today)
        math_row = next(
            row for row in current_progress_for_child(self.child_id) if row['subject'].key == 'math'
        )
        self.assertEqual(math_row['delta'], 17)
        self.assertFalse(math_row['is_new_textbook'])

    def test_15_textbook_change_not_negative_delta(self):
        self._save(page=180, textbook_title='쎈 5-1', recorded_on=self.today - timedelta(days=7))
        self._save(page=20, textbook_title='쎈 5-2', recorded_on=self.today)
        math_row = next(
            row for row in current_progress_for_child(self.child_id) if row['subject'].key == 'math'
        )
        self.assertIsNone(math_row['delta'])
        self.assertTrue(math_row['is_new_textbook'])
        self.assertEqual(math_row['entry'].page, 20)

    def test_16_no_comparable_snapshot(self):
        self._save(page=74)
        math_row = next(
            row for row in current_progress_for_child(self.child_id) if row['subject'].key == 'math'
        )
        self.assertIsNone(math_row['delta'])
        self.assertFalse(math_row['is_new_textbook'])

    def test_17_18_19_progress_does_not_touch_points(self):
        self._save(page=74)
        self.assertEqual(DailyPoints.query.count(), 0)
        child = Child.query.get(self.child_id)
        self.assertEqual(child.cumulative_points or 0, 0)
        self.assertEqual(PointsHistory.query.count(), 0)

    def test_20_points_save_without_progress(self):
        self._login(self.teacher_id)
        resp = self.client.post(
            f'/points/input/{self.child_id}',
            data={
                'date': self.today.isoformat(),
                'korean_points': '100',
                'math_points': '0',
                'ssen_points': '0',
                'reading_points': '0',
                'piano_points': '0',
                'english_points': '0',
                'advanced_math_points': '0',
                'writing_points': '0',
                'manual_entries': '[]',
            },
            follow_redirects=False,
        )
        self.assertIn(resp.status_code, (200, 302))
        self.assertEqual(LearningProgressEntry.query.count(), 0)
        daily = DailyPoints.query.filter_by(child_id=self.child_id).one()
        self.assertEqual(daily.korean_points, 100)

    def test_21_teacher_can_save(self):
        self._login(self.teacher_id)
        math = self._math()
        resp = self.client.post(
            f'/children/{self.child_id}/progress',
            data={
                'learning_subject_id': str(math.id),
                'textbook_title': '쎈 수학 3-2',
                'page': '74',
                'recorded_on': self.today.isoformat(),
                'return_to': 'detail',
            },
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(LearningProgressEntry.query.one().page, 74)

    def test_22_viewer_cannot_save(self):
        self._login(self.viewer_id)
        math = self._math()
        resp = self.client.post(
            f'/children/{self.child_id}/progress',
            data={
                'learning_subject_id': str(math.id),
                'textbook_title': '해킹',
                'page': '10',
                'recorded_on': self.today.isoformat(),
            },
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/viewer', resp.headers.get('Location', ''))
        self.assertEqual(LearningProgressEntry.query.count(), 0)

    def test_23_viewer_cannot_manage_subjects(self):
        self._login(self.viewer_id)
        get_resp = self.client.get('/settings/learning-subjects', follow_redirects=False)
        self.assertEqual(get_resp.status_code, 302)
        post_resp = self.client.post(
            '/settings/learning-subjects',
            data={'key': 'hack', 'name': '해킹'},
            follow_redirects=False,
        )
        self.assertEqual(post_resp.status_code, 302)
        self.assertIsNone(LearningSubject.query.filter_by(key='hack').first())

    def test_24_subject_update(self):
        subject = create_subject('temp2', '임시2')
        update_subject(subject, name='고친이름', sort_order=40)
        saved = LearningSubject.query.get(subject.id)
        self.assertEqual(saved.name, '고친이름')
        self.assertEqual(saved.sort_order, 40)

    def test_25_subject_reactivate(self):
        subject = create_subject('temp3', '임시3')
        set_subject_active(subject, False)
        set_subject_active(subject, True)
        self.assertIn('temp3', [row.key for row in list_active_subjects()])

    def test_26_get_does_not_seed_or_write(self):
        self.assertEqual(LearningSubject.query.count(), 0)
        self._login(self.teacher_id)
        self.client.get(f'/points/input/{self.child_id}')
        self.client.get(f'/children/{self.child_id}')
        subjects_page = self.client.get('/settings/learning-subjects')
        self.client.get(f'/children/{self.child_id}/progress')
        self.assertEqual(LearningSubject.query.count(), 0)
        self.assertEqual(LearningProgressEntry.query.count(), 0)
        html = subjects_page.get_data(as_text=True)
        self.assertIn('신규 추가', html)
        self.assertNotIn('value="math"', html)
        self.assertNotIn('value="수학"', html)
        self.assertNotIn('value="40"', html)
        self.assertNotIn('is_exemption_eligible', html)
        self.assertIn('placeholder="예: science"', html)
        self.assertIn('placeholder="예: 과학"', html)

    def test_settings_hides_learning_subject_manage_link(self):
        self._login(self.teacher_id)
        html = self.client.get('/settings').get_data(as_text=True)
        self.assertNotIn('학습 과목 관리', html)
        self.assertNotIn('learning-subjects', html)

    def test_progress_input_shows_fixed_korean_math_ssen_only(self):
        ensure_default_subjects()
        create_subject('science', '과학', sort_order=90)
        science = LearningSubject.query.filter_by(key='science').one()
        self._login(self.teacher_id)
        html = self.client.get(f'/children/{self.child_id}').get_data(as_text=True)
        self.assertEqual(
            [row.key for row in list_progress_input_subjects()],
            ['korean', 'math', 'ssen'],
        )
        self.assertIn('국어', html)
        self.assertIn('수학', html)
        self.assertIn('쎈', html)
        self.assertNotIn(f'<option value="{science.id}">과학</option>', html)
        self.assertEqual(
            [row['subject'].key for row in current_progress_for_child(self.child_id)],
            ['korean', 'math', 'ssen'],
        )

    def test_daily_points_subject_columns_unchanged(self):
        from features.subjects import CURRENT_SUBJECTS
        cols = {column.name for column in DailyPoints.__table__.columns}
        self.assertEqual(
            {item['daily_points_field'] for item in CURRENT_SUBJECTS.values()},
            {
                'korean_points',
                'math_points',
                'ssen_points',
                'reading_points',
                'piano_points',
                'english_points',
                'advanced_math_points',
                'writing_points',
            },
        )
        self.assertTrue({item['daily_points_field'] for item in CURRENT_SUBJECTS.values()} <= cols)
        self.assertIn('manual_points', cols)

    def test_27_28_29_backup_restore(self):
        self._save(page=74, recorded_on=self.today - timedelta(days=1))
        self._save(page=91, recorded_on=self.today)
        backup_data, error = get_backup_data()
        self.assertIsNone(error)
        self.assertEqual(backup_data['backup_metadata']['records_count']['learning_subjects'], 3)
        self.assertEqual(backup_data['backup_metadata']['records_count']['learning_progress_entries'], 2)

        LearningProgressEntry.query.delete()
        LearningSubject.query.delete()
        db.session.commit()
        restored_subjects, restored_entries = restore_learning_progress_from_backup_data(backup_data)
        self.assertEqual(restored_subjects, 3)
        self.assertEqual(restored_entries, 2)
        math = LearningSubject.query.filter_by(key='math').one()
        latest = (
            LearningProgressEntry.query
            .filter_by(child_id=self.child_id, learning_subject_id=math.id)
            .order_by(LearningProgressEntry.recorded_on.desc())
            .first()
        )
        self.assertEqual(latest.page, 91)

    def test_unique_constraint(self):
        math = self._math()
        self._save(page=10)
        db.session.add(LearningProgressEntry(
            child_id=self.child_id,
            learning_subject_id=math.id,
            recorded_on=self.today,
            textbook_title='중복',
            page=11,
            created_by_user_id=self.teacher_id,
        ))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_reset_data_does_not_delete_progress(self):
        self._save(page=74)
        self._login(self.developer_id)
        resp = self.client.post('/settings/data', data={'action': 'reset_data'}, follow_redirects=False)
        self.assertIn(resp.status_code, (200, 302))
        self.assertEqual(LearningProgressEntry.query.count(), 1)
        self.assertEqual(LearningProgressEntry.query.one().page, 74)

    def test_migration_seeds_default_subjects_on_fresh_sqlite(self):
        migration_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/a9c4e81f6b30_create_learning_progress.py'
        )
        spec = importlib.util.spec_from_file_location('learning_progress_migration', migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine, text

        with tempfile.TemporaryDirectory(prefix='clc_progress_mig_') as tmp:
            db_path = Path(tmp) / 'fresh.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    rows = conn.execute(text(
                        'SELECT key, name, sort_order FROM learning_subject ORDER BY sort_order, id'
                    )).fetchall()
                    tables = conn.execute(text(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )).fetchall()
            finally:
                engine.dispose()

        self.assertEqual(
            [(row[0], row[1], row[2]) for row in rows],
            [('korean', '국어', 10), ('math', '수학', 20), ('ssen', '쎈', 30)],
        )
        self.assertIn('learning_progress_entry', [row[0] for row in tables])

    def test_ensure_adds_korean_without_touching_existing_math_ssen(self):
        math = LearningSubject(key='math', name='수학', is_active=True, sort_order=10)
        ssen = LearningSubject(key='ssen', name='쎈', is_active=True, sort_order=20)
        db.session.add_all([math, ssen])
        db.session.commit()
        math_id = math.id
        ssen_id = ssen.id

        self.assertEqual(ensure_default_subjects(), 1)
        self.assertEqual(ensure_default_subjects(), 0)

        korean = LearningSubject.query.filter_by(key='korean').one()
        self.assertEqual(korean.name, '국어')
        self.assertEqual(korean.sort_order, 10)
        self.assertTrue(korean.is_active)

        math = LearningSubject.query.get(math_id)
        ssen = LearningSubject.query.get(ssen_id)
        self.assertEqual(math.name, '수학')
        self.assertEqual(math.sort_order, 10)
        self.assertEqual(ssen.name, '쎈')
        self.assertEqual(ssen.sort_order, 20)
        self.assertEqual(LearningSubject.query.count(), 3)

    def test_ensure_default_subjects_idempotent(self):
        self.assertEqual(ensure_default_subjects(), 3)
        self.assertEqual(ensure_default_subjects(), 0)
        self.assertEqual([row.key for row in list_active_subjects()], [item['key'] for item in DEFAULT_SUBJECTS])

    def test_corrective_migration_seeds_missing_defaults_without_overwrite(self):
        migration_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/e5b2c81d4a70_ensure_default_learning_subjects.py'
        )
        spec = importlib.util.spec_from_file_location('subject_seed_migration', migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine, text

        with tempfile.TemporaryDirectory(prefix='clc_subject_seed_') as tmp:
            db_path = Path(tmp) / 'partial.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text(
                        "CREATE TABLE learning_subject ("
                        "id INTEGER PRIMARY KEY,"
                        "key VARCHAR(64) NOT NULL,"
                        "name VARCHAR(80) NOT NULL,"
                        "is_active BOOLEAN NOT NULL DEFAULT 1,"
                        "sort_order INTEGER NOT NULL DEFAULT 0,"
                        "created_at DATETIME,"
                        "updated_at DATETIME"
                        ")"
                    ))
                    conn.execute(text(
                        "INSERT INTO learning_subject (key, name, is_active, sort_order) "
                        "VALUES ('math', '사용자수학', 0, 99), ('ssen', '사용자쎈', 1, 7)"
                    ))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    rows = conn.execute(text(
                        "SELECT key, name, is_active, sort_order "
                        "FROM learning_subject ORDER BY key"
                    )).fetchall()
            finally:
                engine.dispose()

        by_key = {row[0]: row for row in rows}
        self.assertEqual(by_key['korean'][1], '국어')
        self.assertTrue(by_key['korean'][2])
        self.assertEqual(by_key['korean'][3], 10)
        self.assertEqual(by_key['math'][1], '사용자수학')
        self.assertFalse(by_key['math'][2])
        self.assertEqual(by_key['math'][3], 99)
        self.assertEqual(by_key['ssen'][1], '사용자쎈')
        self.assertTrue(by_key['ssen'][2])
        self.assertEqual(by_key['ssen'][3], 7)
        self.assertEqual(len(rows), 3)

    def test_latest_migration_chain_has_default_subjects(self):
        progress_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/a9c4e81f6b30_create_learning_progress.py'
        )
        exemption_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/d4e8a01c5b92_add_exemption_ticket_ledger.py'
        )
        seed_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/e5b2c81d4a70_ensure_default_learning_subjects.py'
        )
        modules = []
        for path, name in (
            (progress_path, 'progress_mig'),
            (exemption_path, 'exemption_mig'),
            (seed_path, 'seed_mig'),
        ):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules.append(module)

        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine, text

        with tempfile.TemporaryDirectory(prefix='clc_chain_mig_') as tmp:
            db_path = Path(tmp) / 'chain.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text("CREATE TABLE child (id INTEGER PRIMARY KEY)"))
                    conn.execute(text("CREATE TABLE user (id INTEGER PRIMARY KEY)"))
                    conn.execute(text(
                        "CREATE TABLE child_reading ("
                        "id INTEGER PRIMARY KEY, child_id INTEGER, status VARCHAR(16)"
                        ")"
                    ))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        modules[0].upgrade()
                    conn.execute(text("DELETE FROM learning_subject"))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        modules[1].upgrade()
                        modules[2].upgrade()
                    rows = conn.execute(text(
                        "SELECT key, name, sort_order FROM learning_subject ORDER BY sort_order, id"
                    )).fetchall()
                    subject_cols = [
                        row[1] for row in conn.execute(text("PRAGMA table_info(learning_subject)")).fetchall()
                    ]
                    usage_cols = [
                        row[1] for row in conn.execute(text("PRAGMA table_info(exemption_usage)")).fetchall()
                    ]
            finally:
                engine.dispose()

        self.assertEqual(
            [(row[0], row[1], row[2]) for row in rows],
            [('korean', '국어', 10), ('math', '수학', 20), ('ssen', '쎈', 30)],
        )
        self.assertNotIn('is_exemption_eligible', subject_cols)
        self.assertIn('subject_key', usage_cols)
        self.assertIn('subject_name', usage_cols)
        self.assertNotIn('learning_subject_id', usage_cols)


if __name__ == '__main__':
    unittest.main()
