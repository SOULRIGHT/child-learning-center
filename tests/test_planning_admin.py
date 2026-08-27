"""Learning Planning Admin UI. Growth metric / planner / LLM 은 연결하지 않는다."""
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
from features.planning.exclusions import PlanningError  # noqa: E402
from features.planning.service import (  # noqa: E402
    clear_child_weekdays_override,
    create_workbook_plan,
    effective_child_study_weekdays,
    get_center_weekdays,
    get_child_override_weekdays,
    list_workbook_plans,
    save_child_study_weekdays,
    set_child_weekdays_override,
    update_center_weekdays,
    update_workbook_plan,
    workbook_plan_list_rows,
)
from features.planning.weekdays import DEFAULT_STUDY_WEEKDAYS, format_weekdays  # noqa: E402
from features.progress.service import ensure_default_subjects, kst_today, save_progress_entry  # noqa: E402


class PlanningAdminTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        engine_path = resolved_engine_sqlite_path(db)
        self.assertIsNotNone(engine_path)
        self.assertNotEqual(engine_path, local_development_sqlite_path())

        self.teacher = User(
            username='plan_teacher',
            name='계획교사',
            role='돌봄선생님',
            email='plan-teacher@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='plan_viewer',
            name='계획열람',
            role='학생열람',
            email='plan-viewer@example.test',
            password_hash='',
        )
        self.general = User(
            username='plan_general',
            name='계획일반',
            role='일반사용자',
            email='plan-general@example.test',
            password_hash='',
        )
        self.child = Child(name='계획아동', grade=3, viewer_slug='qqqqqqqqqqqqqqqqqqqqqqqq')
        db.session.add_all([self.teacher, self.viewer, self.general, self.child])
        db.session.commit()
        self.teacher_id = self.teacher.id
        self.viewer_id = self.viewer.id
        self.general_id = self.general.id
        self.child_id = self.child.id
        self.client = app.test_client()
        ensure_default_subjects()
        self.math_id = LearningSubject.query.filter_by(key='math').one().id
        self.korean_id = LearningSubject.query.filter_by(key='korean').one().id

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user_id):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True

    def _plan_form(self, **overrides):
        data = {
            'grade': '3',
            'learning_subject_id': str(self.math_id),
            'textbook_title': '우등생 수학 3-2',
            'start_page': '10',
            'end_page': '184',
            'start_date': '2026-09-01',
            'target_completion_date': '2026-12-20',
            'exclusion_ranges_text': '',
        }
        data.update(overrides)
        return data

    def _assert_viewer_blocked(self, method, path, **kwargs):
        self._login(self.viewer_id)
        client_method = self.client.get if method == 'GET' else self.client.post
        resp = client_method(path, follow_redirects=False, **kwargs)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/viewer', resp.headers.get('Location', ''))

    def test_engine_is_not_instance_db(self):
        self.assertNotEqual(resolved_engine_sqlite_path(db), local_development_sqlite_path())

    def test_center_default_weekdays_are_monday_to_friday(self):
        self.assertEqual(CenterStudyCalendar.query.count(), 0)
        self.assertEqual(get_center_weekdays(), [0, 1, 2, 3, 4])
        self.assertEqual(format_weekdays(get_center_weekdays()), '월 / 화 / 수 / 목 / 금')
        self._login(self.teacher_id)
        html = self.client.get('/settings/study-calendar').get_data(as_text=True)
        self.assertEqual(CenterStudyCalendar.query.count(), 0)
        self.assertIn('id="center-wd-0"', html)
        self.assertRegex(html, r'id="center-wd-0"[^>]*checked')
        self.assertRegex(html, r'id="center-wd-4"[^>]*checked')
        self.assertNotRegex(html, r'id="center-wd-5"[^>]*checked')
        self.assertNotRegex(html, r'id="center-wd-6"[^>]*checked')
        self.assertIn('출석 기록이나 공휴일은 반영하지 않습니다', html)

    def test_center_weekdays_update_and_normalize(self):
        self._login(self.teacher_id)
        resp = self.client.post(
            '/settings/study-calendar',
            data={'study_weekdays': ['2', '0', '2', '4']},
            follow_redirects=True,
        )
        html = resp.get_data(as_text=True)
        self.assertEqual(get_center_weekdays(), [0, 2, 4])
        self.assertEqual(CenterStudyCalendar.query.count(), 1)
        self.assertIn('저장했습니다', html)
        self.assertRegex(html, r'id="center-wd-0"[^>]*checked')
        self.assertRegex(html, r'id="center-wd-2"[^>]*checked')
        self.assertRegex(html, r'id="center-wd-4"[^>]*checked')
        self.assertNotRegex(html, r'id="center-wd-1"[^>]*checked')

    def test_center_weekdays_require_at_least_one(self):
        update_center_weekdays([0, 1, 2, 3, 4])
        with self.assertRaises(PlanningError) as ctx:
            update_center_weekdays([])
        self.assertEqual(ctx.exception.code, 'center_weekdays_required')
        self.assertEqual(get_center_weekdays(), [0, 1, 2, 3, 4])
        self._login(self.teacher_id)
        resp = self.client.post('/settings/study-calendar', data={}, follow_redirects=True)
        html = resp.get_data(as_text=True)
        self.assertIn('하루 이상', html)
        self.assertEqual(get_center_weekdays(), [0, 1, 2, 3, 4])

    def test_center_weekdays_viewer_blocked(self):
        self._assert_viewer_blocked('GET', '/settings/study-calendar')
        self._assert_viewer_blocked(
            'POST',
            '/settings/study-calendar',
            data={'study_weekdays': ['0']},
        )
        self.assertEqual(CenterStudyCalendar.query.count(), 0)

    def test_center_weekdays_unauthenticated_blocked(self):
        resp = self.client.get('/settings/study-calendar', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers.get('Location', ''))

    def test_center_weekdays_general_user_blocked(self):
        self._login(self.general_id)
        resp = self.client.get('/settings/study-calendar', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/dashboard', resp.headers.get('Location', ''))

    def test_settings_index_shows_planning_links(self):
        self._login(self.teacher_id)
        html = self.client.get('/settings').get_data(as_text=True)
        self.assertIn('학습 계획', html)
        self.assertIn('/settings/study-calendar', html)
        self.assertIn('/settings/workbook-plans', html)
        self.assertNotIn('learning-subjects', html)

    def test_create_workbook_plan_and_normalize_title(self):
        self._login(self.teacher_id)
        resp = self.client.post(
            '/settings/workbook-plans',
            data=self._plan_form(textbook_title='  우등생   수학  3-2  '),
            follow_redirects=True,
        )
        html = resp.get_data(as_text=True)
        self.assertIn('추가했습니다', html)
        plan = LearningWorkbookPlan.query.one()
        self.assertEqual(plan.textbook_title, '우등생 수학 3-2')
        self.assertEqual(plan.grade, 3)
        self.assertEqual(plan.start_page, 10)
        self.assertEqual(plan.end_page, 184)
        self.assertEqual(plan.start_date, date(2026, 9, 1))
        self.assertEqual(plan.target_completion_date, date(2026, 12, 20))

    def test_exclusion_blank_stores_null_not_empty_list(self):
        self._login(self.teacher_id)
        self.client.post('/settings/workbook-plans', data=self._plan_form(exclusion_ranges_text=''))
        plan = LearningWorkbookPlan.query.one()
        self.assertIsNone(plan.exclusion_ranges_text)
        self.assertIsNone(plan.exclusion_ranges_json)
        self.assertIsNot(plan.exclusion_ranges_json, [])
        self.assertNotEqual(plan.exclusion_ranges_json, [])

        db.session.delete(plan)
        db.session.commit()
        self.client.post('/settings/workbook-plans', data=self._plan_form(exclusion_ranges_text='   '))
        plan = LearningWorkbookPlan.query.one()
        self.assertIsNone(plan.exclusion_ranges_text)
        self.assertIsNone(plan.exclusion_ranges_json)

    def test_exclusion_exact_ranges_are_stored_canonical(self):
        self._login(self.teacher_id)
        self.client.post(
            '/settings/workbook-plans',
            data=self._plan_form(exclusion_ranges_text='35-42, 67-70, 103'),
        )
        plan = LearningWorkbookPlan.query.one()
        self.assertEqual(plan.exclusion_ranges_text, '35-42, 67-70, 103')
        self.assertEqual(
            plan.exclusion_ranges_json,
            [
                {'start': 35, 'end': 42},
                {'start': 67, 'end': 70},
                {'start': 103, 'end': 103},
            ],
        )

    def test_invalid_exclusion_is_rejected(self):
        self._login(self.teacher_id)
        resp = self.client.post(
            '/settings/workbook-plans',
            data=self._plan_form(exclusion_ranges_text='35-42 abc'),
            follow_redirects=True,
        )
        html = resp.get_data(as_text=True)
        self.assertEqual(LearningWorkbookPlan.query.count(), 0)
        self.assertIn('제외 페이지 형식이 올바르지 않습니다', html)
        self.assertNotIn('IntegrityError', html)

    def test_page_order_and_date_order_rejected(self):
        self._login(self.teacher_id)
        page_html = self.client.post(
            '/settings/workbook-plans',
            data=self._plan_form(start_page='50', end_page='10'),
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertEqual(LearningWorkbookPlan.query.count(), 0)
        self.assertIn('시작 페이지는 마지막 페이지 이하여야 합니다', page_html)

        date_html = self.client.post(
            '/settings/workbook-plans',
            data=self._plan_form(start_date='2026-09-01', target_completion_date='2026-08-31'),
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertEqual(LearningWorkbookPlan.query.count(), 0)
        self.assertIn('목표 완료일은 학습 시작일과 같거나 이후여야 합니다', date_html)

    def test_duplicate_logical_plan_rejected_without_integrity_error(self):
        self._login(self.teacher_id)
        self.client.post('/settings/workbook-plans', data=self._plan_form())
        resp = self.client.post(
            '/settings/workbook-plans',
            data=self._plan_form(end_page='190', textbook_title='  우등생 수학 3-2 '),
            follow_redirects=True,
        )
        html = resp.get_data(as_text=True)
        self.assertEqual(LearningWorkbookPlan.query.count(), 1)
        self.assertIn('같은 학년·과목·교재·시작일의 계획이 이미 있습니다', html)
        self.assertNotIn('IntegrityError', html)
        self.assertNotIn('UNIQUE constraint', html)

    def test_update_workbook_plan(self):
        plan = create_workbook_plan(
            grade=3,
            learning_subject_id=self.math_id,
            textbook_title='우등생 수학 3-2',
            start_page=10,
            end_page=184,
            start_date='2026-09-01',
            target_completion_date='2026-12-20',
            exclusion_ranges_text=None,
        )
        self._login(self.teacher_id)
        resp = self.client.post(
            f'/settings/workbook-plans/{plan.id}',
            data=self._plan_form(
                start_page='12',
                end_page='180',
                target_completion_date='2026-12-18',
                exclusion_ranges_text='35-42',
            ),
            follow_redirects=True,
        )
        html = resp.get_data(as_text=True)
        self.assertIn('수정했습니다', html)
        db.session.refresh(plan)
        self.assertEqual(plan.start_page, 12)
        self.assertEqual(plan.end_page, 180)
        self.assertEqual(plan.target_completion_date, date(2026, 12, 18))
        self.assertEqual(plan.exclusion_ranges_json, [{'start': 35, 'end': 42}])

        self.client.post(
            f'/settings/workbook-plans/{plan.id}',
            data=self._plan_form(exclusion_ranges_text=''),
            follow_redirects=True,
        )
        db.session.refresh(plan)
        self.assertIsNone(plan.exclusion_ranges_text)
        self.assertIsNone(plan.exclusion_ranges_json)

    def test_workbook_plan_list_rendering_and_order(self):
        create_workbook_plan(
            grade=4,
            learning_subject_id=self.math_id,
            textbook_title='나중 수학',
            start_page=1,
            end_page=10,
            start_date='2026-09-01',
            target_completion_date='2026-10-01',
        )
        create_workbook_plan(
            grade=3,
            learning_subject_id=self.math_id,
            textbook_title='둘째 수학',
            start_page=1,
            end_page=20,
            start_date='2026-10-01',
            target_completion_date='2026-12-01',
            exclusion_ranges_text='5-6',
        )
        create_workbook_plan(
            grade=3,
            learning_subject_id=self.korean_id,
            textbook_title='국어 교재',
            start_page=1,
            end_page=30,
            start_date='2026-09-01',
            target_completion_date='2026-11-01',
        )
        create_workbook_plan(
            grade=3,
            learning_subject_id=self.math_id,
            textbook_title='첫째 수학',
            start_page=1,
            end_page=20,
            start_date='2026-09-01',
            target_completion_date='2026-12-01',
        )
        titles = [row.textbook_title for row in list_workbook_plans()]
        self.assertEqual(titles, ['국어 교재', '첫째 수학', '둘째 수학', '나중 수학'])
        labels = [row['exclusion_label'] for row in workbook_plan_list_rows()]
        self.assertEqual(labels, ['20% 추정', '20% 추정', '정확한 제외 범위 있음', '20% 추정'])

        self._login(self.teacher_id)
        html = self.client.get('/settings/workbook-plans').get_data(as_text=True)
        self.assertIn('국어 교재', html)
        self.assertIn('첫째 수학', html)
        self.assertIn('둘째 수학', html)
        self.assertIn('나중 수학', html)
        self.assertIn('20% 추정', html)
        self.assertIn('정확한 제외 범위 있음', html)
        self.assertIn('비워두면 실제 학습량은 전체 페이지의 20%가 제외된 것으로 추정합니다', html)
        self.assertNotIn('삭제', html)
        korean_at = html.index('국어 교재')
        first_math_at = html.index('첫째 수학')
        second_math_at = html.index('둘째 수학')
        later_math_at = html.index('나중 수학')
        self.assertLess(korean_at, first_math_at)
        self.assertLess(first_math_at, second_math_at)
        self.assertLess(second_math_at, later_math_at)

    def test_workbook_plan_viewer_blocked(self):
        self._assert_viewer_blocked('GET', '/settings/workbook-plans')
        self._assert_viewer_blocked('POST', '/settings/workbook-plans', data=self._plan_form())
        self.assertEqual(LearningWorkbookPlan.query.count(), 0)

    def test_missing_override_uses_center_default(self):
        self.assertIsNone(get_child_override_weekdays(self.child_id))
        self.assertEqual(effective_child_study_weekdays(self.child_id), list(DEFAULT_STUDY_WEEKDAYS))
        self._login(self.teacher_id)
        html = self.client.get(f'/children/{self.child_id}').get_data(as_text=True)
        self.assertEqual(ChildStudyWeekdays.query.count(), 0)
        self.assertEqual(CenterStudyCalendar.query.count(), 0)
        self.assertIn('학습 예정 요일', html)
        self.assertIn('센터 기본 사용', html)
        self.assertIn('월 / 화 / 수 / 목 / 금', html)
        self.assertIn('요일을 하나도 선택하지 않으면', html)
        self.assertIn('진도 기록', html)

    def test_child_override_save_update_empty_and_clear(self):
        self._login(self.teacher_id)
        self.client.post(
            f'/children/{self.child_id}/study-weekdays',
            data={'weekday_mode': 'custom', 'study_weekdays': ['0', '2', '4']},
        )
        self.assertEqual(get_child_override_weekdays(self.child_id), [0, 2, 4])
        self.assertEqual(effective_child_study_weekdays(self.child_id), [0, 2, 4])

        self.client.post(
            f'/children/{self.child_id}/study-weekdays',
            data={'weekday_mode': 'custom', 'study_weekdays': ['1', '3']},
        )
        self.assertEqual(get_child_override_weekdays(self.child_id), [1, 3])
        self.assertEqual(ChildStudyWeekdays.query.count(), 1)

        self.client.post(
            f'/children/{self.child_id}/study-weekdays',
            data={'weekday_mode': 'custom'},
        )
        self.assertEqual(get_child_override_weekdays(self.child_id), [])
        self.assertEqual(effective_child_study_weekdays(self.child_id), [])
        self.assertEqual(ChildStudyWeekdays.query.count(), 1)

        self.client.post(
            f'/children/{self.child_id}/study-weekdays',
            data={'weekday_mode': 'center', 'study_weekdays': ['0']},
        )
        self.assertIsNone(get_child_override_weekdays(self.child_id))
        self.assertEqual(ChildStudyWeekdays.query.count(), 0)
        self.assertEqual(effective_child_study_weekdays(self.child_id), list(DEFAULT_STUDY_WEEKDAYS))

    def test_child_override_uses_updated_center_default(self):
        update_center_weekdays([0, 2, 4])
        self.assertEqual(effective_child_study_weekdays(self.child_id), [0, 2, 4])
        set_child_weekdays_override(self.child_id, [6])
        self.assertEqual(effective_child_study_weekdays(self.child_id), [6])
        clear_child_weekdays_override(self.child_id)
        self.assertEqual(effective_child_study_weekdays(self.child_id), [0, 2, 4])

    def test_child_override_viewer_blocked(self):
        self._assert_viewer_blocked(
            'POST',
            f'/children/{self.child_id}/study-weekdays',
            data={'weekday_mode': 'custom', 'study_weekdays': ['0']},
        )
        self.assertEqual(ChildStudyWeekdays.query.count(), 0)

    def test_progress_input_still_saves(self):
        entry, created = save_progress_entry(
            child_id=self.child_id,
            learning_subject_id=self.math_id,
            textbook_title='우등생 수학 3-2',
            page=40,
            recorded_on=kst_today(),
            created_by_user_id=self.teacher_id,
        )
        self.assertTrue(created)
        self.assertEqual(LearningProgressEntry.query.count(), 1)
        self.assertEqual(entry.page, 40)
        self._login(self.teacher_id)
        html = self.client.get(f'/children/{self.child_id}').get_data(as_text=True)
        self.assertIn('학습 진도', html)
        self.assertIn('진도 기록', html)
        self.assertIn('학습 예정 요일', html)

    def test_save_child_weekdays_requires_mode(self):
        with self.assertRaises(PlanningError):
            save_child_study_weekdays(self.child_id, '', ['0'])
        self.assertEqual(ChildStudyWeekdays.query.count(), 0)
