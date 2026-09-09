"""Growth vNext Step 2: 아동 viewer 학습 기록 입력 / 교사 확인."""
from __future__ import annotations

import inspect
import unittest
from datetime import date, timedelta
from pathlib import Path

from werkzeug.datastructures import MultiDict
from flask import g

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_CHILD,
    LearningStudySession,
    LearningStudySessionChange,
    LearningSubject,
    RECORD_VERIFICATION_OBSERVED,
    RECORD_VERIFICATION_VERIFIED,
    STUDY_STATUS_EXPLICIT_NOT_STUDIED,
    STUDY_STATUS_STUDIED,
    STUDY_STATUS_UNKNOWN,
)
from features.dates import kst_today  # noqa: E402
from features.planning.service import create_workbook_plan  # noqa: E402
from features.progress.service import ensure_default_subjects  # noqa: E402
from features.reading.policy import now_utc  # noqa: E402
from features.reading.session import (  # noqa: E402
    SESSION_CHILD_ID,
    SESSION_CHILD_SLUG,
    SESSION_VERIFIED_AT,
)
from features.planning.timeline import resolve_canonical_workbook_plan  # noqa: E402
from features.study.constants import INPUT_CHANNEL_CHILD  # noqa: E402
from features.study.records import mark_sessions_verified  # noqa: E402
from features.study.view import (  # noqa: E402
    CHILD_NO_PLAN_MESSAGE,
    list_child_study_rows,
    pick_applicable_plan,
)
import features.study.child_input as child_input  # noqa: E402
import features.study.view as study_view  # noqa: E402


class ChildViewerStudyInputTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='child_study_teacher',
            name='확인교사',
            role='돌봄선생님',
            email='child-study-teacher@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='child_study_viewer',
            name='학습열람',
            role='학생열람',
            email='child-study-viewer@example.test',
            password_hash='',
        )
        self.child = Child(name='학습아동', grade=3, viewer_slug='aaaaaaaaaaaaaaaaaaaaaaaa')
        self.other = Child(name='다른아동', grade=3, viewer_slug='bbbbbbbbbbbbbbbbbbbbbbbb')
        db.session.add_all([self.teacher, self.viewer, self.child, self.other])
        db.session.commit()
        ensure_default_subjects()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.korean = LearningSubject.query.filter_by(key='korean').one()
        self.today = kst_today()
        self.math_plan = create_workbook_plan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='우등생 수학 3-2',
            start_page=11,
            end_page=150,
            start_date=self.today - timedelta(days=30),
            target_completion_date=self.today + timedelta(days=60),
        )
        self.korean_plan = create_workbook_plan(
            grade=3,
            learning_subject_id=self.korean.id,
            textbook_title='국어 3-2',
            start_page=1,
            end_page=80,
            start_date=self.today - timedelta(days=30),
            target_completion_date=self.today + timedelta(days=60),
        )
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
        g.pop('_login_user', None)

    def _verify(self, child):
        with self.client.session_transaction() as sess:
            sess[SESSION_CHILD_ID] = int(child.id)
            sess[SESSION_CHILD_SLUG] = child.viewer_slug
            sess[SESSION_VERIFIED_AT] = now_utc().isoformat()

    def _study_url(self, child):
        return f'/viewer/report/{child.viewer_slug}/study'

    def _post_rows(self, child, rows, **extra):
        data = [('study_date', extra.get('study_date', self.today.isoformat()))]
        for row in rows:
            subject_id = str(row['subject_id'])
            data.append(('subject_id', subject_id))
            if row.get('status'):
                data.append((f'study_status_{subject_id}', row['status']))
            if row.get('plan_id') is not None:
                data.append((f'plan_id_{subject_id}', str(row['plan_id'])))
            if 'start' in row:
                data.append((f'start_page_{subject_id}', str(row['start'])))
            if 'end' in row:
                data.append((f'end_page_{subject_id}', str(row['end'])))
        if extra.get('record_verification'):
            data.append(('record_verification', extra['record_verification']))
        self._login(self.viewer)
        self._verify(child)
        return self.client.post(
            self._study_url(child),
            data=MultiDict(data),
            follow_redirects=True,
        )

    def test_verified_viewer_can_open_own_study_form(self):
        self._login(self.viewer)
        self._verify(self.child)
        resp = self.client.get(self._study_url(self.child))
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('학습 페이지 기록', html)
        self.assertIn(self.math.name, html)
        self.assertIn(self.korean.name, html)
        self.assertIn('우등생 수학 3-2', html)
        self.assertNotIn('기록만 함', html)
        self.assertNotIn('실제 교재 확인함', html)
        self.assertNotIn('직접 입력', html)
        self.assertIn(CHILD_NO_PLAN_MESSAGE, html)
        self.assertNotIn('/settings/workbook-plans', html)

    def test_cannot_open_other_child_study_form(self):
        self._login(self.viewer)
        self._verify(self.child)
        resp = self.client.get(self._study_url(self.other), follow_redirects=False)
        self.assertEqual(resp.status_code, 403)
        posted = self.client.post(
            self._study_url(self.other),
            data=MultiDict([
                ('study_date', self.today.isoformat()),
                ('subject_id', str(self.math.id)),
                (f'study_status_{self.math.id}', STUDY_STATUS_STUDIED),
                (f'plan_id_{self.math.id}', str(self.math_plan.id)),
                (f'start_page_{self.math.id}', '20'),
                (f'end_page_{self.math.id}', '25'),
            ]),
            follow_redirects=False,
        )
        self.assertEqual(posted.status_code, 403)
        self.assertEqual(LearningStudySession.query.count(), 0)

    def test_report_and_reading_editor_link_to_study(self):
        self._login(self.viewer)
        self._verify(self.child)
        report = self.client.get(f'/viewer/report/{self.child.viewer_slug}').get_data(as_text=True)
        self.assertIn('학습 페이지 기록하기', report)
        self.assertIn('독서 기록하기', report)
        editor = self.client.get(f'/viewer/report/{self.child.viewer_slug}/reading').get_data(as_text=True)
        self.assertIn('학습 페이지 기록하기', editor)

    def test_rows_come_from_plans_not_hardcoded_subjects(self):
        rows = list_child_study_rows(self.child, self.today)
        names = {row['subject_name'] for row in rows}
        self.assertIn(self.math.name, names)
        self.assertIn(self.korean.name, names)
        source = inspect.getsource(study_view) + inspect.getsource(child_input)
        template = Path(app.root_path, 'templates', 'study', 'child_form.html').read_text(encoding='utf-8')
        for banned in ('국어', '수학', '쎈'):
            self.assertNotIn(banned, inspect.getsource(list_child_study_rows))
            self.assertNotIn(banned, template)

    def test_multi_subject_save_and_skip_blank_rows(self):
        ssen = LearningSubject.query.filter_by(key='ssen').one()
        create_workbook_plan(
            grade=3,
            learning_subject_id=ssen.id,
            textbook_title='쎈 수학 3-2',
            start_page=1,
            end_page=100,
            start_date=self.today - timedelta(days=10),
            target_completion_date=self.today + timedelta(days=40),
        )
        self._post_rows(self.child, [
            {
                'subject_id': self.math.id,
                'status': STUDY_STATUS_STUDIED,
                'plan_id': self.math_plan.id,
                'start': 20,
                'end': 25,
            },
            {
                'subject_id': self.korean.id,
                'status': STUDY_STATUS_EXPLICIT_NOT_STUDIED,
                'plan_id': self.korean_plan.id,
            },
            {'subject_id': ssen.id, 'plan_id': None},
        ])
        rows = LearningStudySession.query.order_by(LearningStudySession.learning_subject_id).all()
        self.assertEqual(len(rows), 2)
        by_subject = {row.learning_subject_id: row for row in rows}
        math_row = by_subject[self.math.id]
        self.assertEqual(math_row.study_status, STUDY_STATUS_STUDIED)
        self.assertEqual((math_row.start_page, math_row.end_page), (20, 25))
        self.assertEqual(math_row.record_verification, RECORD_VERIFICATION_OBSERVED)
        self.assertEqual(math_row.actor_type, ACTOR_CHILD)
        self.assertEqual(math_row.input_channel, INPUT_CHANNEL_CHILD)
        self.assertEqual(math_row.textbook_title, '우등생 수학 3-2')
        korean_row = by_subject[self.korean.id]
        self.assertEqual(korean_row.study_status, STUDY_STATUS_EXPLICIT_NOT_STUDIED)
        self.assertIsNone(korean_row.start_page)
        self.assertEqual(LearningStudySession.query.filter_by(learning_subject_id=ssen.id).count(), 0)

    def test_unknown_is_saved_only_when_chosen(self):
        self._post_rows(self.child, [{
            'subject_id': self.math.id,
            'status': STUDY_STATUS_UNKNOWN,
            'plan_id': self.math_plan.id,
        }])
        row = LearningStudySession.query.one()
        self.assertEqual(row.study_status, STUDY_STATUS_UNKNOWN)
        self.assertIsNone(row.start_page)

    def test_child_cannot_set_verified(self):
        self._post_rows(
            self.child,
            [{
                'subject_id': self.math.id,
                'status': STUDY_STATUS_STUDIED,
                'plan_id': self.math_plan.id,
                'start': 20,
                'end': 25,
            }],
            record_verification=RECORD_VERIFICATION_VERIFIED,
        )
        row = LearningStudySession.query.one()
        self.assertEqual(row.record_verification, RECORD_VERIFICATION_OBSERVED)

    def test_same_day_reentry_updates_instead_of_duplicating(self):
        self._post_rows(self.child, [{
            'subject_id': self.math.id,
            'status': STUDY_STATUS_STUDIED,
            'plan_id': self.math_plan.id,
            'start': 20,
            'end': 25,
        }])
        self._post_rows(self.child, [{
            'subject_id': self.math.id,
            'status': STUDY_STATUS_STUDIED,
            'plan_id': self.math_plan.id,
            'start': 26,
            'end': 30,
        }])
        self.assertEqual(LearningStudySession.query.count(), 1)
        row = LearningStudySession.query.one()
        self.assertEqual((row.start_page, row.end_page), (26, 30))
        self.assertEqual(
            LearningStudySessionChange.query.filter_by(event_type='updated').count(),
            1,
        )

    def test_pages_inside_and_outside_plan(self):
        ok = self._post_rows(self.child, [{
            'subject_id': self.math.id,
            'status': STUDY_STATUS_STUDIED,
            'plan_id': self.math_plan.id,
            'start': 11,
            'end': 11,
        }])
        self.assertEqual(LearningStudySession.query.count(), 1)
        html = self._post_rows(self.child, [{
            'subject_id': self.math.id,
            'status': STUDY_STATUS_STUDIED,
            'plan_id': self.math_plan.id,
            'start': 140,
            'end': 151,
        }]).get_data(as_text=True)
        self.assertIn('선택한 교재의 페이지 범위 안에서만', html)
        self.assertEqual(LearningStudySession.query.filter_by(learning_subject_id=self.math.id).count(), 1)
        html = self._post_rows(self.child, [{
            'subject_id': self.math.id,
            'status': STUDY_STATUS_STUDIED,
            'plan_id': self.math_plan.id,
            'start': 30,
            'end': 20,
        }]).get_data(as_text=True)
        self.assertIn('시작 페이지가 끝 페이지보다 클 수 없습니다', html)
        html = self._post_rows(self.child, [{
            'subject_id': self.math.id,
            'status': STUDY_STATUS_STUDIED,
            'plan_id': self.math_plan.id,
        }]).get_data(as_text=True)
        self.assertIn('시작 페이지는 정수여야 합니다', html)
        self.assertEqual(ok.status_code, 200)

    def test_partial_failure_saves_nothing(self):
        self._post_rows(self.child, [
            {
                'subject_id': self.math.id,
                'status': STUDY_STATUS_STUDIED,
                'plan_id': self.math_plan.id,
                'start': 20,
                'end': 25,
            },
            {
                'subject_id': self.korean.id,
                'status': STUDY_STATUS_STUDIED,
                'plan_id': self.korean_plan.id,
                'start': 90,
                'end': 95,
            },
        ])
        self.assertEqual(LearningStudySession.query.count(), 0)

    def test_teacher_can_view_edit_and_batch_verify(self):
        self._post_rows(self.child, [
            {
                'subject_id': self.math.id,
                'status': STUDY_STATUS_STUDIED,
                'plan_id': self.math_plan.id,
                'start': 20,
                'end': 25,
            },
            {
                'subject_id': self.korean.id,
                'status': STUDY_STATUS_EXPLICIT_NOT_STUDIED,
                'plan_id': self.korean_plan.id,
            },
        ])
        math_row = LearningStudySession.query.filter_by(learning_subject_id=self.math.id).one()
        korean_row = LearningStudySession.query.filter_by(learning_subject_id=self.korean.id).one()
        self._login(self.teacher)
        html = self.client.get(f'/children/{self.child.id}').get_data(as_text=True)
        self.assertIn('미확인 학습 기록', html)
        self.assertIn('아동', html)
        self.client.post(
            f'/children/{self.child.id}/study-sessions/{math_row.id}',
            data={'study_status': 'studied', 'start_page': '21', 'end_page': '26', 'return_to': 'detail'},
        )
        db.session.refresh(math_row)
        self.assertEqual((math_row.start_page, math_row.end_page), (21, 26))
        self.assertEqual(math_row.record_verification, RECORD_VERIFICATION_OBSERVED)
        self.client.post(
            f'/children/{self.child.id}/study-sessions/verify',
            data={'session_id': [str(math_row.id), str(korean_row.id)], 'return_to': 'detail'},
        )
        db.session.refresh(math_row)
        db.session.refresh(korean_row)
        self.assertEqual(math_row.record_verification, RECORD_VERIFICATION_VERIFIED)
        self.assertEqual(korean_row.record_verification, RECORD_VERIFICATION_VERIFIED)
        verify_change = LearningStudySessionChange.query.filter_by(
            session_id=math_row.id, event_type='updated',
        ).order_by(LearningStudySessionChange.id.desc()).first()
        self.assertEqual(verify_change.after_payload['record_verification'], RECORD_VERIFICATION_VERIFIED)
        self.assertEqual(verify_change.changed_by_user_id, self.teacher.id)

    def test_child_edit_of_verified_record_returns_to_observed(self):
        self._post_rows(self.child, [{
            'subject_id': self.math.id,
            'status': STUDY_STATUS_STUDIED,
            'plan_id': self.math_plan.id,
            'start': 20,
            'end': 25,
        }])
        row = LearningStudySession.query.one()
        mark_sessions_verified(
            [row.id],
            child_id=self.child.id,
            changed_by_user_id=self.teacher.id,
        )
        db.session.refresh(row)
        self.assertEqual(row.record_verification, RECORD_VERIFICATION_VERIFIED)
        self._post_rows(self.child, [{
            'subject_id': self.math.id,
            'status': STUDY_STATUS_STUDIED,
            'plan_id': self.math_plan.id,
            'start': 30,
            'end': 35,
        }])
        db.session.refresh(row)
        self.assertEqual(LearningStudySession.query.count(), 1)
        self.assertEqual((row.start_page, row.end_page), (30, 35))
        self.assertEqual(row.record_verification, RECORD_VERIFICATION_OBSERVED)

    def test_teacher_and_child_share_canonical_resolver(self):
        ssen = LearningSubject.query.filter_by(key='ssen').one()
        old = create_workbook_plan(
            grade=3,
            learning_subject_id=ssen.id,
            textbook_title='이전 쎈',
            start_page=1,
            end_page=100,
            start_date=date(2026, 3, 1),
            target_completion_date=date(2026, 8, 20),
        )
        new = create_workbook_plan(
            grade=3,
            learning_subject_id=ssen.id,
            textbook_title='새 쎈',
            start_page=1,
            end_page=100,
            start_date=date(2026, 9, 1),
            target_completion_date=date(2026, 9, 5),
        )
        for day, expected in ((date(2026, 8, 25), old), (date(2026, 9, 8), new)):
            child_plan = pick_applicable_plan(self.child, ssen, day)
            teacher_plan = resolve_canonical_workbook_plan(self.child, ssen.id, day)
            self.assertEqual(child_plan.id, expected.id)
            self.assertEqual(teacher_plan.id, expected.id)
            self.assertEqual(child_plan.id, teacher_plan.id)

    def test_no_plan_day_disables_save(self):
        early = (self.today - timedelta(days=90)).isoformat()
        self._login(self.viewer)
        self._verify(self.child)
        html = self.client.get(
            self._study_url(self.child) + f'?study_date={early}',
        ).get_data(as_text=True)
        self.assertIn(CHILD_NO_PLAN_MESSAGE, html)
        self.assertIn('disabled', html)
        self.assertNotIn('/settings/workbook-plans', html)


if __name__ == '__main__':
    unittest.main()
