"""Growth vNext Step 2: 교사용 StudySession 공통 입력/조회."""
from __future__ import annotations

import inspect
import unittest
from datetime import date, timedelta
from unittest import mock

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    LearningProgressEntry,
    LearningStudySession,
    LearningSubject,
    RECORD_VERIFICATION_OBSERVED,
    RECORD_VERIFICATION_VERIFIED,
    STUDY_STATUS_EXPLICIT_NOT_STUDIED,
    STUDY_STATUS_STUDIED,
    STUDY_STATUS_UNKNOWN,
)
from features.dates import kst_today  # noqa: E402
from features.planning.service import create_workbook_plan  # noqa: E402
from features.progress.routes import LEGACY_PROGRESS_POST_MESSAGE  # noqa: E402
from features.progress.service import ensure_default_subjects, save_progress_entry  # noqa: E402
from features.reading.policy import now_utc  # noqa: E402
from features.reading.session import (  # noqa: E402
    SESSION_CHILD_ID,
    SESSION_CHILD_SLUG,
    SESSION_VERIFIED_AT,
    is_write_fresh,
    set_verified_child,
)
from features.study.constants import INPUT_CHANNEL_TEACHER  # noqa: E402
from features.study.routes import save_study_session  # noqa: E402
from features.study.teacher_input import create_teacher_study_session  # noqa: E402
from features.study.view import list_assignment_plans  # noqa: E402


class TeacherStudyInputTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='study_input_teacher',
            name='입력교사',
            role='돌봄선생님',
            email='study-input-teacher@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='study_input_viewer',
            name='입력열람',
            role='학생열람',
            email='study-input-viewer@example.test',
            password_hash='',
        )
        self.child = Child(name='입력아동', grade=3, viewer_slug='tttttttttttttttttttttttt')
        db.session.add_all([self.teacher, self.viewer, self.child])
        db.session.commit()
        ensure_default_subjects()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.today = kst_today()
        self.math_plan = create_workbook_plan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='수학 3-2',
            start_page=1,
            end_page=200,
            start_date=self.today - timedelta(days=400),
            target_completion_date=self.today + timedelta(days=120),
        )
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def _studied_data(self, **overrides):
        data = {
            'learning_subject_id': str(self.math.id),
            'study_date': self.today.isoformat(),
            'study_status': STUDY_STATUS_STUDIED,
            'textbook_title': '수학 3-2',
            'start_page': '70',
            'end_page': '71',
            'record_verification': RECORD_VERIFICATION_OBSERVED,
            'return_to': 'detail',
        }
        data.update(overrides)
        return data

    def _post(self, **overrides):
        self._login(self.teacher)
        return self.client.post(
            f'/children/{self.child.id}/study-sessions',
            data=self._studied_data(**overrides),
            follow_redirects=False,
        )

    def test_studied_start_end_saved(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 302)
        row = LearningStudySession.query.one()
        self.assertEqual(row.study_status, STUDY_STATUS_STUDIED)
        self.assertEqual(row.start_page, 70)
        self.assertEqual(row.end_page, 71)
        self.assertEqual(row.textbook_title, '수학 3-2')
        self.assertEqual(row.input_channel, INPUT_CHANNEL_TEACHER)

    def test_studied_requires_pages(self):
        self._post(start_page='', end_page='')
        self.assertEqual(LearningStudySession.query.count(), 0)

    def test_explicit_not_studied_saved_without_pages(self):
        self._post(
            study_status=STUDY_STATUS_EXPLICIT_NOT_STUDIED,
            start_page='',
            end_page='',
            textbook_title='',
        )
        row = LearningStudySession.query.one()
        self.assertEqual(row.study_status, STUDY_STATUS_EXPLICIT_NOT_STUDIED)
        self.assertIsNone(row.start_page)
        self.assertIsNone(row.end_page)

    def test_unknown_saved_without_pages(self):
        self._post(
            study_status=STUDY_STATUS_UNKNOWN,
            start_page='',
            end_page='',
            textbook_title='',
        )
        row = LearningStudySession.query.one()
        self.assertEqual(row.study_status, STUDY_STATUS_UNKNOWN)
        self.assertIsNone(row.start_page)
        self.assertIsNone(row.end_page)

    def test_observed_is_default_when_verification_omitted(self):
        data = self._studied_data()
        data.pop('record_verification')
        self._login(self.teacher)
        self.client.post(
            f'/children/{self.child.id}/study-sessions',
            data=data,
            follow_redirects=False,
        )
        row = LearningStudySession.query.one()
        self.assertEqual(row.record_verification, RECORD_VERIFICATION_OBSERVED)

    def test_verified_only_when_explicitly_chosen(self):
        self._post(record_verification=RECORD_VERIFICATION_VERIFIED)
        row = LearningStudySession.query.one()
        self.assertEqual(row.record_verification, RECORD_VERIFICATION_VERIFIED)

    def test_teacher_role_does_not_auto_verify(self):
        self.assertEqual(self.teacher.role, '돌봄선생님')
        data = self._studied_data(record_verification='teacher')
        self._login(self.teacher)
        self.client.post(
            f'/children/{self.child.id}/study-sessions',
            data=data,
            follow_redirects=False,
        )
        row = LearningStudySession.query.one()
        self.assertEqual(row.record_verification, RECORD_VERIFICATION_OBSERVED)

    def test_same_day_multiple_studied_ranges(self):
        self._post(start_page='70', end_page='71')
        self._post(start_page='80', end_page='81')
        rows = LearningStudySession.query.order_by(LearningStudySession.start_page).all()
        self.assertEqual([(row.start_page, row.end_page) for row in rows], [(70, 71), (80, 81)])

    def test_conflicting_statuses_blocked(self):
        self._post()
        self._post(study_status=STUDY_STATUS_EXPLICIT_NOT_STUDIED, start_page='', end_page='')
        self.assertEqual(LearningStudySession.query.count(), 1)
        self._post(
            study_date=(self.today - timedelta(days=1)).isoformat(),
            study_status=STUDY_STATUS_UNKNOWN,
            start_page='',
            end_page='',
        )
        self._post(
            study_date=(self.today - timedelta(days=1)).isoformat(),
            start_page='10',
            end_page='11',
        )
        self.assertEqual(
            LearningStudySession.query.filter_by(study_date=self.today - timedelta(days=1)).count(),
            1,
        )
        other = self.today - timedelta(days=2)
        self._post(
            study_date=other.isoformat(),
            study_status=STUDY_STATUS_EXPLICIT_NOT_STUDIED,
            start_page='',
            end_page='',
        )
        self._post(
            study_date=other.isoformat(),
            study_status=STUDY_STATUS_UNKNOWN,
            start_page='',
            end_page='',
        )
        self.assertEqual(LearningStudySession.query.filter_by(study_date=other).count(), 1)

    def test_earlier_pages_on_later_day_allowed(self):
        self._post(
            study_date=(self.today - timedelta(days=3)).isoformat(),
            start_page='70',
            end_page='71',
        )
        self._post(
            study_date=(self.today - timedelta(days=2)).isoformat(),
            start_page='72',
            end_page='73',
        )
        self._post(
            study_date=(self.today - timedelta(days=1)).isoformat(),
            start_page='80',
            end_page='81',
        )
        self._post(start_page='74', end_page='75')
        self.assertEqual(LearningStudySession.query.count(), 4)
        latest = LearningStudySession.query.filter_by(study_date=self.today).one()
        self.assertEqual((latest.start_page, latest.end_page), (74, 75))

    def test_three_surfaces_share_the_same_save_route(self):
        self._login(self.teacher)
        save_url = f'/children/{self.child.id}/study-sessions'
        for path in (
            f'/children/{self.child.id}',
            f'/points/input/{self.child.id}',
            f'/children/{self.child.id}/progress',
        ):
            html = self.client.get(path).get_data(as_text=True)
            self.assertIn(f'action="{save_url}"', html.replace('&amp;', '&'))
            self.assertIn('name="start_page"', html)
            self.assertIn('name="end_page"', html)
            self.assertIn('name="learning_workbook_plan_id"', html)
            self.assertNotIn('직접 입력', html)
            self.assertNotIn('등록된 배정 교재가 없으면 교재명을 직접 입력합니다', html)
            self.assertNotIn('name="textbook_title"', html)
            self.assertNotIn('name="page"', html)
            self.assertIn('기록만 함', html)
            self.assertIn('실제 교재 확인함', html)
            self.assertIn('value="observed" checked', html)
            self.assertNotIn('value="verified" checked', html)

        source = inspect.getsource(save_study_session)
        self.assertIn('create_teacher_study_session', source)
        teacher_source = inspect.getsource(create_teacher_study_session)
        self.assertIn('create_study_session', teacher_source)
        import features.study.records as study_records
        for module_source in (
            source,
            teacher_source,
            inspect.getsource(study_records),
        ):
            self.assertNotIn('save_progress_entry', module_source)

    def test_normal_save_does_not_call_save_progress_entry(self):
        with mock.patch('features.progress.service.save_progress_entry') as mocked:
            self._post()
            mocked.assert_not_called()
        self.assertEqual(LearningStudySession.query.count(), 1)
        self.assertEqual(LearningProgressEntry.query.count(), 0)

    def test_redirects_preserve_return_to(self):
        resp = self._post(return_to='detail')
        self.assertIn(f'/children/{self.child.id}', resp.headers.get('Location', ''))
        resp = self._post(start_page='80', end_page='81', return_to='points')
        self.assertIn(f'/points/input/{self.child.id}', resp.headers.get('Location', ''))
        resp = self._post(
            study_date=(self.today - timedelta(days=1)).isoformat(),
            return_to='history',
        )
        self.assertIn(f'/children/{self.child.id}/progress', resp.headers.get('Location', ''))

    def test_does_not_dual_write_progress_entry(self):
        save_progress_entry(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            textbook_title='예전 스냅샷',
            page=40,
            recorded_on=self.today - timedelta(days=7),
            created_by_user_id=self.teacher.id,
        )
        self._post()
        self.assertEqual(LearningProgressEntry.query.count(), 1)
        snapshot = LearningProgressEntry.query.one()
        self.assertEqual(snapshot.page, 40)
        self.assertEqual(snapshot.textbook_title, '예전 스냅샷')
        self.assertEqual(LearningStudySession.query.count(), 1)

    def test_selected_plan_connects_session_by_plan_id(self):
        plan = create_workbook_plan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='쎈 수학 5-2',
            start_page=1,
            end_page=180,
            start_date=date(2026, 3, 1),
            target_completion_date=date(2026, 12, 20),
        )
        self._login(self.teacher)
        html = self.client.get(f'/children/{self.child.id}').get_data(as_text=True)
        self.assertIn(f'id: {plan.id}', html)
        self.assertIn('name="learning_workbook_plan_id"', html)
        self._post(
            learning_workbook_plan_id=str(plan.id),
            textbook_title='쎈수학 5-2',
        )
        row = LearningStudySession.query.one()
        self.assertEqual(row.learning_workbook_plan_id, plan.id)
        self.assertEqual(row.textbook_title, '쎈 수학 5-2')
        self._post(
            study_date=(self.today - timedelta(days=1)).isoformat(),
            learning_workbook_plan_id=str(plan.id),
            textbook_title='쎈  수학 5-2',
            start_page='80',
            end_page='81',
        )
        ids = {item.learning_workbook_plan_id for item in LearningStudySession.query.all()}
        titles = {item.textbook_title for item in LearningStudySession.query.all()}
        self.assertEqual(ids, {plan.id})
        self.assertEqual(titles, {'쎈 수학 5-2'})

    def test_teacher_form_ignores_spoofed_plan_id(self):
        korean = LearningSubject.query.filter_by(key='korean').one()
        other_subject = create_workbook_plan(
            grade=3,
            learning_subject_id=korean.id,
            textbook_title='국어 3-2',
            start_page=1,
            end_page=100,
            start_date=date(2026, 3, 1),
            target_completion_date=date(2026, 12, 20),
        )
        other_grade = create_workbook_plan(
            grade=4,
            learning_subject_id=self.math.id,
            textbook_title='수학 4-2',
            start_page=1,
            end_page=100,
            start_date=date(2026, 3, 1),
            target_completion_date=date(2026, 12, 20),
        )
        self._login(self.teacher)
        self.client.post(
            f'/children/{self.child.id}/study-sessions',
            data=self._studied_data(learning_workbook_plan_id=str(other_subject.id)),
            follow_redirects=True,
        )
        row = LearningStudySession.query.one()
        self.assertEqual(row.learning_workbook_plan_id, self.math_plan.id)
        self.assertEqual(row.textbook_title, self.math_plan.textbook_title)
        self.client.post(
            f'/children/{self.child.id}/study-sessions',
            data=self._studied_data(
                study_date=(self.today - timedelta(days=1)).isoformat(),
                learning_workbook_plan_id=str(other_grade.id),
                start_page='72',
                end_page='73',
            ),
            follow_redirects=True,
        )
        rows = LearningStudySession.query.order_by(LearningStudySession.id.asc()).all()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].learning_workbook_plan_id, self.math_plan.id)

    def test_past_study_date_selects_plan_that_had_already_started(self):
        past = self.today - timedelta(days=20)
        old_plan = create_workbook_plan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='우등생 수학 3-1',
            start_page=1,
            end_page=180,
            start_date=past - timedelta(days=5),
            target_completion_date=self.today - timedelta(days=5),
        )
        new_plan = create_workbook_plan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='우등생 수학 3-2',
            start_page=1,
            end_page=180,
            start_date=self.today - timedelta(days=2),
            target_completion_date=date(2026, 12, 20),
        )
        self._login(self.teacher)
        html = self.client.get(f'/children/{self.child.id}').get_data(as_text=True)
        self.assertIn(old_plan.start_date.isoformat(), html)
        self.assertIn(new_plan.start_date.isoformat(), html)
        self.assertNotIn('직접 입력', html)
        plans = list_assignment_plans(self.child)
        self.assertEqual(
            {item['id'] for item in plans},
            {self.math_plan.id, old_plan.id, new_plan.id},
        )
        spoofed = self.client.post(
            f'/children/{self.child.id}/study-sessions',
            data=self._studied_data(
                study_date=past.isoformat(),
                learning_workbook_plan_id=str(new_plan.id),
                start_page='10',
                end_page='11',
            ),
            follow_redirects=True,
        )
        self.assertEqual(spoofed.status_code, 200)
        row = LearningStudySession.query.one()
        self.assertEqual(row.learning_workbook_plan_id, old_plan.id)
        self.assertEqual(row.study_date, past)
        self.assertEqual(row.textbook_title, '우등생 수학 3-1')

    def test_legacy_progress_post_is_explicit_deprecation(self):
        self._login(self.teacher)
        resp = self.client.post(
            f'/children/{self.child.id}/progress',
            data={
                'learning_subject_id': str(self.math.id),
                'textbook_title': '쎈 수학 3-2',
                'page': '74',
                'recorded_on': self.today.isoformat(),
                'return_to': 'detail',
            },
            follow_redirects=True,
        )
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(LEGACY_PROGRESS_POST_MESSAGE, html)
        self.assertEqual(LearningProgressEntry.query.count(), 0)
        self.assertEqual(LearningStudySession.query.count(), 0)
        self.assertNotIn('학습 기록을 저장했습니다.', html)

    def test_saved_session_visible_on_surfaces(self):
        self._post(start_page='70', end_page='71')
        self._login(self.teacher)
        for path in (
            f'/children/{self.child.id}',
            f'/points/input/{self.child.id}',
            f'/children/{self.child.id}/progress',
        ):
            html = self.client.get(path).get_data(as_text=True)
            self.assertIn('70~71쪽', html)
            self.assertIn('공부함', html)
            self.assertIn('기록만 함', html)
            self.assertIn('입력교사', html)
            self.assertIn('기존 진도 기록', html)

    def test_legacy_progress_stays_read_only_on_history(self):
        save_progress_entry(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            textbook_title='예전 스냅샷',
            page=40,
            recorded_on=self.today,
            created_by_user_id=self.teacher.id,
        )
        self._login(self.teacher)
        html = self.client.get(f'/children/{self.child.id}/progress').get_data(as_text=True)
        self.assertIn('기존 진도 기록', html)
        self.assertIn('예전 스냅샷', html)
        self.assertIn('40P', html)

    def test_viewer_cannot_save_study_session(self):
        self._login(self.viewer)
        resp = self.client.post(
            f'/children/{self.child.id}/study-sessions',
            data=self._studied_data(),
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/viewer', resp.headers.get('Location', ''))
        self.assertEqual(LearningStudySession.query.count(), 0)

    def test_reading_viewer_session_untouched(self):
        flask_session = {}
        set_verified_child(flask_session, self.child)
        verified_at = flask_session[SESSION_VERIFIED_AT]
        self._post(record_verification=RECORD_VERIFICATION_VERIFIED)
        self.assertEqual(flask_session[SESSION_CHILD_ID], self.child.id)
        self.assertEqual(flask_session[SESSION_CHILD_SLUG], self.child.viewer_slug)
        self.assertEqual(flask_session[SESSION_VERIFIED_AT], verified_at)
        self.assertTrue(is_write_fresh(flask_session, self.child))
        self.assertIsNotNone(now_utc())
        import features.study.teacher_input as teacher_input
        import features.study.routes as study_routes
        self.assertNotIn('viewer_child_verified_at', inspect.getsource(teacher_input))
        self.assertNotIn('SESSION_VERIFIED_AT', inspect.getsource(study_routes))

    def test_points_and_child_detail_still_render(self):
        self._login(self.teacher)
        detail = self.client.get(f'/children/{self.child.id}')
        points = self.client.get(f'/points/input/{self.child.id}')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(points.status_code, 200)
        self.assertIn('학습 기록', detail.get_data(as_text=True))
        self.assertIn('학습 기록 (선택)', points.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
