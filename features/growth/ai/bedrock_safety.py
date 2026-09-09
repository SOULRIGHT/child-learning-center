"""AWS Bedrock Guardrails safety provider. Evidence Packet은 보내지 않는다."""
from __future__ import annotations

import os
import time

from features.growth.ai.safety import SafetyConfigError, SafetyDecision, SafetyProvider

PROVIDER_NAME = 'aws_bedrock_guardrail'
GUARDRAIL_ID_ENV = 'GROWTH_SAFETY_GUARDRAIL_ID'
GUARDRAIL_VERSION_ENV = 'GROWTH_SAFETY_GUARDRAIL_VERSION'
ACTION_NONE = 'NONE'
ACTION_INTERVENED = 'GUARDRAIL_INTERVENED'
ACTION_ERROR = 'ERROR'
SOURCE_OUTPUT = 'OUTPUT'
SOURCE_INPUT = 'INPUT'


class AwsBedrockGuardrailSafetyProvider(SafetyProvider):
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

    def check_response(self, text, timeout_s=None) -> SafetyDecision:
        return self._check(text, source=SOURCE_OUTPUT, timeout_s=timeout_s, empty_reason='empty output is not safety-checked')

    def check_input(self, text, timeout_s=None) -> SafetyDecision:
        """INPUT gate only. 응답 outputs의 익명화/재작성 텍스트는 쓰지 않는다."""
        return self._check(text, source=SOURCE_INPUT, timeout_s=timeout_s, empty_reason='empty input is not safety-checked')

    def _check(self, text, *, source, timeout_s, empty_reason) -> SafetyDecision:
        payload = _visible_text(text)
        if not payload:
            return SafetyDecision(
                safe=False,
                provider=PROVIDER_NAME,
                action=ACTION_ERROR,
                reason=empty_reason,
            )
        guardrail_id, guardrail_version = self._require_guardrail()
        client = self._client or self._build_client(timeout_s=timeout_s)
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
            raise SafetyConfigError('GROWTH_SAFETY_GUARDRAIL_ID/VERSION is not set')
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


def _visible_text(text):
    if not isinstance(text, str):
        return ''
    return text.strip()


def _usage(response):
    usage = response.get('usage')
    if not isinstance(usage, dict):
        return None
    return {
        'topicPolicyUnits': usage.get('topicPolicyUnits'),
        'contentPolicyUnits': usage.get('contentPolicyUnits'),
        'wordPolicyUnits': usage.get('wordPolicyUnits'),
        'sensitiveInformationPolicyUnits': usage.get('sensitiveInformationPolicyUnits'),
        'sensitiveInformationPolicyFreeUnits': usage.get('sensitiveInformationPolicyFreeUnits'),
        'contextualGroundingPolicyUnits': usage.get('contextualGroundingPolicyUnits'),
        'contentPolicyImageUnits': usage.get('contentPolicyImageUnits'),
        'automatedReasoningPolicyUnits': usage.get('automatedReasoningPolicyUnits'),
        'automatedReasoningPolicies': usage.get('automatedReasoningPolicies'),
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
