"""Structured conversational state. transcript와 분리. packet/원문 없음."""
from __future__ import annotations

import re

from features.assistant.copy import (
    CAPABILITY_REPLY,
    CONFIRM_OTHER,
    CONFIRM_YES,
    FALLBACK,
    FUZZY_CONFIRM,
    MSG_NEED_CHILD_FACTS,
    NAV_CHOICE_INVALID,
    NAV_NEED_NAME,
    NAV_NO_MATCH,
    choice_need_text,
    opening_text,
)
from features.assistant.intents import is_greeting, wants_data, wants_help
from features.assistant.navigation import lookup_child, spec_for
from features.assistant.resolve import (
    SEARCH_LIMIT,
    normalize_nickname,
    resolve_children,
    select_child_resolution,
)

SUBJECTS = frozenset({'math', 'korean', 'ssen'})
TOPICS = frozenset({'learning', 'points', 'reading', 'peer', 'help', 'setup', 'nav', 'growth'})
REQUESTED_METRICS = frozenset({
    'summary', 'records', 'recent_total', 'previous_total',
    'change', 'cumulative', 'composition', 'average',
})
PENDING_TYPES = frozenset({'navigate', 'facts'})
AWAITING = frozenset({'child', 'child_confirmation', 'candidate_selection', 'domain'})
DOMAIN_ALL = frozenset({
    '다', '전부', '전체', '다보여줘', '전부보여줘', '전체보여줘',
    '다보여주세요', '전부다', '다요',
})
CANDIDATE_RESET = frozenset({'처음으로', '새 대화', '새대화'})
_ORDINAL_DIGIT = re.compile(r'^(\d+)\s*번(?:째)?$')
_KOREAN_ORDINAL = {
    '첫번째': 1, '첫번째요': 1, '첫째': 1, '첫째요': 1,
    '두번째': 2, '두번째요': 2, '둘째': 2, '둘째요': 2,
    '세번째': 3, '세번째요': 3, '셋째': 3, '셋째요': 3,
    '네번째': 4, '네번째요': 4, '넷째': 4, '넷째요': 4,
    '다섯번째': 5, '다섯번째요': 5, '다섯째': 5,
    '여섯번째': 6, '여섯번째요': 6, '여섯째': 6,
    '일곱번째': 7, '일곱번째요': 7, '일곱째': 7,
    '여덟번째': 8, '여덟번째요': 8, '여덟째': 8,
}
FACT_TOOLS = {
    'get_growth_facts': 'growth',
    'get_learning_facts': 'learning',
    'get_points_facts': 'points',
    'get_reading_facts': 'reading',
    'get_peer_facts': 'peer',
    'get_subject_peer_reference': 'peer',
}
AFFIRM = frozenset({
    '응', '어', '네', '예', '맞아', '맞아요', '맞습니다', '맞어',
    'ㅇㅇ', '그래', '그래요', '그 아이', '그 아동', '그 학생',
    '맞다', '웅',
})
REJECT_PREFIXES = ('아니야', '아니요', '아니', '아님', '다른 아동', '다른 아이', '틀렸', '아니 그')
CAPABILITY_HINTS = (
    '뭐 할 수 있어', '뭘 할 수 있어', '무엇을 할 수', '무슨 일 할 수',
    '뭘 도와', '도움 되는', '할 수 있는 것',
)


def empty_state():
    return {
        'active_child_id': None,
        'active_child_nickname': None,
        'active_subject': None,
        'active_topic': None,
        'pending_action': None,
    }


def sanitize_conversation_state(raw, *, page_context=None):
    data = raw if isinstance(raw, dict) else {}
    state = empty_state()
    child = lookup_child(data.get('active_child_id'))
    if child is not None:
        state['active_child_id'] = child.id
        nickname = normalize_nickname(data.get('active_child_nickname')) or child.name
        state['active_child_nickname'] = str(nickname)[:40]
    subject = data.get('active_subject')
    if subject in SUBJECTS:
        state['active_subject'] = subject
    topic = data.get('active_topic')
    if topic in TOPICS:
        state['active_topic'] = topic
    state['pending_action'] = _sanitize_pending(data.get('pending_action'))
    return apply_page_priority(state, page_context)


def apply_page_priority(state, page_context):
    """페이지 아동은 대화 아동이 없을 때만 채운다.

    명시적/직전 conversational child를 오래된 페이지 아동으로 덮어쓰지 않는다.
    확인·후보 선택 대기 상태는 페이지 아동 때문에 폐기하지 않는다.
    """
    state = dict(state or empty_state())
    page_child = lookup_child((page_context or {}).get('child_id'))
    if page_child is None:
        return state
    pending = state.get('pending_action') or {}
    if pending.get('awaiting') in {'child_confirmation', 'candidate_selection'}:
        return state
    if state.get('active_child_id'):
        return state
    state['active_child_id'] = page_child.id
    state['active_child_nickname'] = page_child.name
    return state


def public_conversation_state(state):
    state = state or empty_state()
    out = {}
    if state.get('active_child_id'):
        out['active_child_id'] = int(state['active_child_id'])
    if state.get('active_child_nickname'):
        out['active_child_nickname'] = str(state['active_child_nickname'])[:40]
    if state.get('active_subject') in SUBJECTS:
        out['active_subject'] = state['active_subject']
    if state.get('active_topic') in TOPICS:
        out['active_topic'] = state['active_topic']
    pending = _sanitize_pending(state.get('pending_action'))
    if pending:
        out['pending_action'] = pending
    return out


def tool_page_context(page_context, state):
    """tool 실행용. 페이지 child_id는 유지하고, 없을 때만 대화 아동을 채운다.

    기본 binding은 conversational child가 페이지보다 우선이다.
    "이 아이/현재 아동"은 원래 page_context.child_id를 쓴다.
    """
    context = dict(page_context or {})
    if context.get('child_id'):
        return context
    child_id = (state or {}).get('active_child_id')
    child = lookup_child(child_id)
    if child is not None:
        context['child_id'] = child.id
        context['child_name'] = child.name
    return context


def is_capability_question(text):
    raw = text or ''
    return any(hint in raw for hint in CAPABILITY_HINTS)


def is_affirmation(text):
    compact = normalize_nickname(text).replace('!', '').replace('.', '').replace('~', '')
    compact = compact.replace('요', '').strip()
    return compact in AFFIRM


def reject_remainder(text):
    raw = normalize_nickname(text)
    for prefix in REJECT_PREFIXES:
        if raw.startswith(prefix):
            rest = normalize_nickname(raw[len(prefix):].lstrip(' ,.'))
            return True, rest
    return False, ''


def should_skip_pending_fill(text):
    raw = (text or '').strip()
    if not raw:
        return True
    if is_greeting(raw) or is_capability_question(raw):
        return True
    if wants_help(raw) and ('뭐야' in raw or '뜻' in raw or '의미' in raw):
        return True
    if any(token in raw for token in ('원문', '몇 등', '등수', '백분위', '시스템 프롬프트', '이전 지시')):
        return True
    if len(raw) > 48:
        return True
    return False


def recover_pending_from_messages(messages, state):
    """LLM이 pending을 안 남긴 경우, 직전 사용자 요청에서 slot만 복구한다."""
    state = dict(state or empty_state())
    if state.get('pending_action'):
        return state
    last = ''
    prev_user = ''
    users = []
    for item in messages or ():
        if isinstance(item, dict) and item.get('role') == 'user':
            users.append(item.get('content') or '')
    if len(users) < 1:
        return state
    last = users[-1]
    if not _looks_like_slot_fill(last):
        return state
    if len(users) < 2:
        return state
    prev_user = users[-2]
    from features.assistant.navigation import extract_child_query, match_destination_from_text
    destination = match_destination_from_text(prev_user)
    spec = spec_for(destination)
    if spec is None or not spec.child_required:
        return state
    query = extract_child_query(prev_user)
    if query:
        resolved = resolve_children(query)
        matches = resolved.get('matches') or []
        if resolved.get('needs_confirmation') or resolved.get('kind') == 'fuzzy':
            if matches:
                pending = pending_need_child(destination=destination)
                pending['awaiting'] = 'child_confirmation'
                pending['candidate_child_id'] = matches[0].get('id')
                pending['candidate_nickname'] = matches[0].get('name')
                pending.pop('missing', None)
                state['pending_action'] = pending
                return state
        if resolved.get('kind') in {'exact', 'partial'} and len(matches) == 1:
            return state
    state['pending_action'] = pending_need_child(destination=destination)
    return state


def _looks_like_slot_fill(text):
    raw = normalize_nickname(text)
    if not raw:
        return False
    if is_affirmation(raw):
        return True
    rejected, _remainder = reject_remainder(raw)
    if rejected:
        return True
    if should_skip_pending_fill(raw):
        return False
    if any(token in raw for token in ('또래', '국어는', '수학은', '완료', '포인트', '왜', '뭐야', '진도')):
        return False
    return len(raw) <= 24


def apply_pending_turn(text, *, state, page_context, role):
    """missing slot / fuzzy confirmation만 처리. 거대한 intent machine이 아니다."""
    pending = _sanitize_pending((state or {}).get('pending_action'))
    if not pending:
        return None
    raw = normalize_nickname(text)
    if pending.get('awaiting') == 'child_confirmation':
        rejected, remainder = reject_remainder(raw)
        if is_affirmation(raw):
            child = lookup_child(pending.get('candidate_child_id'))
            if child is None:
                state['pending_action'] = _pending_need_child(pending)
                return _need_child_payload(state, pending)
            return _execute_pending(state, pending, child, role=role, page_context=page_context)
        if rejected:
            if remainder:
                return _resolve_for_pending(
                    remainder, state, pending, role=role, page_context=page_context,
                )
            state['pending_action'] = _pending_need_child(pending)
            return _need_child_payload(state, pending)
        if should_skip_pending_fill(raw):
            return None
        return _resolve_for_pending(raw, state, pending, role=role, page_context=page_context)
    if pending.get('awaiting') == 'child' or 'child' in (pending.get('missing') or ()):
        if should_skip_pending_fill(raw):
            return None
        if wants_data(raw) and len(raw) > 12:
            return None
        return _resolve_for_pending(raw, state, pending, role=role, page_context=page_context)
    return None


def apply_pending_confirmation(text, *, state, page_context, role):
    """fuzzy 확인/거절과 저장된 후보 서수 선택만 deterministic하게 처리한다.

    일반 awaiting=child 상태는 여기서 이름으로 추정하지 않는다. 그 입력은
    provider가 pending을 참고해 slot 답변인지 새 요청인지 먼저 판단한다.
    awaiting=domain일 때만 "다/전부/전체"를 지원 가능한 모든 domain 요약으로 처리한다.
    """
    pending = _sanitize_pending((state or {}).get('pending_action'))
    if not pending:
        return None
    if pending.get('awaiting') == 'candidate_selection':
        return _apply_candidate_selection(
            text,
            state=state,
            pending=pending,
            page_context=page_context,
            role=role,
        )
    if pending.get('awaiting') == 'domain':
        return _apply_domain_selection(
            text,
            state=state,
            pending=pending,
            page_context=page_context,
            role=role,
        )
    if pending.get('awaiting') != 'child_confirmation':
        return None
    raw = normalize_nickname(text)
    if is_affirmation(raw):
        child = lookup_child(pending.get('candidate_child_id'))
        if child is None:
            state['pending_action'] = _pending_need_child(pending)
            return _need_child_payload(state, pending)
        if not pending.get('destination') and not pending.get('tool'):
            return _bind_confirmed_child_for_domain(state, child)
        return _execute_pending(
            state,
            pending,
            child,
            role=role,
            page_context=page_context,
        )
    rejected, remainder = reject_remainder(raw)
    if not rejected:
        return None
    if remainder:
        return _resolve_for_pending(
            remainder,
            state,
            pending,
            role=role,
            page_context=page_context,
        )
    state['pending_action'] = _pending_need_child(pending)
    return _need_child_payload(state, pending)


def pending_need_child(*, destination=None, tool=None, subject_key=None, requested_metric=None):
    pending = {
        'type': 'navigate' if destination else 'facts',
        'missing': ['child'],
        'awaiting': 'child',
    }
    if destination:
        pending['destination'] = destination
        pending['type'] = 'navigate'
    if tool:
        pending['tool'] = tool
        pending['type'] = 'facts'
    if subject_key in SUBJECTS:
        pending['subject_key'] = subject_key
    if requested_metric in REQUESTED_METRICS:
        pending['requested_metric'] = requested_metric
    return pending


def confirmation_actions(nickname):
    name = nickname or '이 아동'
    return [
        {
            'type': 'reply',
            'label': CONFIRM_YES.format(name=name),
            'content': '응',
        },
        {
            'type': 'reply',
            'label': CONFIRM_OTHER,
            'content': '아니',
        },
    ]


def confirmation_text(child):
    name = (child or {}).get('name') or '이 아동'
    grade = (child or {}).get('grade')
    if grade in (None, ''):
        return f'{name} 아동을 말씀하시는 건가요?'
    return FUZZY_CONFIRM.format(grade=grade, name=name)


def is_domain_all(text):
    compact = normalize_nickname(text).replace(' ', '')
    return compact in DOMAIN_ALL


def fake_follow_up_call(text, state):
    """fake QA 전용. live 자연어 품질을 phrase로 대체하지 않는다."""
    child_id = (state or {}).get('active_child_id')
    if not child_id:
        return None
    raw = (text or '').strip()
    if any(token in raw for token in ('알려', '열어', '이 아이', '이 아동', '현재 아동')):
        return None
    from features.assistant.navigation import classify_remainder_domain, extract_child_query, request_remainder
    from features.assistant.resolve import resolve_children
    query = extract_child_query(text)
    nickname = normalize_nickname((state or {}).get('active_child_nickname'))
    entity_span = None
    if query and normalize_nickname(query) not in {nickname, ''}:
        resolved = resolve_children(query)
        if resolved.get('matches'):
            match_id = resolved['matches'][0].get('id')
            if match_id != child_id:
                return None
            entity_span = query
    elif query and normalize_nickname(query) in {nickname, ''}:
        entity_span = nickname or query
    remainder = request_remainder(text, entity_span, (state or {}).get('active_child_nickname'))
    raw = remainder or ''
    args = {'child_id': child_id}
    subject = (state or {}).get('active_subject')
    classified = classify_remainder_domain(remainder)
    if classified and classified.get('kind') == 'peer':
        if subject in SUBJECTS:
            args['subject_key'] = subject
        if classified.get('subject_key'):
            args['subject_key'] = classified['subject_key']
        return ('get_peer_facts', args)
    if '완료' in raw or '예상' in raw:
        if subject in SUBJECTS:
            args['subject_key'] = subject
        return ('get_learning_facts', args)
    if classified and classified.get('tool') in {
        'get_points_facts', 'get_reading_facts', 'get_learning_facts',
    }:
        if classified.get('subject_key'):
            args['subject_key'] = classified['subject_key']
        elif classified.get('tool') == 'get_learning_facts' and subject in SUBJECTS:
            args['subject_key'] = subject
        return (classified['tool'], args)
    from features.assistant.facts import infer_metric_focus
    focus = infer_metric_focus(raw)
    if focus:
        topic = (state or {}).get('active_topic')
        tool = {
            'reading': 'get_reading_facts',
            'points': 'get_points_facts',
            'learning': 'get_learning_facts',
            'growth': 'get_growth_facts',
        }.get(topic)
        if tool:
            args['focus'] = focus
            if subject in SUBJECTS and tool in {'get_learning_facts', 'get_peer_facts'}:
                args['subject_key'] = subject
            return (tool, args)
    return None


def update_state_from_tools(state, tool_results, *, page_context=None, user_text=None):
    state = dict(state or empty_state())
    previous_pending = _sanitize_pending(state.get('pending_action'))
    selected_search = _selected_search_resolution(tool_results)
    fuzzy_match = _fuzzy_match_from_tools(tool_results)
    multiple_matches = _multiple_matches_from_tools(tool_results)
    pending = previous_pending
    if selected_search and selected_search.get('kind') in {'exact', 'partial'}:
        matches = selected_search.get('matches') or []
        if len(matches) == 1:
            _bind_child(state, matches[0])
    for item in tool_results or ():
        name = item.get('name')
        arguments = item.get('arguments') if isinstance(item.get('arguments'), dict) else {}
        result = item.get('result') or {}
        if name == 'search_child':
            continue
        if name == 'navigate':
            if fuzzy_match:
                dest = result.get('destination') or arguments.get('destination')
                pending = pending_need_child(destination=dest)
                continue
            if result.get('ok') and result.get('child'):
                _bind_child(state, result['child'])
                state['active_topic'] = 'nav'
                pending = None
            elif result.get('error') == 'missing_child':
                dest = result.get('destination') or arguments.get('destination')
                pending = pending_need_child(destination=dest)
            continue
        topic = FACT_TOOLS.get(name)
        if topic:
            if fuzzy_match:
                pending = pending_need_child(
                    tool=name,
                    subject_key=arguments.get('subject_key'),
                    requested_metric=arguments.get('requested_metric'),
                )
                continue
            if result.get('ok') and result.get('child'):
                _bind_child(state, result['child'])
                state['active_topic'] = topic
                subject = arguments.get('subject_key')
                if subject in SUBJECTS:
                    state['active_subject'] = subject
                pending = None
            elif result.get('error') in {'invalid_child', 'missing_child'}:
                pending = pending_need_child(
                    tool=name,
                    subject_key=arguments.get('subject_key'),
                    requested_metric=arguments.get('requested_metric'),
                )
            continue
        if name == 'search_help' and result.get('ok'):
            state['active_topic'] = 'help'
            pending = None
            continue
        if name == 'get_center_setup_status' and result.get('ok'):
            state['active_topic'] = 'setup'
            pending = None
    if fuzzy_match:
        pending = pending or _pending_from_nav_or_facts(tool_results, state) or pending_need_child(
            destination=_destination_from_tools(tool_results),
        )
        pending = dict(pending)
        pending['awaiting'] = 'child_confirmation'
        pending['candidate_child_id'] = fuzzy_match.get('id')
        pending['candidate_nickname'] = fuzzy_match.get('name')
        pending.pop('missing', None)
        state['pending_action'] = pending
    elif multiple_matches:
        pending = (
            _pending_from_nav_or_facts(tool_results, state)
            or previous_pending
            or pending_need_child(destination=_destination_from_tools(tool_results))
        )
        selected = _selected_search_resolution(tool_results) or {}
        state['pending_action'] = _candidate_pending(
            pending,
            multiple_matches,
            query=_search_query_from_tools(tool_results),
            match_type=selected.get('match_type'),
        )
    elif pending:
        state['pending_action'] = pending
    elif _should_await_domain(selected_search, tool_results, user_text=user_text):
        state['pending_action'] = pending_need_domain()
    else:
        state['pending_action'] = None
    return apply_page_priority(state, page_context)


def _fuzzy_match_from_tools(tool_results):
    result = _selected_search_resolution(tool_results)
    matches = (result or {}).get('matches') or []
    if (result or {}).get('needs_confirmation') and len(matches) == 1:
        return matches[0]
    return None


def _multiple_matches_from_tools(tool_results):
    result = _selected_search_resolution(tool_results)
    matches = (result or {}).get('matches') or []
    if (result or {}).get('kind') == 'multiple' and len(matches) > 1:
        return matches
    return None


def _selected_search_resolution(tool_results):
    results = []
    for item in tool_results or ():
        if item.get('name') != 'search_child':
            continue
        result = item.get('result') or {}
        if isinstance(result, dict):
            results.append(result)
    return select_child_resolution(results)


def child_resolution_payload(state, tool_results):
    """LLM이 선택한 search_child 결과를 안전한 후보 UI로 정규화한다."""
    fuzzy = _fuzzy_match_from_tools(tool_results)
    pending = _sanitize_pending((state or {}).get('pending_action'))
    if fuzzy and pending:
        return confirmation_payload(state, fuzzy, pending=pending)
    multiple = _multiple_matches_from_tools(tool_results)
    if multiple and pending:
        selected = _selected_search_resolution(tool_results) or {}
        return choice_payload(
            state,
            multiple,
            pending=pending,
            query=selected.get('child_query') or _search_query_from_tools(tool_results),
            match_type=selected.get('match_type'),
        )
    return None


def confirmation_payload(state, match, *, pending):
    child = match if isinstance(match, dict) else {}
    pending = dict(pending or pending_need_child())
    pending['awaiting'] = 'child_confirmation'
    pending['candidate_child_id'] = child.get('id')
    pending['candidate_nickname'] = child.get('name')
    pending.pop('missing', None)
    state['pending_action'] = pending
    return {
        'text': confirmation_text(child),
        'actions': confirmation_actions(child.get('name')),
        'status': None,
        'character_state': 'help',
        'handled': True,
    }


def choice_payload(state, matches, *, pending, query=None, match_type=None):
    stored = _candidate_pending(
        pending,
        matches,
        query=query or (pending or {}).get('query'),
        match_type=match_type or (pending or {}).get('match_type'),
    )
    candidates = stored.get('candidates') or []
    state['pending_action'] = stored
    actions = []
    for index, child in enumerate(candidates, start=1):
        name = child.get('name')
        grade = child.get('grade')
        label = f"{index}. {name} ({grade}학년)" if grade not in (None, '') else f"{index}. {name}"
        actions.append({
            'type': 'reply',
            'label': label,
            'content': f'{index}번째',
        })
    return {
        'text': _choice_message(stored.get('query'), stored.get('match_type'), candidates),
        'actions': actions,
        'status': None,
        'character_state': 'help',
        'candidates': candidates,
        'handled': True,
        'candidate_count': len(candidates),
        'match_type': stored.get('match_type'),
    }


def capability_payload():
    return {
        'text': CAPABILITY_REPLY,
        'actions': [],
        'status': None,
        'character_state': 'help',
        'handled': True,
    }


def _sanitize_pending(raw):
    if not isinstance(raw, dict):
        return None
    pending_type = raw.get('type')
    if pending_type not in PENDING_TYPES:
        return None
    awaiting = raw.get('awaiting')
    if awaiting not in AWAITING:
        awaiting = 'child'
    pending = {
        'type': pending_type,
        'awaiting': awaiting,
    }
    missing = raw.get('missing')
    if isinstance(missing, list):
        pending['missing'] = [item for item in missing if item in {'child'}][:4]
    destination = raw.get('destination')
    if isinstance(destination, str) and spec_for(destination):
        pending['destination'] = spec_for(destination).key
    tool = raw.get('tool')
    if tool in FACT_TOOLS:
        pending['tool'] = tool
    subject = raw.get('subject_key')
    if subject in SUBJECTS:
        pending['subject_key'] = subject
    requested_metric = raw.get('requested_metric')
    if requested_metric in REQUESTED_METRICS:
        pending['requested_metric'] = requested_metric
    query = raw.get('query')
    if isinstance(query, str) and query.strip():
        pending['query'] = query.strip()[:40]
    match_type = raw.get('match_type')
    if match_type in {'exact', 'partial', 'fuzzy'}:
        pending['match_type'] = match_type
    candidates = _sanitize_candidates(raw.get('candidates'))
    if awaiting == 'candidate_selection':
        if len(candidates) < 2:
            pending['awaiting'] = 'child'
            pending['missing'] = ['child']
        else:
            pending['candidates'] = candidates
            pending.pop('missing', None)
    if awaiting == 'child_confirmation':
        child = lookup_child(raw.get('candidate_child_id'))
        if child is None:
            pending['awaiting'] = 'child'
            pending['missing'] = ['child']
        else:
            pending['candidate_child_id'] = child.id
            pending['candidate_nickname'] = str(raw.get('candidate_nickname') or child.name)[:40]
    if pending['type'] == 'navigate' and not pending.get('destination'):
        if awaiting not in {'child_confirmation', 'candidate_selection'}:
            return None
    if pending['type'] == 'facts' and not pending.get('tool'):
        if awaiting not in {'child_confirmation', 'candidate_selection', 'domain'}:
            return None
    return pending


def pending_need_domain():
    return {
        'type': 'facts',
        'awaiting': 'domain',
    }


def _pending_need_child(pending):
    next_pending = dict(pending or {})
    next_pending['awaiting'] = 'child'
    next_pending['missing'] = ['child']
    next_pending.pop('candidate_child_id', None)
    next_pending.pop('candidate_nickname', None)
    next_pending.pop('candidates', None)
    next_pending.pop('query', None)
    next_pending.pop('match_type', None)
    return next_pending


def _need_child_payload(state, pending):
    state['pending_action'] = _sanitize_pending(pending) or pending
    text = NAV_NEED_NAME if (pending or {}).get('type') == 'navigate' else MSG_NEED_CHILD_FACTS
    return {
        'text': text,
        'actions': [],
        'status': None,
        'character_state': 'help',
        'handled': True,
        'error': 'missing_child',
    }


def _resolve_for_pending(query, state, pending, *, role, page_context):
    resolved = resolve_children(query)
    kind = resolved.get('kind')
    matches = resolved.get('matches') or []
    if kind == 'none' or not matches:
        return {
            'text': NAV_NO_MATCH,
            'actions': [],
            'status': None,
            'character_state': 'help',
            'handled': True,
            'error': 'no_child_match',
        }
    if kind == 'multiple':
        return choice_payload(
            state,
            matches,
            pending=pending,
            query=query,
            match_type=resolved.get('match_type'),
        )
    if resolved.get('needs_confirmation') or kind == 'fuzzy':
        return confirmation_payload(state, matches[0], pending=pending)
    child = lookup_child(matches[0].get('id'))
    if child is None:
        return {
            'text': NAV_NO_MATCH,
            'actions': [],
            'status': None,
            'character_state': 'help',
            'handled': True,
            'error': 'no_child_match',
        }
    return _execute_pending(state, pending, child, role=role, page_context=page_context)


def _execute_pending(state, pending, child, *, role, page_context, selected_index=None):
    from features.assistant.policy import gated_execute
    from features.assistant.provider import compose_from_tools

    found = lookup_child(getattr(child, 'id', None) or (child.get('id') if isinstance(child, dict) else None))
    if found is None:
        return {
            'text': NAV_NO_MATCH,
            'actions': [],
            'status': None,
            'character_state': 'help',
            'handled': True,
            'error': 'no_child_match',
        }
    child = found
    extra = {}
    if selected_index is not None:
        extra['selected_candidate_index'] = int(selected_index)
        extra['candidate_count'] = len((pending or {}).get('candidates') or ())
        extra['match_type'] = (pending or {}).get('match_type')
    if pending.get('type') == 'navigate':
        destination = pending.get('destination')
        result = gated_execute(
            'navigate',
            {'destination': destination, 'child_id': child.id},
            page_context=page_context,
            role=role,
            conversation_state=state,
        )
        if not result.get('ok'):
            return {
                'text': result.get('message') or FALLBACK,
                'actions': [],
                'status': None,
                'character_state': 'help',
                'error': result.get('error'),
                'handled': True,
                **extra,
            }
        _bind_child(state, {'id': child.id, 'name': child.name, 'grade': getattr(child, 'grade', None)})
        state['pending_action'] = None
        spec = spec_for(result.get('destination'))
        return {
            'text': opening_text(spec.key if spec else destination),
            'actions': [{
                'type': 'navigate',
                'label': f"{result.get('label') or '화면'} 열기",
                'url': result['url'],
                'destination': result.get('destination'),
                'auto': True,
                'params': {'child_id': child.id},
            }],
            'status': None,
            'character_state': 'working',
            'handled': True,
            **extra,
        }
    tool = pending.get('tool') or 'get_growth_facts'
    arguments = {'child_id': child.id}
    if pending.get('subject_key') in SUBJECTS:
        arguments['subject_key'] = pending['subject_key']
        state['active_subject'] = pending['subject_key']
    if pending.get('requested_metric') in REQUESTED_METRICS:
        arguments['requested_metric'] = pending['requested_metric']
    result = gated_execute(
        tool,
        arguments,
        page_context=page_context,
        role=role,
        conversation_state=state,
    )
    if result.get('error') in {'invalid_child', 'forbidden', 'unknown_tool'}:
        return {
            'text': result.get('message') or FALLBACK,
            'actions': [],
            'status': None,
            'character_state': 'help',
            'error': result.get('error'),
            'handled': True,
            **extra,
        }
    _bind_child(state, {'id': child.id, 'name': child.name, 'grade': getattr(child, 'grade', None)})
    state['pending_action'] = None
    completion = compose_from_tools(
        [{'name': tool, 'arguments': arguments, 'result': result}],
        user_text='',
        role=role,
    )
    return {
        'text': completion.text,
        'actions': completion.actions,
        'sources': completion.sources,
        'status': completion.status,
        'character_state': completion.character_state or 'working',
        'handled': True,
        **extra,
    }


def _bind_child(state, child):
    if not child:
        return
    child_id = child.get('id') if isinstance(child, dict) else getattr(child, 'id', None)
    found = lookup_child(child_id)
    if found is None:
        return
    state['active_child_id'] = found.id
    state['active_child_nickname'] = found.name


def _bind_confirmed_child_for_domain(state, child):
    from features.assistant.persona import child_record_clarification

    found = lookup_child(getattr(child, 'id', None) or (child.get('id') if isinstance(child, dict) else None))
    if found is None:
        return {
            'text': NAV_NO_MATCH,
            'actions': [],
            'status': None,
            'character_state': 'help',
            'handled': True,
            'error': 'no_child_match',
        }
    _bind_child(state, {'id': found.id, 'name': found.name})
    state['pending_action'] = pending_need_domain()
    return {
        'text': child_record_clarification(found.name),
        'actions': [],
        'status': None,
        'character_state': 'help',
        'handled': True,
    }


def _apply_domain_selection(text, *, state, pending, page_context, role):
    child = lookup_child((state or {}).get('active_child_id'))
    if child is None:
        state['pending_action'] = _pending_need_child(pending)
        return _need_child_payload(state, pending)
    if is_domain_all(text):
        return _execute_domain_summaries(
            state,
            child,
            role=role,
            page_context=page_context,
        )
    from features.assistant.navigation import classify_remainder_domain
    classified = classify_remainder_domain(text)
    if classified is None:
        return None
    if classified.get('kind') == 'navigate':
        next_pending = dict(pending or {})
        next_pending['type'] = 'navigate'
        next_pending['destination'] = classified.get('destination')
        next_pending.pop('awaiting', None)
        next_pending.pop('tool', None)
        return _execute_pending(
            state,
            next_pending,
            child,
            role=role,
            page_context=page_context,
        )
    next_pending = dict(pending or {})
    next_pending['type'] = 'facts'
    next_pending['tool'] = classified.get('tool')
    if classified.get('subject_key'):
        next_pending['subject_key'] = classified['subject_key']
    next_pending.pop('awaiting', None)
    return _execute_pending(
        state,
        next_pending,
        child,
        role=role,
        page_context=page_context,
    )


def _execute_domain_summaries(state, child, *, role, page_context):
    from features.assistant.policy import gated_execute
    from features.assistant.provider import compose_from_tools

    found = lookup_child(getattr(child, 'id', None))
    if found is None:
        return {
            'text': NAV_NO_MATCH,
            'actions': [],
            'status': None,
            'character_state': 'help',
            'handled': True,
            'error': 'no_child_match',
        }
    results = []
    for tool in ('get_learning_facts', 'get_points_facts', 'get_reading_facts'):
        arguments = {'child_id': found.id}
        result = gated_execute(
            tool,
            arguments,
            page_context=page_context,
            role=role,
            conversation_state=state,
        )
        results.append({'name': tool, 'arguments': arguments, 'result': result})
    _bind_child(state, {'id': found.id, 'name': found.name})
    state['pending_action'] = None
    completion = compose_from_tools(results, user_text='', role=role)
    return {
        'text': completion.text,
        'actions': completion.actions,
        'sources': completion.sources,
        'status': completion.status,
        'character_state': completion.character_state or 'working',
        'handled': True,
    }


def _apply_candidate_selection(text, *, state, pending, page_context, role):
    compact = normalize_nickname(text).replace(' ', '')
    if compact in {item.replace(' ', '') for item in CANDIDATE_RESET}:
        state['pending_action'] = None
        return None
    candidates = pending.get('candidates') or []
    index, attempted = _parse_candidate_index(text, candidates)
    if not attempted:
        from features.assistant.navigation import is_explicit_go, match_destination_from_text
        if wants_data(text) or wants_help(text) or is_explicit_go(text) or match_destination_from_text(text):
            state['pending_action'] = None
        return None
    extra = {
        'candidate_count': len(candidates),
        'match_type': pending.get('match_type'),
    }
    if index is None:
        state['pending_action'] = pending
        return {
            'text': NAV_CHOICE_INVALID,
            'actions': _choice_actions_from_candidates(candidates),
            'status': None,
            'character_state': 'help',
            'candidates': candidates,
            'handled': True,
            **extra,
        }
    child = lookup_child(candidates[index].get('id'))
    if child is None:
        state['pending_action'] = pending
        return {
            'text': NAV_NO_MATCH,
            'actions': _choice_actions_from_candidates(candidates),
            'status': None,
            'character_state': 'help',
            'handled': True,
            'error': 'no_child_match',
            **extra,
        }
    return _execute_pending(
        state,
        pending,
        child,
        role=role,
        page_context=page_context,
        selected_index=index,
    )


def _parse_candidate_index(text, candidates):
    raw = normalize_nickname(text)
    if not raw or not candidates:
        return None, False
    compact = raw.replace(' ', '')
    digit = _ORDINAL_DIGIT.match(compact)
    if digit:
        number = int(digit.group(1))
        index = number - 1
        if 0 <= index < len(candidates):
            return index, True
        return None, True
    korean = _KOREAN_ORDINAL.get(compact)
    if korean is not None:
        index = korean - 1
        if 0 <= index < len(candidates):
            return index, True
        return None, True
    needle = normalize_nickname(raw)
    hits = [
        index
        for index, child in enumerate(candidates)
        if normalize_nickname(child.get('name')) == needle
    ]
    if len(hits) == 1:
        return hits[0], True
    return None, False


def _candidate_pending(pending, matches, *, query=None, match_type=None):
    next_pending = dict(pending or pending_need_child())
    candidates = _compact_candidates(matches)
    next_pending['awaiting'] = 'candidate_selection' if len(candidates) >= 2 else 'child'
    next_pending['candidates'] = candidates
    next_pending.pop('candidate_child_id', None)
    next_pending.pop('candidate_nickname', None)
    next_pending.pop('missing', None)
    if len(candidates) < 2:
        next_pending['missing'] = ['child']
        next_pending.pop('candidates', None)
    nickname = str(query or next_pending.get('query') or '').strip()[:40]
    if nickname:
        next_pending['query'] = nickname
    kind = match_type or next_pending.get('match_type')
    if kind in {'exact', 'partial', 'fuzzy'}:
        next_pending['match_type'] = kind
    return next_pending


def _compact_candidates(matches):
    found = []
    seen = set()
    for child in matches or ():
        if not isinstance(child, dict):
            continue
        row = lookup_child(child.get('id') or child.get('child_id'))
        if row is None or row.id in seen:
            continue
        seen.add(row.id)
        found.append({
            'id': row.id,
            'name': str(row.name)[:40],
            'grade': getattr(row, 'grade', None),
        })
        if len(found) >= SEARCH_LIMIT:
            break
    return found


def _sanitize_candidates(raw):
    found = []
    seen = set()
    if not isinstance(raw, list):
        return found
    for child in raw[:SEARCH_LIMIT]:
        if not isinstance(child, dict):
            continue
        row = lookup_child(child.get('id') or child.get('child_id'))
        if row is None or row.id in seen:
            continue
        seen.add(row.id)
        found.append({
            'id': row.id,
            'name': str(child.get('name') or row.name)[:40],
            'grade': child.get('grade') if child.get('grade') is not None else getattr(row, 'grade', None),
        })
    return found


def _choice_message(query, match_type, candidates):
    lines = [choice_need_text(query, match_type)]
    for index, child in enumerate(candidates or (), start=1):
        name = child.get('name') or ''
        grade = child.get('grade')
        if grade not in (None, ''):
            lines.append(f"{index}. {name} ({grade}학년)")
        else:
            lines.append(f"{index}. {name}")
    return '\n'.join(lines)


def _choice_actions_from_candidates(candidates):
    actions = []
    for index, child in enumerate(candidates or (), start=1):
        name = child.get('name')
        grade = child.get('grade')
        label = f"{index}. {name} ({grade}학년)" if grade not in (None, '') else f"{index}. {name}"
        actions.append({
            'type': 'reply',
            'label': label,
            'content': f'{index}번째',
        })
    return actions


def _search_query_from_tools(tool_results):
    for item in tool_results or ():
        if item.get('name') != 'search_child':
            continue
        arguments = item.get('arguments') if isinstance(item.get('arguments'), dict) else {}
        result = item.get('result') if isinstance(item.get('result'), dict) else {}
        query = arguments.get('child_query') or arguments.get('query') or result.get('child_query')
        if query:
            return str(query)[:40]
    return ''


def _should_await_domain(selected_search, tool_results, user_text=None):
    if not selected_search or selected_search.get('kind') not in {'exact', 'partial'}:
        return False
    if len(selected_search.get('matches') or []) != 1:
        return False
    search_items = [
        item for item in tool_results or ()
        if item.get('name') == 'search_child'
    ]
    if len(search_items) != 1:
        return False
    if user_text:
        from features.assistant.navigation import classify_remainder_domain, request_remainder
        child_name = (selected_search.get('matches') or [{}])[0].get('name')
        query = _search_query_from_tools(tool_results)
        if classify_remainder_domain(request_remainder(user_text, child_name, query)) is None:
            return True
    if any(item.get('name') not in {None, 'search_child'} for item in tool_results or ()):
        if any(
            (item.get('result') or {}).get('skipped_unspecified_domain')
            for item in tool_results or ()
        ):
            return True
        return False
    arguments = search_items[0].get('arguments') if isinstance(search_items[0].get('arguments'), dict) else {}
    continuation = arguments.get('continuation')
    return continuation in {None, '', 'search_only'}


def _destination_from_tools(tool_results):
    for item in tool_results or ():
        if item.get('name') != 'navigate':
            continue
        arguments = item.get('arguments') if isinstance(item.get('arguments'), dict) else {}
        result = item.get('result') or {}
        dest = result.get('destination') or arguments.get('destination')
        if spec_for(dest):
            return spec_for(dest).key
    return None


def _pending_from_nav_or_facts(tool_results, state):
    dest = _destination_from_tools(tool_results)
    if dest:
        return pending_need_child(destination=dest)
    for item in tool_results or ():
        name = item.get('name')
        if name in FACT_TOOLS:
            arguments = item.get('arguments') if isinstance(item.get('arguments'), dict) else {}
            return pending_need_child(
                tool=name,
                subject_key=arguments.get('subject_key'),
                requested_metric=arguments.get('requested_metric'),
            )
        if name == 'search_child':
            arguments = item.get('arguments') if isinstance(item.get('arguments'), dict) else {}
            continuation = arguments.get('continuation')
            if continuation == 'navigate' and spec_for(arguments.get('destination')):
                return pending_need_child(destination=arguments.get('destination'))
            if continuation in FACT_TOOLS:
                return pending_need_child(
                    tool=continuation,
                    subject_key=arguments.get('subject_key'),
                    requested_metric=arguments.get('requested_metric'),
                )
    if state.get('pending_action'):
        return dict(state['pending_action'])
    return None


def _role_safe():
    try:
        from features.assistant.config import current_role
        return current_role()
    except Exception:
        return None
