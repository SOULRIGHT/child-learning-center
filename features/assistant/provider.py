"""Assistant provider boundary. Growth/Reading AI runtime을 재사용하지 않는다."""
from __future__ import annotations

from dataclasses import dataclass, field

from features.assistant.config import assistant_provider_name, current_role
from features.assistant.copy import (
    FALLBACK,
    GREETING_REPLY,
    MSG_NEED_CHILD_FACTS,
    MSG_NO_HELP,
    MSG_UNAVAILABLE,
    NAV_NEED_CHOICE,
    NAV_NO_MATCH,
    SETUP_FORBIDDEN,
)
from features.assistant.intents import is_greeting
from features.assistant.policy import gated_execute
from features.assistant.tools import (
    collect_actions,
    collect_sources,
    plan_deterministic_tools,
)


class AssistantProviderError(Exception):
    """생성 실패. 본문 페이지로 전파하지 않는다."""


class AssistantProviderConfigError(AssistantProviderError):
    """설정 오류."""


@dataclass
class AssistantCompletion:
    text: str
    actions: list = field(default_factory=list)
    status: dict | None = None
    character_state: str = 'idle'
    sources: list = field(default_factory=list)
    tool_results: list = field(default_factory=list)


class AssistantProvider:
    def complete(self, *, messages, page_context, conversation_state=None, audit=None) -> AssistantCompletion:
        raise NotImplementedError


class FakeAssistantProvider(AssistantProvider):
    """live AI 없이 결정적 응답. hidden retry 없음. 숫자는 tool result만 사용."""

    def complete(self, *, messages, page_context, conversation_state=None, audit=None) -> AssistantCompletion:
        last = _last_user_text(messages)
        role = current_role()
        if is_greeting(last):
            return AssistantCompletion(text=GREETING_REPLY, character_state='idle')
        planned = plan_deterministic_tools(last, page_context or {})
        if not planned:
            return AssistantCompletion(
                text=FALLBACK,
                character_state='idle',
            )
        results = []
        for name, arguments in planned:
            if name == 'need_child':
                return AssistantCompletion(
                    text=MSG_NEED_CHILD_FACTS,
                    character_state='help',
                    status={'pending_need_child': True},
                )
            result = gated_execute(
                name,
                arguments,
                page_context=page_context,
                role=role,
                conversation_state=conversation_state,
                audit=audit,
            )
            results.append({'name': name, 'arguments': arguments, 'result': result})
        return compose_from_tools(results, user_text=last, role=role)


def compose_from_tools(results, *, user_text='', role=None):
    lines = []
    character_state = 'idle'
    candidates = None
    for item in results:
        name = item.get('name')
        result = item.get('result') or {}
        if name == 'search_child':
            matches = result.get('matches') or []
            if result.get('needs_confirmation') and matches:
                from features.assistant.conversation import confirmation_actions, confirmation_text
                child = matches[0]
                return AssistantCompletion(
                    text=confirmation_text(child),
                    actions=confirmation_actions(child.get('name')),
                    character_state='help',
                    tool_results=results,
                )
            if not matches:
                return AssistantCompletion(text=NAV_NO_MATCH, character_state='help', tool_results=results)
            if len(matches) > 1:
                return AssistantCompletion(
                    text=NAV_NEED_CHOICE,
                    character_state='help',
                    status={'candidates': matches},
                    tool_results=results,
                )
            continue
        if name == 'search_help':
            hits = result.get('hits') or []
            if not hits:
                lines.append(MSG_NO_HELP)
            else:
                for hit in hits:
                    lines.append(hit.get('text') or '')
                character_state = 'help'
            continue
        if name == 'navigate':
            if result.get('error') == 'forbidden':
                lines.append(result.get('message') or SETUP_FORBIDDEN)
                continue
            if result.get('ok'):
                character_state = 'working'
            elif result.get('message'):
                lines.append(result['message'])
            continue
        if name == 'get_center_setup_status':
            if result.get('error') == 'forbidden':
                return AssistantCompletion(
                    text=result.get('message') or SETUP_FORBIDDEN,
                    character_state='help',
                    tool_results=results,
                )
            nxt = result.get('next')
            if nxt and nxt.get('label'):
                lines.append(f"다음 확인은 {nxt['label']}입니다.")
            elif result.get('complete'):
                lines.append('필요한 센터 설정은 확인된 상태입니다.')
            continue
        if str(name or '').endswith('_facts') or name == 'get_subject_peer_reference':
            if not result.get('ok'):
                if result.get('error') == 'invalid_child':
                    lines.append(NAV_NO_MATCH)
                continue
            child = result.get('child') or {}
            name_label = child.get('name')
            prefix = f"{name_label} " if name_label else ''
            available_rows = []
            missing_rows = []
            for fact in result.get('facts') or ():
                if fact.get('available'):
                    available_rows.append(f"{fact.get('label')}: {fact.get('value')}")
                else:
                    missing_rows.append(fact.get('label') or fact.get('evidence_id') or '기록')
            if available_rows:
                if prefix:
                    lines.append(f'{prefix}확인된 기록입니다.')
                lines.extend(available_rows[:8])
            if missing_rows and not available_rows:
                lines.append(MSG_UNAVAILABLE)
            elif missing_rows:
                lines.append('확인되지 않은 항목은 숫자로 채우지 않았습니다.')
            character_state = 'working'
    actions = collect_actions(results, user_text=user_text)
    sources = collect_sources(results, role=role)
    text = '\n'.join(line for line in lines if line).strip()
    if not text:
        text = FALLBACK
    return AssistantCompletion(
        text=text,
        actions=actions,
        character_state=character_state,
        sources=sources,
        status={'candidates': candidates} if candidates else None,
        tool_results=results,
    )


def _last_user_text(messages):
    if not isinstance(messages, list):
        return ''
    for item in reversed(messages):
        if not isinstance(item, dict):
            continue
        if item.get('role') != 'user':
            continue
        content = item.get('content')
        if isinstance(content, str):
            return content.strip()
    return ''


def get_assistant_provider() -> AssistantProvider:
    if assistant_provider_name() == 'openai':
        from features.assistant.openai_provider import OpenAIAssistantProvider
        return OpenAIAssistantProvider()
    return FakeAssistantProvider()
