"""Anthropic Claude fallback provider. Policy Gate / canonical READ tools만 사용한다.

same-provider hidden retry 금지(max_retries=0).
temperature / top_p / top_k / extended thinking budget를 넣지 않는다.
API key / raw response / 아동 PII를 로그에 남기지 않는다.
"""
from __future__ import annotations

import os

from features.assistant.config import (
    ANTHROPIC_API_KEY_ENV,
    assistant_fallback_model,
)
from features.assistant.copy import (
    FALLBACK,
    GREETING_REPLY,
    PROVIDER_ERROR,
    TOOL_ROUND_LIMIT_NOTE,
)
from features.assistant.deadline import MIN_CALL_S
from features.assistant.failures import (
    FAILURE_PROVIDER_5XX,
    FAILURE_PROVIDER_CONNECTION,
    FAILURE_PROVIDER_RATE_LIMIT,
    FAILURE_PROVIDER_TIMEOUT,
    AssistantDeadlineError,
    AssistantToolFailure,
)
from features.assistant.intents import is_greeting
from features.assistant.openai_provider import (
    MAX_HISTORY_MESSAGES,
    MAX_TOOL_ROUNDS,
    SYSTEM_PROMPT,
    _execute_search_continuation,
    _fallback_for_messages,
    _last_user,
    _page_context_note,
    _remainder_domain,
    _search_output,
    _state_note,
)
from features.assistant.policy import gated_execute
from features.assistant.provider import (
    AssistantCompletion,
    AssistantProvider,
    AssistantProviderBadRequestError,
    AssistantProviderConfigError,
    AssistantProviderError,
    AssistantProviderRetryableError,
    compose_from_tools,
)
from features.assistant.tools import TOOL_SCHEMAS, dump_tool_result

DEFAULT_MODEL = 'claude-sonnet-5'
TIMEOUT_S = 20.0


class AnthropicAssistantProvider(AssistantProvider):
    def __init__(self, *, api_key=None, model=None, client=None):
        self._api_key = api_key
        self._model = model
        self._client = client

    @property
    def model(self):
        return self._model or assistant_fallback_model() or DEFAULT_MODEL

    def complete(
        self,
        *,
        messages,
        page_context,
        conversation_state=None,
        role=None,
        audit=None,
        deadline=None,
        timeout_s=None,
    ) -> AssistantCompletion:
        client = self._request_client(timeout_s=_client_timeout(deadline, timeout_s))
        if role is None:
            from features.assistant.config import current_role
            role = current_role()
        chat_messages = _chat_messages(messages)
        if not chat_messages:
            last = _last_user(messages) or '안녕하세요'
            chat_messages = [{'role': 'user', 'content': last}]
        system = SYSTEM_PROMPT + _page_context_note(page_context) + _state_note(conversation_state)
        tool_results = []
        final_text = ''
        hit_round_limit = False
        try:
            for _round in range(MAX_TOOL_ROUNDS):
                _raise_if_deadline(deadline)
                client = self._request_client(timeout_s=_client_timeout(deadline, timeout_s))
                response = client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    system=system,
                    messages=chat_messages,
                    tools=_anthropic_tools(),
                )
                calls = [
                    item for item in (getattr(response, 'content', None) or ())
                    if _block_type(item) == 'tool_use'
                ]
                if not calls:
                    final_text = _text_from_response(response)
                    break
                call_names = {_block_attr(item, 'name') for item in calls}
                chat_messages.append({
                    'role': 'assistant',
                    'content': _as_content_blocks(getattr(response, 'content', None) or ()),
                })
                user_text = _last_user(messages)
                search_query = None
                search_name = None
                tool_blocks = []
                for call in calls:
                    name = _block_attr(call, 'name')
                    raw_args = _block_attr(call, 'input') or {}
                    arguments = raw_args if isinstance(raw_args, dict) else {}
                    skip_unspecified = False
                    if (
                        (str(name or '').endswith('_facts') or name == 'get_subject_peer_reference')
                        and search_query
                        and not arguments.get('focus')
                    ):
                        classified = _remainder_domain(user_text, search_name, search_query)
                        if classified is None:
                            skip_unspecified = True
                    if skip_unspecified:
                        result = {'ok': True, 'skipped_unspecified_domain': True}
                    else:
                        try:
                            result = gated_execute(
                                name,
                                arguments,
                                page_context=page_context,
                                role=role,
                                conversation_state=conversation_state,
                                audit=audit,
                            )
                        except Exception as exc:
                            raise AssistantToolFailure('canonical tool failed') from exc
                    tool_results.append({
                        'name': name,
                        'arguments': arguments,
                        'result': result,
                    })
                    output_result = result
                    if name == 'search_child':
                        search_query = arguments.get('query') or arguments.get('child_query')
                        matches = result.get('matches') or []
                        if len(matches) == 1:
                            search_name = matches[0].get('name')
                        continued = _execute_search_continuation(
                            arguments,
                            result,
                            emitted_names=call_names,
                            page_context=page_context,
                            conversation_state=conversation_state,
                            role=role,
                            audit=audit,
                            user_text=user_text,
                        )
                        if continued:
                            tool_results.append(continued)
                            output_result = _search_output(result, continued)
                    call_id = _block_attr(call, 'id')
                    if not name or not call_id:
                        continue
                    tool_blocks.append({
                        'type': 'tool_result',
                        'tool_use_id': call_id,
                        'content': dump_tool_result(output_result),
                    })
                if tool_blocks:
                    chat_messages.append({'role': 'user', 'content': tool_blocks})
            else:
                hit_round_limit = True
                final_text = ''
        except (AssistantDeadlineError, AssistantToolFailure):
            if tool_results:
                composed = compose_from_tools(tool_results, user_text=_last_user(messages), role=role)
                composed.tool_results = tool_results
                return composed
            raise
        except AssistantProviderError:
            if tool_results:
                composed = compose_from_tools(tool_results, user_text=_last_user(messages), role=role)
                composed.tool_results = tool_results
                return composed
            raise
        except Exception as exc:
            if tool_results:
                composed = compose_from_tools(tool_results, user_text=_last_user(messages), role=role)
                composed.tool_results = tool_results
                return composed
            raise _api_error(exc) from exc

        if not final_text:
            if tool_results:
                composed = compose_from_tools(tool_results, user_text=_last_user(messages), role=role)
                composed.tool_results = tool_results
                return composed
            final_text = (
                GREETING_REPLY
                if is_greeting(_last_user(messages))
                else _fallback_for_messages(messages)
            )
        elif final_text.strip() == FALLBACK:
            final_text = _fallback_for_messages(messages)
        if is_greeting(_last_user(messages)) and not tool_results:
            final_text = GREETING_REPLY
        if tool_results:
            names = {item.get('name') for item in tool_results}
            if any(
                str(name).endswith('_facts') or name in {'search_child', 'get_subject_peer_reference'}
                for name in names
            ):
                composed = compose_from_tools(tool_results, user_text=_last_user(messages), role=role)
                if composed.text and composed.text != FALLBACK:
                    composed.tool_results = tool_results
                    if hit_round_limit and TOOL_ROUND_LIMIT_NOTE not in (composed.text or ''):
                        composed.text = (composed.text.strip() + '\n' + TOOL_ROUND_LIMIT_NOTE).strip()
                    return composed
        from features.assistant.tools import collect_actions, collect_sources
        if hit_round_limit and TOOL_ROUND_LIMIT_NOTE not in (final_text or ''):
            final_text = ((final_text or '').strip() + '\n' + TOOL_ROUND_LIMIT_NOTE).strip()
        return AssistantCompletion(
            text=final_text[:2000],
            actions=collect_actions(tool_results, user_text=_last_user(messages)),
            sources=collect_sources(tool_results, role=role),
            character_state='working' if tool_results else 'idle',
            tool_results=tool_results,
            status={'tool_round_limit': True} if hit_round_limit else None,
        )

    def _request_client(self, timeout_s=None):
        timeout = TIMEOUT_S if timeout_s is None else float(timeout_s)
        if self._client is not None:
            if hasattr(self._client, 'with_options'):
                return self._client.with_options(timeout=timeout, max_retries=0)
            return self._client
        api_key = self._api_key or os.environ.get(ANTHROPIC_API_KEY_ENV)
        if not api_key:
            raise AssistantProviderConfigError('anthropic api key missing')
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise AssistantProviderConfigError('anthropic package missing') from exc
        return Anthropic(api_key=api_key, timeout=timeout, max_retries=0)


def _anthropic_tools():
    tools = []
    for schema in TOOL_SCHEMAS:
        tools.append({
            'name': schema.get('name'),
            'description': schema.get('description') or '',
            'input_schema': schema.get('parameters') or {'type': 'object', 'properties': {}},
        })
    return tools


def _chat_messages(messages):
    items = []
    if not isinstance(messages, list):
        return items
    skipped = {'system', 'confirm', 'quick', 'onboarding', 'nav'}
    for item in messages[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        kind = item.get('kind') or 'chat'
        if kind in skipped:
            continue
        role = item.get('role')
        content = item.get('content')
        if role not in {'user', 'assistant'} or not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        items.append({'role': role, 'content': text[:1500]})
    return items


def _as_content_blocks(output):
    blocks = []
    for item in output:
        if hasattr(item, 'model_dump'):
            blocks.append(item.model_dump())
        elif isinstance(item, dict):
            blocks.append(item)
        else:
            block = {'type': _block_type(item)}
            if block['type'] == 'text':
                block['text'] = _block_attr(item, 'text') or ''
            elif block['type'] == 'tool_use':
                block['id'] = _block_attr(item, 'id')
                block['name'] = _block_attr(item, 'name')
                block['input'] = _block_attr(item, 'input') or {}
            blocks.append(block)
    return blocks


def _text_from_response(response):
    parts = []
    for item in getattr(response, 'content', None) or ():
        if _block_type(item) == 'text':
            text = _block_attr(item, 'text')
            if text:
                parts.append(str(text))
    return ''.join(parts).strip()


def _block_type(item):
    if isinstance(item, dict):
        return item.get('type')
    return getattr(item, 'type', None)


def _block_attr(item, name):
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def _client_timeout(deadline, timeout_s):
    if deadline is not None:
        cap = TIMEOUT_S if timeout_s is None else float(timeout_s)
        return deadline.provider_timeout(cap)
    if timeout_s is not None:
        return max(0.1, float(timeout_s))
    return TIMEOUT_S


def _raise_if_deadline(deadline):
    if deadline is None:
        return
    deadline.raise_if_expired(min_needed=MIN_CALL_S)


def _api_error(exc):
    status = getattr(exc, 'status_code', None)
    if status is None:
        response = getattr(exc, 'response', None)
        status = getattr(response, 'status_code', None)
    name = type(exc).__name__.lower()
    message = str(exc or '').lower()
    if 'timeout' in name or 'timeout' in message:
        return AssistantProviderRetryableError(PROVIDER_ERROR, FAILURE_PROVIDER_TIMEOUT)
    if 'connection' in name or 'connect' in message:
        return AssistantProviderRetryableError(PROVIDER_ERROR, FAILURE_PROVIDER_CONNECTION)
    if status == 429:
        return AssistantProviderRetryableError(PROVIDER_ERROR, FAILURE_PROVIDER_RATE_LIMIT)
    if status is not None and 500 <= int(status) <= 599:
        return AssistantProviderRetryableError(PROVIDER_ERROR, FAILURE_PROVIDER_5XX)
    if status in {401, 403}:
        return AssistantProviderConfigError('anthropic auth configuration error')
    if status == 400:
        return AssistantProviderBadRequestError(PROVIDER_ERROR)
    return AssistantProviderError(PROVIDER_ERROR)
