"""Step 8C3: assistant tools, compact facts, help RAG, fake provider."""
from __future__ import annotations

import json
import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from tests.helpers import PROJECT_ROOT, bootstrap_test_app

app, db = bootstrap_test_app()

from app import VIEWER_ROLE_NAME, Child, DailyPoints, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    POLICY_VERSION_GENERAL_V2,
    Book,
    ChildReading,
    LearningProgressEntry,
    LearningSubject,
    ReadingDay,
)
from features.assistant.config import (
    TEACHER_ASSISTANT_ENABLED_ENV,
    TEACHER_ASSISTANT_LIVE_ENV,
    TEACHER_ASSISTANT_PROVIDER_ENV,
    assistant_provider_name,
)
from features.assistant.copy import SETUP_FORBIDDEN
from features.assistant.facts import growth_facts_for_child
from features.assistant.help import search_help
from features.assistant.openai_provider import OpenAIAssistantProvider
from features.assistant.provider import FakeAssistantProvider, get_assistant_provider
from features.assistant.tools import ALLOWED_TOOLS, execute_tool
from features.growth.ai.runtime import build_current_packet
from features.progress.service import ensure_default_subjects

AS_OF = date(2026, 9, 10)
FLAG_ON = {
    TEACHER_ASSISTANT_ENABLED_ENV: 'true',
    TEACHER_ASSISTANT_PROVIDER_ENV: 'fake',
    'CLC_TESTING': '1',
}
SENTINEL_REVIEW = 'SENTINEL_READING_REVIEW_TEXT_DO_NOT_LEAK'


class AssistantToolsCase(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='tools_teacher',
            name='도구교사',
            role='돌봄선생님',
            email='tools-teacher@example.test',
            password_hash='',
        )
        self.general = User(
            username='tools_general',
            name='도구일반',
            role='일반사용자',
            email='tools-general@example.test',
            password_hash='',
        )
        self.child = Child(name='민수', grade=2, viewer_slug='toolsminsuchildslugxx')
        self.other = Child(name='수진', grade=3, viewer_slug='toolssujinchildslugxx')
        db.session.add_all([self.teacher, self.general, self.child, self.other])
        db.session.commit()
        ensure_default_subjects()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.client = app.test_client()
        self.env = patch.dict(os.environ, FLAG_ON, clear=False)
        self.env.start()
        os.environ.pop(TEACHER_ASSISTANT_LIVE_ENV, None)

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

    def _progress(self, on, *, page=40):
        db.session.add(LearningProgressEntry(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            recorded_on=on,
            textbook_title='수학',
            page=page,
            created_by_user_id=self.teacher.id,
        ))
        db.session.commit()

    def _daily(self, on, *, korean=120):
        db.session.add(DailyPoints(
            child_id=self.child.id,
            date=on,
            korean_points=korean,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=0,
            manual_history='[]',
            total_points=korean,
            created_by=self.teacher.id,
        ))
        db.session.commit()

    def _reading(self, on):
        book = Book(title='도구책', normalized_key='도구책', is_active=True, grade_band='2-3')
        db.session.add(book)
        db.session.flush()
        reading = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            started_on=on,
            status='in_progress',
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        db.session.add(ReadingDay(
            child_reading_id=reading.id,
            date=on,
            review_text=SENTINEL_REVIEW,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        ))
        db.session.commit()


class FactsToolTests(AssistantToolsCase):
    def test_facts_include_evidence_id_and_available(self):
        self._progress(date(2026, 9, 1), page=40)
        self._daily(date(2026, 9, 2), korean=120)
        payload = growth_facts_for_child(self.child.id, as_of=AS_OF, topic='growth')
        self.assertTrue(payload['ok'])
        self.assertTrue(payload['facts'])
        for fact in payload['facts']:
            self.assertIn('evidence_id', fact)
            self.assertIn('available', fact)
            self.assertIn('label', fact)
            if not fact['available']:
                self.assertIsNone(fact.get('value'))
                self.assertNotEqual(fact.get('value'), 0)

    def test_unavailable_is_not_coerced_to_zero(self):
        payload = growth_facts_for_child(self.child.id, as_of=AS_OF, topic='points')
        self.assertTrue(payload['ok'])
        for fact in payload['facts']:
            if fact['available'] is False:
                self.assertIsNone(fact.get('value'))

    def test_reading_facts_exclude_review_text(self):
        self._reading(date(2026, 9, 3))
        payload = growth_facts_for_child(self.child.id, as_of=AS_OF, topic='reading')
        dumped = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(SENTINEL_REVIEW, dumped)
        self.assertNotIn('review_text', dumped)
        for fact in payload['facts']:
            self.assertFalse(str(fact.get('evidence_id') or '').startswith('reading.analysis.observation'))

    def test_peer_facts_come_from_existing_packet(self):
        packet = build_current_packet(self.child, as_of=AS_OF)
        expected_ids = {
            node['evidence_id']
            for node in _walk_ids(packet.get('supporting_facts') or {})
            if 'peer' in node['evidence_id']
        }
        payload = growth_facts_for_child(self.child.id, as_of=AS_OF, topic='peer')
        got = {fact['evidence_id'] for fact in payload['facts']}
        self.assertTrue(got)
        self.assertTrue(got <= expected_ids)


class HelpAndRoutingTests(AssistantToolsCase):
    def test_help_source_kind_is_not_data(self):
        self._login(self.teacher)
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '기본 학습요일이 무슨 뜻이야?'}],
            'page_context': {'endpoint': 'dashboard'},
        }).get_json()
        self.assertIn('월~금', payload['message']['content'])
        self.assertTrue(payload['sources'])
        self.assertTrue(all(item['kind'] == 'help' for item in payload['sources']))
        self.assertFalse(any(item.get('auto') for item in payload['actions']))
        self.assertFalse(any(item.get('destination') == 'study_calendar' and item.get('auto') for item in payload['actions']))

    def test_data_source_kind_is_not_help(self):
        self._progress(date(2026, 9, 1), page=40)
        self._login(self.teacher)
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '민수 수학 진도 알려줘'}],
            'page_context': {'endpoint': 'dashboard'},
        }).get_json()
        self.assertTrue(payload['sources'])
        self.assertTrue(all(item['kind'] == 'data' for item in payload['sources']))
        self.assertTrue(any(item.get('evidence_id') for item in payload['sources']))

    def test_help_search_does_not_invent_missing_docs(self):
        self.assertEqual(search_help('존재하지않는정책문서쿼리xyz'), [])


class PermissionAndSafetyTests(AssistantToolsCase):
    def test_unknown_tool_rejected(self):
        self._login(self.teacher)
        with app.test_request_context('/'):
            result = execute_tool('delete_child', {}, page_context={}, role='돌봄선생님')
        self.assertEqual(result['error'], 'unknown_tool')
        self.assertNotIn('delete_child', ALLOWED_TOOLS)

    def test_settings_forbidden_for_general_user_via_tool(self):
        self._login(self.general)
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '민수 수학 진도 알려주고 교재 계획 화면도 열어줘'}],
        }).get_json()
        self.assertIn(SETUP_FORBIDDEN, payload['message']['content'])
        self.assertFalse(any('/settings/' in (item.get('url') or '') for item in payload['actions']))

    def test_duplicate_names_are_not_auto_selected_for_facts(self):
        twin = Child(name='민수', grade=5, viewer_slug='toolsminsutwinchildxx')
        db.session.add(twin)
        db.session.commit()
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '민수 수학 진도 알려줘'}],
        }, user=self.teacher).get_json()
        self.assertIn('여러 명', payload['message']['content'])
        self.assertEqual(payload.get('sources') or [], [])
        self.assertFalse(any(action.get('auto') for action in payload['actions']))

    def test_mix_facts_and_navigate_without_auto_jump(self):
        self._progress(date(2026, 9, 1), page=40)
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '민수 수학 진도 알려주고 교재 계획 화면도 열어줘'}],
        }, user=self.teacher).get_json()
        self.assertTrue(any(item.get('kind') == 'data' for item in payload['sources']))
        dests = [item.get('destination') for item in payload['actions']]
        self.assertIn('workbook_plans', dests)
        self.assertFalse(any(item.get('auto') for item in payload['actions']))
        self.assertIn('/settings/workbook-plans', payload['actions'][0]['url'])

    def test_navigate_tool_ignores_invented_url(self):
        self._login(self.teacher)
        with app.test_request_context('/'):
            result = execute_tool(
                'navigate',
                {'destination': 'growth', 'child_id': self.child.id, 'url': 'https://evil.example/x'},
                page_context={},
                role='돌봄선생님',
            )
        self.assertTrue(result['ok'])
        self.assertEqual(result['url'], f'/children/{self.child.id}/growth')
        self.assertNotIn('evil', result['url'])


class ProviderBoundaryTests(AssistantToolsCase):
    def test_default_provider_is_fake(self):
        self.assertIsInstance(get_assistant_provider(), FakeAssistantProvider)

    def test_testing_env_does_not_auto_enable_openai(self):
        with patch.dict(os.environ, {
            TEACHER_ASSISTANT_PROVIDER_ENV: 'openai',
            'CLC_TESTING': '1',
        }, clear=False):
            os.environ.pop(TEACHER_ASSISTANT_LIVE_ENV, None)
            self.assertEqual(assistant_provider_name(), 'fake')

    def test_openai_tool_loop_uses_server_tools(self):
        calls = []

        class Responses:
            def __init__(self):
                self.queue = [
                    SimpleNamespace(
                        output=[SimpleNamespace(
                            type='function_call',
                            name='search_help',
                            arguments=json.dumps({'query': '기본 학습요일'}),
                            call_id='call_help',
                            model_dump=lambda: {
                                'type': 'function_call',
                                'name': 'search_help',
                                'arguments': json.dumps({'query': '기본 학습요일'}),
                                'call_id': 'call_help',
                            },
                        )],
                        output_text='',
                    ),
                    SimpleNamespace(output=[], output_text='기본 학습요일이 없으면 월~금을 사용합니다.'),
                ]

            def create(self, **kwargs):
                calls.append(kwargs)
                return self.queue.pop(0)

        client = SimpleNamespace(responses=Responses())
        self._login(self.teacher)
        with app.test_request_context('/'):
            completion = OpenAIAssistantProvider(client=client).complete(
                messages=[{'role': 'user', 'content': '기본 학습요일이 무슨 뜻이야?'}],
                page_context={'endpoint': 'dashboard'},
            )
        self.assertIn('월~금', completion.text)
        self.assertTrue(any(item['kind'] == 'help' for item in completion.sources))
        self.assertEqual(calls[0]['store'], False)
        self.assertIn('tools', calls[0])

    def test_provider_failure_does_not_break_page(self):
        self._login(self.teacher)
        with patch('features.assistant.runtime.get_assistant_provider') as get_provider:
            from features.assistant.provider import AssistantProviderError
            get_provider.return_value.complete.side_effect = AssistantProviderError('boom')
            failed = self._post({
                'intent': 'chat',
                'messages': [{'role': 'user', 'content': '민수 수학 진도 알려줘'}],
            })
            self.assertEqual(failed.status_code, 500)
        page = self.client.get('/dashboard')
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-testid="teacher-assistant-launcher"', page.get_data(as_text=True))


class SessionAndCharacterTests(AssistantToolsCase):
    def test_session_storage_does_not_keep_packet_dump(self):
        js = (PROJECT_ROOT / 'static' / 'js' / 'assistant.js').read_text(encoding='utf-8')
        self.assertIn('function compactSources', js)
        self.assertNotIn('supporting_facts', js)
        self.assertNotIn('review_text', js)
        self.assertNotIn('packet', js)

    def test_character_asset_is_resolved_when_present(self):
        self._login(self.teacher)
        html = self.client.get('/dashboard').get_data(as_text=True)
        self.assertIn('assistant/mark.svg', html)
        template = (PROJECT_ROOT / 'templates' / 'assistant' / '_drawer.html').read_text(encoding='utf-8')
        self.assertNotIn('<img', template)


class RuntimeFixTests(AssistantToolsCase):
    LEGACY = '학습·포인트 숫자 질문은 아직 연결되지 않았습니다'

    def test_legacy_disconnected_copy_is_not_used(self):
        source = (PROJECT_ROOT / 'features' / 'assistant' / 'copy.py').read_text(encoding='utf-8')
        self.assertNotIn(self.LEGACY, source)
        self._login(self.teacher)
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '안녕'}],
            'page_context': {'endpoint': 'dashboard'},
        }).get_json()
        text = payload['message']['content']
        self.assertNotIn(self.LEGACY, text)
        self.assertNotIn('지금은 화면 이동, 센터 설정 안내', text)
        hello = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '안녕하세요'}],
        })
        self.assertEqual(hello.status_code, 200)
        self.assertTrue(hello.get_json()['ok'])
        self.assertIn('안녕하세요', hello.get_json()['message']['content'])

    def test_page_child_alias_uses_canonical_learning_tool(self):
        self._progress(date(2026, 9, 1), page=40)
        with patch('features.assistant.policy.execute_tool', wraps=execute_tool) as wrapped:
            payload = self._post({
                'intent': 'chat',
                'messages': [{'role': 'user', 'content': '이 아이 수학 진도 알려줘'}],
                'page_context': {
                    'endpoint': 'child_detail',
                    'child_id': self.child.id,
                },
            }, user=self.teacher).get_json()
        names = [call.args[0] for call in wrapped.call_args_list]
        self.assertIn('get_learning_facts', names)
        self.assertTrue(any(item.get('kind') == 'data' for item in payload['sources']))
        self.assertNotIn(self.LEGACY, payload['message']['content'])

    def test_points_question_uses_points_tool(self):
        self._daily(date(2026, 9, 2), korean=120)
        with patch('features.assistant.policy.execute_tool', wraps=execute_tool) as wrapped:
            payload = self._post({
                'intent': 'chat',
                'messages': [{'role': 'user', 'content': '최근 포인트 알려줘'}],
                'page_context': {
                    'endpoint': 'child_detail',
                    'child_id': self.child.id,
                },
            }, user=self.teacher).get_json()
        names = [call.args[0] for call in wrapped.call_args_list]
        self.assertIn('get_points_facts', names)
        self.assertTrue(any(item.get('kind') == 'data' for item in payload['sources']))

    def test_observed_progress_help_does_not_require_child(self):
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '관측 기반 진도가 뭐야?'}],
            'page_context': {'endpoint': 'dashboard'},
        }, user=self.teacher).get_json()
        self.assertEqual(self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '관측 기반 진도가 뭐야?'}],
        }, user=self.teacher).status_code, 200)
        self.assertIn('관측 기반 진도', payload['message']['content'])
        self.assertTrue(all(item['kind'] == 'help' for item in payload['sources']))
        self.assertNotIn('어느 아동의 기록을 볼까요', payload['message']['content'])

    def test_reset_and_retry_controls_exist_after_provider_error(self):
        self._login(self.teacher)
        html = self.client.get('/dashboard').get_data(as_text=True)
        self.assertIn('data-testid="assistant-reset"', html)
        self.assertIn('data-testid="assistant-retry"', html)
        js = (PROJECT_ROOT / 'static' / 'js' / 'assistant.js').read_text(encoding='utf-8')
        self.assertIn('function resetConversation', js)
        self.assertIn('function retryLast', js)
        self.assertIn('state.generalMessages = []', js)
        self.assertIn('state.childMessages = []', js)
        self.assertIn('intent: \'bootstrap\'', js)
        with patch('features.assistant.runtime.get_assistant_provider') as get_provider:
            from features.assistant.provider import AssistantProviderError
            get_provider.return_value.complete.side_effect = AssistantProviderError('boom')
            failed = self._post({
                'intent': 'chat',
                'messages': [{'role': 'user', 'content': '안녕'}],
            })
        self.assertEqual(failed.status_code, 500)
        self.assertIn('조교 응답을 가져오지 못했습니다', failed.get_json()['message'])
        page = self.client.get('/dashboard')
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-testid="assistant-reset"', page.get_data(as_text=True))


def _walk_ids(node):
    if isinstance(node, dict):
        if isinstance(node.get('evidence_id'), str):
            yield node
        for value in node.values():
            yield from _walk_ids(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk_ids(item)


if __name__ == '__main__':
    unittest.main()
