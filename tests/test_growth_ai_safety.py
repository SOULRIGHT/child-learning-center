"""Growth AI safety provider. 실제 AWS 호출 없음."""
from __future__ import annotations

import inspect
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from features.growth.ai.bedrock_safety import (
    ACTION_ERROR,
    ACTION_INTERVENED,
    ACTION_NONE,
    AwsBedrockGuardrailSafetyProvider,
    PROVIDER_NAME,
    SOURCE_OUTPUT,
)
from features.growth.ai.prompt import GROWTH_TEACHER_SYSTEM_PROMPT
from features.growth.ai.safety import (
    SafetyConfigError,
    SafetyDecision,
    visible_interpretation_text,
)


SENTINEL_NAME = 'SENTINEL_CHILD_NAME_ZX9'
SENTINEL_PACKET = 'growth_teacher_evidence_v1'
VISIBLE = '최근 독서 활동일이 이전보다 증가했습니다.'


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.calls = []
        self._response = response if response is not None else {'action': ACTION_NONE, 'usage': {}}
        self._error = error

    def apply_guardrail(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


def _provider(client=None, **kwargs):
    return AwsBedrockGuardrailSafetyProvider(
        client=client or _FakeClient(),
        guardrail_id=kwargs.get('guardrail_id', 'gr-test'),
        guardrail_version=kwargs.get('guardrail_version', '1'),
    )


class VisibleTextTests(unittest.TestCase):
    def test_joins_only_model_visible_text(self):
        parsed = {
            'schema_version': 'growth_teacher_interpretation_v1',
            'summary': {
                'text': '요약 문장.',
                'evidence_ids': ['reading.activity_days.current'],
            },
            'observations': [
                {'text': '관찰 문장.', 'evidence_ids': ['points.period.current']},
            ],
            'suggestions': [
                {
                    'text': '제안 문장.',
                    'evidence_ids': ['learning.math.plan.remaining_workload'],
                    'conditional': True,
                },
            ],
        }
        text = visible_interpretation_text(parsed)
        self.assertEqual(text, '요약 문장.\n\n관찰 문장.\n\n제안 문장.')
        self.assertNotIn('evidence_ids', text)
        self.assertNotIn('reading.activity_days.current', text)
        self.assertNotIn(SENTINEL_PACKET, text)

    def test_v2_fields_are_included(self):
        parsed = {
            'priority_insight': {'text': '핵심 변화.', 'evidence_ids': ['reading.activity_days.current']},
            'interpretation': {'text': '의미.', 'evidence_ids': ['reading.activity_days.current']},
            'observations': [{'text': '보조.', 'evidence_ids': ['points.period.current']}],
            'next_actions': [{
                'text': '다음 행동.',
                'evidence_ids': ['reading.activity_days.current'],
                'conditional': True,
            }],
            'next_check': {'text': '다음 확인.', 'evidence_ids': ['reading.activity_days.current']},
        }
        text = visible_interpretation_text(parsed)
        self.assertEqual(text, '핵심 변화.\n\n의미.\n\n다음 확인.\n\n보조.\n\n다음 행동.')


class GrowthAISafetyProviderTests(unittest.TestCase):
    def test_none_is_safe(self):
        client = _FakeClient(response={'action': ACTION_NONE, 'usage': {'contentPolicyUnits': 1}})
        result = _provider(client).check_response(VISIBLE)
        self.assertIsInstance(result, SafetyDecision)
        self.assertTrue(result.safe)
        self.assertEqual(result.provider, PROVIDER_NAME)
        self.assertEqual(result.action, ACTION_NONE)
        self.assertEqual(len(client.calls), 1)

    def test_intervened_is_unsafe(self):
        client = _FakeClient(response={
            'action': ACTION_INTERVENED,
            'actionReason': 'topic blocked',
            'assessments': [{'topicPolicy': {'topics': [{'name': 'INSULT', 'action': 'BLOCKED'}]}}],
        })
        result = _provider(client).check_response(VISIBLE)
        self.assertFalse(result.safe)
        self.assertEqual(result.action, ACTION_INTERVENED)
        self.assertEqual(result.reason, 'topic blocked')

    def test_api_error_is_fail_closed(self):
        client = _FakeClient(error=RuntimeError('upstream'))
        result = _provider(client).check_response(VISIBLE)
        self.assertFalse(result.safe)
        self.assertEqual(result.action, ACTION_ERROR)
        self.assertNotIn('upstream', result.reason or '')
        self.assertNotIn(VISIBLE, repr(result))

    def test_empty_text_is_fail_closed_without_aws_call(self):
        client = _FakeClient()
        result = _provider(client).check_response('   ')
        self.assertFalse(result.safe)
        self.assertEqual(result.action, ACTION_ERROR)
        self.assertEqual(client.calls, [])

    def test_unexpected_action_is_fail_closed(self):
        client = _FakeClient(response={'action': 'SOMETHING_ELSE'})
        result = _provider(client).check_response(VISIBLE)
        self.assertFalse(result.safe)
        self.assertEqual(result.action, ACTION_ERROR)

    def test_missing_guardrail_config(self):
        env = {
            key: value for key, value in os.environ.items()
            if key not in ('GROWTH_SAFETY_GUARDRAIL_ID', 'GROWTH_SAFETY_GUARDRAIL_VERSION')
        }
        with patch.dict(os.environ, env, clear=True):
            provider = AwsBedrockGuardrailSafetyProvider(client=_FakeClient())
            with self.assertRaises(SafetyConfigError):
                provider.check_response(VISIBLE)

    def test_missing_region_is_config_error(self):
        env = {
            key: value for key, value in os.environ.items()
            if key not in ('AWS_REGION', 'AWS_DEFAULT_REGION')
        }
        with patch.dict(os.environ, env, clear=True):
            provider = AwsBedrockGuardrailSafetyProvider(
                guardrail_id='gr-test',
                guardrail_version='1',
            )
            with self.assertRaises(SafetyConfigError):
                provider.check_response(VISIBLE)

    def test_only_visible_text_is_sent(self):
        client = _FakeClient()
        parsed = {
            'summary': {
                'text': VISIBLE,
                'evidence_ids': ['reading.activity_days.current', 'learning.math.plan.status'],
            },
            'observations': [],
            'suggestions': [],
        }
        text = visible_interpretation_text(parsed)
        _provider(client).check_response(text)
        kwargs = client.calls[0]
        self.assertEqual(kwargs['source'], SOURCE_OUTPUT)
        self.assertEqual(kwargs['guardrailIdentifier'], 'gr-test')
        self.assertEqual(kwargs['guardrailVersion'], '1')
        content_text = kwargs['content'][0]['text']['text']
        self.assertEqual(content_text, VISIBLE)
        self.assertEqual(
            set(kwargs.keys()),
            {'guardrailIdentifier', 'guardrailVersion', 'source', 'content'},
        )
        blob = json.dumps(kwargs, ensure_ascii=False)
        self.assertNotIn('evidence_ids', blob)
        self.assertNotIn('reading.activity_days.current', blob)
        self.assertNotIn(SENTINEL_PACKET, blob)
        self.assertNotIn(GROWTH_TEACHER_SYSTEM_PROMPT[:40], blob)
        self.assertNotIn(SENTINEL_NAME, blob)
        self.assertNotIn('AWS_SECRET_ACCESS_KEY', blob)
        self.assertNotIn('aws_access_key_id', blob.lower())

    def test_packet_and_prompt_are_not_sent(self):
        client = _FakeClient()
        packet = {
            'schema_version': SENTINEL_PACKET,
            'child_name': SENTINEL_NAME,
            'supporting_facts': {'reading': {}},
        }
        _provider(client).check_response(VISIBLE)
        blob = json.dumps(client.calls[0], ensure_ascii=False)
        self.assertNotIn(json.dumps(packet), blob)
        self.assertNotIn(SENTINEL_NAME, blob)
        self.assertNotIn('supporting_facts', blob)

    def test_credentials_not_in_decision_repr(self):
        fake_key = 'AKIA_TEST_SHOULD_NEVER_APPEAR'
        with patch.dict(os.environ, {'AWS_ACCESS_KEY_ID': fake_key}):
            result = _provider().check_response(VISIBLE)
        self.assertNotIn(fake_key, repr(result))
        self.assertNotIn(fake_key, str(result))

    def test_independent_from_factual_validator(self):
        import features.growth.ai.bedrock_safety as bedrock_mod
        import features.growth.ai.openai_provider as openai_mod
        import features.growth.ai.safety as safety_mod
        import features.growth.ai.validator as validator_mod
        self.assertNotIn('validator', inspect.getsource(safety_mod))
        self.assertNotIn('validate_teacher_interpretation', inspect.getsource(bedrock_mod))
        self.assertNotIn('apply_guardrail', inspect.getsource(validator_mod))
        self.assertNotIn('SafetyProvider', inspect.getsource(validator_mod))
        self.assertNotIn('apply_guardrail', inspect.getsource(openai_mod))
        self.assertNotIn('SafetyProvider', inspect.getsource(openai_mod))

    def test_production_route_does_not_invoke_aws(self):
        root = Path(__file__).resolve().parents[1]
        service_src = (root / 'features' / 'growth' / 'service.py').read_text(encoding='utf-8')
        routes_src = (root / 'features' / 'growth' / 'routes.py').read_text(encoding='utf-8')
        self.assertNotIn('bedrock', service_src.lower())
        self.assertNotIn('apply_guardrail', service_src)
        self.assertNotIn('SafetyProvider', service_src)
        self.assertNotIn('bedrock', routes_src.lower())
        self.assertNotIn('AwsBedrockGuardrailSafetyProvider', routes_src)
        self.assertNotIn('apply_guardrail', routes_src)
