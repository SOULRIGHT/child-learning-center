"""Reading-specific OpenAI generator. Evidence Packet / growth prompt를 쓰지 않는다."""
from __future__ import annotations

import json
import os
import time

from features.reading.ai.prompt import READING_PROMPT_VERSION, READING_SYSTEM_PROMPT
from features.reading.ai.provider import (
    ReadingAnalysisAPIError,
    ReadingAnalysisConfigError,
    ReadingAnalysisError,
    ReadingAnalysisParseError,
    ReadingAnalysisProvider,
    ReadingGenerationResult,
)
from features.reading.ai.schema import OUTPUT_SCHEMA_VERSION, structured_output_format

DEFAULT_READING_AI_MODEL = 'gpt-5.6-luna'
DEFAULT_PROVIDER_NAME = 'openai'
REASONING_EFFORT = 'low'
API_KEY_ENV = 'OPENAI_API_KEY'
MODEL_ENV = 'READING_AI_MODEL'


class OpenAIReadingAnalysisProvider(ReadingAnalysisProvider):
    def __init__(self, *, api_key=None, model=None, client=None):
        self._api_key = api_key
        self._model = model
        self._client = client

    @property
    def model(self):
        return self._model or os.environ.get(MODEL_ENV) or DEFAULT_READING_AI_MODEL

    def generate(self, payload, timeout_s=None) -> ReadingGenerationResult:
        serialized = _serialize_payload(payload)
        client = self._request_client(timeout_s)
        started = time.perf_counter()
        try:
            response = client.responses.create(
                model=self.model,
                instructions=READING_SYSTEM_PROMPT,
                input=serialized,
                store=False,
                reasoning={'effort': REASONING_EFFORT},
                text={'format': structured_output_format()},
            )
        except ReadingAnalysisError:
            raise
        except Exception as exc:
            raise _api_error(exc) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        parsed = _parse_response(response)
        return ReadingGenerationResult(
            provider=DEFAULT_PROVIDER_NAME,
            model=getattr(response, 'model', None) or self.model,
            prompt_version=READING_PROMPT_VERSION,
            output_schema_version=OUTPUT_SCHEMA_VERSION,
            parsed_output=parsed,
            response_id=getattr(response, 'id', None),
            usage=_usage(response),
            latency_ms=latency_ms,
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
            raise ReadingAnalysisConfigError('OPENAI_API_KEY is not set')
        from openai import OpenAI
        kwargs = {'api_key': api_key}
        if timeout_s is not None:
            kwargs['timeout'] = float(timeout_s)
            kwargs['max_retries'] = 0
        return OpenAI(**kwargs)


def _serialize_payload(payload):
    if not isinstance(payload, dict):
        raise ReadingAnalysisError('reading analysis payload must be a dict')
    try:
        return json.dumps(payload, ensure_ascii=False, default=_reject_non_json)
    except TypeError as exc:
        raise ReadingAnalysisError('reading analysis payload is not JSON serializable') from exc


def _reject_non_json(value):
    raise TypeError(type(value).__name__)


def _api_error(exc):
    try:
        from openai import APIConnectionError, APIStatusError, APITimeoutError
    except ImportError:
        return ReadingAnalysisAPIError('openai api request failed')
    if isinstance(exc, APITimeoutError):
        return ReadingAnalysisAPIError('openai api timeout')
    if isinstance(exc, APIConnectionError):
        return ReadingAnalysisAPIError('openai api connection failed')
    if isinstance(exc, APIStatusError):
        status = getattr(exc, 'status_code', None)
        return ReadingAnalysisAPIError(
            f'openai api error{"" if status is None else f" ({status})"}'
        )
    return ReadingAnalysisAPIError('openai api request failed')


def _parse_response(response):
    status = getattr(response, 'status', None)
    if status not in (None, 'completed'):
        raise ReadingAnalysisParseError('incomplete openai response')
    text = getattr(response, 'output_text', None)
    if not text or not str(text).strip():
        raise ReadingAnalysisParseError('empty openai structured output')
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ReadingAnalysisParseError('malformed openai structured output') from exc
    if not isinstance(parsed, dict):
        raise ReadingAnalysisParseError('malformed openai structured output')
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
