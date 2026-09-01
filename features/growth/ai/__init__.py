"""Teacher Growth interpretation generator. production UI/route에 연결하지 않는다."""

from features.growth.ai.openai_provider import OpenAIGrowthInterpretationProvider
from features.growth.ai.prompt import GROWTH_TEACHER_PROMPT_VERSION, GROWTH_TEACHER_SYSTEM_PROMPT
from features.growth.ai.provider import (
    GenerationResult,
    GrowthInterpretationAPIError,
    GrowthInterpretationConfigError,
    GrowthInterpretationError,
    GrowthInterpretationParseError,
    GrowthInterpretationProvider,
)
from features.growth.ai.schema import (
    INTERPRETATION_JSON_SCHEMA,
    OUTPUT_SCHEMA_VERSION,
    structured_output_format,
)
from features.growth.ai.validator import (
    ValidationResult,
    Violation,
    collect_evidence_index,
    validate_teacher_interpretation,
)

__all__ = [
    'GenerationResult',
    'GrowthInterpretationAPIError',
    'GrowthInterpretationConfigError',
    'GrowthInterpretationError',
    'GrowthInterpretationParseError',
    'GrowthInterpretationProvider',
    'GROWTH_TEACHER_PROMPT_VERSION',
    'GROWTH_TEACHER_SYSTEM_PROMPT',
    'INTERPRETATION_JSON_SCHEMA',
    'OUTPUT_SCHEMA_VERSION',
    'OpenAIGrowthInterpretationProvider',
    'ValidationResult',
    'Violation',
    'collect_evidence_index',
    'structured_output_format',
    'validate_teacher_interpretation',
]
