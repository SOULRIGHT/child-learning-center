"""Teacher assistant application service. hidden retry 없음. form write 없음."""
from __future__ import annotations

from features.assistant.config import current_role
from features.assistant.context import context_scope, sanitize_page_context
from features.assistant.copy import PROVIDER_ERROR
from features.assistant.intents import (
    bootstrap_payload,
    explain_page_payload,
    interpret_user_text,
    navigate_payload,
    onboarding_payload,
    quick_actions,
)
from features.assistant.provider import AssistantProviderError, get_assistant_provider

MAX_MESSAGES = 20
MAX_CONTENT_LEN = 2000

ALLOWED_INTENTS = frozenset({
    'bootstrap',
    'chat',
    'continue_setup',
    'explain_page',
    'navigate',
})


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
    for item in raw[:MAX_MESSAGES]:
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
        messages.append({
            'role': role,
            'content': content,
            'context_scope': {
                'endpoint': _as_text(scope.get('endpoint'), 120),
                **({'child_id': child_id} if child_id else {}),
            },
        })
    return messages


def _assistant_message(text, page_context):
    return {
        'role': 'assistant',
        'content': text,
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
        public.append(item)
    return public


def _result(*, text, page_context, actions=None, status=None, character_state='idle',
            quick_actions=None, error=None, ok=True, extras=None, candidates=None,
            handled=None):
    deny = error in {'unknown_destination', 'forbidden', 'invalid_child'}
    payload = {
        'ok': False if deny else ok,
        'message': _assistant_message(text, page_context),
        'actions': _public_actions(actions),
        'status': status or {},
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
):
    role = current_role()
    page_context = sanitize_page_context(page_context)
    messages = parse_messages(messages)
    intent = (intent or 'chat').strip()
    if intent not in ALLOWED_INTENTS:
        raise AssistantRequestError('invalid_intent')

    if intent == 'bootstrap':
        data = bootstrap_payload(page_context, role)
        return _result(page_context=page_context, **data, extras={'bootstrap': True})

    if intent == 'continue_setup':
        data = onboarding_payload(role)
        return _result(page_context=page_context, **data)

    if intent == 'explain_page':
        data = explain_page_payload(page_context)
        return _result(page_context=page_context, **data)

    if intent == 'navigate' or destination:
        data = navigate_payload(
            destination,
            params or {},
            page_context=page_context,
            auto=True,
            role=role,
        )
        return _result(page_context=page_context, **data)

    last = ''
    for item in reversed(messages):
        if item.get('role') == 'user':
            last = item.get('content') or ''
            break

    interpreted = interpret_user_text(last, page_context, role=role)
    if interpreted.get('handled'):
        return _result(page_context=page_context, **{
            'text': interpreted.get('text') or '',
            'actions': interpreted.get('actions'),
            'status': interpreted.get('status'),
            'character_state': interpreted.get('character_state') or 'idle',
            'error': interpreted.get('error'),
            'candidates': interpreted.get('candidates'),
            'quick_actions': interpreted.get('quick_actions'),
        })

    try:
        completion = get_assistant_provider().complete(
            messages=messages,
            page_context=page_context,
        )
    except AssistantProviderError as exc:
        raise AssistantProviderError(PROVIDER_ERROR) from exc

    return _result(
        text=completion.text,
        page_context=page_context,
        actions=completion.actions,
        status=completion.status,
        character_state=completion.character_state or 'idle',
    )
