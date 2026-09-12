"""Internal assistant failure classes. 사용자에게 코드를 노출하지 않는다."""
from __future__ import annotations

FAILURE_PROVIDER_TIMEOUT = 'provider_timeout'
FAILURE_PROVIDER_RATE_LIMIT = 'provider_rate_limit'
FAILURE_PROVIDER_5XX = 'provider_5xx'
FAILURE_PROVIDER_CONNECTION = 'provider_connection'
FAILURE_PROVIDER_AUTH_CONFIG = 'provider_auth_config'
FAILURE_PROVIDER_BAD_REQUEST = 'provider_bad_request'
FAILURE_FALLBACK_FAILED = 'fallback_failed'
FAILURE_REQUEST_DEADLINE = 'request_deadline'
FAILURE_TOOL = 'tool_failure'
FAILURE_DATA_READ = 'data_read_failure'
FAILURE_AUTH = 'auth_failure'
FAILURE_GROUNDING = 'grounding_failure'
FAILURE_GUARDRAIL_BLOCK = 'guardrail_block'
FAILURE_GUARDRAIL_ERROR = 'guardrail_error'
FAILURE_UNEXPECTED = 'unexpected_internal'

SAFE_FAILURE_CLASSES = frozenset({
    FAILURE_PROVIDER_TIMEOUT,
    FAILURE_PROVIDER_RATE_LIMIT,
    FAILURE_PROVIDER_5XX,
    FAILURE_PROVIDER_CONNECTION,
    FAILURE_PROVIDER_AUTH_CONFIG,
    FAILURE_PROVIDER_BAD_REQUEST,
    FAILURE_FALLBACK_FAILED,
    FAILURE_REQUEST_DEADLINE,
    FAILURE_TOOL,
    FAILURE_DATA_READ,
    FAILURE_AUTH,
    FAILURE_GROUNDING,
    FAILURE_GUARDRAIL_BLOCK,
    FAILURE_GUARDRAIL_ERROR,
    FAILURE_UNEXPECTED,
})


class AssistantDeadlineError(Exception):
    """전체 assistant request deadline 초과."""

    failure_class = FAILURE_REQUEST_DEADLINE


class AssistantToolFailure(Exception):
    """canonical tool / DB / service 예외. cross-provider fallback 금지."""

    failure_class = FAILURE_TOOL


class AssistantGroundingError(Exception):
    """final answer grounding fatal. LLM retry / fallback 금지."""

    failure_class = FAILURE_GROUNDING


class AssistantGuardrailBlock(Exception):
    """Guardrail INTERVENED. conversation segment를 닫는다."""

    failure_class = FAILURE_GUARDRAIL_BLOCK

    def __init__(self, source='input'):
        super().__init__('guardrail_block')
        self.source = source


class AssistantGuardrailError(Exception):
    """Guardrail timeout/network/config. conversation은 유지한다."""

    failure_class = FAILURE_GUARDRAIL_ERROR


def safe_failure_class(code):
    raw = str(code or '')
    if raw in SAFE_FAILURE_CLASSES:
        return raw
    if raw:
        return FAILURE_UNEXPECTED
    return None
