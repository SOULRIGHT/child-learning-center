"""Teacher Growth AI runtime. 실제 OpenAI/AWS 호출 없음."""
from __future__ import annotations

import json
import os
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    GROWTH_AI_STATUS_FAILED,
    GROWTH_AI_STATUS_PENDING,
    GROWTH_AI_STATUS_SUCCESS,
    GrowthAIAttempt,
    GrowthAIFeedback,
    GrowthAIGeneration,
)
from features.growth.ai.bedrock_safety import ACTION_ERROR, ACTION_INTERVENED, ACTION_NONE
from features.growth.ai.hashing import packet_hash, runtime_signature
from features.growth.ai.provider import GenerationResult, GrowthInterpretationAPIError, GrowthInterpretationParseError
from features.growth.ai.runtime import (
    ATTEMPT_GENERATOR,
    ATTEMPT_PARSE,
    ATTEMPT_SUCCESS,
    ATTEMPT_TIMEOUT,
    ATTEMPT_VALIDATOR,
    ATTEMPT_SAFETY,
    ATTEMPT_SAFETY_ERROR,
    CODE_GENERATOR,
    CODE_PARSE,
    CODE_SAFETY_BLOCK,
    CODE_SAFETY_ERROR,
    CODE_TIMEOUT,
    CODE_VALIDATOR,
    DAILY_QUOTA,
    FEEDBACK_MAX_LEN,
    can_use_teacher_ai,
    current_runtime_parts,
    current_runtime_signature,
    generate_teacher_growth_interpretation,
    load_teacher_ai_view,
    public_result_payload,
    save_teacher_ai_feedback,
)
from features.growth.ai.safety import SafetyDecision
from features.growth.ai.schema import OUTPUT_SCHEMA_VERSION
from tests.test_growth_ai_validator import _packet  # noqa: E402


AS_OF = date(2026, 12, 15)


def _pass_output():
    return {
        'schema_version': OUTPUT_SCHEMA_VERSION,
        'priority_insight': {
            'text': '최근 독서 활동일은 5일입니다.',
            'evidence_ids': ['reading.activity_days.current'],
        },
        'interpretation': {
            'text': '최근 독서 활동일을 다른 기록과 함께 보면 우선 확인할 변화가 분명합니다.',
            'evidence_ids': ['reading.activity_days.current'],
        },
        'observations': [
            {
                'text': '최근 독서 활동일은 5일입니다.',
                'evidence_ids': ['reading.activity_days.current'],
            }
        ],
        'next_actions': [
            {
                'text': '학습 계획이 있으면 남은 학습량도 함께 보면 좋겠습니다.',
                'evidence_ids': ['learning.math.plan.remaining_workload'],
                'conditional': True,
            }
        ],
        'next_check': {
            'text': '다음 비교 시점에 같은 기록을 다시 보면 판단이 더 분명해집니다.',
            'evidence_ids': ['reading.activity_days.current'],
        },
    }


def _reject_output():
    parsed = _pass_output()
    parsed['priority_insight']['evidence_ids'] = ['learning.math.plan.status']
    return parsed


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class FakeGenerator:
    def __init__(self, outputs=None, errors=None):
        self.calls = []
        self._outputs = list(outputs or [_pass_output()])
        self._errors = list(errors or [])

    def generate(self, packet, timeout_s=None):
        self.calls.append({'packet': packet, 'timeout_s': timeout_s})
        if self._errors:
            raise self._errors.pop(0)
        parsed = self._outputs.pop(0) if self._outputs else _pass_output()
        return GenerationResult(
            provider='openai',
            model='gpt-5.6-luna',
            prompt_version='growth_teacher_prompt_v2',
            output_schema_version=OUTPUT_SCHEMA_VERSION,
            parsed_output=parsed,
            response_id='resp_test',
            usage={'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2},
            latency_ms=1,
            raw_output=json.dumps(parsed, ensure_ascii=False),
        )


class AdvancingGenerator(FakeGenerator):
    def __init__(self, clock, step=17, **kwargs):
        super().__init__(**kwargs)
        self.clock = clock
        self.step = step

    def generate(self, packet, timeout_s=None):
        self.clock.advance(self.step)
        return super().generate(packet, timeout_s=timeout_s)


class FakeSafety:
    def __init__(self, decisions=None):
        self.calls = []
        self._decisions = list(decisions or [])

    def check_response(self, text, timeout_s=None):
        self.calls.append({'text': text, 'timeout_s': timeout_s})
        if self._decisions:
            return self._decisions.pop(0)
        return SafetyDecision(safe=True, provider='aws_bedrock_guardrail', action=ACTION_NONE)


class GrowthAIRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='ai_runtime_teacher',
            name='AI교사',
            role='돌봄선생님',
            email='ai-runtime@example.test',
            password_hash='',
        )
        self.other = User(
            username='ai_runtime_other',
            name='다른교사',
            role='돌봄선생님',
            email='ai-other@example.test',
            password_hash='',
        )
        self.child = Child(name='런타임아동', grade=3, viewer_slug='airuntimechildslugxx')
        db.session.add_all([self.teacher, self.other, self.child])
        db.session.commit()
        self.packet = _packet()
        self.env = {
            'GROWTH_AI_ENABLED': 'true',
            'GROWTH_SAFETY_GUARDRAIL_ID': 'gr-test',
            'GROWTH_SAFETY_GUARDRAIL_VERSION': '1',
            'GROWTH_AI_MODEL': 'gpt-5.6-luna',
        }
        self.patches = [
            patch.dict(os.environ, self.env, clear=False),
            patch('features.growth.ai.runtime.build_current_packet', side_effect=self._packet_for_call),
        ]
        self._packet_queue = None
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        db.session.remove()
        self.ctx.pop()

    def _packet_for_call(self, *args, **kwargs):
        if self._packet_queue:
            return self._packet_queue.pop(0)
        return self.packet

    def _generate(self, **kwargs):
        return generate_teacher_growth_interpretation(
            child=self.child,
            user_id=kwargs.get('user_id', self.teacher.id),
            as_of=AS_OF,
            generator=kwargs.get('generator') or FakeGenerator(),
            safety=kwargs.get('safety') or FakeSafety(),
            clock=kwargs.get('clock') or FakeClock(),
        )

    def test_disabled_flag_blocks_generation(self):
        with patch.dict(os.environ, {'GROWTH_AI_ENABLED': ''}, clear=False):
            generator = FakeGenerator()
            result = self._generate(generator=generator)
        self.assertFalse(result.ok)
        self.assertEqual(result.state, 'disabled')
        self.assertEqual(generator.calls, [])
        self.assertEqual(GrowthAIGeneration.query.count(), 0)

    def test_volunteer_general_user_can_use_teacher_ai(self):
        self.assertTrue(can_use_teacher_ai('일반사용자'))
        self.assertTrue(can_use_teacher_ai('돌봄선생님'))
        self.assertTrue(can_use_teacher_ai('센터장'))
        self.assertTrue(can_use_teacher_ai('개발자'))
        self.assertFalse(can_use_teacher_ai('학생열람'))
        self.assertFalse(can_use_teacher_ai('학생'))
        self.assertFalse(can_use_teacher_ai(None))

    def test_cache_reuses_success_without_providers(self):
        first = self._generate()
        self.assertTrue(first.ok)
        generator = FakeGenerator()
        safety = FakeSafety()
        second = self._generate(generator=generator, safety=safety)
        self.assertTrue(second.ok)
        self.assertTrue(second.cached)
        self.assertEqual(generator.calls, [])
        self.assertEqual(safety.calls, [])
        self.assertEqual(GrowthAIGeneration.query.count(), 1)

    def test_packet_change_is_stale_on_load(self):
        self._generate()
        changed = _packet(days=9)
        view = load_teacher_ai_view(self.child, as_of=AS_OF, bundle=None, user_id=self.teacher.id)
        self.assertEqual(view['state'], 'success')
        with patch('features.growth.ai.runtime.build_current_packet', return_value=changed):
            view = load_teacher_ai_view(self.child, as_of=AS_OF, user_id=self.teacher.id)
        self.assertEqual(view['state'], 'stale')
        self.assertNotIn('interpretation', view)

    def test_runtime_signature_change_is_cache_miss(self):
        self._generate()
        generator = FakeGenerator()
        with patch('features.growth.ai.runtime.current_runtime_parts') as parts:
            base = current_runtime_parts()
            base['prompt_version'] = 'growth_teacher_prompt_v9'
            parts.return_value = base
            result = self._generate(generator=generator)
        self.assertTrue(result.ok)
        self.assertFalse(result.cached)
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(GrowthAIGeneration.query.filter_by(status=GROWTH_AI_STATUS_SUCCESS).count(), 2)

    def test_quota_thirty_then_reject(self):
        signature = runtime_signature(current_runtime_parts())
        for i in range(DAILY_QUOTA):
            db.session.add(GrowthAIGeneration(
                child_id=self.child.id,
                requested_by_user_id=self.teacher.id,
                packet_hash=('a' * 63) + str(i % 10),
                runtime_signature=signature,
                as_of=AS_OF,
                status=GROWTH_AI_STATUS_SUCCESS,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ))
        db.session.commit()
        generator = FakeGenerator()
        result = self._generate(generator=generator)
        self.assertEqual(result.state, 'quota')
        self.assertEqual(generator.calls, [])

    def test_other_user_quota_is_independent(self):
        signature = runtime_signature(current_runtime_parts())
        for i in range(DAILY_QUOTA):
            db.session.add(GrowthAIGeneration(
                child_id=self.child.id,
                requested_by_user_id=self.teacher.id,
                packet_hash=('b' * 63) + str(i % 10),
                runtime_signature=signature,
                as_of=AS_OF,
                status=GROWTH_AI_STATUS_SUCCESS,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ))
        db.session.commit()
        result = self._generate(user_id=self.other.id)
        self.assertTrue(result.ok)

    def test_cached_view_does_not_consume_quota(self):
        self._generate()
        before = GrowthAIGeneration.query.count()
        self._generate()
        self.assertEqual(GrowthAIGeneration.query.count(), before)

    def test_provider_error_does_not_retry_or_add_quota_row(self):
        generator = FakeGenerator(
            errors=[GrowthInterpretationAPIError('openai api request failed')],
            outputs=[_pass_output()],
        )
        result = self._generate(generator=generator)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, CODE_GENERATOR)
        self.assertEqual(len(generator.calls), 1)
        rows = GrowthAIGeneration.query.all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].attempt_count, 1)
        self.assertEqual(GrowthAIAttempt.query.count(), 1)

    def test_kst_day_rollover(self):
        yesterday = datetime.utcnow() - timedelta(hours=36)
        signature = runtime_signature(current_runtime_parts())
        for i in range(DAILY_QUOTA):
            db.session.add(GrowthAIGeneration(
                child_id=self.child.id,
                requested_by_user_id=self.teacher.id,
                packet_hash=('c' * 63) + str(i % 10),
                runtime_signature=signature,
                as_of=AS_OF,
                status=GROWTH_AI_STATUS_SUCCESS,
                created_at=yesterday,
                completed_at=yesterday,
            ))
        db.session.commit()
        result = self._generate()
        self.assertTrue(result.ok)

    def test_success_pipeline_stores_parsed_output_only(self):
        result = self._generate()
        self.assertTrue(result.ok)
        row = GrowthAIGeneration.query.one()
        self.assertEqual(row.status, GROWTH_AI_STATUS_SUCCESS)
        self.assertEqual(row.parsed_output['priority_insight']['text'], '최근 독서 활동일은 5일입니다.')
        self.assertIsNone(getattr(row, 'packet', None))
        self.assertNotIn('evidence_packet', row.__dict__)
        blob = str(row.parsed_output)
        self.assertNotIn('GROWTH_TEACHER_SYSTEM_PROMPT', blob)
        self.assertNotIn('AWS_SECRET', str(row.__dict__))

    def test_validator_reject_does_not_store_output(self):
        clock = FakeClock()
        generator = AdvancingGenerator(clock, outputs=[_reject_output()])
        result = self._generate(generator=generator, clock=clock)
        self.assertFalse(result.ok)
        row = GrowthAIGeneration.query.one()
        self.assertIsNone(row.parsed_output)
        self.assertEqual(row.failure_code, CODE_VALIDATOR)

    def test_guardrail_intervened_does_not_display_output(self):
        clock = FakeClock()
        safety = FakeSafety(decisions=[
            SafetyDecision(safe=False, provider='aws_bedrock_guardrail', action=ACTION_INTERVENED),
        ])
        result = self._generate(
            generator=AdvancingGenerator(clock),
            safety=safety,
            clock=clock,
        )
        self.assertFalse(result.ok)
        self.assertIsNone(result.interpretation)
        row = GrowthAIGeneration.query.one()
        self.assertIsNone(row.parsed_output)
        self.assertEqual(row.failure_code, CODE_SAFETY_BLOCK)

    def test_safety_error_is_fail_closed(self):
        safety = FakeSafety(decisions=[
            SafetyDecision(safe=False, provider='aws_bedrock_guardrail', action=ACTION_ERROR),
            SafetyDecision(safe=False, provider='aws_bedrock_guardrail', action=ACTION_ERROR),
        ])
        result = self._generate(safety=safety)
        self.assertFalse(result.ok)
        self.assertEqual(GrowthAIGeneration.query.one().failure_code, CODE_SAFETY_ERROR)
        self.assertEqual(len(safety.calls), 1)

    def test_deadline_timeout(self):
        clock = FakeClock()

        class SlowGenerator(FakeGenerator):
            def generate(self, packet, timeout_s=None):
                clock.advance(20)
                return super().generate(packet, timeout_s=timeout_s)

        result = self._generate(generator=SlowGenerator(), clock=clock)
        self.assertEqual(result.state, 'timeout')
        self.assertIsNone(GrowthAIGeneration.query.one().parsed_output)

    def test_provider_error_does_not_ignore_deadline_or_retry(self):
        clock = FakeClock()
        generator = AdvancingGenerator(
            clock,
            errors=[GrowthInterpretationAPIError('openai api request failed')],
            outputs=[_pass_output()],
        )
        result = self._generate(generator=generator, clock=clock)
        self.assertFalse(result.ok)
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(GrowthAIGeneration.query.one().attempt_count, 1)

    def test_stale_during_generation_not_saved_as_success(self):
        changed = _packet(days=9)
        self._packet_queue = [self.packet, changed]
        result = self._generate()
        self.assertEqual(result.state, 'stale')
        self.assertEqual(GrowthAIGeneration.query.one().status != GROWTH_AI_STATUS_SUCCESS, True)
        self.assertIsNone(result.interpretation)

    def test_pending_duplicate_rejected(self):
        digest = packet_hash(self.packet)
        signature = runtime_signature(current_runtime_parts())
        db.session.add(GrowthAIGeneration(
            child_id=self.child.id,
            requested_by_user_id=self.teacher.id,
            packet_hash=digest,
            runtime_signature=signature,
            as_of=AS_OF,
            status=GROWTH_AI_STATUS_PENDING,
            created_at=datetime.utcnow(),
        ))
        db.session.commit()
        generator = FakeGenerator()
        result = self._generate(generator=generator)
        self.assertEqual(result.state, 'in_progress')
        self.assertEqual(generator.calls, [])

    def test_stale_pending_allows_new_generation(self):
        digest = packet_hash(self.packet)
        signature = runtime_signature(current_runtime_parts())
        db.session.add(GrowthAIGeneration(
            child_id=self.child.id,
            requested_by_user_id=self.teacher.id,
            packet_hash=digest,
            runtime_signature=signature,
            as_of=AS_OF,
            status=GROWTH_AI_STATUS_PENDING,
            created_at=datetime.utcnow() - timedelta(seconds=61),
        ))
        db.session.commit()
        generator = FakeGenerator()
        result = self._generate(generator=generator)
        self.assertTrue(result.ok)
        self.assertEqual(len(generator.calls), 1)
        statuses = {row.status for row in GrowthAIGeneration.query.all()}
        self.assertIn(GROWTH_AI_STATUS_FAILED, statuses)
        self.assertIn(GROWTH_AI_STATUS_SUCCESS, statuses)

    def test_feedback_positive_and_negative(self):
        result = self._generate()
        ok, _ = save_teacher_ai_feedback(
            generation_id=result.generation_id, user_id=self.teacher.id, helpful=True,
        )
        self.assertTrue(ok)
        ok, _ = save_teacher_ai_feedback(
            generation_id=result.generation_id,
            user_id=self.teacher.id,
            helpful=False,
            comment='사실과 다른 표현이 있어요.',
        )
        self.assertTrue(ok)
        row = GrowthAIFeedback.query.one()
        self.assertFalse(row.helpful)
        self.assertEqual(row.comment, '사실과 다른 표현이 있어요.')

    def test_feedback_max_length(self):
        result = self._generate()
        ok, detail = save_teacher_ai_feedback(
            generation_id=result.generation_id,
            user_id=self.teacher.id,
            helpful=False,
            comment='가' * (FEEDBACK_MAX_LEN + 1),
        )
        self.assertFalse(ok)
        self.assertEqual(detail, 'too_long')
        self.assertEqual(GrowthAIFeedback.query.count(), 0)

    def test_feedback_not_sent_to_providers(self):
        result = self._generate()
        generator = FakeGenerator()
        safety = FakeSafety()
        save_teacher_ai_feedback(
            generation_id=result.generation_id,
            user_id=self.teacher.id,
            helpful=False,
            comment='비밀 의견',
        )
        self.assertEqual(generator.calls, [])
        self.assertEqual(safety.calls, [])
        self.assertIsNone(GrowthAIGeneration.query.one().parsed_output.get('feedback'))

    def test_success_attempt_is_logged(self):
        result = self._generate()
        self.assertTrue(result.started)
        attempts = GrowthAIAttempt.query.order_by(GrowthAIAttempt.attempt_number).all()
        self.assertEqual(len(attempts), 1)
        row = attempts[0]
        self.assertEqual(row.status, ATTEMPT_SUCCESS)
        self.assertEqual(row.attempt_number, 1)
        self.assertEqual(row.generated_output['priority_insight']['text'], '최근 독서 활동일은 5일입니다.')
        self.assertEqual(row.input_tokens, 1)
        self.assertEqual(row.total_tokens, 2)
        self.assertIsNotNone(row.generator_latency_ms)
        self.assertIsNotNone(row.validator_latency_ms)
        self.assertIsNotNone(row.total_latency_ms)
        blob = json.dumps(row.generated_output, ensure_ascii=False) + (row.generated_text or '')
        self.assertNotIn('GROWTH_TEACHER_SYSTEM_PROMPT', blob)
        self.assertNotIn('review_text', blob)
        self.assertNotIn('OPENAI_API_KEY', blob)
        self.assertIsNone(getattr(row, 'packet', None))

    def test_attempt_persist_failure_does_not_leave_generation_pending(self):
        with patch(
            'features.growth.ai.runtime.GrowthAIAttempt',
            side_effect=RuntimeError('table growth_ai_attempt has no column named safety_categories'),
        ):
            result = self._generate()
        self.assertTrue(result.ok)
        self.assertEqual(result.state, 'success')
        row = GrowthAIGeneration.query.one()
        self.assertEqual(row.status, GROWTH_AI_STATUS_SUCCESS)
        self.assertEqual(GrowthAIAttempt.query.count(), 0)

    def test_validator_reject_stores_generated_output_on_attempt_only(self):
        clock = FakeClock()
        generator = AdvancingGenerator(clock, outputs=[_reject_output()])
        result = self._generate(generator=generator, clock=clock)
        self.assertFalse(result.ok)
        generation = GrowthAIGeneration.query.one()
        self.assertIsNone(generation.parsed_output)
        attempt = GrowthAIAttempt.query.one()
        self.assertEqual(attempt.status, ATTEMPT_VALIDATOR)
        self.assertEqual(attempt.stage, 'validator')
        self.assertIsNotNone(attempt.generated_output)
        self.assertIn('learning.math.plan.status', attempt.generated_output['priority_insight']['evidence_ids'])
        self.assertIn('UNKNOWN_EVIDENCE_ID', attempt.validator_codes)
        self.assertEqual(attempt.validator_issues[0]['evidence_id'], 'learning.math.plan.status')

    def test_safety_reject_stores_generated_output_on_attempt(self):
        clock = FakeClock()
        safety = FakeSafety(decisions=[
            SafetyDecision(
                safe=False,
                provider='aws_bedrock_guardrail',
                action=ACTION_INTERVENED,
                reason='Child Trait Inference',
                assessments=('Child Trait Inference',),
            ),
        ])
        result = self._generate(
            generator=AdvancingGenerator(clock),
            safety=safety,
            clock=clock,
        )
        self.assertFalse(result.ok)
        self.assertIsNone(GrowthAIGeneration.query.one().parsed_output)
        attempt = GrowthAIAttempt.query.one()
        self.assertEqual(attempt.status, ATTEMPT_SAFETY)
        self.assertIsNotNone(attempt.generated_output)
        self.assertEqual(attempt.safety_action, ACTION_INTERVENED)
        self.assertIn('Child Trait Inference', attempt.safety_categories)

    def test_timeout_attempt_output_may_be_null(self):
        clock = FakeClock()

        class TimeoutGenerator(FakeGenerator):
            def generate(self, packet, timeout_s=None):
                clock.advance(17)
                raise GrowthInterpretationAPIError('openai api request timeout')

        result = self._generate(generator=TimeoutGenerator(), clock=clock)
        self.assertEqual(result.state, 'timeout')
        attempt = GrowthAIAttempt.query.one()
        self.assertEqual(attempt.status, ATTEMPT_TIMEOUT)
        self.assertIsNone(attempt.generated_output)

    def test_provider_error_writes_one_attempt_and_one_quota(self):
        generator = FakeGenerator(
            errors=[GrowthInterpretationAPIError('openai api request failed')],
            outputs=[_pass_output()],
        )
        result = self._generate(generator=generator)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, CODE_GENERATOR)
        self.assertEqual(GrowthAIGeneration.query.count(), 1)
        attempts = GrowthAIAttempt.query.order_by(GrowthAIAttempt.attempt_number).all()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].attempt_number, 1)
        self.assertEqual(attempts[0].status, ATTEMPT_GENERATOR)

    def test_timeout_does_not_retry(self):
        clock = FakeClock()

        class SlowGenerator(FakeGenerator):
            def generate(self, packet, timeout_s=None):
                clock.advance(20)
                return super().generate(packet, timeout_s=timeout_s)

        generator = SlowGenerator(outputs=[_pass_output(), _pass_output()])
        result = self._generate(generator=generator, clock=clock)
        self.assertEqual(result.state, 'timeout')
        self.assertEqual(
            result.message,
            'AI 해석 준비 시간이 조금 길어졌어요.\n다시 시도해주세요.',
        )
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(GrowthAIGeneration.query.one().attempt_count, 1)
        self.assertEqual(GrowthAIAttempt.query.count(), 1)

    def test_safety_error_does_not_retry_luna(self):
        generator = FakeGenerator(outputs=[_pass_output(), _pass_output()])
        safety = FakeSafety(decisions=[
            SafetyDecision(safe=False, provider='aws_bedrock_guardrail', action=ACTION_ERROR),
        ])
        result = self._generate(generator=generator, safety=safety)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, CODE_SAFETY_ERROR)
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(len(safety.calls), 1)
        self.assertEqual(GrowthAIAttempt.query.count(), 1)

    def test_parse_failure_does_not_retry(self):
        generator = FakeGenerator(errors=[GrowthInterpretationParseError('invalid json')])
        result = self._generate(generator=generator)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, CODE_PARSE)
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(GrowthAIGeneration.query.one().attempt_count, 1)
        self.assertEqual(GrowthAIAttempt.query.one().status, ATTEMPT_PARSE)

    def test_validator_reject_does_not_retry(self):
        generator = FakeGenerator(outputs=[_reject_output(), _pass_output()])
        result = self._generate(generator=generator)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, CODE_VALIDATOR)
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(GrowthAIAttempt.query.count(), 1)
        self.assertEqual(result.message, '이번에는 AI 성장 해석을 준비하지 못했어요.\n잠시 후 다시 시도해주세요.')

    def test_safety_reject_does_not_retry_luna(self):
        generator = FakeGenerator(outputs=[_pass_output(), _pass_output()])
        safety = FakeSafety(decisions=[
            SafetyDecision(safe=False, provider='aws_bedrock_guardrail', action=ACTION_INTERVENED),
        ])
        result = self._generate(generator=generator, safety=safety)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, CODE_SAFETY_BLOCK)
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(len(safety.calls), 1)

    def test_user_retry_starts_new_generation(self):
        first = FakeGenerator(outputs=[_reject_output()])
        failed = self._generate(generator=first)
        self.assertFalse(failed.ok)
        second = FakeGenerator()
        ok = self._generate(generator=second)
        self.assertTrue(ok.ok)
        self.assertEqual(len(first.calls), 1)
        self.assertEqual(len(second.calls), 1)
        rows = GrowthAIGeneration.query.order_by(GrowthAIGeneration.id).all()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].status, GROWTH_AI_STATUS_FAILED)
        self.assertEqual(rows[1].status, GROWTH_AI_STATUS_SUCCESS)
        self.assertEqual(GrowthAIAttempt.query.count(), 2)
        self.assertTrue(all(row.attempt_count == 1 for row in rows))

    def test_failed_user_request_consumes_quota(self):
        self._generate(generator=FakeGenerator(errors=[GrowthInterpretationAPIError('openai api request failed')]))
        signature = runtime_signature(current_runtime_parts())
        for i in range(DAILY_QUOTA - 1):
            db.session.add(GrowthAIGeneration(
                child_id=self.child.id,
                requested_by_user_id=self.teacher.id,
                packet_hash=('d' * 63) + str(i % 10),
                runtime_signature=signature,
                as_of=AS_OF,
                status=GROWTH_AI_STATUS_SUCCESS,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ))
        db.session.commit()
        result = self._generate(generator=FakeGenerator())
        self.assertEqual(result.state, 'quota')

    def test_quota_preflight_does_not_start_generation(self):
        signature = runtime_signature(current_runtime_parts())
        for i in range(DAILY_QUOTA):
            db.session.add(GrowthAIGeneration(
                child_id=self.child.id,
                requested_by_user_id=self.teacher.id,
                packet_hash=('a' * 63) + str(i % 10),
                runtime_signature=signature,
                as_of=AS_OF,
                status=GROWTH_AI_STATUS_SUCCESS,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            ))
        db.session.commit()
        result = self._generate(generator=FakeGenerator())
        self.assertEqual(result.state, 'quota')
        self.assertFalse(result.started)
        self.assertEqual(GrowthAIAttempt.query.count(), 0)

    def test_v1_runtime_signature_is_not_reused(self):
        old = runtime_signature({
            'generator_provider': 'openai',
            'model': 'gpt-5.6-luna',
            'prompt_version': 'growth_teacher_prompt_v2',
            'output_schema_version': 'growth_teacher_interpretation_v1',
            'factual_validator_version': 'growth_teacher_factual_validator_v1',
            'safety_provider': 'aws_bedrock_guardrail',
            'safety_guardrail_id': 'gr-alpha',
            'safety_guardrail_version': '1',
        })
        with patch.dict(os.environ, {
            'GROWTH_SAFETY_GUARDRAIL_ID': 'gr-alpha',
            'GROWTH_SAFETY_GUARDRAIL_VERSION': '1',
            'GROWTH_AI_MODEL': 'gpt-5.6-luna',
        }, clear=False):
            current = current_runtime_signature()
        self.assertNotEqual(old, current)

    def test_public_payload_does_not_expose_attempts(self):
        result = self._generate()
        payload = public_result_payload(result)
        blob = json.dumps(payload)
        self.assertNotIn('attempt', blob.lower())
        self.assertNotIn('generated_output', blob)
        self.assertTrue(payload['started'])
        self.assertNotIn('failure_code', payload)
