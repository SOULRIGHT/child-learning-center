"""Step 8C2: global teacher assistant shell, navigation, guided setup."""
from __future__ import annotations

import json
import os
import re
import unittest
from datetime import date
from unittest.mock import patch

from tests.helpers import PROJECT_ROOT, bootstrap_test_app

app, db = bootstrap_test_app()

from app import VIEWER_ROLE_NAME, Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    Book,
    CenterStudyCalendar,
    LearningSubject,
    LearningWorkbookPlan,
    ManualPointPreset,
)
from features.assistant.config import TEACHER_ASSISTANT_ENABLED_ENV, is_teacher_assistant_enabled
from features.assistant.copy import PAGE_DESCRIPTIONS, SETUP_FORBIDDEN
from features.assistant.navigation import resolve_navigation, search_children
from features.assistant.provider import AssistantProviderError, FakeAssistantProvider
from features.planning.service import update_center_weekdays  # noqa: E402
from features.planning.weekdays import DEFAULT_STUDY_WEEKDAYS  # noqa: E402
from features.progress.service import ensure_default_subjects  # noqa: E402
from features.setup.status import STATUS_USING_DEFAULT, build_center_setup_status  # noqa: E402
from features.study.calendar import save_subject_study_weekdays  # noqa: E402

AS_OF = date(2026, 9, 10)
FLAG_ON = {
    TEACHER_ASSISTANT_ENABLED_ENV: 'true',
    'TEACHER_ASSISTANT_PROVIDER': 'fake',
}


def _boot_json(html):
    match = re.search(
        r'<script type="application/json" id="assistant-page-context">(.*?)</script>',
        html,
        re.S,
    )
    if not match:
        return None
    return json.loads(match.group(1))


class AssistantCase(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='asst_teacher',
            name='조교교사',
            role='돌봄선생님',
            email='asst-teacher@example.test',
            password_hash='',
        )
        self.director = User(
            username='asst_director',
            name='조교센터장',
            role='센터장',
            email='asst-director@example.test',
            password_hash='',
        )
        self.general = User(
            username='asst_general',
            name='조교일반',
            role='일반사용자',
            email='asst-general@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='asst_viewer',
            name='조교열람',
            role=VIEWER_ROLE_NAME,
            email='asst-viewer@example.test',
            password_hash='',
        )
        self.child = Child(name='민수', grade=2, viewer_slug='asstminsuchildslugxx')
        self.other = Child(name='수진', grade=3, viewer_slug='asstsujinchildslugxx')
        db.session.add_all([
            self.teacher, self.director, self.general, self.viewer, self.child, self.other,
        ])
        db.session.commit()
        self.client = app.test_client()
        self.env = patch.dict(os.environ, FLAG_ON, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        db.session.remove()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def _post(self, payload, user=None):
        if user is not None:
            self._login(user)
        return self.client.post(
            '/assistant/message',
            json=payload,
            headers={'Accept': 'application/json'},
        )


class VisibilityTests(AssistantCase):
    def test_teacher_page_has_launcher(self):
        self._login(self.teacher)
        html = self.client.get('/dashboard').get_data(as_text=True)
        self.assertIn('data-testid="teacher-assistant-launcher"', html)
        self.assertIn('data-testid="teacher-assistant-drawer"', html)
        self.assertIn('id="teacherAssistantTitle">뮤온</h2>', html)
        self.assertNotIn('id="teacherAssistantTitle">조교</h2>', html)
        self.assertIn('assistant-character-stage', html)
        self.assertIn('id="assistant-page-context"', html)
        boot = _boot_json(html)
        self.assertIsNotNone(boot)
        self.assertTrue(boot.get('storage_scope'))
        self.assertEqual(boot.get('question_limit'), 10)
        self.assertIn('/assistant/feedback', boot.get('feedback_url') or '')

    def test_general_user_sees_launcher(self):
        self._login(self.general)
        html = self.client.get('/dashboard').get_data(as_text=True)
        self.assertIn('data-testid="teacher-assistant-launcher"', html)

    def test_viewer_has_no_launcher(self):
        self._login(self.viewer)
        html = self.client.get('/viewer').get_data(as_text=True)
        self.assertNotIn('data-testid="teacher-assistant-launcher"', html)
        self.assertNotIn('id="assistant-page-context"', html)

    def test_flag_off_hides_launcher(self):
        self.env.stop()
        with patch.dict(os.environ, {TEACHER_ASSISTANT_ENABLED_ENV: '0'}, clear=False):
            self.assertFalse(is_teacher_assistant_enabled())
            self._login(self.teacher)
            dash = self.client.get('/dashboard')
            self.assertEqual(dash.status_code, 200)
            html = dash.get_data(as_text=True)
            self.assertNotIn('data-testid="teacher-assistant-launcher"', html)
            self.assertNotIn('js/assistant.js', html)
        self.env = patch.dict(os.environ, FLAG_ON, clear=False)
        self.env.start()


class ApiTests(AssistantCase):
    def test_unauthenticated_denied(self):
        response = self.client.post('/assistant/message', json={'intent': 'bootstrap'})
        self.assertIn(response.status_code, (302, 401))

    def test_viewer_denied(self):
        response = self._post({'intent': 'bootstrap'}, user=self.viewer)
        self.assertIn(response.status_code, (302, 403))

    def test_fake_provider_deterministic(self):
        provider = FakeAssistantProvider()
        first = provider.complete(
            messages=[{'role': 'user', 'content': '안녕하세요'}],
            page_context={'endpoint': 'dashboard'},
            role='돌봄선생님',
        )
        second = provider.complete(
            messages=[{'role': 'user', 'content': '안녕하세요'}],
            page_context={'endpoint': 'dashboard'},
            role='돌봄선생님',
        )
        self.assertEqual(first.text, second.text)
        self.assertIn('안녕하세요', first.text)
        self.assertNotIn('아직 연결되지 않았습니다', first.text)
        self.assertNotIn('지금은 화면 이동, 센터 설정 안내', first.text)

    def test_provider_failure_does_not_break_page(self):
        self._login(self.teacher)
        with patch(
            'features.assistant.runtime.get_assistant_provider'
        ) as get_provider:
            get_provider.return_value.complete.side_effect = AssistantProviderError('boom')
            failed = self._post({
                'intent': 'chat',
                'messages': [{'role': 'user', 'content': '안녕하세요'}],
                'page_context': {'endpoint': 'dashboard', 'role': '센터장'},
            })
            self.assertEqual(failed.status_code, 500)
            body = failed.get_json()
            self.assertFalse(body['ok'])
        page = self.client.get('/dashboard')
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-testid="teacher-assistant-launcher"', page.get_data(as_text=True))


class ContextTests(AssistantCase):
    def test_growth_context_includes_child(self):
        self._login(self.teacher)
        html = self.client.get(f'/children/{self.child.id}/growth').get_data(as_text=True)
        boot = _boot_json(html)
        self.assertIsNotNone(boot)
        page = boot['page']
        self.assertEqual(page['endpoint'], 'growth.teacher')
        self.assertEqual(page['child_id'], self.child.id)
        self.assertEqual(page['child_name'], '민수')
        self.assertEqual(page['role'], '돌봄선생님')
        self.assertIn('as_of', page)
        self.assertIn('학습·포인트·독서', PAGE_DESCRIPTIONS['growth.teacher'])

    def test_non_child_page_has_no_child_id(self):
        self._login(self.teacher)
        boot = _boot_json(self.client.get('/dashboard').get_data(as_text=True))
        self.assertNotIn('child_id', boot['page'])
        self.assertEqual(boot['page']['endpoint'], 'dashboard')

    def test_client_role_spoof_is_ignored(self):
        payload = self._post({
            'intent': 'navigate',
            'destination': 'workbook_plans',
            'page_context': {'endpoint': 'dashboard', 'role': '센터장', 'child_id': 999999},
        }, user=self.general).get_json()
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error'], 'forbidden')
        self.assertEqual(payload['message']['content'], SETUP_FORBIDDEN)
        self.assertEqual(payload['actions'], [])
        self.assertEqual(payload['message']['context_scope']['endpoint'], 'dashboard')
        self.assertNotIn('child_id', payload['message']['context_scope'])


class NavigationTests(AssistantCase):
    def test_allowlisted_destination_uses_existing_endpoint(self):
        self._login(self.teacher)
        with app.test_request_context('/'):
            from flask import url_for
            resolved = resolve_navigation('growth', {'child_id': self.child.id}, role='돌봄선생님')
            self.assertTrue(resolved['ok'])
            self.assertEqual(resolved['url'], url_for('growth.teacher', child_id=self.child.id))
            self.assertEqual(resolved['endpoint'], 'growth.teacher')
            points = resolve_navigation('points_detail', {'child_id': self.child.id}, role='돌봄선생님')
            self.assertEqual(points['url'], url_for('child_point_analysis', child_id=self.child.id))
            self.assertEqual(points['endpoint'], 'child_point_analysis')
            setup = resolve_navigation('setup_hub', {}, role='돌봄선생님')
            self.assertEqual(setup['url'], url_for('setup.hub'))

    def test_unknown_destination_rejected(self):
        payload = self._post({
            'intent': 'navigate',
            'destination': 'not_a_real_place',
        }, user=self.teacher).get_json()
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error'], 'unknown_destination')
        self.assertEqual(payload['actions'], [])

    def test_child_destination_missing_id_rejected(self):
        payload = self._post({
            'intent': 'navigate',
            'destination': 'growth',
            'page_context': {'endpoint': 'dashboard'},
        }, user=self.teacher).get_json()
        self.assertEqual(payload['error'], 'missing_child')
        self.assertEqual(payload['actions'], [])

    def test_invalid_child_rejected(self):
        payload = self._post({
            'intent': 'navigate',
            'destination': 'growth',
            'params': {'child_id': 999999},
        }, user=self.teacher).get_json()
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error'], 'invalid_child')
        self.assertEqual(payload['actions'], [])

    def test_settings_forbidden_for_general_user(self):
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '교재 계획 설정 가줘'}],
        }, user=self.general).get_json()
        self.assertEqual(payload['message']['content'], SETUP_FORBIDDEN)
        self.assertEqual(payload['actions'], [])

    def test_growth_navigation_from_child_page(self):
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '성장 리포트 열어줘'}],
            'page_context': {
                'endpoint': 'child_detail',
                'child_id': self.child.id,
                'role': '학생열람',
            },
        }, user=self.teacher).get_json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['actions'][0]['destination'], 'growth')
        self.assertTrue(payload['actions'][0]['auto'])
        self.assertEqual(payload['actions'][0]['url'], f'/children/{self.child.id}/growth')
        self.assertEqual(payload['message']['context_scope']['child_id'], self.child.id)

    def test_quick_actions_hide_setup_for_general_user(self):
        payload = self._post({'intent': 'bootstrap'}, user=self.general).get_json()
        labels = [item['label'] for item in payload['quick_actions']]
        self.assertNotIn('센터 설정 이어서 하기', labels)
        self.assertIn('현재 화면 설명', labels)


class ChildSearchTests(AssistantCase):
    def test_exact_and_partial_search(self):
        exact = search_children('민수')
        self.assertEqual([row.id for row in exact], [self.child.id])
        partial = search_children('민')
        self.assertEqual([row.id for row in partial], [self.child.id])

    def test_duplicate_names_are_not_auto_selected(self):
        twin = Child(name='민수', grade=5, viewer_slug='asstminsutwinchildxx')
        db.session.add(twin)
        db.session.commit()
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '민수 성장 리포트 열어줘'}],
        }, user=self.teacher).get_json()
        self.assertIn('여러 명', payload['message']['content'])
        self.assertFalse(any(action.get('auto') for action in payload['actions']))
        self.assertTrue(all(action.get('type') == 'reply' for action in payload['actions']))
        labels = ' '.join(action.get('label') or '' for action in payload['actions'])
        self.assertIn('2학년', labels)
        self.assertIn('5학년', labels)

    def test_no_fake_child_id(self):
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '없는아이 성장 리포트 열어줘'}],
        }, user=self.teacher).get_json()
        self.assertEqual(payload['actions'], [])
        self.assertEqual(search_children('없는아이'), [])


class OnboardingTests(AssistantCase):
    def test_using_default_recommends_weekday_check(self):
        ensure_default_subjects()
        status = build_center_setup_status(today=AS_OF)
        self.assertEqual(status['next']['key'], 'center_study_weekdays')
        self.assertEqual(status['next']['status'], STATUS_USING_DEFAULT)
        payload = self._post({
            'intent': 'continue_setup',
        }, user=self.teacher).get_json()
        nxt = payload['status']['onboarding']['next']
        self.assertEqual(nxt['key'], 'center_study_weekdays')
        self.assertEqual(nxt['status'], STATUS_USING_DEFAULT)
        self.assertEqual(payload['actions'][0]['url'], '/settings/study-calendar')
        self.assertFalse(payload['actions'][0].get('auto'))

    def test_saved_moves_to_next_step(self):
        ensure_default_subjects()
        update_center_weekdays(list(DEFAULT_STUDY_WEEKDAYS))
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '다음 뭐 해야 해?'}],
        }, user=self.teacher).get_json()
        self.assertEqual(payload['status']['onboarding']['next']['key'], 'subject_weekdays')
        self.assertEqual(payload['actions'][0]['url'], '/settings/subject-weekdays')

    def test_all_relevant_complete_is_setup_confirm_state(self):
        ensure_default_subjects()
        update_center_weekdays(list(DEFAULT_STUDY_WEEKDAYS))
        for subject in LearningSubject.query.filter_by(is_active=True):
            save_subject_study_weekdays(subject.id, [0, 1, 2, 3, 4])
        math = LearningSubject.query.filter_by(key='math').one()
        db.session.add(LearningWorkbookPlan(
            grade=2,
            learning_subject_id=math.id,
            textbook_title='수학',
            start_page=1,
            end_page=50,
            start_date=date(2026, 3, 1),
            target_completion_date=date(2026, 7, 1),
        ))
        db.session.add(ManualPointPreset(
            key='print',
            label='프린트',
            default_points=-100,
            is_active=True,
            sort_order=1,
        ))
        db.session.add(Book(title='도서', normalized_key='도서', is_active=True))
        db.session.commit()
        payload = self._post({
            'intent': 'continue_setup',
        }, user=self.teacher).get_json()
        self.assertTrue(payload['status']['onboarding']['complete'])
        self.assertIsNone(payload['status']['onboarding']['next'])
        self.assertIn('확인된 상태', payload['message']['content'])
        self.assertEqual(payload['actions'][0]['url'], '/settings/setup')

    def test_onboarding_does_not_write_progress(self):
        before = CenterStudyCalendar.query.count()
        self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '센터 설정 도와줘'}],
        }, user=self.teacher)
        self.assertEqual(CenterStudyCalendar.query.count(), before)
        self.assertIsNone(CenterStudyCalendar.query.first())

    def test_navigate_only_no_form_submit(self):
        ensure_default_subjects()
        payload = self._post({
            'intent': 'continue_setup',
        }, user=self.teacher).get_json()
        for action in payload['actions']:
            self.assertEqual(action['type'], 'navigate')
            self.assertIn('url', action)
            self.assertNotIn('form', action)
            self.assertNotIn('method', action)


class SessionUiTests(AssistantCase):
    def test_session_storage_and_child_reset_code_path(self):
        js = (PROJECT_ROOT / 'static' / 'js' / 'assistant.js').read_text(encoding='utf-8')
        self.assertIn('sessionStorage.getItem(STORAGE_KEY)', js)
        self.assertIn("clc.teacherAssistant.v2", js)
        self.assertIn('function resetConversation', js)
        self.assertIn('function isolateChild', js)
        self.assertIn('function bindScope', js)
        isolate_start = js.index('function isolateChild')
        isolate_end = js.index('function isChildScoped')
        isolate = js[isolate_start:isolate_end]
        self.assertNotIn('childMessages = []', isolate)
        self.assertIn('state.childMessages = []', js)
        self.assertIn('generalMessages', js)
        self.assertIn('storageScope', js)
        self.assertIn('if (state.storageScope !== scope)', js)
        login = (PROJECT_ROOT / 'templates' / 'login.html').read_text(encoding='utf-8')
        self.assertIn("sessionStorage.removeItem('clc.teacherAssistant.v2')", login)

    def test_mobile_and_character_hook_have_no_blank_placeholder(self):
        css = (PROJECT_ROOT / 'static' / 'css' / 'assistant.css').read_text(encoding='utf-8')
        self.assertIn('width: 100vw', css)
        self.assertIn('.assistant-character-stage:not(.is-filled)', css)
        self.assertIn('display: none', css)
        html = (PROJECT_ROOT / 'templates' / 'assistant' / '_drawer.html').read_text(encoding='utf-8')
        self.assertIn('assistant-character-stage', html)
        self.assertIn('hidden', html)
        self.assertNotIn('<img', html)
        self.assertNotIn('placeholder illustration', html.lower())
        self.assertNotIn('assistant-placeholder', html)
        self._login(self.teacher)
        page = self.client.get('/dashboard').get_data(as_text=True)
        self.assertIn('assistant-drawer', page)
        self.assertIn('data-assistant-stage="idle"', page)
        self.assertNotIn('assistant-placeholder', page)


class DisabledApiTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='asst_off_teacher',
            name='끄기교사',
            role='돌봄선생님',
            email='asst-off@example.test',
            password_hash='',
        )
        db.session.add(self.teacher)
        db.session.commit()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_flag_off_api_is_disabled(self):
        with patch.dict(os.environ, {TEACHER_ASSISTANT_ENABLED_ENV: ''}, clear=False):
            os.environ.pop(TEACHER_ASSISTANT_ENABLED_ENV, None)
            with self.client.session_transaction() as sess:
                sess['_user_id'] = str(self.teacher.id)
                sess['_fresh'] = True
            response = self.client.post('/assistant/message', json={'intent': 'bootstrap'})
            self.assertEqual(response.status_code, 404)
            dash = self.client.get('/dashboard')
            self.assertEqual(dash.status_code, 200)


if __name__ == '__main__':
    unittest.main()
