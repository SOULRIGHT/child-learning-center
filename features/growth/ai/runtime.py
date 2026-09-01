"""Teacher Growth AI application service. route에 provider를 나열하지 않는다."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, timedelta, timezone

from extensions import db
from feature_models import (
    GROWTH_AI_STATUS_FAILED,
    GROWTH_AI_STATUS_PENDING,
    GROWTH_AI_STATUS_SUCCESS,
    GrowthAIFeedback,
    GrowthAIGeneration,
)
from features.dates import KST, kst_today
from features.growth.ai.bedrock_safety import (
    ACTION_ERROR,
    ACTION_INTERVENED,
    ACTION_NONE,
    AwsBedrockGuardrailSafetyProvider,
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
from features.growth.ai.presenter import present_cited_evidence
from features.growth.ai.prompt import GROWTH_TEACHER_PROMPT_VERSION
from features.growth.ai.provider import (
    GenerationResult,
    GrowthInterpretationAPIError,
    GrowthInterpretationConfigError,
    GrowthInterpretationError,
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
MIN_RETRY_REMAINING_S = 4.0
MIN_SAFETY_RETRY_S = 2.0
PENDING_STALE_S = 30
FEEDBACK_MAX_LEN = 1000
TEACHER_AI_ROLES = frozenset({'돌봄선생님', '센터장', '개발자'})

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
    quota_remaining: int | None = None
    cached: bool = False
    failure_code: str | None = None


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
        return TeacherAIResult(ok=False, state='disabled', message=MSG_DISABLED, failure_code=CODE_DISABLED)
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
            cached=True,
            quota_remaining=_quota_remaining(user_id),
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
        )
    used = _quota_used(user_id)
    if used >= DAILY_QUOTA:
        return TeacherAIResult(
            ok=False,
            state='quota',
            message=MSG_QUOTA,
            failure_code=CODE_QUOTA,
            quota_remaining=0,
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
        cached=False,
        quota_remaining=_quota_remaining(user_id),
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
    if result.quota_remaining is not None:
        payload['quota_remaining'] = result.quota_remaining
    if result.cached:
        payload['cached'] = True
    return payload


class _PipelineFail(Exception):
    def __init__(self, code):
        self.code = code


def _run_pipeline(packet, generator, safety, deadline, row):
    regenerated = False
    safety_retried = False
    parsed = None
    gen_meta = None
    while True:
        deadline.raise_if_expired()
        try:
            gen_meta = generator.generate(packet, timeout_s=deadline.remaining())
        except TypeError:
            gen_meta = generator.generate(packet)
        except DeadlineExceeded:
            raise
        except GrowthInterpretationConfigError as exc:
            raise _PipelineFail(CODE_CONFIG) from exc
        except GrowthInterpretationError as exc:
            if deadline.remaining() < MIN_CALL_S:
                raise DeadlineExceeded() from exc
            if not regenerated and deadline.remaining() >= MIN_RETRY_REMAINING_S:
                regenerated = True
                row.attempt_count = (row.attempt_count or 1) + 1
                db.session.commit()
                continue
            if isinstance(exc, GrowthInterpretationAPIError) and 'timeout' in str(exc).lower():
                raise _PipelineFail(CODE_TIMEOUT) from exc
            raise _PipelineFail(CODE_GENERATOR) from exc
        deadline.raise_if_expired()
        parsed = gen_meta.parsed_output if isinstance(gen_meta, GenerationResult) else None
        if not isinstance(parsed, dict):
            if not regenerated and deadline.remaining() >= MIN_RETRY_REMAINING_S:
                regenerated = True
                row.attempt_count = (row.attempt_count or 1) + 1
                db.session.commit()
                continue
            raise _PipelineFail(CODE_GENERATOR)
        validation = validate_teacher_interpretation(packet, parsed)
        if not validation.valid:
            if not regenerated and deadline.remaining() >= MIN_RETRY_REMAINING_S:
                regenerated = True
                row.attempt_count = (row.attempt_count or 1) + 1
                db.session.commit()
                continue
            raise _PipelineFail(CODE_VALIDATOR)
        text = visible_interpretation_text(parsed)
        deadline.raise_if_expired()
        try:
            decision = safety.check_response(text, timeout_s=deadline.remaining())
        except TypeError:
            decision = safety.check_response(text)
        except Exception:
            decision = None
        if decision is None or getattr(decision, 'action', None) == ACTION_ERROR:
            if not safety_retried and deadline.remaining() >= MIN_SAFETY_RETRY_S:
                safety_retried = True
                row.attempt_count = (row.attempt_count or 1) + 1
                db.session.commit()
                try:
                    decision = safety.check_response(text, timeout_s=deadline.remaining())
                except TypeError:
                    decision = safety.check_response(text)
                except Exception:
                    raise _PipelineFail(CODE_SAFETY_ERROR)
            if decision is None or getattr(decision, 'action', None) == ACTION_ERROR:
                raise _PipelineFail(CODE_SAFETY_ERROR)
        if decision.action == ACTION_INTERVENED:
            if not regenerated and deadline.remaining() >= MIN_RETRY_REMAINING_S:
                regenerated = True
                row.attempt_count = (row.attempt_count or 1) + 1
                db.session.commit()
                continue
            raise _PipelineFail(CODE_SAFETY_BLOCK)
        if decision.action != ACTION_NONE or decision.safe is not True:
            raise _PipelineFail(CODE_SAFETY_ERROR)
        return parsed, gen_meta, decision


def _success_view(row, packet, *, cached, enabled):
    parsed = row.parsed_output if isinstance(row.parsed_output, dict) else {}
    return {
        'state': 'success',
        'enabled': enabled,
        'cached': cached,
        'generation_id': row.id,
        'interpretation': _ui_interpretation(parsed),
        'evidence': present_cited_evidence(packet, parsed),
        'timeout_ms': FRONTEND_TIMEOUT_MS,
        'message': None,
    }


def _ui_interpretation(parsed):
    summary = parsed.get('summary') if isinstance(parsed.get('summary'), dict) else {}
    observations = []
    for item in parsed.get('observations') or []:
        if isinstance(item, dict) and isinstance(item.get('text'), str) and item['text'].strip():
            observations.append(item['text'].strip())
    suggestions = []
    for item in parsed.get('suggestions') or []:
        if isinstance(item, dict) and isinstance(item.get('text'), str) and item['text'].strip():
            suggestions.append(item['text'].strip())
    return {
        'summary': (summary.get('text') or '').strip(),
        'observations': observations,
        'suggestions': suggestions,
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
