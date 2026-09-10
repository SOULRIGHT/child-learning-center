"""Output harness. 시스템/원문/순위 누출을 최종 응답 전에 막는다."""
from __future__ import annotations

import re

from features.assistant.copy import (
    CAPABILITY_REPLY,
    NO_RANK_REPLY,
    NO_RAW_READING_REPLY,
    POLICY_SCOPE_REPLY,
)

RANK_MARKERS = ('몇 등', '등수', '백분위', '상위 몇', '하위 몇', '1등', '꼴등', '제일 잘')
RAW_READING_MARKERS = ('원문', '감상문 전부', '감상문 원문', 'review_text', 'select_text')
LEAK_MARKERS = (
    'SYSTEM_PROMPT',
    'developer prompt',
    'hidden instructions',
    'OPENAI_API_KEY',
    'sk-',
)
INJECTION_MARKERS = (
    '이전 지시',
    '시스템 프롬프트',
    '개발자 명령',
    'tool 목록',
    '숨겨진 tool',
    'DB 전체',
    'sql 직접',
    '권한 우회',
)
ZERO_CLAIM = re.compile(r'0점|0으로 계산')


def is_rank_request(text):
    raw = text or ''
    return any(marker in raw for marker in RANK_MARKERS)


def is_raw_reading_request(text):
    raw = text or ''
    return any(marker in raw for marker in RAW_READING_MARKERS)


def is_injection_request(text):
    raw = (text or '').casefold()
    return any(marker.casefold() in raw for marker in INJECTION_MARKERS)


def sanitize_output(text, *, user_text='', tool_results=None, system_prompt=''):
    cleaned = (text or '').strip()
    if system_prompt and system_prompt[:80] in cleaned:
        cleaned = POLICY_SCOPE_REPLY
    if any(marker in cleaned for marker in LEAK_MARKERS):
        cleaned = POLICY_SCOPE_REPLY
    if 'supporting_facts' in cleaned or 'review_text' in cleaned:
        cleaned = NO_RAW_READING_REPLY if is_raw_reading_request(user_text) else POLICY_SCOPE_REPLY
    if is_raw_reading_request(user_text):
        if any(marker in cleaned for marker in ('감상문', '원문', 'review')):
            cleaned = NO_RAW_READING_REPLY
        elif not cleaned:
            cleaned = NO_RAW_READING_REPLY
    if is_rank_request(user_text):
        if not _has_peer_facts(tool_results):
            cleaned = NO_RANK_REPLY
        elif any(marker in cleaned for marker in ('등수', '백분위', '몇 등', '1등')):
            cleaned = cleaned + '\n' + NO_RANK_REPLY
    elif any(marker in cleaned for marker in ('등수', '백분위')):
        cleaned = NO_RANK_REPLY
    if is_injection_request(user_text) and _looks_like_dump(cleaned):
        cleaned = POLICY_SCOPE_REPLY
    if _claimed_zero_for_unavailable(cleaned, tool_results):
        cleaned = _unavailable_zero_text(tool_results) or cleaned
    return cleaned[:2000]


def safety_override_payload(user_text):
    if is_raw_reading_request(user_text):
        return {
            'text': NO_RAW_READING_REPLY,
            'actions': [],
            'character_state': 'help',
        }
    if is_rank_request(user_text):
        return {
            'text': NO_RANK_REPLY,
            'actions': [],
            'character_state': 'help',
        }
    return None


def capability_or_none(user_text):
    from features.assistant.conversation import is_capability_question
    if is_capability_question(user_text):
        return {
            'text': CAPABILITY_REPLY,
            'actions': [],
            'character_state': 'help',
        }
    return None


def _has_peer_facts(tool_results):
    for item in tool_results or ():
        if item.get('name') in {'get_peer_facts', 'get_subject_peer_reference'}:
            return True
    return False


def _looks_like_dump(text):
    raw = text or ''
    if 'function' in raw and 'parameters' in raw:
        return True
    if raw.count('{') > 8:
        return True
    if 'os.environ' in raw or 'API_KEY' in raw:
        return True
    return False


def _claimed_zero_for_unavailable(text, tool_results):
    if not ZERO_CLAIM.search(text or ''):
        return False
    for item in tool_results or ():
        result = item.get('result') or {}
        for fact in result.get('facts') or ():
            if fact.get('available') is False:
                return True
    return False


def _unavailable_zero_text(tool_results):
    for item in tool_results or ():
        result = item.get('result') or {}
        for fact in result.get('facts') or ():
            if fact.get('available') is False:
                return (
                    '현재는 0점으로 계산된 것이 아니라, '
                    '비교할 자료가 충분하지 않아 값을 제공할 수 없는 상태입니다.'
                )
    return None
