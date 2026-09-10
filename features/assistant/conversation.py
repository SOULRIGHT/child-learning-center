"""Structured conversational state. transcript와 분리. packet/원문 없음."""
from __future__ import annotations

from features.assistant.copy import (
    CAPABILITY_REPLY,
    CONFIRM_OTHER,
    CONFIRM_YES,
    FALLBACK,
    FUZZY_CONFIRM,
    MSG_NEED_CHILD_FACTS,
    NAV_NEED_CHOICE,
    NAV_NEED_NAME,
    NAV_NO_MATCH,
    opening_text,
)
from features.assistant.intents import is_greeting, wants_data, wants_help
from features.assistant.navigation import lookup_child, resolve_navigation, spec_for
from features.assistant.resolve import normalize_nickname, resolve_children

SUBJECTS = frozenset({'math', 'korean', 'ssen'})
TOPICS = frozenset({'learning', 'points', 'reading', 'peer', 'help', 'setup', 'nav', 'growth'})
PENDING_TYPES = frozenset({'navigate', 'facts'})
AWAITING = frozenset({'child', 'child_confirmation'})
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
    """실제 페이지 아동이 대화 기억보다 우선. client role은 여기서 쓰지 않는다."""
    state = dict(state or empty_state())
    page_child = lookup_child((page_context or {}).get('child_id'))
    if page_child is None:
        return state
    prev = state.get('active_child_id')
    state['active_child_id'] = page_child.id
    state['active_child_nickname'] = page_child.name
    pending = state.get('pending_action')
    if pending and prev and prev != page_child.id:
        if pending.get('awaiting') == 'child_confirmation':
            pending = dict(pending)
            pending.pop('candidate_child_id', None)
            pending.pop('candidate_nickname', None)
            pending['awaiting'] = 'child'
            pending['missing'] = ['child']
            state['pending_action'] = pending
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
    """tool 실행용. 페이지 아동이 있으면 그대로, 없으면 대화 아동."""
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
    """fuzzy 후보 직후의 짧은 확인/거절만 deterministic하게 처리한다.

    일반 awaiting=child 상태는 여기서 이름으로 추정하지 않는다. 그 입력은
    provider가 pending을 참고해 slot 답변인지 새 요청인지 먼저 판단한다.
    """
    pending = _sanitize_pending((state or {}).get('pending_action'))
    if not pending or pending.get('awaiting') != 'child_confirmation':
        return None
    raw = normalize_nickname(text)
    if is_affirmation(raw):
        child = lookup_child(pending.get('candidate_child_id'))
        if child is None:
            state['pending_action'] = _pending_need_child(pending)
            return _need_child_payload(state, pending)
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


def pending_need_child(*, destination=None, tool=None, subject_key=None):
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
        return f'{name}을 말씀하시는 건가요?'
    return FUZZY_CONFIRM.format(grade=grade, name=name)


def fake_follow_up_call(text, state):
    """fake QA 전용. live 자연어 품질을 phrase로 대체하지 않는다."""
    child_id = (state or {}).get('active_child_id')
    if not child_id:
        return None
    raw = (text or '').strip()
    if any(token in raw for token in ('알려', '열어', '이 아이', '이 아동', '현재 아동')):
        return None
    from features.assistant.navigation import extract_child_query
    from features.assistant.resolve import resolve_children
    query = extract_child_query(text)
    nickname = normalize_nickname((state or {}).get('active_child_nickname'))
    if query and normalize_nickname(query) not in {nickname, ''}:
        resolved = resolve_children(query)
        if resolved.get('matches'):
            match_id = resolved['matches'][0].get('id')
            if match_id != child_id:
                return None
    raw = text or ''
    args = {'child_id': child_id}
    subject = (state or {}).get('active_subject')
    if '또래' in raw or '비교' in raw:
        if subject in SUBJECTS:
            args['subject_key'] = subject
        return ('get_peer_facts', args)
    if '완료' in raw or '예상' in raw:
        if subject in SUBJECTS:
            args['subject_key'] = subject
        return ('get_learning_facts', args)
    if '국어' in raw:
        args['subject_key'] = 'korean'
        return ('get_learning_facts', args)
    if '쎈' in raw:
        args['subject_key'] = 'ssen'
        return ('get_learning_facts', args)
    if '수학' in raw:
        args['subject_key'] = 'math'
        return ('get_learning_facts', args)
    if '포인트' in raw:
        return ('get_points_facts', args)
    if '이전' in raw and (state or {}).get('active_topic') == 'points':
        return ('get_points_facts', args)
    return None


def update_state_from_tools(state, tool_results, *, page_context=None):
    state = dict(state or empty_state())
    previous_pending = _sanitize_pending(state.get('pending_action'))
    fuzzy_match = _fuzzy_match_from_tools(tool_results)
    multiple_matches = _multiple_matches_from_tools(tool_results)
    pending = previous_pending
    for item in tool_results or ():
        name = item.get('name')
        arguments = item.get('arguments') if isinstance(item.get('arguments'), dict) else {}
        result = item.get('result') or {}
        if name == 'search_child':
            matches = result.get('matches') or []
            if result.get('kind') in {'exact', 'partial'} and len(matches) == 1:
                _bind_child(state, matches[0])
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
                pending = pending_need_child(tool=name, subject_key=arguments.get('subject_key'))
                continue
            if result.get('ok') and result.get('child'):
                _bind_child(state, result['child'])
                state['active_topic'] = topic
                subject = arguments.get('subject_key')
                if subject in SUBJECTS:
                    state['active_subject'] = subject
                pending = None
            elif result.get('error') in {'invalid_child', 'missing_child'}:
                pending = pending_need_child(tool=name, subject_key=arguments.get('subject_key'))
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
        state['pending_action'] = pending
    elif pending:
        state['pending_action'] = pending
    else:
        state['pending_action'] = None
    return apply_page_priority(state, page_context)


def _fuzzy_match_from_tools(tool_results):
    for item in tool_results or ():
        if item.get('name') != 'search_child':
            continue
        result = item.get('result') or {}
        matches = result.get('matches') or []
        if result.get('needs_confirmation') and len(matches) == 1:
            return matches[0]
    return None


def _multiple_matches_from_tools(tool_results):
    for item in tool_results or ():
        if item.get('name') != 'search_child':
            continue
        result = item.get('result') or {}
        matches = result.get('matches') or []
        if result.get('kind') == 'multiple' and len(matches) > 1:
            return matches
    return None


def child_resolution_payload(state, tool_results):
    """LLM이 선택한 search_child 결과를 안전한 후보 UI로 정규화한다."""
    fuzzy = _fuzzy_match_from_tools(tool_results)
    pending = _sanitize_pending((state or {}).get('pending_action'))
    if fuzzy and pending:
        return confirmation_payload(state, fuzzy, pending=pending)
    multiple = _multiple_matches_from_tools(tool_results)
    if multiple and pending and pending.get('type') == 'navigate':
        return choice_payload(state, multiple, pending=pending)
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


def choice_payload(state, matches, *, pending):
    pending = dict(pending or pending_need_child())
    pending['awaiting'] = 'child'
    pending['missing'] = ['child']
    pending.pop('candidate_child_id', None)
    pending.pop('candidate_nickname', None)
    state['pending_action'] = pending
    actions = []
    destination = pending.get('destination') or 'growth'
    for child in matches:
        resolved = resolve_navigation(destination, {'child_id': child.get('id')}, role=_role_safe())
        if not resolved.get('ok'):
            continue
        actions.append({
            'type': 'navigate',
            'label': f"{child.get('name')} ({child.get('grade')}학년) {resolved.get('label') or '화면'}",
            'url': resolved['url'],
            'destination': destination,
            'auto': False,
            'params': {'child_id': child.get('id')},
        })
    return {
        'text': NAV_NEED_CHOICE,
        'actions': actions,
        'status': None,
        'character_state': 'help',
        'candidates': matches,
        'handled': True,
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
    if awaiting == 'child_confirmation':
        child = lookup_child(raw.get('candidate_child_id'))
        if child is None:
            pending['awaiting'] = 'child'
            pending['missing'] = ['child']
        else:
            pending['candidate_child_id'] = child.id
            pending['candidate_nickname'] = str(raw.get('candidate_nickname') or child.name)[:40]
    if pending['type'] == 'navigate' and not pending.get('destination'):
        return None
    if pending['type'] == 'facts' and not pending.get('tool'):
        return None
    return pending


def _pending_need_child(pending):
    next_pending = dict(pending or {})
    next_pending['awaiting'] = 'child'
    next_pending['missing'] = ['child']
    next_pending.pop('candidate_child_id', None)
    next_pending.pop('candidate_nickname', None)
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
        return choice_payload(state, matches, pending=pending)
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


def _execute_pending(state, pending, child, *, role, page_context):
    from features.assistant.policy import gated_execute
    from features.assistant.provider import compose_from_tools

    _bind_child(state, {'id': child.id, 'name': child.name, 'grade': getattr(child, 'grade', None)})
    state['pending_action'] = None
    if pending.get('type') == 'navigate':
        destination = pending.get('destination')
        result = resolve_navigation(destination, {'child_id': child.id}, role=role)
        if not result.get('ok'):
            return {
                'text': result.get('message') or FALLBACK,
                'actions': [],
                'status': None,
                'character_state': 'help',
                'error': result.get('error'),
                'handled': True,
            }
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
        }
    tool = pending.get('tool') or 'get_growth_facts'
    arguments = {'child_id': child.id}
    if pending.get('subject_key') in SUBJECTS:
        arguments['subject_key'] = pending['subject_key']
        state['active_subject'] = pending['subject_key']
    result = gated_execute(
        tool,
        arguments,
        page_context=page_context,
        role=role,
        conversation_state=state,
    )
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
    }


def _bind_child(state, child):
    if not child:
        return
    child_id = child.get('id')
    found = lookup_child(child_id)
    if found is None:
        return
    state['active_child_id'] = found.id
    state['active_child_nickname'] = found.name


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
            return pending_need_child(tool=name, subject_key=arguments.get('subject_key'))
    if state.get('pending_action'):
        return dict(state['pending_action'])
    return None


def _role_safe():
    try:
        from features.assistant.config import current_role
        return current_role()
    except Exception:
        return None
