"""Growth Step 0: 기존 포인트 리포트 / NFC / 순위 / DailyPoints dedupe 회귀 lock.

Growth 기능은 다루지 않는다. 집계 공식·NFC 목적지·allowlist를 바꾸지 않은 현재 동작을 고정한다.
이미 test_core_regression / reading / viewer history 가 잠근 계약은 반복하지 않는다.
"""
from __future__ import annotations

import unittest
from datetime import date

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import (  # noqa: E402
    VIEWER_ALLOWED_ENDPOINTS,
    Child,
    DailyPoints,
    User,
    build_child_report_context,
    fetch_child_daily_point_records,
)


REPORT_DAY = date(2026, 8, 20)


class CanonicalReportRegressionTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()

        self.teacher = User(
            username='canon_teacher',
            name='리포트교사',
            role='돌봄선생님',
            email='canon-teacher@example.test',
            password_hash='',
        )
        self.center_head = User(
            username='canon_head',
            name='리포트센터장',
            role='센터장',
            email='canon-head@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='canon_viewer',
            name='리포트열람',
            role='학생열람',
            email='canon-viewer@example.test',
            password_hash='',
        )
        self.child_high = Child(
            name='고득점아동',
            grade=3,
            viewer_slug='cccccccccccccccccccccccc',
            cumulative_points=300,
            include_in_stats=True,
        )
        self.child_mid = Child(
            name='중간아동',
            grade=4,
            viewer_slug='dddddddddddddddddddddddd',
            cumulative_points=200,
            include_in_stats=False,
        )
        self.child_low = Child(
            name='낮은아동',
            grade=5,
            viewer_slug='eeeeeeeeeeeeeeeeeeeeeeee',
            cumulative_points=100,
            include_in_stats=True,
        )
        db.session.add_all([
            self.teacher,
            self.center_head,
            self.viewer,
            self.child_high,
            self.child_mid,
            self.child_low,
        ])
        db.session.commit()

        self._add_daily(self.child_high, korean=200, math=100, total=300)
        self._add_daily(self.child_mid, korean=200, total=200)
        self._add_daily(self.child_low, korean=100, total=100)
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def _add_daily(self, child, *, korean=0, math=0, total=0, on=REPORT_DAY):
        row = DailyPoints(
            child_id=child.id,
            date=on,
            korean_points=korean,
            math_points=math,
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
        db.session.flush()
        return row

    def _report_context(self, child):
        with app.test_request_context('/'):
            return build_child_report_context(child)

    def test_growth_routes_are_not_registered_yet(self):
        """Step 0 시점에는 growth blueprint가 없어야 한다. Step 3에서 갱신한다."""
        endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
        self.assertFalse(any((endpoint or '').startswith('growth.') for endpoint in endpoints))
        self.assertNotIn('growth.viewer', VIEWER_ALLOWED_ENDPOINTS)
        self.assertNotIn('growth.teacher', VIEWER_ALLOWED_ENDPOINTS)

    def test_teacher_nfc_stays_on_points_input_not_growth(self):
        """교사·센터장 NFC는 포인트 입력이고 /growth 가 아니다."""
        for user in (self.teacher, self.center_head):
            self._login(user)
            response = self.client.get(f'/nfc/{self.child_high.id}', follow_redirects=False)
            self.assertEqual(response.status_code, 302, user.role)
            location = response.headers.get('Location', '')
            self.assertIn(f'/points/input/{self.child_high.id}', location)
            self.assertNotIn('/growth', location)
            self.assertNotIn('/viewer/report/', location)

    def test_viewer_nfc_stays_on_onepage_report_not_growth(self):
        """학생열람 NFC는 기존 viewer_report 이며 Growth로 보내지 않는다."""
        self._login(self.viewer)
        response = self.client.get(f'/nfc/{self.child_high.id}', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        location = response.headers.get('Location', '')
        self.assertIn(f'/viewer/report/{self.child_high.viewer_slug}', location)
        self.assertNotIn('/growth', location)
        self.assertNotIn('/points/input/', location)

    def _assert_shared_onepage_markers(self, html):
        self.assertIn('포인트 리포트', html)
        self.assertIn('전체 순위', html)
        self.assertIn('활동일수', html)
        self.assertIn('1위 / 3명', html)
        self.assertIn('고득점아동', html)
        self.assertIn('weeklyTrendChart', html)
        self.assertIn('window.print()', html)

    def test_teacher_print_uses_canonical_onepage(self):
        """교사 인쇄 리포트는 기존 원페이지 템플릿이다. 학생 독서 허브 버튼은 없다."""
        self._login(self.teacher)
        response = self.client.get(
            f'/settings/print/child/{self.child_high.id}',
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self._assert_shared_onepage_markers(html)
        self.assertIn('돌봄선생님', html)
        self.assertNotIn('독서 기록하기', html)
        self.assertNotIn('내 독서 기록', html)
        self.assertIn('/settings/print/children', html)

    def test_viewer_report_uses_canonical_onepage_and_reading_hub(self):
        """학생 리포트는 같은 원페이지이며 기존 독서 진입 버튼을 유지한다."""
        self._login(self.viewer)
        response = self.client.get(
            f'/viewer/report/{self.child_high.viewer_slug}',
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self._assert_shared_onepage_markers(html)
        self.assertIn('학생열람', html)
        self.assertIn('독서 기록하기', html)
        self.assertIn(
            f'/viewer/report/{self.child_high.viewer_slug}/reading/confirm',
            html,
        )
        self.assertIn('내 독서 기록', html)
        self.assertIn(
            f'/viewer/report/{self.child_high.viewer_slug}/reading/history',
            html,
        )

    def test_viewer_cannot_open_teacher_print_route(self):
        """학생열람은 교사 인쇄 URL로 원페이지에 들어가지 못한다."""
        self._login(self.viewer)
        response = self.client.get(
            f'/settings/print/child/{self.child_high.id}',
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/viewer', response.headers.get('Location', ''))

    def test_onepage_rank_baseline_includes_stats_excluded_child(self):
        """원페이지 순위 baseline. include_in_stats=False 아동도 분모에 넣는다. 공식은 수정하지 않는다."""
        ctx_high = self._report_context(self.child_high)
        self.assertEqual(ctx_high['final_points'], 300)
        self.assertEqual(ctx_high['overall_rank'], 1)
        self.assertEqual(ctx_high['overall_total_children'], 3)
        self.assertEqual(ctx_high['viewer_slug'], self.child_high.viewer_slug)
        self.assertIn(
            f'/viewer/report/{self.child_high.viewer_slug}',
            ctx_high['report_url'],
        )

        ctx_mid = self._report_context(self.child_mid)
        self.assertEqual(ctx_mid['final_points'], 200)
        self.assertEqual(ctx_mid['overall_rank'], 2)
        self.assertEqual(ctx_mid['overall_total_children'], 3)

        ctx_low = self._report_context(self.child_low)
        self.assertEqual(ctx_low['final_points'], 100)
        self.assertEqual(ctx_low['overall_rank'], 3)
        self.assertEqual(ctx_low['overall_total_children'], 3)

        self._login(self.viewer)
        html = self.client.get(
            f'/viewer/report/{self.child_mid.viewer_slug}',
        ).get_data(as_text=True)
        self.assertIn('2위 / 3명', html)
        self.assertIn('중간아동', html)

    def test_onepage_uses_max_id_row_when_same_day_duplicates_exist(self):
        """같은 child/date DailyPoints가 2개면 원페이지는 MAX(id) 행만 쓴다."""
        older = self._add_daily(self.child_high, korean=50, total=50, on=date(2026, 8, 21))
        newer = self._add_daily(self.child_high, korean=200, math=50, total=250, on=date(2026, 8, 21))
        db.session.commit()
        self.assertLess(older.id, newer.id)
        self.assertEqual(
            DailyPoints.query.filter_by(child_id=self.child_high.id, date=date(2026, 8, 21)).count(),
            2,
        )

        records = fetch_child_daily_point_records(self.child_high.id)
        same_day = [row for row in records if row['date'] == date(2026, 8, 21)]
        self.assertEqual(len(same_day), 1)
        self.assertEqual(same_day[0]['id'], newer.id)
        self.assertEqual(same_day[0]['total_points'], 250)
        self.assertEqual(same_day[0]['subjects']['korean'], 200)
        self.assertEqual(same_day[0]['subjects']['math'], 50)

        ctx = self._report_context(self.child_high)
        self.assertEqual(ctx['final_points'], 300 + 250)
        self.assertNotEqual(ctx['final_points'], 300 + 50 + 250)


if __name__ == '__main__':
    unittest.main()
