"""Growth AI safety provider boundary. AWS SDK와 B3A에 의존하지 않는다."""
from __future__ import annotations

from dataclasses import dataclass


class SafetyError(Exception):
    """안전 검사 실패. 검사 대상 전문을 메시지에 넣지 않는다."""


class SafetyConfigError(SafetyError):
    """guardrail id/version/region 등 설정 오류."""


@dataclass(frozen=True)
class SafetyDecision:
    safe: bool
    provider: str
    action: str
    reason: str | None = None
    usage: dict | None = None
    latency_ms: int | None = None

    def __repr__(self):
        return (
            f'SafetyDecision(safe={self.safe}, provider={self.provider!r}, '
            f'action={self.action!r})'
        )


class SafetyProvider:
    """check_response(text) -> SafetyDecision. text는 사용자 노출 자연어만."""

    def check_response(self, text, timeout_s=None) -> SafetyDecision:
        raise NotImplementedError


def visible_interpretation_text(parsed_output) -> str:
    """interpretation에서 사용자 노출 text만 deterministic하게 합친다.

    evidence_ids / packet / prompt는 포함하지 않는다.
    """
    if not isinstance(parsed_output, dict):
        return ''
    parts = []
    summary = parsed_output.get('summary')
    if isinstance(summary, dict):
        _append_text(parts, summary.get('text'))
    observations = parsed_output.get('observations')
    if isinstance(observations, list):
        for item in observations:
            if isinstance(item, dict):
                _append_text(parts, item.get('text'))
    suggestions = parsed_output.get('suggestions')
    if isinstance(suggestions, list):
        for item in suggestions:
            if isinstance(item, dict):
                _append_text(parts, item.get('text'))
    return '\n\n'.join(parts)


def _append_text(parts, value):
    if not isinstance(value, str):
        return
    stripped = value.strip()
    if stripped:
        parts.append(stripped)
