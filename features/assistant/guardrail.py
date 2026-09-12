"""Teacher Assistant AWS Bedrock Guardrail. Growth runtime과 합치지 않는다.

Growth SafetyDecision 철학만 재사용한다. Evidence Packet / 생성 프롬프트는 보내지 않는다.
테스트(CLC_TESTING=1)와 명시적 local disable만 Noop을 허용한다.
Guardrail을 써야 하는 런타임에서 ID/version/region이 빠지면 silent 통과하지 않는다.
"""
from __future__ import annotations

import os
import time

from features.growth.ai.safety import SafetyConfigError, SafetyDecision

PROVIDER_NAME = 'aws_bedrock_guardrail'
NOOP_PROVIDER = 'noop'
FAKE_PROVIDER = 'fake'
CONFIG_PROVIDER = 'config'
GUARDRAIL_ID_ENV = 'TEACHER_ASSISTANT_GUARDRAIL_ID'
GUARDRAIL_VERSION_ENV = 'TEACHER_ASSISTANT_GUARDRAIL_VERSION'
GUARDRAIL_DISABLED_ENV = 'TEACHER_ASSISTANT_GUARDRAIL_DISABLED'
ACTION_NONE = 'NONE'
ACTION_INTERVENED = 'GUARDRAIL_INTERVENED'
ACTION_ERROR = 'ERROR'
SOURCE_OUTPUT = 'OUTPUT'
SOURCE_INPUT = 'INPUT'
# AWS Bedrock Guardrail built-in content filter types.
# Docs: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-content-filters.html
# This is not a product-coverage claim. Categories not listed here are not
# automatically protected by the built-in filter.
AWS_BUILTIN_CONTENT_FILTER_TYPES = frozenset({
    'HATE',
    'INSULTS',
    'SEXUAL',
    'VIOLENCE',
    'MISCONDUCT',
    'PROMPT_ATTACK',
})
# Custom topicPolicy names the product would configure. Not created/updated live.
# Built-in content filters do not include these as first-class categories.
ASSISTANT_REQUIRED_DENIED_TOPICS = (
    {
        'name': 'POLITICAL_PREFERENCE',
        'reason': (
            'Politics, candidate evaluation, endorsement, or choosing sides '
            'is outside MUON scope. There is no built-in politics category.'
        ),
    },
    {
        'name': 'SELF_HARM',
        'reason': (
            'Product requires full-scope refusal. Do not assume Violence '
            'will catch self-harm discussion.'
        ),
    },
    {
        'name': 'DRUGS',
        'reason': (
            'Product requires full-scope refusal. Do not assume Misconduct '
            'will catch substance advice.'
        ),
    },
    {
        'name': 'GAMBLING',
        'reason': (
            'Product requires full-scope refusal. Do not assume Misconduct '
            'will catch gambling advice.'
        ),
    },
)


class AssistantGuardrail:
    def check_input(self, text, timeout_s=None) -> SafetyDecision:
        raise NotImplementedError

    def check_response(self, text, timeout_s=None) -> SafetyDecision:
        raise NotImplementedError


class NoopAssistantGuardrail(AssistantGuardrail):
    """CLC_TESTING=1 또는 명시적 local/dev disable. AWS 호출 없음. 통과만 한다."""

    def check_input(self, text, timeout_s=None) -> SafetyDecision:
        return SafetyDecision(safe=True, provider=NOOP_PROVIDER, action=ACTION_NONE)

    def check_response(self, text, timeout_s=None) -> SafetyDecision:
        return SafetyDecision(safe=True, provider=NOOP_PROVIDER, action=ACTION_NONE)


class FailClosedAssistantGuardrail(AssistantGuardrail):
    """Guardrail required 인데 ID/version/region이 불완전. provider/tool 전에 ERROR."""

    def check_input(self, text, timeout_s=None) -> SafetyDecision:
        return self._error()

    def check_response(self, text, timeout_s=None) -> SafetyDecision:
        return self._error()

    def _error(self) -> SafetyDecision:
        return SafetyDecision(
            safe=False,
            provider=CONFIG_PROVIDER,
            action=ACTION_ERROR,
            reason='guardrail not configured',
        )


class FakeAssistantGuardrail(AssistantGuardrail):
    """테스트용. live AWS를 부르지 않는다."""

    def __init__(self, *, input_decision=None, output_decision=None, input_error=None, output_error=None):
        self.input_decision = input_decision
        self.output_decision = output_decision
        self.input_error = input_error
        self.output_error = output_error
        self.input_calls = []
        self.output_calls = []

    def check_input(self, text, timeout_s=None) -> SafetyDecision:
        self.input_calls.append({'text': text, 'timeout_s': timeout_s})
        if self.input_error is not None:
            raise self.input_error
        return self.input_decision or SafetyDecision(
            safe=True, provider=FAKE_PROVIDER, action=ACTION_NONE,
        )

    def check_response(self, text, timeout_s=None) -> SafetyDecision:
        self.output_calls.append({'text': text, 'timeout_s': timeout_s})
        if self.output_error is not None:
            raise self.output_error
        return self.output_decision or SafetyDecision(
            safe=True, provider=FAKE_PROVIDER, action=ACTION_NONE,
        )


class AwsBedrockAssistantGuardrail(AssistantGuardrail):
    def __init__(
        self,
        *,
        client=None,
        guardrail_id=None,
        guardrail_version=None,
        region=None,
    ):
        self._client = client
        self._guardrail_id = guardrail_id
        self._guardrail_version = guardrail_version
        self._region = region

    def check_input(self, text, timeout_s=None) -> SafetyDecision:
        return self._check(text, source=SOURCE_INPUT, timeout_s=timeout_s, empty_reason='empty input is not safety-checked')

    def check_response(self, text, timeout_s=None) -> SafetyDecision:
        return self._check(text, source=SOURCE_OUTPUT, timeout_s=timeout_s, empty_reason='empty output is not safety-checked')

    def _check(self, text, *, source, timeout_s, empty_reason) -> SafetyDecision:
        payload = text.strip() if isinstance(text, str) else ''
        if not payload:
            return SafetyDecision(
                safe=False,
                provider=PROVIDER_NAME,
                action=ACTION_ERROR,
                reason=empty_reason,
            )
        try:
            guardrail_id, guardrail_version = self._require_guardrail()
            client = self._client or self._build_client(timeout_s=timeout_s)
        except SafetyConfigError:
            return SafetyDecision(
                safe=False,
                provider=PROVIDER_NAME,
                action=ACTION_ERROR,
                reason='aws guardrail config failed',
            )
        started = time.perf_counter()
        try:
            response = client.apply_guardrail(
                guardrailIdentifier=guardrail_id,
                guardrailVersion=guardrail_version,
                source=source,
                content=[{'text': {'text': payload}}],
            )
        except Exception:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return SafetyDecision(
                safe=False,
                provider=PROVIDER_NAME,
                action=ACTION_ERROR,
                reason='aws guardrail request failed',
                latency_ms=latency_ms,
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        action = response.get('action')
        categories = _categories(response)
        if action == ACTION_NONE:
            return SafetyDecision(
                safe=True,
                provider=PROVIDER_NAME,
                action=action,
                reason=_reason(response),
                usage=_usage(response),
                latency_ms=latency_ms,
                assessments=categories,
            )
        if action == ACTION_INTERVENED:
            return SafetyDecision(
                safe=False,
                provider=PROVIDER_NAME,
                action=action,
                reason=_reason(response),
                usage=_usage(response),
                latency_ms=latency_ms,
                assessments=categories,
            )
        return SafetyDecision(
            safe=False,
            provider=PROVIDER_NAME,
            action=ACTION_ERROR,
            reason='unexpected guardrail action',
            usage=_usage(response),
            latency_ms=latency_ms,
        )

    def _require_guardrail(self):
        guardrail_id = self._guardrail_id or os.environ.get(GUARDRAIL_ID_ENV)
        guardrail_version = self._guardrail_version or os.environ.get(GUARDRAIL_VERSION_ENV)
        if not guardrail_id or not guardrail_version:
            raise SafetyConfigError('TEACHER_ASSISTANT_GUARDRAIL_ID/VERSION is not set')
        return guardrail_id, guardrail_version

    def _build_client(self, timeout_s=None):
        region = self._region or os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
        if not region:
            raise SafetyConfigError('AWS_REGION is not set')
        import boto3
        kwargs = {'region_name': region}
        if timeout_s is not None:
            from botocore.config import Config
            remaining = max(1.0, float(timeout_s))
            kwargs['config'] = Config(
                connect_timeout=min(3.0, remaining),
                read_timeout=max(1.0, remaining),
                retries={'max_attempts': 1, 'mode': 'standard'},
            )
        return boto3.client('bedrock-runtime', **kwargs)


def _env_text(name):
    return (os.environ.get(name) or '').strip()


def guardrail_region():
    return _env_text('AWS_REGION') or _env_text('AWS_DEFAULT_REGION')


def guardrail_configured():
    return bool(
        _env_text(GUARDRAIL_ID_ENV)
        and _env_text(GUARDRAIL_VERSION_ENV)
        and guardrail_region()
    )


def is_guardrail_explicitly_disabled():
    from features.assistant.config import _truthy_env
    return _truthy_env(GUARDRAIL_DISABLED_ENV)


def is_local_fake_guardrail_exempt():
    """provider=fake 이고 LIVE가 아니면 local/dev. AWS 없이 브라우저 개발을 유지한다."""
    from features.assistant.config import assistant_provider_name, is_assistant_live_enabled
    return assistant_provider_name() == 'fake' and not is_assistant_live_enabled()


def assistant_guardrail_is_release_blocker():
    """assistant enabled + required Guardrail 설정 누락. production release blocker.

    CLC_TESTING/local fake Noop과 별개다. 테스트 런타임이 Noop이어도 True일 수 있다.
    """
    from features.assistant.config import is_teacher_assistant_enabled
    return (
        is_teacher_assistant_enabled()
        and not is_guardrail_explicitly_disabled()
        and not guardrail_configured()
    )


def get_assistant_guardrail():
    if os.environ.get('CLC_TESTING') == '1':
        return NoopAssistantGuardrail()
    if is_guardrail_explicitly_disabled():
        return NoopAssistantGuardrail()
    if guardrail_configured():
        return AwsBedrockAssistantGuardrail()
    if is_local_fake_guardrail_exempt() and not (
        _env_text(GUARDRAIL_ID_ENV) or _env_text(GUARDRAIL_VERSION_ENV)
    ):
        return NoopAssistantGuardrail()
    return FailClosedAssistantGuardrail()


def _usage(response):
    usage = response.get('usage')
    if not isinstance(usage, dict):
        return None
    return {
        'topicPolicyUnits': usage.get('topicPolicyUnits'),
        'contentPolicyUnits': usage.get('contentPolicyUnits'),
    }


def _categories(response):
    names = []
    for assessment in response.get('assessments') or []:
        if not isinstance(assessment, dict):
            continue
        for topic in ((assessment.get('topicPolicy') or {}).get('topics') or []):
            if not isinstance(topic, dict):
                continue
            if topic.get('action') == 'BLOCKED' or topic.get('detected') is True:
                name = topic.get('name')
                if isinstance(name, str) and name.strip():
                    names.append(name.strip())
        for filt in ((assessment.get('contentPolicy') or {}).get('filters') or []):
            if not isinstance(filt, dict):
                continue
            if filt.get('action') == 'BLOCKED' or filt.get('detected') is True:
                kind = filt.get('type')
                if isinstance(kind, str) and kind.strip():
                    names.append(kind.strip())
    return tuple(names[:8]) if names else None


def _reason(response):
    action_reason = response.get('actionReason')
    if isinstance(action_reason, str) and action_reason.strip():
        return action_reason.strip()
    names = _categories(response)
    if names:
        return ','.join(names)
    return None
