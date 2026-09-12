"""Output harness. 시스템/원문/순위 누출을 최종 응답 전에 막는다."""
from __future__ import annotations

import re

from features.assistant.copy import (
    CAPABILITY_REPLY,
    NO_ATTENDANCE_FROM_LEARNING_REPLY,
    NO_IMPUTATION_REPLY,
    NO_RANK_REPLY,
    NO_RAW_READING_REPLY,
    POLICY_SCOPE_REPLY,
)

RANK_MARKERS = (
    '몇 등', '등수', '백분위', '상위 몇', '하위 몇', '1등', '꼴등',
    '제일 잘', '제일 못해', '꼴찌', '하위권', '상위권', '최하위', '최상위', 'percentile',
)
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
ZERO_CLAIM = re.compile(r'0으로 계산')


def is_rank_request(text):
    raw = text or ''
    if any(marker in raw for marker in RANK_MARKERS):
        return True
    return bool(re.search(r'제일.{0,8}못해', raw))


def is_raw_reading_request(text):
    raw = text or ''
    return any(marker in raw for marker in RAW_READING_MARKERS)


def is_injection_request(text):
    raw = (text or '').casefold()
    return any(marker.casefold() in raw for marker in INJECTION_MARKERS)


def is_imputation_request(text):
    raw = text or ''
    missing = any(token in raw for token in (
        '없는 날', '기록 없는', '빠진 날', '비어 있는', '없는 값', '빠진 값',
    ))
    fill = any(token in raw for token in (
        '채우', '추정', '적당히', '평균값', '0으로',
    ))
    if missing and fill:
        return True
    return any(token in raw for token in (
        '채워 계산', '채워서 계산', '적당히 채', '추정해서 계산',
        '0으로 넣어서', '0으로 넣', '평균값으로 채',
    ))


def is_attendance_equivalence_request(text):
    raw = text or ''
    study = any(token in raw for token in ('공부', '학습'))
    attend = any(token in raw for token in (
        '출석', '온 거', '온거', '온 거잖아',
    ))
    return study and attend


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
    if is_injection_request(user_text):
        return {
            'text': POLICY_SCOPE_REPLY,
            'actions': [],
            'character_state': 'help',
        }
    if is_imputation_request(user_text):
        return {
            'text': NO_IMPUTATION_REPLY,
            'actions': [],
            'character_state': 'help',
        }
    if is_attendance_equivalence_request(user_text):
        return {
            'text': NO_ATTENDANCE_FROM_LEARNING_REPLY,
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
    cleaned = text or ''
    for item in tool_results or ():
        result = item.get('result') or {}
        for fact in result.get('facts') or ():
            if fact.get('available') is not False:
                continue
            if ZERO_CLAIM.search(cleaned):
                return True
            label = str(fact.get('label') or '').strip()
            if label and re.search(
                re.escape(label) + r'.{0,16}(?:0점|0일|0권|0%|0페이지|0건)',
                cleaned,
            ):
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
