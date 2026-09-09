"""Growth Step 3: teacher route authorization and HTML. viewer Growth 없음."""
from __future__ import annotations

import json
import os
import re
import unittest
from datetime import date, timedelta
from unittest import mock

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import VIEWER_ALLOWED_ENDPOINTS, VIEWER_ROLE_NAME, Child, DailyPoints, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    POLICY_VERSION_GENERAL_V2,
    STATUS_COMPLETED,
    Book,
    ChildReading,
    LearningProgressEntry,
    LearningSubject,
    ReadingDay,
)
from features.dates import DEV_DATE_CONTROL_ENV
from features.growth.copy import (
    HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN,
    READING_ACTIVITY_INCREASE,
    fallback_copy,
)
from features.growth.learning_view import PERIOD_RECORDS_INSUFFICIENT_LABEL  # noqa: E402
from features.growth.service import build_growth_view_model
from features.progress.service import ensure_default_subjects  # noqa: E402


AS_OF = date(2026, 12, 15)
PREV_START = date(2026, 10, 17)
CURRENT_START = date(2026, 11, 16)


class GrowthRouteTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        ensure_default_subjects()
        self.teacher = User(
            username='growth_route_teacher',
            name='성장교사',
            role='돌봄선생님',
            email='growth-route@example.test',
            password_hash='',
        )
        self.manager = User(
            username='growth_route_manager',
            name='성장센터장',
            role='센터장',
            email='growth-manager@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='growth_route_viewer',
            name='성장학생',
            role=VIEWER_ROLE_NAME,
            email='growth-viewer@example.test',
            password_hash='',
        )
        self.child = Child(name='시드-독서증가', grade=2, viewer_slug='s1s1s1s1s1s1s1s1s1s1s1s1')
        self.empty = Child(name='시드-신규희소', grade=1, viewer_slug='s13s13s13s13s13s13s13s13')
        db.session.add_all([self.teacher, self.manager, self.viewer, self.child, self.empty])
        db.session.commit()
        self.subjects = {row.key: row for row in LearningSubject.query.all()}
        self.client = app.test_client()
        os.environ.pop(DEV_DATE_CONTROL_ENV, None)
        os.environ.pop('FLASK_ENV', None)

    def tearDown(self):
        os.environ.pop(DEV_DATE_CONTROL_ENV, None)
        os.environ.pop('FLASK_ENV', None)
        db.session.remove()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def _book(self, title):
        book = Book(title=title, normalized_key=title, is_active=True, grade_band='2-3')
        db.session.add(book)
        db.session.flush()
        return book

    def _reading_increase(self, child):
        book = self._book('증가책')
        reading = ChildReading(
            child_id=child.id,
            book_id=book.id,
            started_on=PREV_START,
            status='in_progress',
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        dates = [PREV_START + timedelta(days=offset) for offset in range(6)]
        dates += [CURRENT_START + timedelta(days=offset) for offset in range(11)]
        for on in dates:
            db.session.add(ReadingDay(
                child_reading_id=reading.id,
                date=on,
                created_by_user_id=self.teacher.id,
                actor_type=ACTOR_TEACHER,
                policy_version=POLICY_VERSION_GENERAL_V2,
            ))
        db.session.commit()

    def _paired(self, child):
        for index, (diff, fun) in enumerate(((3, 4), (3, 4), (3, 4))):
            self._complete(child, f'이전{index}', PREV_START + timedelta(days=index), diff, fun)
        for index, (diff, fun) in enumerate(((4, 4), (4, 4), (4, 4))):
            self._complete(child, f'최근{index}', CURRENT_START + timedelta(days=index), diff, fun)

    def _complete(self, child, title, completed_on, difficulty, fun):
        book = self._book(title)
        reading = ChildReading(
            child_id=child.id,
            book_id=book.id,
            started_on=completed_on - timedelta(days=2),
            completed_on=completed_on,
            status=STATUS_COMPLETED,
            policy_version=POLICY_VERSION_GENERAL_V2,
            difficulty_rating=difficulty,
            fun_rating=fun,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        db.session.add(ReadingDay(
            child_reading_id=reading.id,
            date=completed_on,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        ))
        db.session.commit()

    def _progress(self, child, subject_key, recorded_on, page, title):
        db.session.add(LearningProgressEntry(
            child_id=child.id,
            learning_subject_id=self.subjects[subject_key].id,
            recorded_on=recorded_on,
            textbook_title=title,
            page=page,
            created_by_user_id=self.teacher.id,
        ))
        db.session.commit()

    def _points(self, child, recorded_on, total):
        db.session.add(DailyPoints(
            child_id=child.id,
            date=recorded_on,
            korean_points=total,
            math_points=0,
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
        ))
        db.session.commit()

    def _growth(self, child_id, **params):
        return self.client.get(f'/children/{child_id}/growth', query_string=params)

    def test_teacher_authorized_route_200(self):
        self._login(self.teacher)
        response = self._growth(self.child.id)
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('성장 리포트', body)
        self.assertIn(self.child.name, body)

    def test_center_manager_can_open(self):
        self._login(self.manager)
        self.assertEqual(self._growth(self.child.id).status_code, 200)

    def test_viewer_is_denied(self):
        self._login(self.viewer)
        response = self._growth(self.child.id)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/viewer', response.headers.get('Location', ''))

    def test_unauthenticated_is_denied(self):
        response = self._growth(self.child.id)
        self.assertIn(response.status_code, (302, 401))
        self.assertNotEqual(response.status_code, 200)

    def test_missing_child_404(self):
        self._login(self.teacher)
        self.assertEqual(self._growth(99999).status_code, 404)

    def test_reading_increase_renders(self):
        self._reading_increase(self.child)
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        response = self._growth(self.child.id, as_of=AS_OF.isoformat())
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(fallback_copy(READING_ACTIVITY_INCREASE)['headline'], body)
        self.assertIn('6일 → 11일', body)
        self.assertIn('분석 근거 보기', body)
        self.assertIn('2026-10-17 ~ 2026-11-15', body)

    def test_paired_insight_renders(self):
        self._paired(self.child)
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        body = self._growth(self.child.id, as_of=AS_OF.isoformat()).get_data(as_text=True)
        self.assertIn(fallback_copy(HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN)['headline'], body)

    def test_empty_state_renders(self):
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        body = self._growth(self.empty.id, as_of=AS_OF.isoformat()).get_data(as_text=True)
        self.assertIn(PERIOD_RECORDS_INSUFFICIENT_LABEL, body)
        self.assertNotIn('아직 비교할 수 있는 기록이 충분하지 않습니다.', body)
        self.assertNotIn('card h-100 growth-insight-card', body)
        self.assertIn('과거 누적값 확인 불가', body)
        self.assertIn('평가 기록 없음', body)
        self.assertNotIn('0 / 5', body)

    def test_existing_links_are_present(self):
        self._login(self.teacher)
        body = self._growth(self.child.id).get_data(as_text=True)
        self.assertIn(f'/points/input/{self.child.id}', body)
        self.assertIn(f'/points/child/{self.child.id}', body)
        self.assertIn(f'/settings/print/child/{self.child.id}', body)
        self.assertIn(f'/children/{self.child.id}/reading/history', body)
        self.assertIn(f'href="/children/{self.child.id}/reading"', body)
        self.assertIn(f'/children/{self.child.id}/progress', body)

    def test_dev_as_of_override_requires_flag(self):
        self._reading_increase(self.child)
        self._login(self.teacher)
        with mock.patch('features.growth.routes.kst_today', return_value=date(2026, 8, 23)):
            without = self._growth(self.child.id, as_of=AS_OF.isoformat())
            self.assertEqual(without.status_code, 200)
            self.assertNotIn(
                fallback_copy(READING_ACTIVITY_INCREASE)['headline'],
                without.get_data(as_text=True),
            )
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        with_flag = self._growth(self.child.id, as_of=AS_OF.isoformat())
        self.assertIn(fallback_copy(READING_ACTIVITY_INCREASE)['headline'], with_flag.get_data(as_text=True))
        self.assertIn('개발 기준일: 2026-12-15', with_flag.get_data(as_text=True))

    def test_invalid_dev_as_of_is_400(self):
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        self.assertEqual(self._growth(self.child.id, as_of='not-a-date').status_code, 400)

    def test_production_ignores_as_of_query(self):
        self._reading_increase(self.child)
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        with mock.patch.dict(os.environ, {'FLASK_ENV': 'production'}, clear=False):
            with mock.patch('features.growth.routes.kst_today', return_value=date(2026, 8, 23)):
                response = self._growth(self.child.id, as_of=AS_OF.isoformat())
                self.assertEqual(response.status_code, 200)
                body = response.get_data(as_text=True)
                self.assertNotIn(fallback_copy(READING_ACTIVITY_INCREASE)['headline'], body)
                self.assertNotIn('개발 기준일: 2026-12-15', body)

    def test_no_change_empty_state_renders(self):
        dates = [PREV_START + timedelta(days=offset) for offset in range(6)]
        dates += [CURRENT_START + timedelta(days=offset) for offset in range(6)]
        book = self._book('평탄책')
        reading = ChildReading(
            child_id=self.empty.id,
            book_id=book.id,
            started_on=PREV_START,
            status='in_progress',
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        for on in dates:
            db.session.add(ReadingDay(
                child_reading_id=reading.id,
                date=on,
                created_by_user_id=self.teacher.id,
                actor_type=ACTOR_TEACHER,
                policy_version=POLICY_VERSION_GENERAL_V2,
            ))
        db.session.commit()
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        body = self._growth(self.empty.id, as_of=AS_OF.isoformat()).get_data(as_text=True)
        self.assertIn('최근 기록에서는 기준을 넘는 뚜렷한 변화가 발견되지 않았습니다.', body)
        self.assertNotIn('card h-100 growth-insight-card', body)

    def test_dashboard_header_windows_and_kpis(self):
        self._reading_increase(self.child)
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        body = self._growth(self.child.id, as_of=AS_OF.isoformat()).get_data(as_text=True)
        self.assertIn('성장 리포트', body)
        self.assertIn('2026-11-16 ~ 2026-12-15', body)
        self.assertIn('2026-10-17 ~ 2026-11-15', body)
        self.assertIn('최근 독서 기록일', body)
        self.assertIn('11일', body)
        self.assertIn('↑', body)
        self.assertNotIn('AI가 발견한', body)

    def test_progress_snapshot_cards_render(self):
        self._progress(self.child, 'korean', date(2026, 10, 1), 51, '우등생 국어 3-2')
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        body = self._growth(self.child.id, as_of=AS_OF.isoformat()).get_data(as_text=True)
        self.assertNotIn('우등생 국어 3-2', body)
        self.assertNotIn('현재 51p', body)
        self.assertNotIn('최근 기록 10/1', body)
        self.assertNotIn('진도 기록 없음', body)

    def test_chart_dataset_matches_view_model(self):
        self._reading_increase(self.child)
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        body = self._growth(self.child.id, as_of=AS_OF.isoformat()).get_data(as_text=True)
        match = re.search(r'<script id="growth-chart-data"[^>]*>(.*?)</script>', body, re.S)
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1))
        view = build_growth_view_model(self.child, as_of=AS_OF)
        self.assertEqual(payload['activity']['current'], view['charts']['activity']['current'])
        self.assertEqual(payload['activity']['previous'], view['charts']['activity']['previous'])
        self.assertEqual(payload['activity']['labels'], ['독서 기록일'])
        self.assertIsNone(payload['points'])
        self.assertNotIn('id="growthPointsChart"', body)
        self.assertNotIn("'bundle'", body)
        self.assertNotIn('InsightCandidate', body)
        self.assertLessEqual(body.count('growth-insight-card {'), 1)
        self.assertEqual(body.count('card h-100 growth-insight-card'), 1)

    def test_incomparable_progress_keeps_current_without_fake_zero_comparison(self):
        self._progress(self.child, 'korean', CURRENT_START, 12, '최근 국어')
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        body = self._growth(self.child.id, as_of=AS_OF.isoformat()).get_data(as_text=True)

        self.assertNotIn('학습 진도 기록 최근 1건', body)
        self.assertNotIn('학습 진도 기록 이전 0건 → 최근 1건', body)
        self.assertNotIn('최근 학습 진도 기록', body)
        self.assertIn('이전 기간과 비교할 자료가 부족합니다', body)

    def test_incomparable_points_show_current_without_comparison_chart(self):
        self._points(self.child, CURRENT_START, 1200)
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        body = self._growth(self.child.id, as_of=AS_OF.isoformat()).get_data(as_text=True)
        match = re.search(r'<script id="growth-chart-data"[^>]*>(.*?)</script>', body, re.S)
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1))

        self.assertIn('1,200점', body)
        self.assertIn('이전 기간과 비교할 자료가 부족합니다', body)
        self.assertNotIn('0점 → 1,200점', body)
        self.assertIsNone(payload['points'])
        self.assertNotIn('id="growthPointsChart"', body)

    def test_comparable_zero_points_render_as_no_change(self):
        self._points(self.child, PREV_START, 0)
        self._login(self.teacher)
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        body = self._growth(self.child.id, as_of=AS_OF.isoformat()).get_data(as_text=True)
        match = re.search(r'<script id="growth-chart-data"[^>]*>(.*?)</script>', body, re.S)
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1))

        self.assertIn('0점 → 0점', body)
        self.assertIn('변화 없음', body)
        self.assertEqual(payload['points']['values'], [0, 0])
        self.assertIn('id="growthPointsChart"', body)

    def test_viewer_allowlist_does_not_include_growth_teacher(self):
        self.assertNotIn('growth.teacher', VIEWER_ALLOWED_ENDPOINTS)
        self.assertNotIn('growth.viewer', VIEWER_ALLOWED_ENDPOINTS)
        endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
        self.assertIn('growth.teacher', endpoints)
        self.assertNotIn('growth.viewer', endpoints)
