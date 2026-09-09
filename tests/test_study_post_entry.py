"""Growth vNext Step 3: 교사 사후입력 LEARN-018 / 설정 UI."""
from __future__ import annotations

import inspect
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock
from werkzeug.datastructures import MultiDict

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import (  # noqa: E402
    CenterNonStudyDay,
    LearningStudySession,
    LearningSubject,
    STUDY_STATUS_STUDIED,
    STUDY_STATUS_UNKNOWN,
)
from features.planning.service import create_workbook_plan  # noqa: E402
from features.progress.service import create_subject, ensure_default_subjects  # noqa: E402
from features.study.calendar import save_subject_study_weekdays  # noqa: E402
from features.study.constants import INPUT_CHANNEL_TEACHER  # noqa: E402
from features.study.records import create_study_session  # noqa: E402
from features.study.teacher_input import save_teacher_post_entry_form  # noqa: E402
from features.study.view import list_child_study_rows, list_teacher_post_entry_rows  # noqa: E402
import features.study.teacher_input as teacher_input  # noqa: E402

TODAY = date(2026, 9, 8)  # 화 → 수학 예정


class TeacherPostEntryTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='post_teacher',
            name='사후교사',
            role='돌봄선생님',
            email='post-teacher@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='post_viewer',
            name='사후열람',
            role='학생열람',
            email='post-viewer@example.test',
            password_hash='',
        )
        self.child = Child(
            name='사후아동',
            grade=3,
            viewer_slug='postentrychildpostentrych',
            created_at=datetime(2020, 1, 1),
        )
        db.session.add_all([self.teacher, self.viewer, self.child])
        db.session.commit()
        ensure_default_subjects()
        self.korean = LearningSubject.query.filter_by(key='korean').one()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.ssen = LearningSubject.query.filter_by(key='ssen').one()
        save_subject_study_weekdays(self.korean.id, [0, 2])
        save_subject_study_weekdays(self.math.id, [1, 3])
        save_subject_study_weekdays(self.ssen.id, [4])
        for subject in (self.korean, self.math, self.ssen):
            create_workbook_plan(
                grade=3,
                learning_subject_id=subject.id,
                textbook_title=f'{subject.name} 교재',
                start_page=1,
                end_page=100,
                start_date=date(2026, 3, 1),
                target_completion_date=date(2026, 12, 31),
            )
        self.client = app.test_client()
        self.patchers = [
            mock.patch('features.study.schedule.kst_today', return_value=TODAY),
            mock.patch('features.study.records.kst_today', return_value=TODAY),
            mock.patch('features.study.routes.kst_today', return_value=TODAY),
            mock.patch('features.planning.routes.kst_today', return_value=TODAY),
            mock.patch('features.study.settings.kst_today', return_value=TODAY),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def test_post_entry_shows_missing_and_explicit_unknown(self):
        create_study_session(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            study_date=TODAY,
            study_status=STUDY_STATUS_UNKNOWN,
            recorded_by_user_id=self.teacher.id,
            actor_type='teacher',
            input_channel=INPUT_CHANNEL_TEACHER,
        )
        rows = list_teacher_post_entry_rows(self.child, TODAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['subject_id'], self.math.id)
        self.assertEqual(rows[0]['unknown_kind'], 'explicit_unknown')
        self.assertEqual(rows[0]['unknown_label'], '기억 안 남')

        LearningStudySession.query.delete()
        db.session.commit()
        rows = list_teacher_post_entry_rows(self.child, TODAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['unknown_kind'], 'missing')
        self.assertEqual(rows[0]['unknown_label'], '미입력')

    def test_post_entry_ignores_unscheduled_subject(self):
        rows = list_teacher_post_entry_rows(self.child, TODAY)
        ids = {row['subject_id'] for row in rows}
        self.assertEqual(ids, {self.math.id})
        self.assertNotIn(self.korean.id, ids)

    def test_daily_points_do_not_change_post_entry_target(self):
        db.session.add(DailyPoints(
            child_id=self.child.id,
            date=TODAY,
            korean_points=100,
            created_by=self.teacher.id,
        ))
        db.session.commit()
        rows = list_teacher_post_entry_rows(self.child, TODAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['unknown_kind'], 'missing')
        source = inspect.getsource(teacher_input)
        self.assertNotIn('from app import DailyPoints', source)
        self.assertNotIn('DailyPoints.query', source)

    def test_teacher_post_entry_http_save(self):
        self._login(self.teacher)
        html = self.client.get(
            f'/children/{self.child.id}/study-post-entry?study_date={TODAY.isoformat()}'
        ).get_data(as_text=True)
        self.assertIn('미입력', html)
        self.assertIn(self.math.name, html)
        self.assertNotIn('manage_non_study_days', Path(app.root_path, 'templates', 'study', 'child_form.html').read_text(encoding='utf-8'))
        resp = self.client.post(
            f'/children/{self.child.id}/study-post-entry',
            data=MultiDict([
                ('study_date', TODAY.isoformat()),
                ('subject_id', str(self.math.id)),
                (f'study_status_{self.math.id}', STUDY_STATUS_STUDIED),
                (f'start_page_{self.math.id}', '10'),
                (f'end_page_{self.math.id}', '12'),
                ('record_verification', 'observed'),
            ]),
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        row = LearningStudySession.query.one()
        self.assertEqual(row.study_status, STUDY_STATUS_STUDIED)
        self.assertEqual(row.start_page, 10)
        self.assertEqual(row.end_page, 12)
        self.assertEqual(row.input_channel, INPUT_CHANNEL_TEACHER)

    def test_post_entry_skips_non_expected_form_tamper(self):
        form = MultiDict([
            ('study_date', TODAY.isoformat()),
            ('subject_id', str(self.korean.id)),
            (f'study_status_{self.korean.id}', STUDY_STATUS_STUDIED),
            (f'start_page_{self.korean.id}', '10'),
            (f'end_page_{self.korean.id}', '12'),
        ])
        saved = save_teacher_post_entry_form(self.child.id, self.teacher.id, form)
        self.assertEqual(saved, [])
        self.assertEqual(LearningStudySession.query.count(), 0)

    def test_child_rows_keep_unscheduled_subjects(self):
        rows = list_child_study_rows(self.child, TODAY)
        by_id = {row['subject_id']: row for row in rows}
        self.assertTrue(by_id[self.math.id]['is_expected'])
        self.assertFalse(by_id[self.korean.id]['is_expected'])
        self.assertTrue(by_id[self.korean.id]['can_input'])
        science = create_subject('science', '과학', is_active=True, sort_order=90)
        rows = list_child_study_rows(self.child, TODAY)
        self.assertIn(science.id, {row['subject_id'] for row in rows})

    def test_child_template_has_no_calendar_settings_link(self):
        template = Path(app.root_path, 'templates', 'study', 'child_form.html').read_text(encoding='utf-8')
        self.assertNotIn('manage_non_study_days', template)
        self.assertNotIn('manage_subject_weekdays', template)
        self.assertNotIn('study-calendar', template)
        self.assertIn('추가로 공부한 과목', template)
        self.assertIn('오늘 예정된 과목', template)

    def test_viewer_blocked_from_post_entry_and_settings(self):
        self._login(self.viewer)
        resp = self.client.get(f'/children/{self.child.id}/study-post-entry', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/viewer', resp.headers.get('Location', ''))
        resp = self.client.get('/settings/subject-weekdays', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get('/settings/non-study-days', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

    def test_subject_weekday_settings_use_active_subjects(self):
        create_subject('science', '과학', is_active=True, sort_order=90)
        self._login(self.teacher)
        html = self.client.get('/settings/subject-weekdays').get_data(as_text=True)
        self.assertIn('과학', html)
        self.assertIn(self.korean.name, html)
        self.assertIn('센터 기본', html)
        resp = self.client.post(
            '/settings/subject-weekdays',
            data={
                f'weekday_mode_{self.korean.id}': 'custom',
                f'study_weekdays_{self.korean.id}': ['0', '2'],
                f'weekday_mode_{self.math.id}': 'center',
                f'weekday_mode_{self.ssen.id}': 'center',
                f'weekday_mode_{LearningSubject.query.filter_by(key="science").one().id}': 'center',
            },
            follow_redirects=True,
        )
        self.assertIn('저장했습니다', resp.get_data(as_text=True))

    def test_non_study_day_add_and_restore(self):
        self._login(self.teacher)
        html = self.client.get('/settings/non-study-days?year=2026&month=9').get_data(as_text=True)
        self.assertIn('2026년 9월', html)
        self.client.post(
            '/settings/non-study-days?year=2026&month=9',
            data={
                'action': 'add',
                'year': '2026',
                'month': '9',
                'day': '2026-09-10',
                'label': '체험학습',
            },
            follow_redirects=True,
        )
        row = CenterNonStudyDay.query.filter_by(day=date(2026, 9, 10)).one()
        self.assertEqual(row.label, '체험학습')
        self.client.post(
            '/settings/non-study-days?year=2026&month=9',
            data={
                'action': 'restore',
                'year': '2026',
                'month': '9',
                'day': '2026-09-10',
            },
            follow_redirects=True,
        )
        self.assertIsNone(CenterNonStudyDay.query.filter_by(day=date(2026, 9, 10)).first())
