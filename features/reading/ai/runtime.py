"""Reading-specific AI application service.

GET에서 LLM을 호출하지 않는다.
Overall Growth Evidence Packet / prompt / packet_hash / attempt 구조를 재사용하지 않는다.
review_text 를 로그·DB cache·에러 메시지에 넣지 않는다.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime

from extensions import db
from feature_models import (
    READING_AI_STATUS_FAILED,
    READING_AI_STATUS_SUCCESS,
    ReadingAnalysisResult,
)
from features.growth.ai.bedrock_safety import (
    ACTION_ERROR,
    ACTION_INTERVENED,
    AwsBedrockGuardrailSafetyProvider,
    PROVIDER_NAME as SAFETY_PROVIDER_NAME,
)
from features.growth.ai.hashing import sha256_hex, canonical_json
from features.growth.ai.runtime import DEADLINE_S, DeadlineExceeded, MIN_CALL_S
from features.growth.ai.safety import SafetyDecision, SafetyError
from features.growth.windows import resolve_as_of
from features.reading.analysis import (
    ANALYZER_VERSION,
    TIER_NO_CHANGE,
    ai_input_records,
    allowed_evidence_refs,
    apply_allowed_ids,
    build_public_facts,
    fingerprint_payload,
    select_text_records,
)
from features.reading.ai.copy import (
    MSG_CONFIRM,
    MSG_DISABLED,
    MSG_ERROR,
    MSG_INSUFFICIENT,
    MSG_LIMITED,
    MSG_NONE,
    MSG_SAFETY,
    MSG_STALE,
    MSG_TIMEOUT,
    MSG_UNAVAILABLE,
)
from features.reading.ai.openai_provider import (
    DEFAULT_PROVIDER_NAME,
    DEFAULT_READING_AI_MODEL,
    MODEL_ENV,
    OpenAIReadingAnalysisProvider,
)
from features.reading.ai.prompt import READING_PROMPT_VERSION
from features.reading.ai.provider import (
    ReadingAnalysisAPIError,
    ReadingAnalysisConfigError,
    ReadingAnalysisParseError,
)
from features.reading.ai.schema import OUTPUT_SCHEMA_VERSION
from features.reading.ai.validator import VALIDATOR_VERSION, validate_reading_analysis

logger = logging.getLogger(__name__)

READING_AI_ENABLED_ENV = 'READING_AI_ENABLED'
FRONTEND_TIMEOUT_MS = int(DEADLINE_S * 1000) + 1000

CODE_DISABLED = 'DISABLED'
CODE_CONFIRM = 'CONFIRMATION_REQUIRED'
CODE_INSUFFICIENT = 'INSUFFICIENT_SAMPLE'
CODE_TIMEOUT = 'TIMEOUT'
CODE_GENERATOR = 'GENERATOR_ERROR'
CODE_VALIDATOR = 'VALIDATOR_REJECT'
CODE_SAFETY_BLOCK = 'SAFETY_INTERVENED'
CODE_SAFETY_ERROR = 'SAFETY_ERROR'
CODE_PARSE = 'PARSE_ERROR'
CODE_CONFIG = 'CONFIG'

INPUT_SCHEMA_VERSION = 'reading_analysis_input_v1'


@dataclass
class ReadingAIResult:
    ok: bool
    state: str
    message: str | None = None
    analysis_id: int | None = None
    output: dict | None = None
    facts: dict | None = None
    cached: bool = False
    stale: bool = False
    failure_code: str | None = None
    started: bool = False


@dataclass
class _Deadline:
    seconds: float
    clock: object
    start: float = field(init=False)

    def __post_init__(self):
        self.start = self.clock()

    def remaining(self):
        return self.seconds - (self.clock() - self.start)

    def raise_if_expired(self, min_needed=MIN_CALL_S):
        if self.remaining() < min_needed:
            raise DeadlineExceeded()


def is_reading_ai_enabled():
    raw = (os.environ.get(READING_AI_ENABLED_ENV) or '').strip().lower()
    return raw in ('1', 'true', 'yes', 'on')


def current_runtime_parts():
    model = os.environ.get(MODEL_ENV) or DEFAULT_READING_AI_MODEL
    return {
        'generator_provider': DEFAULT_PROVIDER_NAME,
        'model': model,
        'prompt_version': READING_PROMPT_VERSION,
        'analyzer_version': ANALYZER_VERSION,
        'output_schema_version': OUTPUT_SCHEMA_VERSION,
        'validator_version': VALIDATOR_VERSION,
        'safety_provider': SAFETY_PROVIDER_NAME,
    }


def current_fingerprint(selection, facts):
    payload = fingerprint_payload(selection, facts, current_runtime_parts())
    return sha256_hex(canonical_json(payload))


def load_reading_ai_view(child_id, as_of=None):
    """GET용. LLM/Guardrail을 호출하지 않는다."""
    as_of = resolve_as_of(as_of)
    selection = select_text_records(child_id, as_of=as_of)
    facts = build_public_facts(child_id, as_of=as_of, selection=selection)
    view = {
        'enabled': is_reading_ai_enabled(),
        'facts': facts,
        'sufficiency': facts['sufficiency'],
        'timeout_ms': FRONTEND_TIMEOUT_MS,
        'output': None,
        'stale': False,
        'cached': False,
        'analysis_id': None,
    }
    if facts['sufficiency'] == TIER_NO_CHANGE:
        view['state'] = 'insufficient'
        view['message'] = MSG_INSUFFICIENT
        return _with_stale_if_any(view, child_id, selection, facts)
    if not view['enabled']:
        view['state'] = 'unavailable'
        view['message'] = MSG_DISABLED
        return view
    digest = current_fingerprint(selection, facts)
    current = _latest_success(child_id, digest)
    if current is not None:
        view['state'] = 'current'
        view['cached'] = True
        view['analysis_id'] = current.id
        view['output'] = _public_output(current)
        if facts['sufficiency'] == 'limited':
            view['message'] = MSG_LIMITED
        return view
    previous = _latest_success_for_child(child_id)
    if previous is not None:
        view['state'] = 'stale'
        view['stale'] = True
        view['analysis_id'] = previous.id
        view['output'] = _public_output(previous)
        view['message'] = MSG_STALE
        return view
    view['state'] = 'none'
    view['message'] = MSG_NONE
    return view


def generate_reading_analysis(
    *,
    child_id,
    user_id,
    as_of=None,
    confirmed=False,
    generator=None,
    safety=None,
    clock=None,
):
    """교사 explicit confirmation 후에만 LLM을 호출한다. hidden retry 없음."""
    as_of = resolve_as_of(as_of)
    selection = select_text_records(child_id, as_of=as_of)
    facts = build_public_facts(child_id, as_of=as_of, selection=selection)
    if not confirmed:
        return ReadingAIResult(
            ok=False,
            state='confirm',
            message=MSG_CONFIRM,
            facts=facts,
            failure_code=CODE_CONFIRM,
        )
    if not is_reading_ai_enabled():
        return ReadingAIResult(
            ok=False,
            state='unavailable',
            message=MSG_DISABLED,
            facts=facts,
            failure_code=CODE_DISABLED,
        )
    digest = current_fingerprint(selection, facts)
    cached = _latest_success(child_id, digest)
    if cached is not None:
        return ReadingAIResult(
            ok=True,
            state='current',
            analysis_id=cached.id,
            output=_public_output(cached),
            facts=facts,
            cached=True,
        )
    if facts['sufficiency'] == TIER_NO_CHANGE:
        return ReadingAIResult(
            ok=False,
            state='insufficient',
            message=MSG_INSUFFICIENT,
            facts=facts,
            failure_code=CODE_INSUFFICIENT,
        )

    generator = generator or OpenAIReadingAnalysisProvider()
    safety = safety or AwsBedrockGuardrailSafetyProvider()
    deadline = _Deadline(DEADLINE_S, clock or time_clock())
    try:
        allowed_selection, blocked, safety_error = _filter_inputs(
            selection, safety, deadline,
        )
    except DeadlineExceeded:
        return _fail(child_id, user_id, as_of, digest, facts, CODE_TIMEOUT, MSG_TIMEOUT)
    except SafetyError:
        return _fail(child_id, user_id, as_of, digest, facts, CODE_SAFETY_ERROR, MSG_UNAVAILABLE)
    if safety_error:
        return _fail(child_id, user_id, as_of, digest, facts, CODE_SAFETY_ERROR, MSG_UNAVAILABLE)
    usable_facts = build_public_facts(child_id, as_of=as_of, selection=allowed_selection)
    usable_digest = current_fingerprint(allowed_selection, usable_facts)
    if blocked:
        usable_facts = dict(usable_facts)
        usable_facts['blocked_record_count'] = blocked
    if usable_facts['sufficiency'] == TIER_NO_CHANGE:
        message = MSG_SAFETY if blocked else MSG_INSUFFICIENT
        return ReadingAIResult(
            ok=False,
            state='insufficient',
            message=message,
            facts=usable_facts,
            failure_code=CODE_INSUFFICIENT,
        )
    cached = _latest_success(child_id, usable_digest)
    if cached is not None:
        return ReadingAIResult(
            ok=True,
            state='current',
            analysis_id=cached.id,
            output=_public_output(cached),
            facts=usable_facts,
            cached=True,
        )
    payload = _llm_payload(allowed_selection, usable_facts)
    try:
        deadline.raise_if_expired()
        result = generator.generate(payload, timeout_s=deadline.remaining())
        deadline.raise_if_expired()
        validation = validate_reading_analysis(
            result.parsed_output,
            allowed_refs=allowed_evidence_refs(allowed_selection),
            sufficiency=usable_facts['sufficiency'],
            raw_texts=_raw_texts(allowed_selection),
        )
        if not validation.valid:
            logger.info('reading ai validator rejected codes=%s', validation.codes)
            return _fail(
                child_id, user_id, as_of, usable_digest, usable_facts,
                CODE_VALIDATOR, MSG_UNAVAILABLE,
            )
        output_text = _visible_output_text(result.parsed_output)
        output_decision = _check_output(safety, output_text, deadline)
        if output_decision.action == ACTION_ERROR:
            return _fail(
                child_id, user_id, as_of, usable_digest, usable_facts,
                CODE_SAFETY_ERROR, MSG_UNAVAILABLE,
            )
        if not output_decision.safe:
            return _fail(
                child_id, user_id, as_of, usable_digest, usable_facts,
                CODE_SAFETY_BLOCK, MSG_UNAVAILABLE,
            )
    except DeadlineExceeded:
        return _fail(child_id, user_id, as_of, usable_digest, usable_facts, CODE_TIMEOUT, MSG_TIMEOUT)
    except ReadingAnalysisConfigError:
        return _fail(child_id, user_id, as_of, usable_digest, usable_facts, CODE_CONFIG, MSG_UNAVAILABLE)
    except ReadingAnalysisParseError:
        return _fail(child_id, user_id, as_of, usable_digest, usable_facts, CODE_PARSE, MSG_UNAVAILABLE)
    except ReadingAnalysisAPIError:
        return _fail(child_id, user_id, as_of, usable_digest, usable_facts, CODE_GENERATOR, MSG_ERROR)
    except Exception:
        logger.exception('reading ai generator failed')
        return _fail(child_id, user_id, as_of, usable_digest, usable_facts, CODE_GENERATOR, MSG_ERROR)

    row = _store_success(
        child_id=child_id,
        user_id=user_id,
        as_of=as_of,
        fingerprint=usable_digest,
        facts=usable_facts,
        parsed=result.parsed_output,
        generator=result,
    )
    state = 'limited' if usable_facts['sufficiency'] == 'limited' else 'current'
    return ReadingAIResult(
        ok=True,
        state=state,
        analysis_id=row.id,
        output=_public_output(row),
        facts=usable_facts,
        message=MSG_LIMITED if state == 'limited' else None,
        started=True,
    )


def public_result_payload(result: ReadingAIResult):
    payload = {
        'ok': result.ok,
        'state': result.state,
    }
    if result.message:
        payload['message'] = result.message
    if result.analysis_id is not None:
        payload['analysis_id'] = result.analysis_id
    if result.output is not None:
        payload['output'] = result.output
    if result.facts is not None:
        payload['facts'] = result.facts
    payload['cached'] = bool(result.cached)
    payload['stale'] = bool(result.stale)
    payload['started'] = bool(result.started)
    _assert_no_raw(payload)
    return payload


def time_clock():
    import time
    return time.perf_counter


def _filter_inputs(selection, safety, deadline):
    allowed_ids = []
    blocked = 0
    for record in list(selection.recent) + list(selection.previous):
        deadline.raise_if_expired()
        decision = _check_input(safety, record.review_text, deadline)
        if decision.action == ACTION_ERROR:
            logger.info('reading ai input guardrail error record_id=%s', record.day_id)
            return selection, 0, True
        if not decision.safe or decision.action == ACTION_INTERVENED:
            blocked += 1
            logger.info('reading ai input guardrail blocked record_id=%s', record.day_id)
            continue
        allowed_ids.append(record.day_id)
    filtered = apply_allowed_ids(selection, allowed_ids)
    return filtered, blocked, False


def _check_input(safety, text, deadline):
    if not hasattr(safety, 'check_input'):
        return SafetyDecision(
            safe=False,
            provider='none',
            action=ACTION_ERROR,
            reason='input guardrail missing',
        )
    return safety.check_input(text, timeout_s=deadline.remaining())


def _check_output(safety, text, deadline):
    if not text.strip():
        return SafetyDecision(
            safe=False,
            provider=SAFETY_PROVIDER_NAME,
            action=ACTION_ERROR,
            reason='empty output is not safety-checked',
        )
    return safety.check_response(text, timeout_s=deadline.remaining())


def _llm_payload(selection, facts):
    return {
        'schema_version': INPUT_SCHEMA_VERSION,
        'as_of': facts.get('as_of'),
        'sufficiency': facts.get('sufficiency'),
        'facts': {
            'text_record_count': facts.get('text_record_count'),
            'recent_count': facts.get('recent_count'),
            'previous_count': facts.get('previous_count'),
            'character_count': facts.get('character_count'),
            'sentence_count': facts.get('sentence_count'),
            'completed_count': facts.get('completed_count'),
            'completion_duration_median': facts.get('completion_duration_median'),
        },
        'records': ai_input_records(selection),
    }


def _raw_texts(selection):
    return [row.review_text for row in list(selection.recent) + list(selection.previous)]


def _visible_output_text(parsed):
    parts = []
    for item in parsed.get('observations') or []:
        if isinstance(item, dict):
            text = item.get('observation')
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    for item in parsed.get('limitations') or []:
        if isinstance(item, str) and item.strip():
            parts.append(item.strip())
    return '\n\n'.join(parts)


def _store_success(*, child_id, user_id, as_of, fingerprint, facts, parsed, generator):
    snapshot = _safe_json(facts)
    output = _safe_json(parsed)
    row = ReadingAnalysisResult(
        child_id=child_id,
        requested_by_user_id=user_id,
        fingerprint=fingerprint,
        as_of=as_of,
        status=READING_AI_STATUS_SUCCESS,
        sufficiency=facts.get('sufficiency'),
        parsed_output=output,
        facts_snapshot=snapshot,
        generator_provider=generator.provider,
        model=generator.model,
        prompt_version=generator.prompt_version,
        analyzer_version=ANALYZER_VERSION,
        output_schema_version=generator.output_schema_version,
        validator_version=VALIDATOR_VERSION,
        safety_provider=SAFETY_PROVIDER_NAME,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.session.add(row)
    db.session.commit()
    return row


def _fail(child_id, user_id, as_of, fingerprint, facts, code, message):
    row = ReadingAnalysisResult(
        child_id=child_id,
        requested_by_user_id=user_id,
        fingerprint=fingerprint,
        as_of=as_of,
        status=READING_AI_STATUS_FAILED,
        sufficiency=facts.get('sufficiency'),
        facts_snapshot=_safe_json(facts),
        failure_code=code,
        analyzer_version=ANALYZER_VERSION,
        prompt_version=READING_PROMPT_VERSION,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.session.add(row)
    db.session.commit()
    previous = _latest_success_for_child(child_id)
    stale_output = _public_output(previous) if previous is not None else None
    return ReadingAIResult(
        ok=False,
        state='stale' if stale_output else 'unavailable',
        message=MSG_STALE if stale_output else message,
        analysis_id=previous.id if previous is not None else row.id,
        output=stale_output,
        facts=facts,
        stale=bool(stale_output),
        failure_code=code,
        started=True,
    )


def _latest_success(child_id, fingerprint):
    return (
        ReadingAnalysisResult.query
        .filter_by(
            child_id=child_id,
            fingerprint=fingerprint,
            status=READING_AI_STATUS_SUCCESS,
        )
        .order_by(ReadingAnalysisResult.id.desc())
        .first()
    )


def _latest_success_for_child(child_id):
    return (
        ReadingAnalysisResult.query
        .filter_by(child_id=child_id, status=READING_AI_STATUS_SUCCESS)
        .order_by(ReadingAnalysisResult.id.desc())
        .first()
    )


def _with_stale_if_any(view, child_id, selection, facts):
    previous = _latest_success_for_child(child_id)
    if previous is None:
        return view
    digest = current_fingerprint(selection, facts)
    if previous.fingerprint == digest:
        return view
    view['stale'] = True
    view['analysis_id'] = previous.id
    view['output'] = _public_output(previous)
    if view.get('state') == 'insufficient':
        return view
    view['state'] = 'stale'
    view['message'] = MSG_STALE
    return view


def _public_output(row):
    if row is None or not row.parsed_output:
        return None
    parsed = row.parsed_output
    if not isinstance(parsed, dict):
        return None
    return {
        'status': parsed.get('status'),
        'observations': parsed.get('observations') or [],
        'limitations': parsed.get('limitations') or [],
    }


def _safe_json(value):
    encoded = json.dumps(value, ensure_ascii=False, default=str)
    _assert_no_raw(encoded)
    return json.loads(encoded)


def _assert_no_raw(value):
    blob = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    lowered = blob.lower()
    if 'review_text' in lowered:
        raise RuntimeError('reading ai cache/payload must not contain review_text')
