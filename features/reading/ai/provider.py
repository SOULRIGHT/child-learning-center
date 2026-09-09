"""Reading-specific AI provider boundary."""
from __future__ import annotations

from dataclasses import dataclass


class ReadingAnalysisError(Exception):
    """독서 분석 생성 실패. 원문을 메시지에 넣지 않는다."""


class ReadingAnalysisConfigError(ReadingAnalysisError):
    """API key 등 설정 오류."""


class ReadingAnalysisAPIError(ReadingAnalysisError):
    """원격 API 오류 / timeout."""


class ReadingAnalysisParseError(ReadingAnalysisError):
    """빈 응답, incomplete, JSON/schema parse 실패."""


@dataclass(frozen=True)
class ReadingGenerationResult:
    provider: str
    model: str
    prompt_version: str
    output_schema_version: str
    parsed_output: dict
    response_id: str | None
    usage: dict
    latency_ms: int | None = None


class ReadingAnalysisProvider:
    """generate(payload) -> ReadingGenerationResult. payload는 독서 전용 입력."""

    def generate(self, payload, timeout_s=None) -> ReadingGenerationResult:
        raise NotImplementedError
