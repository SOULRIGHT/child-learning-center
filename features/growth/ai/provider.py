"""Growth interpretation provider boundary. OpenAI SDK에 의존하지 않는다."""
from __future__ import annotations

from dataclasses import dataclass


class GrowthInterpretationError(Exception):
    """해석 생성 실패. Evidence Packet을 메시지에 넣지 않는다."""


class GrowthInterpretationConfigError(GrowthInterpretationError):
    """API key 등 설정 오류."""


class GrowthInterpretationAPIError(GrowthInterpretationError):
    """원격 API 오류 / timeout."""


class GrowthInterpretationParseError(GrowthInterpretationError):
    """빈 응답, incomplete, JSON/schema parse 실패."""


@dataclass(frozen=True)
class GenerationResult:
    provider: str
    model: str
    prompt_version: str
    output_schema_version: str
    parsed_output: dict
    response_id: str | None
    usage: dict
    latency_ms: int | None = None
    raw_output: str | None = None


class GrowthInterpretationProvider:
    """generate(packet) -> GenerationResult. packet은 growth_teacher_evidence_v1 dict."""

    def generate(self, packet, timeout_s=None) -> GenerationResult:
        raise NotImplementedError
