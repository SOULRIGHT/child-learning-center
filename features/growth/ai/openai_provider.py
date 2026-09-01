"""OpenAI GPT-5.6 Luna generator. Evidence Packet JSON만 보낸다."""
from __future__ import annotations

import json
import os
import time

from features.growth.ai.prompt import GROWTH_TEACHER_PROMPT_VERSION, GROWTH_TEACHER_SYSTEM_PROMPT
from features.growth.ai.provider import (
    GenerationResult,
    GrowthInterpretationAPIError,
    GrowthInterpretationConfigError,
    GrowthInterpretationError,
    GrowthInterpretationParseError,
    GrowthInterpretationProvider,
)
from features.growth.ai.schema import OUTPUT_SCHEMA_VERSION, structured_output_format
from features.growth.evidence_packet import AUDIENCE_TEACHER, SCHEMA_VERSION

DEFAULT_GROWTH_AI_MODEL = 'gpt-5.6-luna'
DEFAULT_PROVIDER_NAME = 'openai'
REASONING_EFFORT = 'low'
API_KEY_ENV = 'OPENAI_API_KEY'
MODEL_ENV = 'GROWTH_AI_MODEL'


class OpenAIGrowthInterpretationProvider(GrowthInterpretationProvider):
    def __init__(self, *, api_key=None, model=None, client=None):
        self._api_key = api_key
        self._model = model
        self._client = client

    @property
    def model(self):
        return self._model or os.environ.get(MODEL_ENV) or DEFAULT_GROWTH_AI_MODEL

    def generate(self, packet, timeout_s=None) -> GenerationResult:
        payload = _serialize_packet(packet)
        client = self._request_client(timeout_s)
        started = time.perf_counter()
        try:
            response = client.responses.create(
                model=self.model,
                instructions=GROWTH_TEACHER_SYSTEM_PROMPT,
                input=payload,
                store=False,
                reasoning={'effort': REASONING_EFFORT},
                text={'format': structured_output_format()},
            )
        except GrowthInterpretationError:
            raise
        except Exception as exc:
            raise _api_error(exc) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        parsed = _parse_response(response)
        return GenerationResult(
            provider=DEFAULT_PROVIDER_NAME,
            model=getattr(response, 'model', None) or self.model,
            prompt_version=GROWTH_TEACHER_PROMPT_VERSION,
            output_schema_version=OUTPUT_SCHEMA_VERSION,
            parsed_output=parsed,
            response_id=getattr(response, 'id', None),
            usage=_usage(response),
            latency_ms=latency_ms,
            raw_output=getattr(response, 'output_text', None),
        )

    def _request_client(self, timeout_s):
        if self._client is not None:
            if timeout_s is not None and hasattr(self._client, 'with_options'):
                return self._client.with_options(timeout=float(timeout_s), max_retries=0)
            return self._client
        return self._build_client(timeout_s=timeout_s)

    def _build_client(self, timeout_s=None):
        api_key = self._api_key or os.environ.get(API_KEY_ENV)
        if not api_key:
            raise GrowthInterpretationConfigError('OPENAI_API_KEY is not set')
        from openai import OpenAI
        kwargs = {'api_key': api_key}
        if timeout_s is not None:
            kwargs['timeout'] = float(timeout_s)
            kwargs['max_retries'] = 0
        return OpenAI(**kwargs)


def _serialize_packet(packet):
    if not isinstance(packet, dict):
        raise GrowthInterpretationError('evidence packet must be a dict')
    if packet.get('schema_version') != SCHEMA_VERSION:
        raise GrowthInterpretationError('unsupported evidence packet schema')
    if packet.get('audience') != AUDIENCE_TEACHER:
        raise GrowthInterpretationError('audience must be teacher')
    try:
        return json.dumps(packet, ensure_ascii=False, default=_reject_non_json)
    except TypeError as exc:
        raise GrowthInterpretationError('evidence packet is not JSON serializable') from exc


def _reject_non_json(value):
    raise TypeError(type(value).__name__)


def _api_error(exc):
    try:
        from openai import APIConnectionError, APIStatusError, APITimeoutError
    except ImportError:
        return GrowthInterpretationAPIError('openai api request failed')
    if isinstance(exc, APITimeoutError):
        return GrowthInterpretationAPIError('openai api timeout')
    if isinstance(exc, APIConnectionError):
        return GrowthInterpretationAPIError('openai api connection failed')
    if isinstance(exc, APIStatusError):
        status = getattr(exc, 'status_code', None)
        return GrowthInterpretationAPIError(
            f'openai api error{"" if status is None else f" ({status})"}'
        )
    return GrowthInterpretationAPIError('openai api request failed')


def _parse_response(response):
    status = getattr(response, 'status', None)
    if status not in (None, 'completed'):
        raise GrowthInterpretationParseError('incomplete openai response')
    text = getattr(response, 'output_text', None)
    if not text or not str(text).strip():
        raise GrowthInterpretationParseError('empty openai structured output')
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise GrowthInterpretationParseError('malformed openai structured output') from exc
    if not isinstance(parsed, dict):
        raise GrowthInterpretationParseError('malformed openai structured output')
    return parsed


def _usage(response):
    usage = getattr(response, 'usage', None)
    if usage is None:
        return {
            'input_tokens': None,
            'output_tokens': None,
            'total_tokens': None,
        }
    return {
        'input_tokens': getattr(usage, 'input_tokens', None),
        'output_tokens': getattr(usage, 'output_tokens', None),
        'total_tokens': getattr(usage, 'total_tokens', None),
    }
