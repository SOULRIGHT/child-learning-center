"""Teacher assistant application service. form write 없음.

same-provider hidden retry 금지.
retryable infrastructure failure에 한해 최대 1회 audited cross-provider failover만 허용한다.

Browser conversation / LLM working context / server audit 를 섞지 않는다.
"""
from __future__ import annotations

import copy
import time

from features.assistant.audit import (
    elapsed_ms,
    new_request_id,
    now_iso,
    record_request_end,
    record_request_start,
    start_timer,
)
from features.assistant.config import (
    assistant_fallback_model,
    assistant_primary_timeout_s,
    assistant_provider_name,
    assistant_request_timeout_s,
    current_role,
    is_assistant_fallback_enabled,
)
from features.assistant.context import context_scope, sanitize_page_context
from features.assistant.conversation import (
    apply_pending_confirmation,
    apply_pending_turn,
    capability_payload,
    child_resolution_payload,
    empty_state,
    fake_follow_up_call,
    is_capability_question,
    pending_need_child,
    public_conversation_state,
    sanitize_conversation_state,
    tool_page_context,
    update_state_from_tools,
)
from features.assistant.copy import (
    FALLBACK,
    MSG_GROUNDING_UNSAFE,
    MSG_GUARDRAIL_BLOCK,
    MSG_GUARDRAIL_UNAVAILABLE,
    MSG_RECORD_UNAVAILABLE,
    MSG_REQUEST_TIMEOUT,
    NEW_CONVERSATION,
    PROVIDER_ERROR,
    QUESTION_LIMIT_REPLY,
    opening_text,
)
from features.assistant.deadline import RequestDeadline
from features.assistant.failures import (
    FAILURE_FALLBACK_FAILED,
    FAILURE_GROUNDING,
    FAILURE_GUARDRAIL_BLOCK,
    FAILURE_GUARDRAIL_ERROR,
    FAILURE_PROVIDER_TIMEOUT,
    FAILURE_REQUEST_DEADLINE,
    FAILURE_TOOL,
    FAILURE_UNEXPECTED,
    AssistantDeadlineError,
    AssistantGroundingError,
    AssistantGuardrailBlock,
    AssistantGuardrailError,
    AssistantToolFailure,
)
from features.assistant.grounding import (
    SOURCE_COMPOSE,
    SOURCE_GUARDRAIL,
    SOURCE_LLM,
    SOURCE_NAVIGATION,
    SOURCE_PENDING,
    SOURCE_SAFETY,
    validate_grounding,
)
from features.assistant.intents import (
    bootstrap_payload,
    explain_page_payload,
    interpret_user_text,
    navigate_payload,
    onboarding_payload,
    quick_actions,
)
from features.assistant.policy import gated_execute
from features.assistant.provider import (
    AssistantProviderBadRequestError,
    AssistantProviderConfigError,
    AssistantProviderError,
    AssistantProviderRetryableError,
    compose_from_tools,
    get_assistant_provider,
)
from features.assistant.resolve import select_child_resolution
from features.assistant.safety import sanitize_output, safety_override_payload
from features.assistant.guardrail import (
    ACTION_ERROR,
    ACTION_INTERVENED,
    ACTION_NONE,
    get_assistant_guardrail,
)

MAX_MESSAGES = 48
MAX_CONTENT_LEN = 2000
MAX_LLM_MESSAGES = 12
QUESTION_LIMIT = 10
VALID_KINDS = frozenset({'chat', 'llm', 'system', 'confirm', 'quick', 'onboarding', 'nav'})
LLM_CONTEXT_KINDS = frozenset({'chat', 'llm'})
# Count = 정상 처리된 자유 질문. LLM 호출 횟수가 아니다.
# 포함: LLM/facts/deterministic safety/policy/Product Contract refusal
# 제외: 실패·timeout, candidate/confirm/domain slot, nav/onboarding/quick
COUNTED_KINDS = frozenset({'chat', 'llm'})
ALLOWED_INTENTS = frozenset({
    'bootstrap',
    'chat',
    'continue_setup',
    'explain_page',
    'navigate',
})
QUICK_INTENTS = frozenset({
    'bootstrap',
    'continue_setup',
    'explain_page',
    'navigate',
})
INTENT_KIND = {
    'bootstrap': 'system',
    'continue_setup': 'onboarding',
    'explain_page': 'system',
    'navigate': 'nav',
}


class AssistantRequestError(ValueError):
    """잘못된 JSON 요청."""


def _as_text(value, limit=MAX_CONTENT_LEN):
    if not isinstance(value, str):
        return ''
    return value.strip()[:limit]


def parse_messages(raw):
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AssistantRequestError('invalid_messages')
    messages = []
    window = raw[-MAX_MESSAGES:]
    for item in window:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        if role not in {'user', 'assistant'}:
            continue
        content = _as_text(item.get('content'))
        if not content:
            continue
        scope = item.get('context_scope')
        if not isinstance(scope, dict):
            scope = {}
        child_id = scope.get('child_id')
        try:
            child_id = int(child_id) if child_id is not None else None
        except (TypeError, ValueError):
            child_id = None
        kind = item.get('kind')
        if kind not in VALID_KINDS:
            kind = 'chat'
        messages.append({
            'role': role,
            'content': content,
            'kind': kind,
            'context_scope': {
                'endpoint': _as_text(scope.get('endpoint'), 120),
                **({'child_id': child_id} if child_id else {}),
            },
        })
    return messages


def provider_messages(messages):
    """LLM working context: 최근 12개의 자유 대화만. onboarding/quick/nav/confirm 제외."""
    filtered = []
    for item in messages or ():
        kind = item.get('kind') or 'chat'
        if kind not in LLM_CONTEXT_KINDS:
            continue
        filtered.append({
            'role': item.get('role'),
            'content': item.get('content'),
            'kind': kind,
            'context_scope': item.get('context_scope') or {},
        })
    return filtered[-MAX_LLM_MESSAGES:]


def count_chat_questions(messages):
    n = 0
    for item in messages or ():
        if item.get('role') != 'user':
            continue
        kind = item.get('kind') or 'chat'
        if kind in COUNTED_KINDS:
            n += 1
    return n


def _uncount_last_if_tagged(messages, count):
    if not messages:
        return count
    last = messages[-1]
    if last.get('role') != 'user':
        return count
    if (last.get('kind') or 'chat') in COUNTED_KINDS:
        return max(0, count - 1)
    return count


def _assistant_message(text, page_context, *, kind='system'):
    return {
        'role': 'assistant',
        'content': text,
        'kind': kind,
        'context_scope': context_scope(page_context),
    }


def _public_actions(actions):
    public = []
    for action in actions or ():
        if not isinstance(action, dict):
            continue
        item = {
            'type': action.get('type') or 'navigate',
            'label': action.get('label') or '',
        }
        if action.get('url'):
            item['url'] = action['url']
        if action.get('destination'):
            item['destination'] = action['destination']
        if action.get('auto'):
            item['auto'] = True
        if action.get('params'):
            item['params'] = action['params']
        if action.get('type') == 'reply' or action.get('content'):
            item['type'] = action.get('type') or item['type']
            if action.get('content'):
                item['content'] = _as_text(action.get('content'), 80)
        if action.get('type') == 'new_conversation':
            item['type'] = 'new_conversation'
        public.append(item)
    return public


def _public_sources(sources):
    public = []
    for source in sources or ():
        if not isinstance(source, dict):
            continue
        kind = source.get('kind')
        if kind not in {'data', 'help'}:
            kind = 'data'
        item = {
            'kind': kind,
            'label': _as_text(source.get('label'), 80) or '근거',
        }
        evidence_id = source.get('evidence_id')
        if isinstance(evidence_id, str) and evidence_id.strip():
            item['evidence_id'] = evidence_id.strip()[:120]
        if source.get('url'):
            item['url'] = source['url']
        if source.get('destination'):
            item['destination'] = source['destination']
        if 'available' in source:
            item['available'] = bool(source.get('available'))
        public.append(item)
        if len(public) >= 12:
            break
    return public


def _result(*, text, page_context, actions=None, status=None, character_state='idle',
            quick_actions=None, error=None, ok=True, extras=None, candidates=None,
            handled=None, sources=None, conversation_state=None, pending_hint=None,
            destination=None, source_kind=None, kind=None, **_ignored):
    deny = error in {'unknown_destination', 'forbidden', 'invalid_child'}
    merged_status = dict(status or {})
    merged_status['conversation_state'] = public_conversation_state(conversation_state)
    payload = {
        'ok': False if deny else ok,
        'message': _assistant_message(text, page_context, kind=kind or source_kind or 'system'),
        'actions': _public_actions(actions),
        'sources': _public_sources(sources),
        'status': merged_status,
        'character_state': character_state,
        'quick_actions': quick_actions if quick_actions is not None else quick_actions_for(page_context),
    }
    if error:
        payload['error'] = error
    if candidates:
        payload['candidates'] = candidates
    if extras:
        payload.update(extras)
    return payload


def quick_actions_for(page_context):
    return quick_actions(page_context)


def complete_assistant(
    *,
    messages=None,
    page_context=None,
    intent=None,
    destination=None,
    params=None,
    conversation_state=None,
    clock=None,
):
    started = start_timer()
    request_id = new_request_id()
    role = current_role()
    page_context = sanitize_page_context(page_context)
    messages = parse_messages(messages)
    intent = (intent or 'chat').strip()
    if intent not in ALLOWED_INTENTS:
        raise AssistantRequestError('invalid_intent')
    original_state = sanitize_conversation_state(conversation_state, page_context=page_context)
    working_state = copy.deepcopy(original_state)
    last = _last_user(messages)
    audit = {
        'request_id': request_id,
        'timestamp': now_iso(),
        'user_id': _audit_user_id(),
        'user_role': role,
        'page_endpoint': (page_context or {}).get('endpoint'),
        'page_child_id': (page_context or {}).get('child_id'),
        'as_of': str((page_context or {}).get('as_of') or '') or None,
        'user_prompt': last if intent == 'chat' else '',
        'provider': assistant_provider_name(),
        'model': _audit_model(),
        'intent': intent,
        'source_kind': INTENT_KIND.get(intent, 'chat'),
        'conversation_state': public_conversation_state(original_state),
        'primary_provider': assistant_provider_name(),
    }
    record_request_start(audit)
    try:
        deadline = RequestDeadline(assistant_request_timeout_s(), clock=clock or time.monotonic)
        audit['deadline_ms'] = int(deadline.seconds * 1000)
        payload, meta = _dispatch(
            messages=messages,
            page_context=page_context,
            intent=intent,
            destination=destination,
            params=params,
            state=working_state,
            last=last,
            role=role,
            audit=audit,
            deadline=deadline,
        )
        _enforce_output_guardrail(payload, meta, intent=intent, deadline=deadline, audit=audit)
    except AssistantGuardrailBlock as exc:
        return _guardrail_block_result(
            page_context=page_context,
            original_state=original_state,
            audit=audit,
            started=started,
            messages=messages,
            source=getattr(exc, 'source', 'input'),
        )
    except AssistantGuardrailError:
        return _safe_failure(
            text=MSG_GUARDRAIL_UNAVAILABLE,
            page_context=page_context,
            original_state=original_state,
            audit=audit,
            started=started,
            messages=messages,
            failure_class=FAILURE_GUARDRAIL_ERROR,
            error='guardrail_error',
        )
    except AssistantDeadlineError:
        return _safe_failure(
            text=MSG_REQUEST_TIMEOUT,
            page_context=page_context,
            original_state=original_state,
            audit=audit,
            started=started,
            messages=messages,
            failure_class=FAILURE_REQUEST_DEADLINE,
            error='request_deadline',
        )
    except (AssistantToolFailure, AssistantGroundingError) as exc:
        if isinstance(exc, AssistantGroundingError):
            return _safe_failure(
                text=MSG_GROUNDING_UNSAFE,
                page_context=page_context,
                original_state=original_state,
                audit=audit,
                started=started,
                messages=messages,
                failure_class=FAILURE_GROUNDING,
                error='grounding_failure',
            )
        return _safe_failure(
            text=MSG_RECORD_UNAVAILABLE,
            page_context=page_context,
            original_state=original_state,
            audit=audit,
            started=started,
            messages=messages,
            failure_class=getattr(exc, 'failure_class', FAILURE_TOOL),
            error='tool_failure',
        )
    except AssistantProviderError as exc:
        audit['error'] = 'provider_error'
        audit['final_status'] = 'provider_error'
        audit['failure_class'] = getattr(exc, 'failure_class', None) or audit.get('failure_class') or 'provider_error'
        audit['total_latency_ms'] = elapsed_ms(started)
        audit['elapsed_ms'] = audit['total_latency_ms']
        record_request_end(audit)
        raise AssistantProviderError(PROVIDER_ERROR) from exc
    except Exception:
        audit['error'] = 'error'
        audit['final_status'] = 'error'
        audit['failure_class'] = FAILURE_UNEXPECTED
        audit['total_latency_ms'] = elapsed_ms(started)
        audit['elapsed_ms'] = audit['total_latency_ms']
        record_request_end(audit)
        raise
    if meta.get('answer_source'):
        audit['answer_source'] = meta['answer_source']
    return _decorate_result(
        payload,
        audit=audit,
        started=started,
        messages=messages,
        conversation_state=meta.get('conversation_state') or working_state,
        kind=meta.get('kind') or 'system',
        feedback_enabled=bool(meta.get('feedback_enabled')),
        counted=bool(meta.get('counted')),
        limit_reached=bool(meta.get('limit_reached')),
        uncount_kind=meta.get('uncount_kind'),
    )


def _dispatch(*, messages, page_context, intent, destination, params, state, last, role, audit, deadline=None):
    if intent == 'bootstrap':
        data = bootstrap_payload(page_context, role)
        next_state = empty_state() if not (page_context or {}).get('child_id') else state
        return _result(
            page_context=page_context,
            **data,
            extras={'bootstrap': True},
            conversation_state=next_state,
            kind='system',
        ), {'kind': 'system', 'conversation_state': next_state}

    if intent == 'continue_setup':
        data = onboarding_payload(role)
        return _result(
            page_context=page_context, **data, conversation_state=state, kind='onboarding',
        ), {'kind': 'onboarding', 'conversation_state': state}

    if intent == 'explain_page':
        data = explain_page_payload(page_context)
        return _result(
            page_context=page_context, **data, conversation_state=state, kind='system',
        ), {'kind': 'system', 'conversation_state': state}

    if intent == 'navigate' or (destination and intent in QUICK_INTENTS):
        data = navigate_payload(
            destination,
            params or {},
            page_context=page_context,
            auto=True,
            role=role,
        )
        state = _apply_payload_hint(state, data)
        return _result(
            page_context=page_context, **data, conversation_state=state, kind='nav',
        ), {'kind': 'nav', 'conversation_state': state}

    if state.get('segment_closed') and intent == 'chat':
        return _closed_segment_payload(page_context)

    pending_before = dict(state.get('pending_action') or {})
    pending_done = apply_pending_confirmation(
        last,
        state=state,
        page_context=page_context,
        role=role,
    )
    if pending_done:
        state = _apply_payload_hint(state, pending_done)
        text = sanitize_output(pending_done.get('text') or '', user_text=last)
        pending_done = dict(pending_done)
        pending_done['text'] = text
        for key in ('selected_candidate_index', 'candidate_count', 'match_type'):
            if pending_done.get(key) is not None:
                audit[key] = pending_done[key]
        return _result(
            page_context=page_context, **pending_done, conversation_state=state, kind='confirm',
        ), {'kind': 'confirm', 'conversation_state': state, 'counted': False, 'answer_source': SOURCE_PENDING}

    counted = count_chat_questions(messages)
    if intent == 'chat' and counted > QUESTION_LIMIT:
        return _result(
            text=QUESTION_LIMIT_REPLY,
            page_context=page_context,
            actions=[],
            character_state='help',
            conversation_state=state,
            kind='system',
            error='question_limit',
            ok=True,
        ), {'kind': 'system', 'conversation_state': state, 'limit_reached': True}

    if intent == 'chat' and last:
        _enforce_input_guardrail(last, deadline=deadline, audit=audit)

    contract = safety_override_payload(last)
    if contract:
        return _result(
            page_context=page_context,
            text=contract['text'],
            actions=[],
            character_state=contract.get('character_state') or 'help',
            conversation_state=state,
            kind='system',
        ), {'kind': 'system', 'conversation_state': state, 'counted': True, 'answer_source': SOURCE_SAFETY}

    live = assistant_provider_name() == 'openai'
    if live:
        payload, state, feedback_enabled, counted, source = _complete_live(
            messages=messages,
            page_context=page_context,
            state=state,
            pending_before=pending_before,
            last=last,
            role=role,
            audit=audit,
            deadline=deadline,
        )
        return payload, {
            'kind': 'llm' if feedback_enabled else payload['message'].get('kind') or 'system',
            'feedback_enabled': feedback_enabled,
            'counted': counted,
            'conversation_state': state,
            'answer_source': source,
        }
    payload, state, kind, counted, source = _complete_fake(
        messages=messages,
        page_context=page_context,
        state=state,
        last=last,
        role=role,
        audit=audit,
        deadline=deadline,
    )
    return payload, {
        'kind': kind,
        'counted': counted,
        'conversation_state': state,
        'answer_source': source,
    }


def _complete_live(*, messages, page_context, state, pending_before, last, role, audit, deadline=None):
    if deadline is not None:
        deadline.raise_if_expired()
    try:
        completion = _run_live_provider(
            messages=messages,
            page_context=page_context,
            state=state,
            role=role,
            audit=audit,
            deadline=deadline,
        )
    except AssistantDeadlineError:
        raise
    except AssistantToolFailure:
        raise
    except (AssistantProviderConfigError, AssistantProviderBadRequestError):
        raise
    except AssistantProviderRetryableError:
        raise
    except AssistantProviderError as exc:
        raise AssistantProviderError(PROVIDER_ERROR) from exc
    tool_results = getattr(completion, 'tool_results', None) or []
    audit['tool_names'] = [item.get('name') for item in tool_results if item.get('name')]
    selected_pending = _llm_selected_pending_completion(
        pending_before,
        last,
        state=state,
        page_context=page_context,
        role=role,
        tool_results=tool_results,
    )
    if selected_pending:
        state = _apply_payload_hint(state, selected_pending)
        return _result(
            page_context=page_context,
            **selected_pending,
            conversation_state=state,
            kind='confirm',
        ), state, False, False, SOURCE_PENDING
    pending_fallback = _llm_first_pending_fallback(
        pending_before,
        last,
        state=state,
        page_context=page_context,
        role=role,
        audit=audit,
        tool_results=tool_results,
        completion_text=completion.text,
    )
    if pending_fallback:
        state = _apply_payload_hint(state, pending_fallback)
        return _result(
            page_context=page_context,
            **pending_fallback,
            conversation_state=state,
            kind='confirm',
        ), state, False, False, SOURCE_PENDING
    state = _prepare_resolution_pending(state, last, tool_results)
    state = update_state_from_tools(state, tool_results, page_context=page_context, user_text=last)
    slot_completion = _is_pending_slot_completion(
        pending_before,
        last,
        tool_results,
    )
    resolution = child_resolution_payload(state, tool_results)
    if resolution:
        for key in ('selected_candidate_index', 'candidate_count', 'match_type'):
            if resolution.get(key) is not None:
                audit[key] = resolution[key]
        return _result(
            page_context=page_context,
            **resolution,
            conversation_state=state,
            kind='confirm',
        ), state, False, not slot_completion, SOURCE_PENDING
    contract = safety_override_payload(last)
    if contract:
        return _result(
            page_context=page_context,
            text=contract['text'],
            actions=[],
            character_state=contract.get('character_state') or 'help',
            conversation_state=state,
            kind='system',
        ), state, False, True, SOURCE_SAFETY
    text = sanitize_output(
        completion.text,
        user_text=last,
        tool_results=tool_results,
        system_prompt=_live_prompt_marker(),
    )
    from features.assistant.facts import infer_metric_focus
    names = {item.get('name') for item in tool_results or ()}
    should_compose = infer_metric_focus(last) or any(
        str(name).endswith('_facts') or name in {'search_child', 'get_subject_peer_reference'}
        for name in names
    )
    answer_source = SOURCE_LLM
    if should_compose and tool_results:
        composed = compose_from_tools(tool_results, user_text=last, role=role)
        if composed.text and composed.text != FALLBACK:
            text = sanitize_output(
                composed.text,
                user_text=last,
                tool_results=tool_results,
                system_prompt=_live_prompt_marker(),
            )
            answer_source = SOURCE_COMPOSE
            if composed.sources:
                completion.sources = composed.sources
            if composed.actions:
                completion.actions = composed.actions
    actions = list(completion.actions or [])
    text = _align_navigate_text(text, actions)
    sources = getattr(completion, 'sources', None) or []
    from features.assistant.navigation import is_explicit_go, match_destination_from_text
    clear_nav = is_explicit_go(last) and match_destination_from_text(last)
    if (
        not any(item.get('url') for item in actions)
        and (
            not text or text == FALLBACK or clear_nav
        )
        and (not sources or clear_nav)
    ):
        interpreted = interpret_user_text(
            last,
            tool_page_context(page_context, state),
            role=role,
        )
        if interpreted.get('handled'):
            state = _apply_payload_hint(state, interpreted)
            text = sanitize_output(interpreted.get('text') or '', user_text=last)
            interpreted = dict(interpreted)
            interpreted['text'] = text
            kind = 'nav' if interpreted.get('actions') else 'system'
            return _result(
                page_context=page_context, **interpreted, conversation_state=state, kind=kind,
            ), state, False, True, SOURCE_NAVIGATION
    if _should_auto_navigate(actions, tool_results, last, state):
        actions = [dict(item, auto=True) if item.get('url') else item for item in actions]
    text, grounded_completion = _finalize_grounded_text(
        text,
        user_text=last,
        tool_results=tool_results,
        state=state,
        page_context=page_context,
        answer_source=answer_source,
        role=role,
        audit=audit,
    )
    if grounded_completion is not None:
        if grounded_completion.sources:
            completion.sources = grounded_completion.sources
        if grounded_completion.actions:
            actions = list(grounded_completion.actions)
    status = dict(completion.status or {})
    return _result(
        text=text,
        page_context=page_context,
        actions=actions,
        status=status,
        character_state=completion.character_state or 'idle',
        sources=getattr(completion, 'sources', None),
        conversation_state=state,
        kind='llm',
    ), state, True, not slot_completion, answer_source


def _complete_fake(*, messages, page_context, state, last, role, audit, deadline=None):
    if deadline is not None:
        deadline.raise_if_expired()
    if is_capability_question(last):
        data = capability_payload()
        return _result(
            page_context=page_context, **data, conversation_state=state, kind='system',
        ), state, 'system', True, SOURCE_SAFETY
    override = safety_override_payload(last)
    if override:
        return _result(
            page_context=page_context,
            text=override['text'],
            actions=[],
            character_state=override.get('character_state') or 'help',
            conversation_state=state,
            kind='system',
        ), state, 'system', True, SOURCE_SAFETY
    pending = state.get('pending_action') or {}
    if pending.get('awaiting') == 'child':
        from features.assistant.resolve import resolve_children
        resolved = resolve_children(last)
        if resolved.get('matches'):
            pending_done = apply_pending_turn(
                last,
                state=state,
                page_context=page_context,
                role=role,
            )
            if pending_done:
                state = _apply_payload_hint(state, pending_done)
                return _result(
                    page_context=page_context,
                    **pending_done,
                    conversation_state=state,
                    kind='confirm',
                ), state, 'confirm', False, SOURCE_PENDING
    follow = fake_follow_up_call(last, state)
    if follow:
        name, arguments = follow
        try:
            result = gated_execute(
                name,
                arguments,
                page_context=tool_page_context(page_context, state),
                role=role,
                conversation_state=state,
                audit=audit,
            )
        except Exception as exc:
            raise AssistantToolFailure('canonical tool failed') from exc
        completion = compose_from_tools(
            [{'name': name, 'arguments': arguments, 'result': result}],
            user_text=last,
            role=role,
        )
        state = update_state_from_tools(
            state,
            [{'name': name, 'arguments': arguments, 'result': result}],
            page_context=page_context,
            user_text=last,
        )
        return _completion_result(
            completion, page_context, state, last, kind='chat', role=role, audit=audit,
        ), state, 'chat', True, SOURCE_COMPOSE

    interpreted = interpret_user_text(
        last,
        tool_page_context(page_context, state),
        role=role,
    )
    if interpreted.get('handled'):
        state = _apply_payload_hint(state, interpreted)
        text = sanitize_output(interpreted.get('text') or '', user_text=last)
        interpreted = dict(interpreted)
        interpreted['text'] = text
        kind = 'nav' if interpreted.get('actions') else 'system'
        return _result(
            page_context=page_context, **interpreted, conversation_state=state, kind=kind,
        ), state, kind, False, SOURCE_NAVIGATION if kind == 'nav' else SOURCE_LLM

    try:
        completion = get_assistant_provider().complete(
            messages=provider_messages(messages),
            page_context=tool_page_context(page_context, state),
            conversation_state=state,
            role=role,
            audit=audit,
            deadline=deadline,
            timeout_s=deadline.provider_timeout(assistant_primary_timeout_s()) if deadline else None,
        )
    except AssistantProviderError as exc:
        raise AssistantProviderError(PROVIDER_ERROR) from exc
    tool_results = getattr(completion, 'tool_results', None) or []
    state = update_state_from_tools(state, tool_results, page_context=page_context, user_text=last)
    if getattr(completion, 'status', None) and completion.status.get('pending_need_child'):
        state['pending_action'] = pending_need_child(tool='get_growth_facts')
    source = SOURCE_COMPOSE if tool_results else SOURCE_LLM
    return _completion_result(
        completion, page_context, state, last, kind='chat', role=role, audit=audit, answer_source=source,
    ), state, 'chat', True, source


def _run_live_provider(*, messages, page_context, state, audit, deadline, role=None):
    primary = get_assistant_provider()
    primary_deadline = None
    primary_timeout = None
    if deadline is not None:
        primary_deadline = deadline.capped(assistant_primary_timeout_s())
        primary_timeout = min(primary_deadline.remaining(), deadline.remaining())
    provider_started = start_timer()
    try:
        if primary_timeout is not None and primary_timeout <= 0:
            raise AssistantDeadlineError()
        completion = primary.complete(
            messages=provider_messages(messages),
            page_context=tool_page_context(page_context, state),
            conversation_state=state,
            role=role,
            audit=audit,
            deadline=primary_deadline,
            timeout_s=primary_timeout,
        )
        audit['provider_latency_ms'] = elapsed_ms(provider_started)
        return completion
    except (AssistantProviderRetryableError, AssistantDeadlineError) as exc:
        audit['provider_latency_ms'] = elapsed_ms(provider_started)
        if isinstance(exc, AssistantDeadlineError) and (deadline is None or deadline.expired()):
            raise
        audit['failure_class'] = getattr(exc, 'failure_class', None) or FAILURE_PROVIDER_TIMEOUT
        if not _can_use_fallback(deadline, audit):
            raise
        audit['fallback_attempted'] = True
        audit['fallback_provider'] = assistant_fallback_model()
        if deadline is not None:
            deadline.raise_if_expired()
        from features.assistant.anthropic_provider import AnthropicAssistantProvider
        fallback_started = start_timer()
        try:
            completion = AnthropicAssistantProvider().complete(
                messages=provider_messages(messages),
                page_context=tool_page_context(page_context, state),
                conversation_state=state,
                role=role,
                audit=audit,
                deadline=deadline,
                timeout_s=deadline.remaining() if deadline else None,
            )
        except (AssistantDeadlineError, AssistantToolFailure):
            audit['fallback_succeeded'] = False
            audit['failure_class'] = FAILURE_FALLBACK_FAILED
            raise
        except Exception as fallback_exc:
            audit['fallback_succeeded'] = False
            audit['failure_class'] = FAILURE_FALLBACK_FAILED
            raise AssistantProviderError(PROVIDER_ERROR) from fallback_exc
        audit['provider_latency_ms'] = (audit.get('provider_latency_ms') or 0) + (elapsed_ms(fallback_started) or 0)
        audit['fallback_succeeded'] = True
        audit['answer_source'] = 'fallback'
        return completion


def _can_use_fallback(deadline, audit):
    if not is_assistant_fallback_enabled():
        return False
    if audit.get('fallback_attempted'):
        return False
    if deadline is not None and deadline.expired():
        return False
    return True


def _finalize_grounded_text(
    text,
    *,
    user_text,
    tool_results,
    state,
    page_context,
    answer_source,
    role,
    audit,
):
    result = validate_grounding(
        user_text=user_text,
        draft_text=text,
        tool_results=tool_results,
        conversation_state=state,
        page_context=page_context,
        answer_source=answer_source,
    )
    _store_grounding(audit, result, answer_source)
    if result.ok:
        return text, None
    names = {item.get('name') for item in tool_results or ()}
    can_compose = any(
        str(name).endswith('_facts') or name in {'search_child', 'get_subject_peer_reference'}
        for name in names
    )
    if can_compose and answer_source != SOURCE_COMPOSE:
        composed = compose_from_tools(tool_results, user_text=user_text, role=role)
        composed_text = sanitize_output(
            composed.text or '',
            user_text=user_text,
            tool_results=tool_results,
        )
        second = validate_grounding(
            user_text=user_text,
            draft_text=composed_text,
            tool_results=tool_results,
            conversation_state=state,
            page_context=page_context,
            answer_source=SOURCE_COMPOSE,
        )
        _store_grounding(audit, second, SOURCE_COMPOSE)
        if second.ok:
            return composed_text, composed
    raise AssistantGroundingError()


def _store_grounding(audit, result, answer_source):
    if audit is None:
        return
    audit['answer_source'] = answer_source
    audit['grounding_status'] = result.status
    audit['grounding_violation_codes'] = result.codes()
    audit['used_evidence_ids'] = list(result.used_evidence_ids)[:12]
    if result.status == 'fail':
        audit['failure_class'] = FAILURE_GROUNDING


def _guardrail_timeout_s(deadline):
    if deadline is None:
        return 3.0
    remaining = float(deadline.remaining())
    if remaining <= 0:
        return 0.0
    return min(3.0, remaining)


def _apply_guardrail_decision(decision, *, source, audit):
    if decision is None:
        raise AssistantGuardrailError()
    audit['guardrail_provider'] = getattr(decision, 'provider', None)
    if decision.latency_ms is not None:
        audit['guardrail_latency_ms'] = decision.latency_ms
    if decision.assessments:
        audit['guardrail_categories'] = [
            str(item)[:40] for item in decision.assessments if item
        ][:8]
    if decision.action == ACTION_INTERVENED:
        audit['guardrail_status'] = 'blocked'
        audit['guardrail_source'] = source
        raise AssistantGuardrailBlock(source)
    if decision.safe and decision.action in {ACTION_NONE, None}:
        audit['guardrail_status'] = 'ok'
        audit['guardrail_source'] = source
        return
    audit['guardrail_status'] = 'error'
    audit['guardrail_source'] = source
    if decision.action == ACTION_ERROR:
        raise AssistantGuardrailError()
    raise AssistantGuardrailError()


def _enforce_input_guardrail(text, *, deadline, audit):
    timeout_s = _guardrail_timeout_s(deadline)
    if timeout_s <= 0:
        raise AssistantGuardrailError()
    try:
        decision = get_assistant_guardrail().check_input(text, timeout_s=timeout_s)
    except AssistantGuardrailBlock:
        raise
    except AssistantGuardrailError:
        raise
    except Exception:
        raise AssistantGuardrailError()
    _apply_guardrail_decision(decision, source='input', audit=audit)


def _enforce_output_guardrail(payload, meta, *, intent, deadline, audit):
    kind = (meta or {}).get('kind')
    source = (meta or {}).get('answer_source')
    if intent in QUICK_INTENTS or kind in {'confirm', 'nav', 'onboarding'}:
        return
    if source in {SOURCE_PENDING, SOURCE_NAVIGATION, SOURCE_SAFETY, SOURCE_GUARDRAIL}:
        return
    text = ((payload or {}).get('message') or {}).get('content') or ''
    if not str(text).strip():
        return
    timeout_s = _guardrail_timeout_s(deadline)
    if timeout_s <= 0:
        raise AssistantGuardrailError()
    try:
        decision = get_assistant_guardrail().check_response(text, timeout_s=timeout_s)
    except AssistantGuardrailBlock:
        raise
    except AssistantGuardrailError:
        raise
    except Exception:
        raise AssistantGuardrailError()
    _apply_guardrail_decision(decision, source='output', audit=audit)


def _closed_state():
    closed = empty_state()
    closed['segment_closed'] = True
    return closed


def _closed_segment_payload(page_context):
    closed = _closed_state()
    payload = _result(
        text=MSG_GUARDRAIL_BLOCK,
        page_context=page_context,
        actions=[{'type': 'new_conversation', 'label': NEW_CONVERSATION}],
        character_state='help',
        conversation_state=closed,
        kind='system',
    )
    return payload, {
        'kind': 'system',
        'conversation_state': closed,
        'counted': False,
        'uncount_kind': 'system',
        'answer_source': SOURCE_GUARDRAIL,
        'segment_closed': True,
    }


def _guardrail_block_result(*, page_context, original_state, audit, started, messages, source):
    closed = _closed_state()
    audit['failure_class'] = FAILURE_GUARDRAIL_BLOCK
    audit['guardrail_status'] = 'blocked'
    audit['guardrail_source'] = source
    audit['conversation_closed'] = True
    payload = _result(
        text=MSG_GUARDRAIL_BLOCK,
        page_context=page_context,
        actions=[{'type': 'new_conversation', 'label': NEW_CONVERSATION}],
        character_state='help',
        conversation_state=closed,
        kind='system',
        extras={'segment_closed': True},
    )
    return _decorate_result(
        payload,
        audit=audit,
        started=started,
        messages=messages,
        conversation_state=closed,
        kind='system',
        feedback_enabled=False,
        counted=False,
        limit_reached=False,
        uncount_kind='system',
    )


def _safe_failure(*, text, page_context, original_state, audit, started, messages, failure_class, error):
    audit['error'] = error
    audit['final_status'] = failure_class
    audit['failure_class'] = failure_class
    payload = _result(
        text=text,
        page_context=page_context,
        actions=[],
        character_state='help',
        conversation_state=original_state,
        kind='system',
        error=error,
        ok=True,
    )
    return _decorate_result(
        payload,
        audit=audit,
        started=started,
        messages=messages,
        conversation_state=original_state,
        kind='system',
        feedback_enabled=False,
        counted=False,
        limit_reached=False,
        uncount_kind='system',
    )


def _align_navigate_text(text, actions):
    nav = next((item for item in actions or () if item.get('url')), None)
    if not nav:
        return text
    if not text or str(text).strip() == FALLBACK:
        dest = nav.get('destination')
        return opening_text(dest) if dest else '해당 화면으로 이동할게요.'
    return text


def _completion_result(
    completion, page_context, state, last, *, kind='chat', role=None, audit=None, answer_source=SOURCE_COMPOSE,
):
    text = sanitize_output(
        completion.text,
        user_text=last,
        tool_results=getattr(completion, 'tool_results', None),
    )
    text = _align_navigate_text(text, completion.actions)
    text, grounded = _finalize_grounded_text(
        text,
        user_text=last,
        tool_results=getattr(completion, 'tool_results', None),
        state=state,
        page_context=page_context,
        answer_source=answer_source,
        role=role,
        audit=audit,
    )
    if grounded is not None:
        completion = grounded
    return _result(
        text=text,
        page_context=page_context,
        actions=completion.actions,
        status=completion.status,
        character_state=completion.character_state or 'idle',
        sources=getattr(completion, 'sources', None),
        conversation_state=state,
        kind=kind,
    )


def _decorate_result(
    payload, *, audit, started, messages, conversation_state, kind, feedback_enabled,
    counted, limit_reached, uncount_kind=None,
):
    n = count_chat_questions(messages)
    if not counted:
        n = _uncount_last_if_tagged(messages, n)
    if limit_reached:
        n = min(n, QUESTION_LIMIT)
        limit_reached = True
    elif counted:
        limit_reached = n >= QUESTION_LIMIT
    message = payload.get('message') or {}
    message['kind'] = kind or message.get('kind') or 'system'
    if audit.get('request_id'):
        payload['request_id'] = audit['request_id']
        if feedback_enabled:
            message['request_id'] = audit['request_id']
            message['feedback_enabled'] = True
    payload['message'] = message
    payload['feedback_enabled'] = bool(feedback_enabled)
    if uncount_kind:
        payload['last_user_kind'] = uncount_kind
    elif (
        not counted
        and messages
        and messages[-1].get('role') == 'user'
        and (messages[-1].get('kind') or 'chat') in COUNTED_KINDS
    ):
        payload['last_user_kind'] = 'confirm'
    payload['question_count'] = n
    payload['question_limit'] = QUESTION_LIMIT
    status = dict(payload.get('status') or {})
    status['question_count'] = n
    status['question_limit'] = QUESTION_LIMIT
    if limit_reached:
        status['limit_reached'] = True
    if (conversation_state or {}).get('segment_closed'):
        status['segment_closed'] = True
        payload['segment_closed'] = True
    if conversation_state is not None:
        status['conversation_state'] = public_conversation_state(conversation_state)
    payload['status'] = status

    nav = None
    for action in payload.get('actions') or ():
        if action.get('destination') or action.get('url'):
            nav = action.get('destination') or action.get('url')
            break
    rag_ids = [
        item.get('evidence_id')
        for item in payload.get('sources') or ()
        if isinstance(item, dict) and item.get('evidence_id')
    ]
    audit['displayed_response'] = message.get('content')
    audit['resolved_child_id'] = (conversation_state or {}).get('active_child_id')
    audit['resolved_subject'] = (conversation_state or {}).get('active_subject')
    audit['resolved_topic'] = (conversation_state or {}).get('active_topic')
    audit['rag_source_ids'] = rag_ids
    audit['navigation_destination'] = nav
    audit['total_latency_ms'] = elapsed_ms(started)
    audit['elapsed_ms'] = audit['total_latency_ms']
    audit['feedback_enabled'] = bool(feedback_enabled)
    audit['tool_round_limit'] = bool((status or {}).get('tool_round_limit'))
    audit['conversation_state'] = public_conversation_state(conversation_state)
    audit['last_user_kind'] = payload.get('last_user_kind')
    audit['error'] = payload.get('error')
    audit['final_status'] = 'ok' if payload.get('ok') else (payload.get('error') or 'error')
    if payload.get('selected_candidate_index') is not None:
        audit['selected_candidate_index'] = payload.get('selected_candidate_index')
    if payload.get('candidate_count') is not None:
        audit['candidate_count'] = payload.get('candidate_count')
    if payload.get('match_type'):
        audit['match_type'] = payload.get('match_type')
    record_request_end(audit)
    return payload


def _is_pending_slot_completion(pending, user_text, tool_results):
    """LLM이 old pending의 child slot으로 해석해 resolver를 쓴 경우만 제외."""
    if not pending or pending.get('awaiting') != 'child':
        return False
    if not any(item.get('name') == 'search_child' for item in tool_results or ()):
        return False
    from features.assistant.intents import wants_data, wants_help
    from features.assistant.navigation import match_destination_from_text
    if match_destination_from_text(user_text):
        return False
    if wants_data(user_text) or wants_help(user_text):
        return False
    return True


def _prepare_resolution_pending(state, user_text, tool_results):
    """LLM이 child resolver를 선택한 뒤 새 명시적 navigation 목적지만 보존."""
    selected = _selected_search_result(tool_results)
    if not selected or selected.get('kind') not in {'multiple', 'fuzzy'}:
        return state
    from features.assistant.navigation import match_destination_from_text, spec_for
    destination = match_destination_from_text(user_text)
    spec = spec_for(destination)
    if spec is None or not spec.child_required:
        return state
    updated = dict(state or empty_state())
    updated['pending_action'] = pending_need_child(destination=spec.key)
    return updated


def _llm_first_pending_fallback(
    pending,
    user_text,
    *,
    state,
    page_context,
    role,
    audit,
    tool_results,
    completion_text,
):
    """LLM이 tool을 고르지 못했을 때 DB nickname match가 있는 slot만 복구."""
    if (
        tool_results
        or not pending
        or pending.get('awaiting') != 'child'
        or (completion_text or '').strip() != FALLBACK
    ):
        return None
    search = gated_execute(
        'search_child',
        {'query': user_text},
        page_context=tool_page_context(page_context, state),
        role=role,
        conversation_state=state,
        audit=audit,
    )
    if not search.get('matches'):
        return None
    return apply_pending_turn(
        user_text,
        state=state,
        page_context=page_context,
        role=role,
    )


def _llm_selected_pending_completion(
    pending,
    user_text,
    *,
    state,
    page_context,
    role,
    tool_results,
):
    """LLM이 exact/partial search를 선택했지만 후속 operation을 생략한 경우."""
    if not _is_pending_slot_completion(pending, user_text, tool_results):
        return None
    if any(item.get('name') != 'search_child' for item in tool_results or ()):
        return None
    result = _selected_search_result(tool_results)
    matches = (result or {}).get('matches') or []
    if (result or {}).get('kind') in {'exact', 'partial'} and len(matches) == 1:
        return apply_pending_turn(
            user_text,
            state=state,
            page_context=page_context,
            role=role,
        )
    return None


def _selected_search_result(tool_results):
    return select_child_resolution([
        item.get('result') or {}
        for item in tool_results or ()
        if item.get('name') == 'search_child'
    ])


def _apply_payload_hint(state, payload):
    hint = (payload or {}).get('pending_hint')
    if hint:
        merged = dict(state or empty_state())
        merged['pending_action'] = hint
        return sanitize_conversation_state(merged, page_context=None)
    if (payload or {}).get('error') == 'missing_child':
        destination = (payload or {}).get('destination') or (hint or {}).get('destination')
        merged = dict(state or empty_state())
        merged['pending_action'] = pending_need_child(destination=destination)
        return sanitize_conversation_state(merged)
    if payload.get('actions'):
        for action in payload.get('actions') or ():
            if action.get('auto'):
                merged = dict(state or empty_state())
                child_id = action.get('params', {}).get('child_id')
                if child_id:
                    merged['active_child_id'] = child_id
                merged['pending_action'] = None
                if action.get('destination'):
                    merged['active_topic'] = 'nav'
                return sanitize_conversation_state(merged)
    return state


def _last_user(messages):
    for item in reversed(messages or ()):
        if item.get('role') == 'user':
            return item.get('content') or ''
    return ''


def _should_auto_navigate(actions, tool_results, user_text, state):
    if not actions:
        return False
    names = {item.get('name') for item in tool_results or ()}
    if any(str(name).endswith('_facts') for name in names) or 'search_help' in names:
        return False
    pending = (state or {}).get('pending_action') or {}
    if pending.get('type') == 'navigate':
        return True
    from features.assistant.intents import wants_help
    from features.assistant.navigation import is_explicit_go
    if names <= {'navigate', 'search_child', None} and not wants_help(user_text):
        return True
    return is_explicit_go(user_text) and not wants_help(user_text)


def _live_prompt_marker():
    try:
        from features.assistant.openai_provider import SYSTEM_PROMPT
        return SYSTEM_PROMPT
    except Exception:
        return ''


def _audit_user_id():
    try:
        from flask_login import current_user
        if getattr(current_user, 'is_authenticated', False):
            return str(current_user.get_id() or '')[:32]
    except Exception:
        return None
    return None


def _audit_model():
    if assistant_provider_name() != 'openai':
        return 'fake'
    try:
        from features.assistant.openai_provider import DEFAULT_MODEL
        import os
        from features.assistant.config import TEACHER_ASSISTANT_MODEL_ENV
        return (os.environ.get(TEACHER_ASSISTANT_MODEL_ENV) or DEFAULT_MODEL)[:80]
    except Exception:
        return 'openai'
