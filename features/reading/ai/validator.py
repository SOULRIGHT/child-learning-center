"""Reading AI output validator. 원문 echo / 능력·정서 평가를 기계적으로 거절한다."""
from __future__ import annotations

import re
from dataclasses import dataclass

from features.reading.ai.schema import (
    ALLOWED_DIMENSIONS,
    ALLOWED_STATUSES,
    OUTPUT_SCHEMA_VERSION,
)

VALIDATOR_VERSION = 'reading_analysis_validator_v1'
QUOTE_ECHO_MIN = 20

CODE_SCHEMA = 'SCHEMA'
CODE_STATUS_MISMATCH = 'STATUS_MISMATCH'
CODE_DIMENSION = 'BAD_DIMENSION'
CODE_EVIDENCE_REF = 'BAD_EVIDENCE_REF'
CODE_FORBIDDEN_LANGUAGE = 'FORBIDDEN_LANGUAGE'
CODE_RAW_ECHO = 'RAW_ECHO'
CODE_QUOTE = 'DIRECT_QUOTE'

_FORBIDDEN = re.compile(
    '|'.join((
        r'글쓰기\s*능력',
        r'사고력',
        r'공감\s*능력',
        r'성격',
        r'정서\s*상태',
        r'인지\s*능력',
        r'심리',
        r'진단',
        r'성향',
        r'sentiment',
        r'personality',
        r'writing ability',
        r'iq\b',
        r'지능',
        r'순위',
        r'백분위',
        r'상위권',
        r'열등',
    )),
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReadingValidationResult:
    valid: bool
    codes: tuple[str, ...]


def validate_reading_analysis(parsed_output, *, allowed_refs, sufficiency, raw_texts):
    codes = []
    if not isinstance(parsed_output, dict):
        return ReadingValidationResult(False, (CODE_SCHEMA,))
    if parsed_output.get('schema_version') != OUTPUT_SCHEMA_VERSION:
        codes.append(CODE_SCHEMA)
    status = parsed_output.get('status')
    if status not in ALLOWED_STATUSES:
        codes.append(CODE_SCHEMA)
    elif status != sufficiency:
        codes.append(CODE_STATUS_MISMATCH)
    observations = parsed_output.get('observations')
    limitations = parsed_output.get('limitations')
    if not isinstance(observations, list) or not isinstance(limitations, list):
        codes.append(CODE_SCHEMA)
        return ReadingValidationResult(False, tuple(dict.fromkeys(codes)))
    allowed = {_ref_key(item) for item in allowed_refs}
    texts = []
    for item in observations:
        if not isinstance(item, dict):
            codes.append(CODE_SCHEMA)
            continue
        if item.get('dimension') not in ALLOWED_DIMENSIONS:
            codes.append(CODE_DIMENSION)
        observation = item.get('observation')
        if not isinstance(observation, str) or not observation.strip():
            codes.append(CODE_SCHEMA)
        else:
            texts.append(observation)
            _scan_text(observation, raw_texts, codes)
        refs = item.get('evidence_refs')
        if not isinstance(refs, list) or not refs:
            codes.append(CODE_EVIDENCE_REF)
            continue
        for ref in refs:
            if _ref_key(ref) not in allowed:
                codes.append(CODE_EVIDENCE_REF)
    for item in limitations:
        if isinstance(item, str):
            texts.append(item)
            _scan_text(item, raw_texts, codes)
        else:
            codes.append(CODE_SCHEMA)
    if sufficiency == 'limited':
        joined = '\n'.join(texts)
        if re.search(r'뚜렷한\s*변화|크게\s*성장|급격|확실히\s*늘', joined):
            codes.append(CODE_FORBIDDEN_LANGUAGE)
    return ReadingValidationResult(not codes, tuple(dict.fromkeys(codes)))


def _scan_text(text, raw_texts, codes):
    if _FORBIDDEN.search(text):
        codes.append(CODE_FORBIDDEN_LANGUAGE)
    if '"' in text or '“' in text or '”' in text or '「' in text:
        codes.append(CODE_QUOTE)
    lowered = text
    for raw in raw_texts:
        snippet = (raw or '').strip()
        if len(snippet) < QUOTE_ECHO_MIN:
            continue
        if snippet in lowered:
            codes.append(CODE_RAW_ECHO)


def _ref_key(ref):
    if not isinstance(ref, dict):
        return None
    try:
        record_id = int(ref.get('record_id'))
    except (TypeError, ValueError):
        return None
    return (record_id, str(ref.get('date') or ''), ref.get('book_title'))
