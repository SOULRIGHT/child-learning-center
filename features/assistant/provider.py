"""Assistant provider boundary. Growth/Reading AI runtime을 재사용하지 않는다."""
from __future__ import annotations

from dataclasses import dataclass, field

from features.assistant.config import assistant_provider_name, current_role
from features.assistant.copy import (
    FALLBACK,
    GREETING_REPLY,
    MSG_FOCUS_UNAVAILABLE,
    MSG_NEED_CHILD_FACTS,
    MSG_NO_HELP,
    MSG_UNAVAILABLE,
    NAV_NO_MATCH,
    POINT_AVERAGE_UNSUPPORTED,
    SETUP_FORBIDDEN,
    opening_text,
)
from features.assistant.intents import is_greeting
from features.assistant.persona import child_record_clarification
from features.assistant.facts import (
    facts_matching_focus,
    format_all_domain_facts,
    format_tool_facts,
    infer_metric_focus,
)
from features.assistant.navigation import classify_remainder_domain, request_remainder
from features.assistant.policy import gated_execute
from features.assistant.resolve import select_child_resolution
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
        planned = plan_deterministic_tools(last, page_context or {}, conversation_state)
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
    selected_search = select_child_resolution([
        item.get('result') or {}
        for item in results or ()
        if item.get('name') == 'search_child'
    ])
    if selected_search:
        matches = selected_search.get('matches') or []
        if selected_search.get('needs_confirmation') and matches:
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
        if selected_search.get('kind') == 'multiple' or len(matches) > 1:
            from features.assistant.copy import choice_need_text
            query = ''
            for item in results or ():
                if item.get('name') != 'search_child':
                    continue
                arguments = item.get('arguments') if isinstance(item.get('arguments'), dict) else {}
                result = item.get('result') if isinstance(item.get('result'), dict) else {}
                query = arguments.get('child_query') or arguments.get('query') or result.get('child_query') or ''
                if query:
                    break
            return AssistantCompletion(
                text=choice_need_text(query, selected_search.get('match_type')),
                character_state='help',
                status={'candidates': matches},
                tool_results=results,
            )
        if selected_search.get('kind') in {'exact', 'partial'} and len(matches) == 1:
            child_name = matches[0].get('name')
            query = ''
            for item in results or ():
                if item.get('name') != 'search_child':
                    continue
                arguments = item.get('arguments') if isinstance(item.get('arguments'), dict) else {}
                result = item.get('result') if isinstance(item.get('result'), dict) else {}
                query = arguments.get('child_query') or arguments.get('query') or result.get('child_query') or ''
                if query:
                    break
            remainder = request_remainder(user_text, child_name, query)
            only_search = not any(
                item.get('name') not in {None, 'search_child'}
                and not (item.get('result') or {}).get('skipped_unspecified_domain')
                for item in results or ()
            )
            unspecified = (
                (user_text and classify_remainder_domain(remainder) is None)
                or (not user_text and only_search)
            )
            if unspecified and only_search:
                return AssistantCompletion(
                    text=child_record_clarification(child_name),
                    character_state='help',
                    tool_results=results,
                )
    used_facts = []
    fact_composed = False
    fact_items = [
        item for item in results or ()
        if (
            str(item.get('name') or '').endswith('_facts')
            or item.get('name') == 'get_subject_peer_reference'
        ) and not (item.get('result') or {}).get('skipped_unspecified_domain')
    ]
    if len(fact_items) >= 2 and all(
        item.get('name') in {'get_learning_facts', 'get_points_facts', 'get_reading_facts'}
        for item in fact_items
    ):
        formatted = format_all_domain_facts(fact_items)
        if formatted.get('text'):
            lines.append(formatted['text'])
            used_facts.extend(formatted.get('used_facts') or ())
            character_state = 'working'
            fact_composed = True
            fact_items = []
    for item in results:
        name = item.get('name')
        result = item.get('result') or {}
        if name == 'search_child':
            continue
        if result.get('skipped_unspecified_domain'):
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
                dest = result.get('destination')
                lines.append(opening_text(dest) if dest else '해당 화면으로 이동할게요.')
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
            if name not in {item.get('name') for item in fact_items}:
                continue
            if not result.get('ok'):
                if result.get('error') == 'invalid_child':
                    lines.append(NAV_NO_MATCH)
                continue
            if name == 'get_points_facts' and result.get('metric_supported') is False:
                lines.append(POINT_AVERAGE_UNSUPPORTED)
                character_state = 'help'
                continue
            focus = result.get('focus') or infer_metric_focus(user_text)
            facts = list(result.get('facts') or ())
            if focus:
                focused = facts_matching_focus(facts, focus)
                if not focused:
                    lines.append(MSG_FOCUS_UNAVAILABLE)
                    character_state = 'help'
                    continue
                result = dict(result)
                result['facts'] = focused
            formatted = format_tool_facts(name, result, user_text=user_text, focus=focus)
            if formatted.get('text'):
                lines.append(formatted['text'])
                used_facts.extend(formatted.get('used_facts') or ())
                character_state = 'working'
                fact_composed = True
            elif focus:
                lines.append(MSG_FOCUS_UNAVAILABLE)
                character_state = 'help'
            else:
                lines.append(MSG_UNAVAILABLE)
    actions = collect_actions(results, user_text=user_text)
    sources = collect_sources(
        results,
        role=role,
        used_facts=used_facts if fact_composed else None,
    )
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
