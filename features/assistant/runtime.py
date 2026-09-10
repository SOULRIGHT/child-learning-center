"""Teacher assistant application service. hidden retry 없음. form write 없음.

Browser conversation / LLM working context / server audit 를 섞지 않는다.
"""
from __future__ import annotations

from features.assistant.audit import (
    elapsed_ms,
    new_request_id,
    now_iso,
    record_request_end,
    record_request_start,
    start_timer,
)
from features.assistant.config import assistant_provider_name, current_role
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
from features.assistant.copy import FALLBACK, PROVIDER_ERROR, QUESTION_LIMIT_REPLY
from features.assistant.intents import (
    bootstrap_payload,
    explain_page_payload,
    interpret_user_text,
    navigate_payload,
    onboarding_payload,
    quick_actions,
)
from features.assistant.policy import gated_execute
from features.assistant.provider import AssistantProviderError, compose_from_tools, get_assistant_provider
from features.assistant.safety import sanitize_output, safety_override_payload

MAX_MESSAGES = 48
MAX_CONTENT_LEN = 2000
MAX_LLM_MESSAGES = 12
QUESTION_LIMIT = 10
VALID_KINDS = frozenset({'chat', 'llm', 'system', 'confirm', 'quick', 'onboarding', 'nav'})
LLM_CONTEXT_KINDS = frozenset({'chat', 'llm'})
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
):
    started = start_timer()
    request_id = new_request_id()
    role = current_role()
    page_context = sanitize_page_context(page_context)
    messages = parse_messages(messages)
    intent = (intent or 'chat').strip()
    if intent not in ALLOWED_INTENTS:
        raise AssistantRequestError('invalid_intent')
    state = sanitize_conversation_state(conversation_state, page_context=page_context)
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
        'conversation_state': public_conversation_state(state),
    }
    record_request_start(audit)
    try:
        payload, meta = _dispatch(
            messages=messages,
            page_context=page_context,
            intent=intent,
            destination=destination,
            params=params,
            state=state,
            last=last,
            role=role,
            audit=audit,
        )
    except AssistantProviderError:
        audit['error'] = 'provider_error'
        audit['final_status'] = 'provider_error'
        audit['total_latency_ms'] = elapsed_ms(started)
        record_request_end(audit)
        raise
    except Exception:
        audit['error'] = 'error'
        audit['final_status'] = 'error'
        audit['total_latency_ms'] = elapsed_ms(started)
        record_request_end(audit)
        raise
    return _decorate_result(
        payload,
        audit=audit,
        started=started,
        messages=messages,
        conversation_state=meta.get('conversation_state') or state,
        kind=meta.get('kind') or 'system',
        feedback_enabled=bool(meta.get('feedback_enabled')),
        counted=bool(meta.get('counted')),
        limit_reached=bool(meta.get('limit_reached')),
    )


def _dispatch(*, messages, page_context, intent, destination, params, state, last, role, audit):
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
        return _result(
            page_context=page_context, **pending_done, conversation_state=state, kind='confirm',
        ), {'kind': 'confirm', 'conversation_state': state}

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

    raw_block = safety_override_payload(last)
    if raw_block and '원문' in last:
        return _result(
            page_context=page_context,
            text=raw_block['text'],
            actions=[],
            character_state=raw_block.get('character_state') or 'help',
            conversation_state=state,
            kind='system',
        ), {'kind': 'system', 'conversation_state': state, 'counted': True}

    live = assistant_provider_name() == 'openai'
    if live:
        payload, state, feedback_enabled, counted = _complete_live(
            messages=messages,
            page_context=page_context,
            state=state,
            pending_before=pending_before,
            last=last,
            role=role,
            audit=audit,
        )
        return payload, {
            'kind': 'llm' if feedback_enabled else payload['message'].get('kind') or 'system',
            'feedback_enabled': feedback_enabled,
            'counted': counted,
            'conversation_state': state,
        }
    payload, state, kind, counted = _complete_fake(
        messages=messages,
        page_context=page_context,
        state=state,
        last=last,
        role=role,
        audit=audit,
    )
    return payload, {
        'kind': kind,
        'counted': counted,
        'conversation_state': state,
    }


def _complete_live(*, messages, page_context, state, pending_before, last, role, audit):
    try:
        completion = get_assistant_provider().complete(
            messages=provider_messages(messages),
            page_context=tool_page_context(page_context, state),
            conversation_state=state,
            audit=audit,
        )
    except AssistantProviderError as exc:
        raise AssistantProviderError(PROVIDER_ERROR) from exc
    tool_results = getattr(completion, 'tool_results', None) or []
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
        ), state, False, False
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
        ), state, False, False
    state = _prepare_resolution_pending(state, last, tool_results)
    state = update_state_from_tools(state, tool_results, page_context=page_context)
    slot_completion = _is_pending_slot_completion(
        pending_before,
        last,
        tool_results,
    )
    resolution = child_resolution_payload(state, tool_results)
    if resolution:
        return _result(
            page_context=page_context,
            **resolution,
            conversation_state=state,
            kind='confirm',
        ), state, False, not slot_completion
    text = sanitize_output(
        completion.text,
        user_text=last,
        tool_results=tool_results,
        system_prompt=_live_prompt_marker(),
    )
    actions = list(completion.actions or [])
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
        interpreted = interpret_user_text(last, page_context, role=role)
        if interpreted.get('handled'):
            state = _apply_payload_hint(state, interpreted)
            text = sanitize_output(interpreted.get('text') or '', user_text=last)
            interpreted = dict(interpreted)
            interpreted['text'] = text
            kind = 'nav' if interpreted.get('actions') else 'system'
            return _result(
                page_context=page_context, **interpreted, conversation_state=state, kind=kind,
            ), state, False, True
    if _should_auto_navigate(actions, tool_results, last, state):
        actions = [dict(item, auto=True) if item.get('url') else item for item in actions]
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
    ), state, True, not slot_completion


def _complete_fake(*, messages, page_context, state, last, role, audit):
    if is_capability_question(last):
        data = capability_payload()
        return _result(
            page_context=page_context, **data, conversation_state=state, kind='system',
        ), state, 'system', True
    override = safety_override_payload(last)
    if override:
        return _result(
            page_context=page_context,
            text=override['text'],
            actions=[],
            character_state=override.get('character_state') or 'help',
            conversation_state=state,
            kind='system',
        ), state, 'system', True
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
                ), state, 'confirm', False
    follow = fake_follow_up_call(last, state)
    if follow:
        name, arguments = follow
        result = gated_execute(
            name,
            arguments,
            page_context=tool_page_context(page_context, state),
            role=role,
            conversation_state=state,
            audit=audit,
        )
        completion = compose_from_tools(
            [{'name': name, 'arguments': arguments, 'result': result}],
            user_text=last,
            role=role,
        )
        state = update_state_from_tools(
            state,
            [{'name': name, 'arguments': arguments, 'result': result}],
            page_context=page_context,
        )
        return _completion_result(completion, page_context, state, last, kind='chat'), state, 'chat', True

    interpreted = interpret_user_text(last, page_context, role=role)
    if interpreted.get('handled'):
        state = _apply_payload_hint(state, interpreted)
        text = sanitize_output(interpreted.get('text') or '', user_text=last)
        interpreted = dict(interpreted)
        interpreted['text'] = text
        kind = 'nav' if interpreted.get('actions') else 'system'
        return _result(
            page_context=page_context, **interpreted, conversation_state=state, kind=kind,
        ), state, kind, False

    try:
        completion = get_assistant_provider().complete(
            messages=provider_messages(messages),
            page_context=tool_page_context(page_context, state),
            conversation_state=state,
            audit=audit,
        )
    except AssistantProviderError as exc:
        raise AssistantProviderError(PROVIDER_ERROR) from exc
    tool_results = getattr(completion, 'tool_results', None) or []
    state = update_state_from_tools(state, tool_results, page_context=page_context)
    if getattr(completion, 'status', None) and completion.status.get('pending_need_child'):
        state['pending_action'] = pending_need_child(tool='get_growth_facts')
    return _completion_result(completion, page_context, state, last, kind='chat'), state, 'chat', True


def _completion_result(completion, page_context, state, last, *, kind='chat'):
    text = sanitize_output(
        completion.text,
        user_text=last,
        tool_results=getattr(completion, 'tool_results', None),
    )
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
    counted, limit_reached,
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
    if (
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
    audit['feedback_enabled'] = bool(feedback_enabled)
    audit['tool_round_limit'] = bool((status or {}).get('tool_round_limit'))
    audit['conversation_state'] = public_conversation_state(conversation_state)
    audit['last_user_kind'] = payload.get('last_user_kind')
    audit['error'] = payload.get('error')
    audit['final_status'] = 'ok' if payload.get('ok') else (payload.get('error') or 'error')
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
    unresolved = False
    for item in tool_results or ():
        if item.get('name') != 'search_child':
            continue
        result = item.get('result') or {}
        if result.get('kind') in {'multiple', 'fuzzy'}:
            unresolved = True
            break
    if not unresolved:
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
    for item in tool_results or ():
        result = item.get('result') or {}
        matches = result.get('matches') or []
        if result.get('kind') in {'exact', 'partial'} and len(matches) == 1:
            return apply_pending_turn(
                user_text,
                state=state,
                page_context=page_context,
                role=role,
            )
    return None


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
