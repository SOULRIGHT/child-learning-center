"""Growth AI generator: prompt / schema / OpenAI provider. 실제 네트워크 호출 없음."""
from __future__ import annotations

import inspect
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from features.growth.ai.openai_provider import (
    DEFAULT_GROWTH_AI_MODEL,
    OpenAIGrowthInterpretationProvider,
    REASONING_EFFORT,
)
from features.growth.ai.prompt import GROWTH_TEACHER_PROMPT_VERSION, GROWTH_TEACHER_SYSTEM_PROMPT
from features.growth.ai.provider import (
    GenerationResult,
    GrowthInterpretationAPIError,
    GrowthInterpretationConfigError,
    GrowthInterpretationError,
    GrowthInterpretationParseError,
)
from features.growth.ai.schema import (
    INTERPRETATION_JSON_SCHEMA,
    OUTPUT_SCHEMA_VERSION,
    structured_output_format,
)
from features.growth.evidence_packet import SCHEMA_VERSION
from features.growth.service import build_growth_view_model
from tests.test_growth_evidence_packet import (
    SENTINEL_NAME,
    SENTINEL_REVIEW,
    SENTINEL_SLUG,
    SENTINEL_URL,
    _packet,
)


VALID_OUTPUT = {
    'schema_version': OUTPUT_SCHEMA_VERSION,
    'summary': {
        'text': '최근 독서 기록일이 이전 기간보다 늘었고, 같은 교재 계획도 진행 중입니다.',
        'evidence_ids': ['reading.activity_days.current', 'reading.activity_days.previous'],
    },
    'observations': [
        {
            'text': '최근 독서 기록일은 4일이고 이전은 2일입니다.',
            'evidence_ids': ['reading.activity_days.current', 'reading.activity_days.previous'],
        }
    ],
    'suggestions': [
        {
            'text': '같은 교재 계획이 있으면 다음 기록 때 남은 학습량도 함께 보면 좋겠습니다.',
            'evidence_ids': ['learning.math.plan.remaining_workload'],
            'conditional': True,
        }
    ],
}

MIN_PACKET = {
    'schema_version': SCHEMA_VERSION,
    'audience': 'teacher',
    'as_of': '2026-12-15',
    'grade': 3,
    'scope': {
        'window_days': 30,
        'current_window': {'start': '2026-11-16', 'end': '2026-12-15'},
        'previous_window': {'start': '2026-10-17', 'end': '2026-11-15'},
        'freshness': {'max_snapshot_age_days': 21},
    },
    'selected_insights': [],
    'supporting_facts': {'reading': {}, 'points': {}, 'learning': {}},
}


def _walk_schema_objects(node, found=None):
    found = found if found is not None else []
    if isinstance(node, dict):
        if node.get('type') == 'object':
            found.append(node)
        for value in node.values():
            _walk_schema_objects(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk_schema_objects(item, found)
    return found


class GrowthAIPromptTests(unittest.TestCase):
    def test_prompt_version(self):
        self.assertEqual(GROWTH_TEACHER_PROMPT_VERSION, 'growth_teacher_prompt_v1')

    def test_critical_policies_are_present(self):
        text = GROWTH_TEACHER_SYSTEM_PROMPT
        self.assertIn('Evidence Packet', text)
        self.assertIn('계산 엔진이 아니다', text)
        self.assertIn('만들어내지 않는다', text)
        self.assertIn('template summarizer', text)
        self.assertIn('available=false인 값은 0이 아니다', text)
        self.assertIn('estimated', text)
        self.assertIn('출석일', text)
        self.assertIn('실제 참석일', text)
        self.assertIn('전체 또래를 대표한다고 일반화하지 않는다', text)
        self.assertIn('집중력', text)
        self.assertIn('의욕', text)
        self.assertIn('성격', text)
        self.assertIn('학습 능력', text)
        self.assertIn('원인과 결과라고 단정하지 않는다', text)
        self.assertIn('조건부', text)
        self.assertIn('적극적으로 연결', text)
        self.assertIn('evidence_id', text)
        self.assertIn('selected_insights가 비어 있으면', text)
        self.assertNotIn('SENTINEL_CHILD_NAME', text)
        self.assertNotIn('{packet', text)
        self.assertNotIn('metrics_bundle', text)


class GrowthAISchemaTests(unittest.TestCase):
    def test_output_schema_version_and_json(self):
        self.assertEqual(OUTPUT_SCHEMA_VERSION, 'growth_teacher_interpretation_v1')
        json.dumps(INTERPRETATION_JSON_SCHEMA)
        fmt = structured_output_format()
        self.assertEqual(fmt['type'], 'json_schema')
        self.assertTrue(fmt['strict'])
        self.assertEqual(fmt['name'], OUTPUT_SCHEMA_VERSION)
        self.assertEqual(fmt['schema'], INTERPRETATION_JSON_SCHEMA)

    def test_required_fields_and_limits(self):
        schema = INTERPRETATION_JSON_SCHEMA
        self.assertEqual(
            set(schema['required']),
            {'schema_version', 'summary', 'observations', 'suggestions'},
        )
        self.assertEqual(schema['properties']['observations']['maxItems'], 3)
        self.assertEqual(schema['properties']['suggestions']['maxItems'], 2)
        self.assertEqual(set(schema['properties']['summary']['required']), {'text', 'evidence_ids'})
        self.assertEqual(
            set(schema['properties']['suggestions']['items']['required']),
            {'text', 'evidence_ids', 'conditional'},
        )

    def test_additional_properties_forbidden_on_objects(self):
        for node in _walk_schema_objects(INTERPRETATION_JSON_SCHEMA):
            self.assertIs(node.get('additionalProperties'), False)


class _FakeUsage:
    input_tokens = 11
    output_tokens = 22
    total_tokens = 33


class _FakeResponse:
    id = 'resp_test_1'
    status = 'completed'
    model = DEFAULT_GROWTH_AI_MODEL
    output_text = json.dumps(VALID_OUTPUT, ensure_ascii=False)
    usage = _FakeUsage()


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.calls = []
        self._response = response if response is not None else _FakeResponse()
        self._error = error
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


class GrowthAIOpenAIProviderTests(unittest.TestCase):
    def _generate(self, packet=None, client=None, **kwargs):
        provider = OpenAIGrowthInterpretationProvider(client=client or _FakeClient(), **kwargs)
        return provider.generate(packet if packet is not None else MIN_PACKET)

    def test_request_uses_responses_api_contract(self):
        client = _FakeClient()
        result = self._generate(client=client)
        self.assertEqual(len(client.calls), 1)
        kwargs = client.calls[0]
        self.assertEqual(kwargs['model'], DEFAULT_GROWTH_AI_MODEL)
        self.assertIs(kwargs['store'], False)
        self.assertEqual(kwargs['reasoning'], {'effort': REASONING_EFFORT})
        self.assertEqual(REASONING_EFFORT, 'low')
        self.assertNotIn('tools', kwargs)
        self.assertNotIn('previous_response_id', kwargs)
        self.assertNotIn('conversation', kwargs)
        self.assertNotIn('temperature', kwargs)
        self.assertNotIn('top_p', kwargs)
        self.assertEqual(kwargs['instructions'], GROWTH_TEACHER_SYSTEM_PROMPT)
        self.assertEqual(json.loads(kwargs['input']), MIN_PACKET)
        fmt = kwargs['text']['format']
        self.assertEqual(fmt['type'], 'json_schema')
        self.assertTrue(fmt['strict'])
        self.assertEqual(fmt['schema'], INTERPRETATION_JSON_SCHEMA)
        self.assertIsInstance(result, GenerationResult)
        self.assertEqual(result.provider, 'openai')
        self.assertEqual(result.model, DEFAULT_GROWTH_AI_MODEL)
        self.assertEqual(result.prompt_version, GROWTH_TEACHER_PROMPT_VERSION)
        self.assertEqual(result.output_schema_version, OUTPUT_SCHEMA_VERSION)
        self.assertEqual(result.parsed_output, VALID_OUTPUT)
        self.assertEqual(result.response_id, 'resp_test_1')
        self.assertEqual(result.usage['input_tokens'], 11)
        self.assertEqual(result.usage['output_tokens'], 22)
        self.assertEqual(result.usage['total_tokens'], 33)
        self.assertIsInstance(result.latency_ms, int)

    def test_model_override_env(self):
        client = _FakeClient()
        with patch.dict(os.environ, {'GROWTH_AI_MODEL': 'gpt-5.6-luna'}):
            provider = OpenAIGrowthInterpretationProvider(client=client)
            self.assertEqual(provider.model, 'gpt-5.6-luna')
        provider = OpenAIGrowthInterpretationProvider(client=client, model='gpt-5.6-luna')
        self.assertEqual(provider.model, 'gpt-5.6-luna')

    def test_missing_api_key(self):
        env = {key: value for key, value in os.environ.items() if key != 'OPENAI_API_KEY'}
        with patch.dict(os.environ, env, clear=True):
            provider = OpenAIGrowthInterpretationProvider()
            with self.assertRaises(GrowthInterpretationConfigError):
                provider.generate(MIN_PACKET)

    def test_api_exception(self):
        client = _FakeClient(error=RuntimeError('upstream'))
        with self.assertRaises(GrowthInterpretationAPIError) as caught:
            self._generate(client=client)
        self.assertNotIn(json.dumps(MIN_PACKET), str(caught.exception))

    def test_empty_and_malformed_output(self):
        empty = _FakeResponse()
        empty.output_text = '  '
        with self.assertRaises(GrowthInterpretationParseError):
            self._generate(client=_FakeClient(response=empty))
        incomplete = _FakeResponse()
        incomplete.status = 'incomplete'
        with self.assertRaises(GrowthInterpretationParseError):
            self._generate(client=_FakeClient(response=incomplete))
        malformed = _FakeResponse()
        malformed.output_text = 'not-json'
        with self.assertRaises(GrowthInterpretationParseError):
            self._generate(client=_FakeClient(response=malformed))

    def test_rejects_non_packet_input(self):
        provider = OpenAIGrowthInterpretationProvider(client=_FakeClient())
        with self.assertRaises(GrowthInterpretationError):
            provider.generate('not a packet')
        with self.assertRaises(GrowthInterpretationError):
            provider.generate({'schema_version': 'other', 'audience': 'teacher'})

    def test_privacy_request_contains_only_packet(self):
        packet = _packet(grade=3)
        client = _FakeClient()
        self._generate(packet=packet, client=client)
        kwargs = client.calls[0]
        blob = json.dumps(kwargs, ensure_ascii=False)
        self.assertEqual(json.loads(kwargs['input']), packet)
        self.assertNotIn(SENTINEL_NAME, blob)
        self.assertNotIn(SENTINEL_SLUG, blob)
        self.assertNotIn(SENTINEL_REVIEW, blob)
        self.assertNotIn(SENTINEL_URL, blob)
        self.assertNotIn('plan_id', kwargs['input'])
        self.assertNotIn('viewer_slug', kwargs['input'])
        self.assertNotIn('child_id', kwargs['input'])
        self.assertNotIn('/nfc/', blob)
        self.assertIn('"grade": 3', kwargs['input'])

    def test_growth_engine_and_html_path_do_not_call_provider(self):
        service_src = inspect.getsource(inspect.getmodule(build_growth_view_model))
        self.assertNotIn('openai', service_src.lower())
        self.assertNotIn('features.growth.ai', service_src)
        from features.growth import routes as growth_routes
        routes_src = inspect.getsource(growth_routes)
        self.assertNotIn('features.growth.ai', routes_src)
        self.assertNotIn('OpenAIGrowthInterpretationProvider', routes_src)
