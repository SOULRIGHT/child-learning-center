"""Reading-specific AI runtime. 실제 OpenAI/AWS 호출 없음."""
from __future__ import annotations

import inspect
import json
import logging
import os
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    POLICY_VERSION_GENERAL_V2,
    READING_AI_STATUS_SUCCESS,
    STATUS_IN_PROGRESS,
    Book,
    ChildReading,
    ReadingAnalysisResult,
    ReadingDay,
)
from features.growth.ai.bedrock_safety import ACTION_ERROR, ACTION_INTERVENED, ACTION_NONE
from features.growth.ai.safety import SafetyDecision
from features.growth.evidence_packet import build_teacher_evidence_packet
from features.growth.metrics import metrics_bundle
from features.reading.analysis import build_public_facts, select_text_records
from features.reading.ai.openai_provider import OpenAIReadingAnalysisProvider
from features.reading.ai.prompt import READING_SYSTEM_PROMPT
from features.reading.ai.runtime import (
    CODE_CONFIRM,
    CODE_INSUFFICIENT,
    CODE_SAFETY_ERROR,
    CODE_VALIDATOR,
    current_fingerprint,
    generate_reading_analysis,
    load_reading_ai_view,
    public_result_payload,
)
from features.reading.ai.schema import OUTPUT_SCHEMA_VERSION
from features.reading.ai.validator import validate_reading_analysis


AS_OF = date(2026, 8, 22)
SENTINEL = 'SENTINEL_RAW_REVIEW_ZX9'


def _decision(safe=True, action=ACTION_NONE):
    return SafetyDecision(safe=safe, provider='test', action=action)


class FakeSafety:
    def __init__(self, input_results=None, output_result=None, fail_input=False):
        self.input_calls = []
        self.output_calls = []
        self._input_results = list(input_results or [])
        self._output_result = output_result or _decision()
        self._fail_input = fail_input

    def check_input(self, text, timeout_s=None):
        self.input_calls.append({'text': text, 'timeout_s': timeout_s})
        if self._fail_input:
            return _decision(safe=False, action=ACTION_ERROR)
        if self._input_results:
            return self._input_results.pop(0)
        return _decision()

    def check_response(self, text, timeout_s=None):
        self.output_calls.append({'text': text, 'timeout_s': timeout_s})
        return self._output_result


class FakeGenerator:
    def __init__(self, outputs=None, errors=None):
        self.calls = []
        self._outputs = list(outputs or [])
        self._errors = list(errors or [])
        self.model = 'test-model'
        self.provider = 'openai'
        self.prompt_version = 'reading_analysis_prompt_v1'
        self.output_schema_version = OUTPUT_SCHEMA_VERSION

    def generate(self, payload, timeout_s=None):
        self.calls.append({'payload': payload, 'timeout_s': timeout_s})
        if self._errors:
            raise self._errors.pop(0)
        if self._outputs:
            parsed = self._outputs.pop(0)
        else:
            parsed = _output_from_payload(payload)
        from features.reading.ai.provider import ReadingGenerationResult
        return ReadingGenerationResult(
            provider=self.provider,
            model=self.model,
            prompt_version=self.prompt_version,
            output_schema_version=self.output_schema_version,
            parsed_output=parsed,
            response_id='resp-test',
            usage={'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2},
            latency_ms=1,
        )


def _output_from_payload(payload):
    recent = ((payload.get('records') or {}).get('recent') or [{}])[0]
    return _pass_output(
        status=payload.get('sufficiency') or 'limited',
        record_id=recent.get('record_id') or 1,
        on=recent.get('date') or '2026-08-21',
        title=recent.get('book_title') or '표본책',
    )


def _pass_output(status='limited', record_id=None, on='2026-08-21', title='표본책'):
    return {
        'schema_version': OUTPUT_SCHEMA_VERSION,
        'status': status,
        'observations': [
            {
                'dimension': 'content',
                'observation': '최근 기록에서 줄거리가 조금 더 구체적으로 적혀 있습니다.',
                'evidence_refs': [
                    {'record_id': int(record_id or 1), 'date': on, 'book_title': title},
                ],
            }
        ],
        'limitations': ['표본이 적어 강한 변화로 보지 않습니다.'],
    }


class ReadingAIRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='reading_ai_teacher',
            name='원문교사',
            role='돌봄선생님',
            email='reading-ai@example.test',
            password_hash='',
        )
        self.child = Child(name='원문아동', grade=3, viewer_slug='readingaireadingaireadingai')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.teacher.id)
            sess['_fresh'] = True

    def _book(self, title='표본책'):
        book = Book(title=title, normalized_key=title, is_active=True)
        db.session.add(book)
        db.session.flush()
        return book

    def _add_text(self, on, text, book=None):
        current = (
            ChildReading.query
            .filter_by(child_id=self.child.id, status=STATUS_IN_PROGRESS)
            .first()
        )
        if current is None:
            book = book or self._book(f'책{on.isoformat()}')
            current = ChildReading(
                child_id=self.child.id,
                book_id=book.id,
                started_on=on,
                status=STATUS_IN_PROGRESS,
                policy_version=POLICY_VERSION_GENERAL_V2,
                created_by_user_id=self.teacher.id,
                actor_type=ACTOR_TEACHER,
            )
            db.session.add(current)
            db.session.flush()
        day = ReadingDay(
            child_reading_id=current.id,
            date=on,
            review_text=text,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        )
        db.session.add(day)
        db.session.commit()
        return day

    def _seed_pair(self, count_recent=8, count_previous=3, text=SENTINEL):
        days = []
        start = date(2026, 7, 20)
        total = count_recent + count_previous
        for index in range(total):
            days.append(self._add_text(start + timedelta(days=index), f'{text} {index} extra words here'))
        return days

    def test_packet_and_prompt_exclude_review_text(self):
        self._add_text(date(2026, 8, 20), SENTINEL)
        bundle = metrics_bundle(self.child.id, as_of=AS_OF)
        packet = build_teacher_evidence_packet(bundle, grade=3)
        encoded = json.dumps(packet)
        self.assertNotIn(SENTINEL, encoded)
        self.assertNotIn('review_text', encoded)
        self.assertNotIn('review_text', READING_SYSTEM_PROMPT)
        from features.growth.ai import runtime as growth_runtime
        from features.growth.ai import prompt as growth_prompt
        self.assertNotIn('review_text', inspect.getsource(growth_runtime))
        self.assertNotIn('review_text', inspect.getsource(growth_prompt))

    def test_get_does_not_call_generator(self):
        self._seed_pair()
        generator = FakeGenerator()
        with patch.dict(os.environ, {'READING_AI_ENABLED': 'true'}, clear=False):
            with patch('features.reading.ai.runtime.OpenAIReadingAnalysisProvider', return_value=generator):
                view = load_reading_ai_view(self.child.id, as_of=AS_OF)
                self._login()
                response = self.client.get(f'/children/{self.child.id}/growth')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(generator.calls, [])
        self.assertEqual(view['state'], 'none')
        html = response.get_data(as_text=True)
        self.assertNotIn(SENTINEL, html)
        self.assertIn('data-testid="growth-reading-analysis"', html)
        self.assertIn('data-testid="growth-reading-ai"', html)

    def test_get_route_does_not_call_generate(self):
        self._seed_pair()
        self._login()
        with patch('features.growth.routes.generate_reading_analysis') as mocked:
            response = self.client.get(f'/children/{self.child.id}/growth')
        self.assertEqual(response.status_code, 200)
        mocked.assert_not_called()

    def test_confirmation_required(self):
        self._seed_pair()
        generator = FakeGenerator()
        result = generate_reading_analysis(
            child_id=self.child.id,
            user_id=self.teacher.id,
            as_of=AS_OF,
            confirmed=False,
            generator=generator,
            safety=FakeSafety(),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, CODE_CONFIRM)
        self.assertEqual(generator.calls, [])

    def test_post_without_confirm_does_not_call(self):
        self._seed_pair()
        generator = FakeGenerator()
        self._login()
        with patch.dict(os.environ, {'READING_AI_ENABLED': 'true'}, clear=False):
            with patch('features.growth.routes.generate_reading_analysis', wraps=generate_reading_analysis):
                with patch('features.reading.ai.runtime.OpenAIReadingAnalysisProvider', return_value=generator):
                    response = self.client.post(
                        f'/children/{self.child.id}/growth/reading-ai',
                        data={},
                        follow_redirects=False,
                    )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(generator.calls, [])

    def test_structured_result_and_cache_reuse(self):
        self._seed_pair()
        generator = FakeGenerator()
        safety = FakeSafety()
        with patch.dict(os.environ, {'READING_AI_ENABLED': 'true'}, clear=False):
            first = generate_reading_analysis(
                child_id=self.child.id,
                user_id=self.teacher.id,
                as_of=AS_OF,
                confirmed=True,
                generator=generator,
                safety=safety,
            )
            second = generate_reading_analysis(
                child_id=self.child.id,
                user_id=self.teacher.id,
                as_of=AS_OF,
                confirmed=True,
                generator=generator,
                safety=safety,
            )
            view = load_reading_ai_view(self.child.id, as_of=AS_OF)
        self.assertTrue(first.ok)
        self.assertTrue(second.cached)
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(view['state'], 'current')
        self.assertFalse(view['stale'])
        self.assertEqual(view['analysis_id'], first.analysis_id)
        payload = json.dumps(public_result_payload(first))
        self.assertNotIn(SENTINEL, payload)
        self.assertNotIn('review_text', payload)
        row = ReadingAnalysisResult.query.get(first.analysis_id)
        blob = json.dumps({'parsed': row.parsed_output, 'facts': row.facts_snapshot})
        self.assertNotIn(SENTINEL, blob)
        self.assertNotIn('review_text', blob)
        self.assertEqual(safety.input_calls[0]['text'].split()[0], SENTINEL)

    def test_guardrail_block_and_failure(self):
        self._seed_pair(count_recent=8, count_previous=5)
        blocked = FakeSafety(input_results=[_decision(False, ACTION_INTERVENED)] + [_decision()] * 12)
        generator = FakeGenerator()
        with patch.dict(os.environ, {'READING_AI_ENABLED': 'true'}, clear=False):
            result = generate_reading_analysis(
                child_id=self.child.id,
                user_id=self.teacher.id,
                as_of=AS_OF,
                confirmed=True,
                generator=generator,
                safety=blocked,
            )
        self.assertTrue(result.ok)
        delivered_n = (
            len(generator.calls[0]['payload']['records']['recent'])
            + len(generator.calls[0]['payload']['records']['previous'])
        )
        self.assertEqual(delivered_n, 12)
        failing = FakeSafety(fail_input=True)
        generator2 = FakeGenerator()
        with patch.dict(os.environ, {'READING_AI_ENABLED': 'true'}, clear=False):
            failed = generate_reading_analysis(
                child_id=self.child.id,
                user_id=self.teacher.id,
                as_of=AS_OF,
                confirmed=True,
                generator=generator2,
                safety=failing,
            )
        self.assertFalse(failed.ok)
        self.assertEqual(failed.failure_code, CODE_SAFETY_ERROR)
        self.assertEqual(generator2.calls, [])
        self.assertIsNotNone(failed.facts)
        self.assertGreaterEqual(failed.facts['text_record_count'], 1)
        success_row = ReadingAnalysisResult.query.get(result.analysis_id)
        self.assertEqual(success_row.status, READING_AI_STATUS_SUCCESS)
        self.assertIsNotNone(success_row.parsed_output)
        failed_rows = ReadingAnalysisResult.query.filter_by(status='FAILED').all()
        self.assertTrue(failed_rows)
        self.assertTrue(all(row.id != success_row.id for row in failed_rows))
        self.assertTrue(failed.stale)
        self.assertEqual(failed.analysis_id, success_row.id)
        self.assertIsNotNone(failed.output)
        delivered = json.dumps(generator.calls[0]['payload'])
        self.assertIn(SENTINEL, delivered)

    def test_insufficient_does_not_call_llm(self):
        self._add_text(date(2026, 8, 20), f'{SENTINEL} only one')
        generator = FakeGenerator()
        with patch.dict(os.environ, {'READING_AI_ENABLED': 'true'}, clear=False):
            result = generate_reading_analysis(
                child_id=self.child.id,
                user_id=self.teacher.id,
                as_of=AS_OF,
                confirmed=True,
                generator=generator,
                safety=FakeSafety(),
            )
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, CODE_INSUFFICIENT)
        self.assertEqual(generator.calls, [])

    def test_validator_failure_hidden_no_retry(self):
        self._seed_pair()
        generator = FakeGenerator(outputs=[_pass_output(record_id=999), _pass_output(record_id=1)])
        with patch.dict(os.environ, {'READING_AI_ENABLED': 'true'}, clear=False):
            result = generate_reading_analysis(
                child_id=self.child.id,
                user_id=self.teacher.id,
                as_of=AS_OF,
                confirmed=True,
                generator=generator,
                safety=FakeSafety(),
            )
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, CODE_VALIDATOR)
        self.assertIsNone(result.output)
        self.assertEqual(len(generator.calls), 1)

    def test_fingerprint_changes_and_stale(self):
        days = self._seed_pair()
        generator = FakeGenerator()
        with patch.dict(os.environ, {'READING_AI_ENABLED': 'true'}, clear=False):
            first = generate_reading_analysis(
                child_id=self.child.id,
                user_id=self.teacher.id,
                as_of=AS_OF,
                confirmed=True,
                generator=generator,
                safety=FakeSafety(),
            )
            latest = days[-1]
            latest.review_text = f'{SENTINEL} edited extra words here'
            db.session.commit()
            view = load_reading_ai_view(self.child.id, as_of=AS_OF)
            self.assertEqual(view['state'], 'stale')
            self.assertTrue(view['stale'])
            self.assertIsNotNone(view['output'])
            generator = FakeGenerator()
            second = generate_reading_analysis(
                child_id=self.child.id,
                user_id=self.teacher.id,
                as_of=AS_OF,
                confirmed=True,
                generator=generator,
                safety=FakeSafety(),
            )
        self.assertTrue(second.ok)
        self.assertFalse(second.cached)
        self.assertEqual(ReadingAnalysisResult.query.filter_by(status=READING_AI_STATUS_SUCCESS).count(), 2)
        self.assertNotEqual(first.analysis_id, second.analysis_id)

    def test_reanalysis_failure_keeps_prior_success(self):
        days = self._seed_pair()
        with patch.dict(os.environ, {'READING_AI_ENABLED': 'true'}, clear=False):
            first = generate_reading_analysis(
                child_id=self.child.id,
                user_id=self.teacher.id,
                as_of=AS_OF,
                confirmed=True,
                generator=FakeGenerator(),
                safety=FakeSafety(),
            )
            days[-1].review_text = f'{SENTINEL} edited extra words here'
            db.session.commit()
            failed = generate_reading_analysis(
                child_id=self.child.id,
                user_id=self.teacher.id,
                as_of=AS_OF,
                confirmed=True,
                generator=FakeGenerator(errors=[RuntimeError('boom')]),
                safety=FakeSafety(),
            )
            view = load_reading_ai_view(self.child.id, as_of=AS_OF)
        self.assertTrue(first.ok)
        self.assertFalse(failed.ok)
        prior = ReadingAnalysisResult.query.get(first.analysis_id)
        self.assertEqual(prior.status, READING_AI_STATUS_SUCCESS)
        self.assertIsNotNone(prior.parsed_output)
        self.assertEqual(
            ReadingAnalysisResult.query.filter_by(status=READING_AI_STATUS_SUCCESS).count(),
            1,
        )
        self.assertTrue(failed.stale)
        self.assertEqual(failed.analysis_id, first.analysis_id)
        self.assertEqual(view['state'], 'stale')
        self.assertEqual(view['analysis_id'], first.analysis_id)

    def test_new_record_and_version_change_new_fingerprint(self):
        self._seed_pair()
        selection = select_text_records(self.child.id, as_of=AS_OF)
        facts = build_public_facts(self.child.id, as_of=AS_OF, selection=selection)
        first = current_fingerprint(selection, facts)
        self._add_text(date(2026, 8, 21), f'{SENTINEL} new extra words here')
        selection2 = select_text_records(self.child.id, as_of=AS_OF)
        facts2 = build_public_facts(self.child.id, as_of=AS_OF, selection=selection2)
        self.assertNotEqual(first, current_fingerprint(selection2, facts2))
        with patch('features.reading.ai.runtime.READING_PROMPT_VERSION', 'reading_analysis_prompt_v2'):
            self.assertNotEqual(first, current_fingerprint(selection, facts))

    def test_no_hidden_retry_or_fallback_model(self):
        source = inspect.getsource(generate_reading_analysis)
        self.assertNotIn('for attempt', source)
        self.assertNotIn('fallback', inspect.getsource(generate_reading_analysis).lower())
        provider_source = inspect.getsource(OpenAIReadingAnalysisProvider)
        self.assertIn('max_retries=0', provider_source.replace(' ', ''))

    def test_failure_keeps_deterministic_and_logs_omit_raw(self):
        self._seed_pair()
        generator = FakeGenerator(errors=[RuntimeError('boom')])
        with patch.dict(os.environ, {'READING_AI_ENABLED': 'true'}, clear=False):
            with self.assertLogs('features.reading.ai.runtime', level='INFO') as captured:
                result = generate_reading_analysis(
                    child_id=self.child.id,
                    user_id=self.teacher.id,
                    as_of=AS_OF,
                    confirmed=True,
                    generator=generator,
                    safety=FakeSafety(),
                )
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.facts)
        self.assertGreaterEqual(result.facts['recent_count'] + result.facts['previous_count'], 3)
        self.assertNotIn(SENTINEL, '\n'.join(captured.output))
        self._login()
        response = self.client.get(f'/children/{self.child.id}/growth')
        html = response.get_data(as_text=True)
        self.assertIn('data-testid="growth-reading-analysis"', html)
        self.assertIn('data-growth-learning', html)
        self.assertNotIn(SENTINEL, html)

    def test_validator_rejects_quotes_and_ability_language(self):
        refs = [{'record_id': 1, 'date': '2026-08-21', 'book_title': '표본책'}]
        parsed = _pass_output(record_id=1)
        parsed['observations'][0]['observation'] = f'아동의 사고력이 늘었고 "{SENTINEL}" 라고 썼습니다.'
        result = validate_reading_analysis(
            parsed,
            allowed_refs=refs,
            sufficiency='limited',
            raw_texts=[f'{SENTINEL} extra words here 1234567890'],
        )
        self.assertFalse(result.valid)
        self.assertTrue(set(result.codes) & {'FORBIDDEN_LANGUAGE', 'DIRECT_QUOTE', 'RAW_ECHO'})

    def test_input_guardrail_uses_input_source_and_original_text(self):
        from features.growth.ai.bedrock_safety import (
            AwsBedrockGuardrailSafetyProvider,
            SOURCE_INPUT,
            SOURCE_OUTPUT,
        )

        class Client:
            def __init__(self):
                self.calls = []

            def apply_guardrail(self, **kwargs):
                self.calls.append(kwargs)
                return {'action': ACTION_NONE}

        client = Client()
        provider = AwsBedrockGuardrailSafetyProvider(
            client=client, guardrail_id='g', guardrail_version='1',
        )
        original = f'{SENTINEL} keep me'
        provider.check_input(original)
        provider.check_response('관찰 문장입니다.')
        self.assertEqual(client.calls[0]['source'], SOURCE_INPUT)
        self.assertEqual(client.calls[0]['content'][0]['text']['text'], original)
        self.assertEqual(client.calls[1]['source'], SOURCE_OUTPUT)
