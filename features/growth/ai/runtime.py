"""Teacher Growth AI application service. route에 provider를 나열하지 않는다."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, timedelta, timezone

from extensions import db
from feature_models import (
    GROWTH_AI_STATUS_FAILED,
    GROWTH_AI_STATUS_PENDING,
    GROWTH_AI_STATUS_SUCCESS,
    GrowthAIAttempt,
    GrowthAIFeedback,
    GrowthAIGeneration,
)
from features.dates import KST, kst_today
from features.growth.ai.bedrock_safety import (
    ACTION_ERROR,
    ACTION_INTERVENED,
    ACTION_NONE,
    AwsBedrockGuardrailSafetyProvider,
    GUARDRAIL_ID_ENV,
    GUARDRAIL_VERSION_ENV,
    PROVIDER_NAME as SAFETY_PROVIDER_NAME,
)
from features.growth.ai.copy import (
    MSG_DISABLED,
    MSG_ERROR,
    MSG_IN_PROGRESS,
    MSG_QUOTA,
    MSG_STALE,
    MSG_STALE_DURING,
    MSG_TIMEOUT,
)
from features.growth.ai.hashing import packet_hash, runtime_signature
from features.growth.ai.openai_provider import (
    DEFAULT_GROWTH_AI_MODEL,
    DEFAULT_PROVIDER_NAME,
    MODEL_ENV,
    OpenAIGrowthInterpretationProvider,
)
from features.growth.ai.presenter import present_cited_evidence_bundle
from features.growth.ai.prompt import GROWTH_TEACHER_PROMPT_VERSION
from features.growth.ai.provider import (
    GenerationResult,
    GrowthInterpretationAPIError,
    GrowthInterpretationConfigError,
    GrowthInterpretationError,
    GrowthInterpretationParseError,
)
from features.growth.ai.schema import OUTPUT_SCHEMA_VERSION
from features.growth.ai.safety import visible_interpretation_text
from features.growth.ai.validator import FACTUAL_VALIDATOR_VERSION, validate_teacher_interpretation
from features.growth.evidence_packet import build_teacher_evidence_packet
from features.growth.metrics import metrics_bundle
from features.growth.windows import resolve_as_of

GROWTH_AI_ENABLED_ENV = 'GROWTH_AI_ENABLED'
DAILY_QUOTA = 30
DEADLINE_S = 20.0
FRONTEND_TIMEOUT_MS = 21000
MIN_CALL_S = 0.5
PENDING_STALE_S = 60
FEEDBACK_MAX_LEN = 1000
TEACHER_AI_ROLES = frozenset({'돌봄선생님', '센터장', '개발자', '일반사용자'})  # 일반사용자 = 봉사선생님. DB role rename 없음.

CODE_DISABLED = 'DISABLED'
CODE_QUOTA = 'QUOTA_EXCEEDED'
CODE_IN_PROGRESS = 'IN_PROGRESS'
CODE_TIMEOUT = 'TIMEOUT'
CODE_GENERATOR = 'GENERATOR_ERROR'
CODE_VALIDATOR = 'VALIDATOR_REJECT'
CODE_SAFETY_BLOCK = 'SAFETY_INTERVENED'
CODE_SAFETY_ERROR = 'SAFETY_ERROR'
CODE_STALE = 'STALE_DURING_GENERATION'
CODE_CONFIG = 'CONFIG'
CODE_PARSE = 'PARSE_ERROR'

ATTEMPT_SUCCESS = 'SUCCESS'
ATTEMPT_GENERATOR = 'GENERATOR_ERROR'
ATTEMPT_PARSE = 'PARSE_ERROR'
ATTEMPT_VALIDATOR = 'VALIDATOR_REJECT'
ATTEMPT_SAFETY = 'SAFETY_REJECT'
ATTEMPT_SAFETY_ERROR = 'SAFETY_ERROR'
ATTEMPT_TIMEOUT = 'TIMEOUT'
ATTEMPT_CONFIG = 'CONFIG'


class DeadlineExceeded(Exception):
    """전체 20초 budget 초과. 검사 대상 전문을 넣지 않는다."""


@dataclass
class TeacherAIResult:
    ok: bool
    state: str
    message: str | None = None
    generation_id: int | None = None
    interpretation: dict | None = None
    evidence: list | None = None
    evidence_groups: dict | None = None
    quota_remaining: int | None = None
    cached: bool = False
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


def is_growth_ai_enabled():
    raw = (os.environ.get(GROWTH_AI_ENABLED_ENV) or '').strip().lower()
    return raw in ('1', 'true', 'yes', 'on')


def can_use_teacher_ai(role):
    return role in TEACHER_AI_ROLES


def current_runtime_parts():
    model = os.environ.get(MODEL_ENV) or DEFAULT_GROWTH_AI_MODEL
    return {
        'generator_provider': DEFAULT_PROVIDER_NAME,
        'model': model,
        'prompt_version': GROWTH_TEACHER_PROMPT_VERSION,
        'output_schema_version': OUTPUT_SCHEMA_VERSION,
        'factual_validator_version': FACTUAL_VALIDATOR_VERSION,
        'safety_provider': SAFETY_PROVIDER_NAME,
        'safety_guardrail_id': (os.environ.get(GUARDRAIL_ID_ENV) or '').strip(),
        'safety_guardrail_version': (os.environ.get(GUARDRAIL_VERSION_ENV) or '').strip(),
    }


def current_runtime_signature():
    return runtime_signature(current_runtime_parts())


def build_current_packet(child, as_of=None, bundle=None):
    as_of = resolve_as_of(as_of)
    if bundle is None:
        bundle = metrics_bundle(child.id, as_of=as_of)
    return build_teacher_evidence_packet(bundle, grade=getattr(child, 'grade', None))


def load_teacher_ai_view(child, as_of=None, bundle=None, user_id=None):
    """GET용. OpenAI/AWS를 호출하지 않는다. 실패해도 예외를 삼키지 않는 호출측에서 보호."""
    enabled = is_growth_ai_enabled()
    if not enabled:
        return {
            'state': 'disabled',
            'enabled': False,
            'message': MSG_DISABLED,
            'timeout_ms': FRONTEND_TIMEOUT_MS,
        }
    packet = build_current_packet(child, as_of=as_of, bundle=bundle)
    digest = packet_hash(packet)
    signature = current_runtime_signature()
    cached = _latest_success(child.id, digest, signature)
    if cached is not None:
        view = _success_view(cached, packet, cached=True, enabled=True)
        view['quota_remaining'] = _quota_remaining(user_id)
        return view
    stale = _latest_success_any_hash(child.id, signature)
    if stale is not None and stale.packet_hash != digest:
        return {
            'state': 'stale',
            'enabled': True,
            'message': MSG_STALE,
            'timeout_ms': FRONTEND_TIMEOUT_MS,
            'quota_remaining': _quota_remaining(user_id),
        }
    return {
        'state': 'idle',
        'enabled': True,
        'timeout_ms': FRONTEND_TIMEOUT_MS,
        'quota_remaining': _quota_remaining(user_id),
    }


def generate_teacher_growth_interpretation(
    *,
    child,
    user_id,
    as_of=None,
    generator=None,
    safety=None,
    clock=time.monotonic,
):
    if not is_growth_ai_enabled():
        return TeacherAIResult(ok=False, state='disabled', message=MSG_DISABLED, failure_code=CODE_DISABLED, started=False)
    as_of = resolve_as_of(as_of)
    packet = build_current_packet(child, as_of=as_of)
    digest = packet_hash(packet)
    parts = current_runtime_parts()
    signature = runtime_signature(parts)
    cached = _latest_success(child.id, digest, signature)
    if cached is not None:
        view = _success_view(cached, packet, cached=True, enabled=True)
        return TeacherAIResult(
            ok=True,
            state='success',
            generation_id=cached.id,
            interpretation=view['interpretation'],
            evidence=view['evidence'],
            evidence_groups=view.get('evidence_groups'),
            cached=True,
            quota_remaining=_quota_remaining(user_id),
            started=False,
        )
    pending = _active_pending(child.id, digest, signature)
    if pending is not None:
        return TeacherAIResult(
            ok=False,
            state='in_progress',
            message=MSG_IN_PROGRESS,
            generation_id=pending.id,
            failure_code=CODE_IN_PROGRESS,
            quota_remaining=_quota_remaining(user_id),
            started=False,
        )
    used = _quota_used(user_id)
    if used >= DAILY_QUOTA:
        return TeacherAIResult(
            ok=False,
            state='quota',
            message=MSG_QUOTA,
            failure_code=CODE_QUOTA,
            quota_remaining=0,
            started=False,
        )
    row = GrowthAIGeneration(
        child_id=child.id,
        requested_by_user_id=user_id,
        packet_hash=digest,
        runtime_signature=signature,
        as_of=as_of,
        status=GROWTH_AI_STATUS_PENDING,
        generator_provider=parts['generator_provider'],
        model=parts['model'],
        prompt_version=parts['prompt_version'],
        output_schema_version=parts['output_schema_version'],
        factual_validator_version=parts['factual_validator_version'],
        safety_provider=parts['safety_provider'],
        safety_guardrail_version=parts['safety_guardrail_version'] or None,
        attempt_count=1,
        created_at=datetime.utcnow(),
    )
    db.session.add(row)
    db.session.commit()
    generator = generator or OpenAIGrowthInterpretationProvider()
    safety = safety or AwsBedrockGuardrailSafetyProvider()
    deadline = _Deadline(DEADLINE_S, clock)
    try:
        parsed, gen_meta, safety_meta = _run_pipeline(
            packet, generator, safety, deadline, row,
        )
    except DeadlineExceeded:
        _fail(row, CODE_TIMEOUT)
        return TeacherAIResult(
            ok=False,
            state='timeout',
            message=MSG_TIMEOUT,
            generation_id=row.id,
            failure_code=CODE_TIMEOUT,
            quota_remaining=_quota_remaining(user_id),
            started=True,
        )
    except _PipelineFail as exc:
        _fail(row, exc.code)
        state = 'timeout' if exc.code == CODE_TIMEOUT else 'error'
        message = MSG_TIMEOUT if state == 'timeout' else MSG_ERROR
        return TeacherAIResult(
            ok=False,
            state=state,
            message=message,
            generation_id=row.id,
            failure_code=exc.code,
            quota_remaining=_quota_remaining(user_id),
            started=True,
        )
    current_packet = build_current_packet(child, as_of=as_of)
    current_digest = packet_hash(current_packet)
    if current_digest != digest:
        _fail(row, CODE_STALE)
        return TeacherAIResult(
            ok=False,
            state='stale',
            message=MSG_STALE_DURING,
            generation_id=row.id,
            failure_code=CODE_STALE,
            quota_remaining=_quota_remaining(user_id),
            started=True,
        )
    row.status = GROWTH_AI_STATUS_SUCCESS
    row.parsed_output = parsed
    row.failure_code = None
    row.completed_at = datetime.utcnow()
    if gen_meta is not None:
        row.generator_provider = gen_meta.provider
        row.model = gen_meta.model
        row.prompt_version = gen_meta.prompt_version
        row.output_schema_version = gen_meta.output_schema_version
    if safety_meta is not None:
        row.safety_provider = safety_meta.provider
    db.session.commit()
    view = _success_view(row, current_packet, cached=False, enabled=True)
    return TeacherAIResult(
        ok=True,
        state='success',
        generation_id=row.id,
        interpretation=view['interpretation'],
        evidence=view['evidence'],
        evidence_groups=view.get('evidence_groups'),
        cached=False,
        quota_remaining=_quota_remaining(user_id),
        started=True,
    )


def save_teacher_ai_feedback(*, generation_id, user_id, helpful, comment=None):
    generation = GrowthAIGeneration.query.get(generation_id)
    if generation is None or generation.status != GROWTH_AI_STATUS_SUCCESS:
        return False, 'not_found'
    text = None if comment is None else str(comment).strip()
    if text == '':
        text = None
    if text is not None and len(text) > FEEDBACK_MAX_LEN:
        return False, 'too_long'
    if helpful is False and not text:
        # 싫어요만도 허용. comment는 optional.
        pass
    row = GrowthAIFeedback.query.filter_by(
        generation_id=generation_id, user_id=user_id,
    ).first()
    now = datetime.utcnow()
    if row is None:
        row = GrowthAIFeedback(
            generation_id=generation_id,
            user_id=user_id,
            helpful=bool(helpful),
            comment=text,
            created_at=now,
            updated_at=now,
        )
        db.session.add(row)
    else:
        row.helpful = bool(helpful)
        row.comment = text
        row.updated_at = now
    db.session.commit()
    return True, row.id


def public_result_payload(result: TeacherAIResult):
    payload = {
        'ok': result.ok,
        'state': result.state,
    }
    if result.message:
        payload['message'] = result.message
    if result.generation_id is not None:
        payload['generation_id'] = result.generation_id
    if result.interpretation is not None:
        payload['interpretation'] = result.interpretation
    if result.evidence is not None:
        payload['evidence'] = result.evidence
    if result.evidence_groups is not None:
        payload['evidence_groups'] = result.evidence_groups
    if result.quota_remaining is not None:
        payload['quota_remaining'] = result.quota_remaining
    if result.cached:
        payload['cached'] = True
    payload['started'] = bool(result.started)
    return payload


class _PipelineFail(Exception):
    def __init__(self, code):
        self.code = code


def _run_pipeline(packet, generator, safety, deadline, row):
    row.attempt_count = 1
    db.session.commit()
    rec = _AttemptRecorder(row, 1)
    try:
        deadline.raise_if_expired()
    except DeadlineExceeded:
        rec.finish(ATTEMPT_TIMEOUT, stage='generator', failure_code=CODE_TIMEOUT)
        raise
    try:
        try:
            gen_meta = generator.generate(packet, timeout_s=deadline.remaining())
        except TypeError:
            gen_meta = generator.generate(packet)
    except DeadlineExceeded:
        rec.finish(ATTEMPT_TIMEOUT, stage='generator', failure_code=CODE_TIMEOUT)
        raise
    except GrowthInterpretationConfigError as exc:
        rec.finish(ATTEMPT_CONFIG, stage='generator', failure_code=CODE_CONFIG)
        raise _PipelineFail(CODE_CONFIG) from exc
    except GrowthInterpretationParseError as exc:
        rec.finish(ATTEMPT_PARSE, stage='parse', failure_code=CODE_PARSE)
        raise _PipelineFail(CODE_PARSE) from exc
    except GrowthInterpretationError as exc:
        timeout_like = (
            isinstance(exc, GrowthInterpretationAPIError)
            and 'timeout' in str(exc).lower()
        )
        if timeout_like or deadline.remaining() < MIN_CALL_S:
            rec.finish(ATTEMPT_TIMEOUT, stage='generator', failure_code=CODE_TIMEOUT)
            if timeout_like:
                raise _PipelineFail(CODE_TIMEOUT) from exc
            raise DeadlineExceeded() from exc
        rec.finish(ATTEMPT_GENERATOR, stage='generator', failure_code=CODE_GENERATOR)
        raise _PipelineFail(CODE_GENERATOR) from exc
    rec.capture_generator(gen_meta)
    try:
        deadline.raise_if_expired()
    except DeadlineExceeded:
        rec.finish(ATTEMPT_TIMEOUT, stage='generator', failure_code=CODE_TIMEOUT)
        raise
    parsed = gen_meta.parsed_output if isinstance(gen_meta, GenerationResult) else None
    if not isinstance(parsed, dict):
        rec.finish(ATTEMPT_PARSE, stage='parse', failure_code=CODE_PARSE)
        raise _PipelineFail(CODE_PARSE)
    rec.generated_output = parsed
    if rec.generated_text is None:
        rec.generated_text = gen_meta.raw_output if isinstance(gen_meta, GenerationResult) else None
    validator_started = time.perf_counter()
    validation = validate_teacher_interpretation(packet, parsed)
    rec.validator_latency_ms = int((time.perf_counter() - validator_started) * 1000)
    rec.capture_validator(validation)
    if not validation.valid:
        rec.finish(ATTEMPT_VALIDATOR, stage='validator', failure_code=CODE_VALIDATOR)
        raise _PipelineFail(CODE_VALIDATOR)
    text = visible_interpretation_text(parsed)
    rec.generated_text = rec.generated_text or text
    try:
        deadline.raise_if_expired()
    except DeadlineExceeded:
        rec.finish(ATTEMPT_TIMEOUT, stage='safety', failure_code=CODE_TIMEOUT)
        raise
    decision = _check_safety(safety, text, deadline)
    rec.capture_safety(decision)
    if decision is None or getattr(decision, 'action', None) == ACTION_ERROR:
        rec.finish(ATTEMPT_SAFETY_ERROR, stage='safety', failure_code=CODE_SAFETY_ERROR)
        raise _PipelineFail(CODE_SAFETY_ERROR)
    if decision.action == ACTION_INTERVENED:
        rec.finish(ATTEMPT_SAFETY, stage='safety', failure_code=CODE_SAFETY_BLOCK)
        raise _PipelineFail(CODE_SAFETY_BLOCK)
    if decision.action != ACTION_NONE or decision.safe is not True:
        rec.finish(ATTEMPT_SAFETY_ERROR, stage='safety', failure_code=CODE_SAFETY_ERROR)
        raise _PipelineFail(CODE_SAFETY_ERROR)
    rec.finish(ATTEMPT_SUCCESS, stage='safety', failure_code=None)
    return parsed, gen_meta, decision


def _check_safety(safety, text, deadline):
    started = time.perf_counter()
    try:
        try:
            decision = safety.check_response(text, timeout_s=deadline.remaining())
        except TypeError:
            decision = safety.check_response(text)
    except Exception:
        decision = None
    if decision is not None and getattr(decision, 'latency_ms', None) is None:
        try:
            object.__setattr__(decision, 'latency_ms', int((time.perf_counter() - started) * 1000))
        except Exception:
            pass
    return decision


class _AttemptRecorder:
    def __init__(self, generation, attempt_number):
        self.generation = generation
        self.attempt_number = attempt_number
        self.started_at = datetime.utcnow()
        self.started_mono = time.perf_counter()
        self.generator_provider = generation.generator_provider
        self.model = generation.model
        self.prompt_version = generation.prompt_version
        self.output_schema_version = generation.output_schema_version
        self.generated_output = None
        self.generated_text = None
        self.validator_valid = None
        self.validator_codes = None
        self.validator_issues = None
        self.safety_action = None
        self.safety_reason = None
        self.safety_categories = None
        self.input_tokens = None
        self.output_tokens = None
        self.total_tokens = None
        self.generator_latency_ms = None
        self.validator_latency_ms = None
        self.safety_latency_ms = None

    def capture_generator(self, gen_meta):
        if not isinstance(gen_meta, GenerationResult):
            return
        self.generator_provider = gen_meta.provider
        self.model = gen_meta.model
        self.prompt_version = gen_meta.prompt_version
        self.output_schema_version = gen_meta.output_schema_version
        self.generator_latency_ms = gen_meta.latency_ms
        usage = gen_meta.usage if isinstance(gen_meta.usage, dict) else {}
        self.input_tokens = usage.get('input_tokens')
        self.output_tokens = usage.get('output_tokens')
        self.total_tokens = usage.get('total_tokens')
        self.generated_output = gen_meta.parsed_output if isinstance(gen_meta.parsed_output, dict) else None
        raw = gen_meta.raw_output
        if isinstance(raw, str) and raw.strip():
            self.generated_text = raw
        elif self.generated_output is not None:
            self.generated_text = json.dumps(self.generated_output, ensure_ascii=False)

    def capture_validator(self, validation):
        self.validator_valid = bool(validation.valid)
        issues = []
        codes = []
        for item in validation.violations or ():
            codes.append(item.code)
            issue = {'code': item.code, 'location': item.location}
            if getattr(item, 'evidence_id', None):
                issue['evidence_id'] = item.evidence_id
            issues.append(issue)
        self.validator_codes = codes or None
        self.validator_issues = issues or None

    def capture_safety(self, decision):
        if decision is None:
            self.safety_action = ACTION_ERROR
            self.safety_reason = 'safety provider returned no decision'
            return
        self.safety_action = getattr(decision, 'action', None)
        self.safety_reason = getattr(decision, 'reason', None)
        assessments = getattr(decision, 'assessments', None)
        if assessments:
            self.safety_categories = list(assessments)
        elif isinstance(self.safety_reason, str) and self.safety_reason:
            self.safety_categories = [part.strip() for part in self.safety_reason.split(',') if part.strip()]
        if getattr(decision, 'latency_ms', None) is not None:
            self.safety_latency_ms = decision.latency_ms

    def finish(self, status, *, stage, failure_code):
        try:
            total_ms = int((time.perf_counter() - self.started_mono) * 1000)
            row = GrowthAIAttempt(
                generation_id=self.generation.id,
                attempt_number=self.attempt_number,
                started_at=self.started_at,
                completed_at=datetime.utcnow(),
                generator_provider=self.generator_provider,
                model=self.model,
                prompt_version=self.prompt_version,
                output_schema_version=self.output_schema_version,
                stage=stage,
                status=status,
                generated_output=self.generated_output,
                generated_text=_clip_text(self.generated_text),
                validator_valid=self.validator_valid,
                validator_codes=self.validator_codes,
                validator_issues=self.validator_issues,
                safety_action=self.safety_action,
                safety_reason=_clip_text(self.safety_reason, 255),
                safety_categories=self.safety_categories,
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                total_tokens=self.total_tokens,
                generator_latency_ms=self.generator_latency_ms,
                validator_latency_ms=self.validator_latency_ms,
                safety_latency_ms=self.safety_latency_ms,
                total_latency_ms=total_ms,
                failure_code=failure_code,
            )
            db.session.add(row)
            db.session.commit()
        except Exception:
            db.session.rollback()


def _clip_text(value, limit=20000):
    if not isinstance(value, str):
        return value
    if len(value) <= limit:
        return value
    return value[:limit]


def attempt_diagnostic_query():
    """B5 eval이 읽는 attempt 필드. 일반 UI/API에 노출하지 않는다."""
    return GrowthAIAttempt.query


def _success_view(row, packet, *, cached, enabled):
    parsed = row.parsed_output if isinstance(row.parsed_output, dict) else {}
    evidence = present_cited_evidence_bundle(packet, parsed)
    return {
        'state': 'success',
        'enabled': enabled,
        'cached': cached,
        'generation_id': row.id,
        'interpretation': _ui_interpretation(parsed),
        'evidence': evidence['items'],
        'evidence_groups': evidence,
        'timeout_ms': FRONTEND_TIMEOUT_MS,
        'message': None,
    }


def _ui_interpretation(parsed):
    def text_of(key):
        item = parsed.get(key) if isinstance(parsed.get(key), dict) else {}
        return (item.get('text') or '').strip()

    observations = []
    for item in parsed.get('observations') or []:
        if isinstance(item, dict) and isinstance(item.get('text'), str) and item['text'].strip():
            observations.append(item['text'].strip())
    actions = []
    for key in ('next_actions', 'suggestions'):
        for item in parsed.get(key) or []:
            if isinstance(item, dict) and isinstance(item.get('text'), str) and item['text'].strip():
                actions.append(item['text'].strip())
        if actions:
            break
    priority = text_of('priority_insight') or text_of('summary')
    return {
        'priority_insight': priority,
        'interpretation': text_of('interpretation'),
        'summary': priority,
        'observations': observations,
        'next_actions': actions,
        'suggestions': actions,
        'next_check': text_of('next_check'),
    }


def _latest_success(child_id, digest, signature):
    return (
        GrowthAIGeneration.query.filter_by(
            child_id=child_id,
            packet_hash=digest,
            runtime_signature=signature,
            status=GROWTH_AI_STATUS_SUCCESS,
        )
        .order_by(GrowthAIGeneration.completed_at.desc(), GrowthAIGeneration.id.desc())
        .first()
    )


def _latest_success_any_hash(child_id, signature):
    return (
        GrowthAIGeneration.query.filter_by(
            child_id=child_id,
            runtime_signature=signature,
            status=GROWTH_AI_STATUS_SUCCESS,
        )
        .order_by(GrowthAIGeneration.completed_at.desc(), GrowthAIGeneration.id.desc())
        .first()
    )


def _active_pending(child_id, digest, signature):
    cutoff = datetime.utcnow() - timedelta(seconds=PENDING_STALE_S)
    stale_rows = GrowthAIGeneration.query.filter(
        GrowthAIGeneration.child_id == child_id,
        GrowthAIGeneration.packet_hash == digest,
        GrowthAIGeneration.runtime_signature == signature,
        GrowthAIGeneration.status == GROWTH_AI_STATUS_PENDING,
        GrowthAIGeneration.created_at < cutoff,
    ).all()
    for row in stale_rows:
        _fail(row, CODE_TIMEOUT)
    return (
        GrowthAIGeneration.query.filter_by(
            child_id=child_id,
            packet_hash=digest,
            runtime_signature=signature,
            status=GROWTH_AI_STATUS_PENDING,
        )
        .order_by(GrowthAIGeneration.created_at.desc())
        .first()
    )


def _quota_used(user_id):
    start = _kst_day_start_utc_naive()
    return GrowthAIGeneration.query.filter(
        GrowthAIGeneration.requested_by_user_id == user_id,
        GrowthAIGeneration.created_at >= start,
    ).count()


def _quota_remaining(user_id):
    if user_id is None:
        return None
    used = _quota_used(user_id)
    remaining = DAILY_QUOTA - used
    return remaining if remaining > 0 else 0


def _kst_day_start_utc_naive(day=None):
    day = day or kst_today()
    start = datetime.combine(day, dt_time.min, tzinfo=KST)
    return start.astimezone(timezone.utc).replace(tzinfo=None)


def _fail(row, code):
    row.status = GROWTH_AI_STATUS_FAILED
    row.failure_code = code
    row.parsed_output = None
    row.completed_at = datetime.utcnow()
    db.session.commit()
