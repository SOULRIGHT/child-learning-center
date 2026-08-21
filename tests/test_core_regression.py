"""Step 0: 현재 운영 포인트/NFC/학생열람 경로 회귀테스트.

Book/ChildReading/ReadingDay, QR 본인확인, 일반독서 100/0 정책은 다루지 않는다.
"""
from __future__ import annotations

import json
import unittest
from datetime import datetime

from tests.helpers import bootstrap_test_app, import_side_effects

app, db = bootstrap_test_app()

from app import Child, DailyPoints, PointsHistory, User  # noqa: E402


def _utc_today():
    return datetime.utcnow().date()


def _local_today():
    return datetime.now().date()


class CoreRegressionTests(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()

        self.teacher = User(
            username='step0_teacher',
            name='테스트교사',
            role='돌봄선생님',
            email='step0-teacher@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='step0_viewer',
            name='테스트열람',
            role='학생열람',
            email='studentview-step0@example.test',
            password_hash='',
        )
        self.child_a = Child(name='아동A', grade=3, viewer_slug='aaaaaaaaaaaaaaaaaaaaaaaa')
        self.child_b = Child(name='아동B', grade=4, viewer_slug='bbbbbbbbbbbbbbbbbbbbbbbb')
        db.session.add_all([self.teacher, self.viewer, self.child_a, self.child_b])
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def _points_form(self, **overrides):
        data = {
            'date': _utc_today().isoformat(),
            'korean_points': '200',
            'math_points': '100',
            'ssen_points': '100',
            'reading_points': '0',
            'piano_points': '0',
            'english_points': '0',
            'advanced_math_points': '0',
            'writing_points': '0',
            'manual_entries': '[]',
        }
        data.update(overrides)
        return data

    def _reload_child(self, child):
        db.session.expire_all()
        return db.session.get(Child, child.id)

    def _reload_daily(self, daily):
        db.session.expire_all()
        return db.session.get(DailyPoints, daily.id)

    def _post_points(self, child, **overrides):
        return self.client.post(
            f'/points/input/{child.id}',
            data=self._points_form(**overrides),
            follow_redirects=False,
        )

    def test_import_uses_isolated_sqlite_without_side_effects(self):
        """app.py import 가 원격 DB/Firebase/백업 스레드를 건드리지 않는다."""
        self.assertEqual(import_side_effects(), [])
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        self.assertTrue(uri.startswith('sqlite:///'))
        self.assertNotIn('child_center.db', uri)

    def test_daily_points_create_persists_row(self):
        """교사 포인트 신규 입력이 DailyPoints 한 행을 만든다."""
        self._login(self.teacher)
        response = self._post_points(self.child_a)
        self.assertIn(response.status_code, (302, 200))
        self.assertNotIn('/login', response.headers.get('Location', ''))

        rows = DailyPoints.query.filter_by(child_id=self.child_a.id).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].korean_points, 200)
        self.assertEqual(rows[0].math_points, 100)
        self.assertEqual(rows[0].ssen_points, 100)
        self.assertEqual(rows[0].reading_points, 0)
        self.assertEqual(rows[0].date, _utc_today())

    def test_same_child_date_update_keeps_single_row(self):
        """같은 child/date 재저장 시 행이 늘지 않고 값이 갱신된다."""
        self._login(self.teacher)
        self._post_points(self.child_a, korean_points='200')
        self._post_points(self.child_a, korean_points='100')

        rows = DailyPoints.query.filter_by(
            child_id=self.child_a.id,
            date=_utc_today(),
        ).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].korean_points, 100)

    def test_total_points_equals_subject_and_manual_sum(self):
        """total_points 가 과목 포인트 + 수동 포인트 합과 같다."""
        self._login(self.teacher)
        self._post_points(
            self.child_a,
            korean_points='200',
            math_points='100',
            ssen_points='100',
            reading_points='0',
            piano_points='0',
            english_points='0',
            advanced_math_points='0',
            writing_points='0',
        )
        row = DailyPoints.query.filter_by(child_id=self.child_a.id).one()
        expected = (
            row.korean_points
            + row.math_points
            + row.ssen_points
            + row.reading_points
            + row.piano_points
            + row.english_points
            + row.advanced_math_points
            + row.writing_points
            + (row.manual_points or 0)
        )
        self.assertEqual(row.total_points, expected)
        self.assertEqual(row.total_points, 400)

    def test_cumulative_points_tracks_daily_sum(self):
        """Child.cumulative_points 가 DailyPoints.total_points 합계와 같다."""
        self._login(self.teacher)
        self._post_points(self.child_a)
        stored = self._reload_child(self.child_a)
        first_total = DailyPoints.query.filter_by(child_id=self.child_a.id).one().total_points
        self.assertEqual(stored.cumulative_points, first_total)

        self._post_points(self.child_a, korean_points='0', math_points='0', ssen_points='0')
        stored = self._reload_child(self.child_a)
        new_total = DailyPoints.query.filter_by(child_id=self.child_a.id).one().total_points
        self.assertEqual(stored.cumulative_points, new_total)

    def test_points_history_create_then_update(self):
        """신규 입력은 create, 같은 날 수정은 update 이력을 남긴다."""
        self._login(self.teacher)
        self._post_points(self.child_a, korean_points='200')
        created = PointsHistory.query.filter_by(
            child_id=self.child_a.id,
            change_type='create',
        ).all()
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].new_korean_points, 200)

        self._post_points(self.child_a, korean_points='100')
        updated = PointsHistory.query.filter_by(
            child_id=self.child_a.id,
            change_type='update',
        ).all()
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].old_korean_points, 200)
        self.assertEqual(updated[0].new_korean_points, 100)

    def test_manual_points_add_and_delete(self):
        """수동 포인트 API 추가 후 삭제가 DailyPoints 합계를 맞춘다."""
        self._login(self.teacher)
        self._post_points(self.child_a)
        daily = DailyPoints.query.filter_by(child_id=self.child_a.id).one()
        base_total = daily.total_points
        target_date = daily.date.isoformat()

        add_resp = self.client.post(
            '/api/manual-points',
            data=json.dumps({
                'child_id': self.child_a.id,
                'subject': '청소 도움',
                'points': 50,
                'reason': 'Step0 테스트',
                'date': target_date,
            }),
            content_type='application/json',
        )
        self.assertEqual(add_resp.status_code, 200)
        payload = add_resp.get_json()
        self.assertTrue(payload.get('success'), payload)

        daily = self._reload_daily(daily)
        self.assertEqual(daily.manual_points, 50)
        self.assertEqual(daily.total_points, base_total + 50)
        history = json.loads(daily.manual_history)
        self.assertEqual(len(history), 1)
        item_id = f'{daily.id}_{history[0]["id"]}'

        del_resp = self.client.delete(f'/api/manual-points/{item_id}')
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.get_json().get('success'), del_resp.get_json())

        daily = self._reload_daily(daily)
        self.assertEqual(daily.manual_points, 0)
        self.assertEqual(daily.total_points, base_total)
        self.assertEqual(json.loads(daily.manual_history or '[]'), [])

    def test_teacher_nfc_redirects_to_points_input(self):
        """교사 NFC는 해당 아동 포인트 입력으로 보낸다."""
        self._login(self.teacher)
        response = self.client.get(f'/nfc/{self.child_a.id}', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/points/input/{self.child_a.id}', response.headers.get('Location', ''))

    def test_viewer_report_and_nfc_use_slug(self):
        """학생열람은 viewer_report 조회가 되고 NFC는 slug 리포트로 보낸다."""
        self._login(self.viewer)
        report = self.client.get(
            f'/viewer/report/{self.child_a.viewer_slug}',
            follow_redirects=False,
        )
        self.assertEqual(report.status_code, 200)

        nfc = self.client.get(f'/nfc/{self.child_a.id}', follow_redirects=False)
        self.assertEqual(nfc.status_code, 302)
        self.assertIn(
            f'/viewer/report/{self.child_a.viewer_slug}',
            nfc.headers.get('Location', ''),
        )

        followed = self.client.get(f'/nfc/{self.child_a.id}', follow_redirects=True)
        self.assertEqual(followed.status_code, 200)
        html = followed.get_data(as_text=True)
        self.assertIn(self.child_a.name, html)
        self.assertIn('개인 리포트', html)

    def test_viewer_cannot_post_points_or_manual_points(self):
        """학생열람 POST는 포인트/수동포인트를 저장하지 못한다."""
        self._login(self.viewer)
        points_before = DailyPoints.query.count()
        history_before = PointsHistory.query.count()

        points_resp = self._post_points(self.child_a)
        self.assertEqual(points_resp.status_code, 302)
        self.assertIn('/viewer', points_resp.headers.get('Location', ''))

        manual_resp = self.client.post(
            '/api/manual-points',
            data=json.dumps({
                'child_id': self.child_a.id,
                'subject': '차단되어야 함',
                'points': 999,
                'reason': 'viewer-write',
                'date': _local_today().isoformat(),
            }),
            content_type='application/json',
        )
        self.assertEqual(manual_resp.status_code, 302)
        self.assertIn('/viewer', manual_resp.headers.get('Location', ''))

        self.assertEqual(DailyPoints.query.count(), points_before)
        self.assertEqual(PointsHistory.query.count(), history_before)

    def test_child_daily_points_are_isolated(self):
        """아동 A 포인트가 아동 B DailyPoints 에 섞이지 않는다."""
        self._login(self.teacher)
        self._post_points(self.child_a, korean_points='200', math_points='100', ssen_points='0')

        self.assertEqual(DailyPoints.query.filter_by(child_id=self.child_a.id).count(), 1)
        self.assertEqual(DailyPoints.query.filter_by(child_id=self.child_b.id).count(), 0)

        row_a = DailyPoints.query.filter_by(child_id=self.child_a.id).one()
        self.assertEqual(row_a.korean_points, 200)
        self.assertIsNone(
            DailyPoints.query.filter_by(child_id=self.child_b.id, korean_points=200).first()
        )
        child_b = self._reload_child(self.child_b)
        self.assertEqual(child_b.cumulative_points or 0, 0)


if __name__ == '__main__':
    unittest.main()
