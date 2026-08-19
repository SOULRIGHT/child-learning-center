"""Step 3: ManualPointPreset 설정. 기존 수동포인트 지급 경로는 유지한다."""
from __future__ import annotations

import json
import unittest
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, PointsHistory, User, get_backup_data  # noqa: E402
from feature_models import ManualPointPreset  # noqa: E402
from features.presets.restore import restore_presets_from_backup_data  # noqa: E402
from features.presets.service import (  # noqa: E402
    DEFAULT_PRESETS,
    PresetError,
    create_preset,
    ensure_default_presets,
    list_active_presets,
    set_preset_active,
    update_preset,
)


def _utc_today():
    return datetime.utcnow().date()


class ManualPointPresetTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()

        self.teacher = User(
            username='preset_teacher',
            name='프리셋교사',
            role='돌봄선생님',
            email='preset-teacher@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='preset_viewer',
            name='프리셋열람',
            role='학생열람',
            email='studentview-preset@example.test',
            password_hash='',
        )
        self.child = Child(name='프리셋아동', grade=3, viewer_slug='dddddddddddddddddddddddd')
        db.session.add_all([self.teacher, self.viewer, self.child])
        db.session.commit()
        self.teacher_id = self.teacher.id
        self.viewer_id = self.viewer.id
        self.child_id = self.child.id
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user_id):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True

    def _points_form(self, **overrides):
        data = {
            'date': _utc_today().isoformat(),
            'korean_points': '0',
            'math_points': '0',
            'ssen_points': '0',
            'reading_points': '0',
            'piano_points': '0',
            'english_points': '0',
            'advanced_math_points': '0',
            'writing_points': '0',
            'manual_entries': '[]',
        }
        data.update(overrides)
        return data

    def test_01_create_preset(self):
        preset = create_preset('sticker', '스티커', 200, '칭찬 스티커')
        self.assertEqual(preset.key, 'sticker')
        self.assertEqual(preset.label, '스티커')
        self.assertEqual(preset.default_points, 200)
        self.assertTrue(preset.is_active)

    def test_02_key_unique(self):
        create_preset('sticker', '스티커', 200)
        with self.assertRaises(PresetError):
            create_preset('sticker', '다른 이름', 100)
        db.session.add(ManualPointPreset(key='sticker', label='중복', default_points=1))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_03_positive_points(self):
        preset = create_preset('bonus', '보너스', 3000)
        self.assertEqual(preset.default_points, 3000)

    def test_04_negative_points(self):
        preset = create_preset('penalty', '차감', -100)
        self.assertEqual(preset.default_points, -100)

    def test_05_default_five_presets(self):
        created = ensure_default_presets()
        self.assertEqual(created, 5)
        self.assertEqual(ensure_default_presets(), 0)
        keys = [row.key for row in list_active_presets()]
        self.assertEqual(keys, [item['key'] for item in DEFAULT_PRESETS])
        by_key = {row.key: row for row in ManualPointPreset.query.all()}
        self.assertEqual(by_key['textbook'].default_points, 3000)
        self.assertEqual(by_key['print'].default_points, -100)
        self.assertEqual(by_key['pencil'].default_points, -300)
        self.assertEqual(by_key['eraser'].default_points, -500)
        self.assertEqual(by_key['pencil_case'].default_points, -1000)
        self.assertIsNone(ManualPointPreset.query.filter_by(key='eraser_1000').first())

    def test_06_active_only_on_input_ui(self):
        ensure_default_presets()
        pencil = ManualPointPreset.query.filter_by(key='pencil').one()
        set_preset_active(pencil, False)
        self._login(self.teacher_id)
        html = self.client.get(f'/points/input/{self.child_id}').get_data(as_text=True)
        self.assertIn('data-preset-key="textbook"', html)
        self.assertNotIn('data-preset-key="pencil"', html)
        self.assertNotIn('eraser_1000', html)

    def test_07_sort_order(self):
        create_preset('zeta', 'Z', 10, sort_order=30)
        create_preset('alpha', 'A', 20, sort_order=10)
        create_preset('mid', 'M', 30, sort_order=20)
        from features.presets.service import list_presets
        keys = [row.key for row in list_presets(include_inactive=False)]
        self.assertEqual(keys, ['alpha', 'mid', 'zeta'])

    def test_08_update_preset(self):
        preset = create_preset('pencil2', '연필', -300, '연필 구매')
        update_preset(preset, default_points=-500, label='연필굵은')
        self.assertEqual(ManualPointPreset.query.get(preset.id).default_points, -500)
        self.assertEqual(ManualPointPreset.query.get(preset.id).label, '연필굵은')

    def test_09_deactivate(self):
        preset = create_preset('temp', '임시', 10)
        set_preset_active(preset, False)
        self.assertFalse(preset.is_active)
        self.assertNotIn('temp', [row.key for row in list_active_presets()])

    def test_10_reactivate(self):
        preset = create_preset('temp', '임시', 10)
        set_preset_active(preset, False)
        set_preset_active(preset, True)
        self.assertIn('temp', [row.key for row in list_active_presets()])

    def test_11_viewer_cannot_manage_presets(self):
        self._login(self.viewer_id)
        get_resp = self.client.get('/settings/manual-presets', follow_redirects=False)
        self.assertEqual(get_resp.status_code, 302)
        self.assertIn('/viewer', get_resp.headers.get('Location', ''))
        post_resp = self.client.post(
            '/settings/manual-presets',
            data={'key': 'hack', 'label': '해킹', 'default_points': '1'},
            follow_redirects=False,
        )
        self.assertEqual(post_resp.status_code, 302)
        self.assertIn('/viewer', post_resp.headers.get('Location', ''))
        self.assertIsNone(ManualPointPreset.query.filter_by(key='hack').first())

    def test_12_viewer_manual_points_still_blocked(self):
        self._login(self.viewer_id)
        resp = self.client.post(
            '/api/manual-points',
            data=json.dumps({
                'child_id': self.child_id,
                'subject': '교재',
                'points': 3000,
                'reason': '교재 완료',
                'date': _utc_today().isoformat(),
            }),
            content_type='application/json',
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/viewer', resp.headers.get('Location', ''))
        self.assertEqual(DailyPoints.query.count(), 0)

    def test_13_teacher_saves_via_existing_manual_points_api(self):
        ensure_default_presets()
        textbook = ManualPointPreset.query.filter_by(key='textbook').one()
        self._login(self.teacher_id)
        self.client.post(f'/points/input/{self.child_id}', data=self._points_form())
        resp = self.client.post(
            '/api/manual-points',
            data=json.dumps({
                'child_id': self.child_id,
                'subject': textbook.label,
                'points': textbook.default_points,
                'reason': textbook.default_reason,
                'date': _utc_today().isoformat(),
            }),
            content_type='application/json',
        )
        self.assertTrue(resp.get_json().get('success'), resp.get_json())
        daily = DailyPoints.query.filter_by(child_id=self.child_id).one()
        self.assertEqual(daily.manual_points, 3000)
        history = json.loads(daily.manual_history)
        self.assertEqual(history[0]['subject'], '교재')
        self.assertEqual(history[0]['points'], 3000)

    def test_14_preset_update_does_not_rewrite_history(self):
        ensure_default_presets()
        pencil = ManualPointPreset.query.filter_by(key='pencil').one()
        self._login(self.teacher_id)
        self.client.post(f'/points/input/{self.child_id}', data=self._points_form())
        self.client.post(
            '/api/manual-points',
            data=json.dumps({
                'child_id': self.child_id,
                'subject': pencil.label,
                'points': pencil.default_points,
                'reason': pencil.default_reason,
                'date': _utc_today().isoformat(),
            }),
            content_type='application/json',
        )
        update_preset(pencil, default_points=-500)
        daily = DailyPoints.query.filter_by(child_id=self.child_id).one()
        history = json.loads(daily.manual_history)
        self.assertEqual(history[0]['points'], -300)
        self.assertEqual(history[0]['subject'], '연필')
        self.assertEqual(ManualPointPreset.query.filter_by(key='pencil').one().default_points, -500)

    def test_15_freeform_manual_input_remains(self):
        self._login(self.teacher_id)
        self.client.post(f'/points/input/{self.child_id}', data=self._points_form())
        resp = self.client.post(
            '/api/manual-points',
            data=json.dumps({
                'child_id': self.child_id,
                'subject': '청소 도움',
                'points': 50,
                'reason': '자유 입력',
                'date': _utc_today().isoformat(),
            }),
            content_type='application/json',
        )
        self.assertTrue(resp.get_json().get('success'), resp.get_json())
        history = json.loads(DailyPoints.query.filter_by(child_id=self.child_id).one().manual_history)
        self.assertEqual(history[0]['subject'], '청소 도움')
        self.assertEqual(history[0]['points'], 50)

    def test_16_manual_delete_still_works(self):
        self._login(self.teacher_id)
        self.client.post(f'/points/input/{self.child_id}', data=self._points_form(korean_points='200'))
        daily = DailyPoints.query.filter_by(child_id=self.child_id).one()
        base_total = daily.total_points
        self.client.post(
            '/api/manual-points',
            data=json.dumps({
                'child_id': self.child_id,
                'subject': '청소 도움',
                'points': 50,
                'reason': '삭제 테스트',
                'date': daily.date.isoformat(),
            }),
            content_type='application/json',
        )
        daily = DailyPoints.query.get(daily.id)
        item_id = f'{daily.id}_{json.loads(daily.manual_history)[0]["id"]}'
        del_resp = self.client.delete(f'/api/manual-points/{item_id}')
        self.assertTrue(del_resp.get_json().get('success'))
        daily = DailyPoints.query.get(daily.id)
        self.assertEqual(daily.manual_points, 0)
        self.assertEqual(daily.total_points, base_total)
        self.assertEqual(json.loads(daily.manual_history or '[]'), [])

    def test_17_18_19_totals_cumulative_and_history(self):
        self._login(self.teacher_id)
        self.client.post(f'/points/input/{self.child_id}', data=self._points_form(korean_points='200'))
        self.client.post(
            '/api/manual-points',
            data=json.dumps({
                'child_id': self.child_id,
                'subject': '교재',
                'points': 3000,
                'reason': '교재 완료',
                'date': _utc_today().isoformat(),
            }),
            content_type='application/json',
        )
        daily = DailyPoints.query.filter_by(child_id=self.child_id).one()
        self.assertEqual(daily.manual_points, 3000)
        self.assertEqual(daily.total_points, 3200)
        child = Child.query.get(self.child_id)
        self.assertEqual(child.cumulative_points, 3200)
        self.assertGreaterEqual(PointsHistory.query.filter_by(child_id=self.child_id).count(), 1)

    def test_20_backup_restore(self):
        ensure_default_presets()
        update_preset(ManualPointPreset.query.filter_by(key='pencil').one(), default_points=-400)
        backup_data, error = get_backup_data()
        self.assertIsNone(error)
        self.assertEqual(backup_data['backup_metadata']['records_count']['manual_point_presets'], 5)
        pencil_row = next(item for item in backup_data['manual_point_presets'] if item['key'] == 'pencil')
        self.assertEqual(pencil_row['default_points'], -400)

        ManualPointPreset.query.delete()
        db.session.commit()
        restored = restore_presets_from_backup_data(backup_data)
        self.assertEqual(restored, 5)
        self.assertEqual(ManualPointPreset.query.filter_by(key='pencil').one().default_points, -400)

    def test_list_active_presets_does_not_change_row_count(self):
        self.assertEqual(ManualPointPreset.query.count(), 0)
        listed = list_active_presets()
        self.assertEqual(listed, [])
        self.assertEqual(ManualPointPreset.query.count(), 0)

        ensure_default_presets()
        before = ManualPointPreset.query.count()
        self.assertEqual(before, 5)
        keys_before = [row.key for row in list_active_presets()]
        self.assertEqual(ManualPointPreset.query.count(), before)
        self.assertEqual(keys_before, [item['key'] for item in DEFAULT_PRESETS])

        pencil = ManualPointPreset.query.filter_by(key='pencil').one()
        db.session.delete(pencil)
        db.session.commit()
        after_delete = ManualPointPreset.query.count()
        keys_after = [row.key for row in list_active_presets()]
        self.assertEqual(ManualPointPreset.query.count(), after_delete)
        self.assertNotIn('pencil', keys_after)
        self.assertIsNone(ManualPointPreset.query.filter_by(key='pencil').first())

    def test_get_pages_do_not_recreate_missing_presets(self):
        self._login(self.teacher_id)
        points_html = self.client.get(f'/points/input/{self.child_id}').get_data(as_text=True)
        self.assertEqual(ManualPointPreset.query.count(), 0)
        self.assertNotIn('data-preset-key="textbook"', points_html)

        manage_html = self.client.get('/settings/manual-presets').get_data(as_text=True)
        self.assertNotIn('value="textbook"', manage_html)
        self.assertNotIn('value="pencil_case"', manage_html)
        self.assertEqual(ManualPointPreset.query.count(), 0)

    def test_migration_seeds_five_on_fresh_sqlite(self):
        import importlib.util
        from pathlib import Path
        import tempfile

        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine, text

        migration_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/e3a7b16c4d20_create_manual_point_preset.py'
        )
        spec = importlib.util.spec_from_file_location('manual_point_preset_migration', migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory(prefix='clc_preset_mig_') as tmp:
            db_path = Path(tmp) / 'fresh.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    rows = conn.execute(text(
                        'SELECT key, label, default_points FROM manual_point_preset '
                        'ORDER BY sort_order, id'
                    )).fetchall()
            finally:
                engine.dispose()

        self.assertEqual(
            [(row[0], row[1], row[2]) for row in rows],
            [
                ('textbook', '교재', 3000),
                ('print', '프린트', -100),
                ('pencil', '연필', -300),
                ('eraser', '지우개', -500),
                ('pencil_case', '필통', -1000),
            ],
        )

    def test_teacher_can_open_manage_page(self):
        ensure_default_presets()
        self._login(self.teacher_id)
        resp = self.client.get('/settings/manual-presets')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('교재', html)
        self.assertIn('pencil_case', html)

    def test_zero_points_rejected(self):
        with self.assertRaises(PresetError):
            create_preset('zero', '0점', 0)


if __name__ == '__main__':
    unittest.main()
