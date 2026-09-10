"""Assistant provider boundary. Growth/Reading AI runtime을 재사용하지 않는다."""
from __future__ import annotations

from dataclasses import dataclass, field


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


class AssistantProvider:
    def complete(self, *, messages, page_context) -> AssistantCompletion:
        raise NotImplementedError


class FakeAssistantProvider(AssistantProvider):
    """live AI 없이 결정적 응답. hidden retry 없음."""

    def complete(self, *, messages, page_context) -> AssistantCompletion:
        from features.assistant.intents import interpret_user_text

        last = _last_user_text(messages)
        interpreted = interpret_user_text(last, page_context or {})
        return AssistantCompletion(
            text=interpreted.get('text') or '',
            actions=list(interpreted.get('actions') or ()),
            status=interpreted.get('status'),
            character_state=interpreted.get('character_state') or 'idle',
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
    return FakeAssistantProvider()
