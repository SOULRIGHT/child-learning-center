"""결정적 사용자 의도 해석. live LLM / data tool 없음."""
from __future__ import annotations

from features.assistant.config import can_manage_settings, current_role
from features.assistant.copy import (
    FALLBACK,
    DRAWER_NOTICE,
    GREETING_REPLY,
    NAV_NEED_CHOICE,
    NAV_NEED_NAME,
    NAV_NO_MATCH,
    ONBOARDING_DONE,
    ONBOARDING_UNAVAILABLE,
    PAGE_GENERIC,
    QUICK_CHILD_SUMMARY,
    QUICK_CONTINUE_SETUP,
    QUICK_EXPLAIN_PAGE,
    QUICK_OPEN_GROWTH,
    QUICK_OPEN_READING,
    SETUP_CONTINUE,
    SETUP_FORBIDDEN,
    opening_text,
    page_description,
)
from features.assistant.navigation import (
    extract_child_query,
    is_explicit_go,
    match_destination_from_text,
    resolve_navigation,
    spec_for,
)
from features.assistant.resolve import resolve_children
from features.setup.present import attach_setup_hrefs
from features.setup.status import build_center_setup_status

ONBOARDING_PHRASES = (
    '센터 설정',
    '처음 설정',
    '운영 설정',
    '다음 뭐',
    '다음에 뭐',
    '이어서',
    '설정 도와',
    '설정 어떻게',
    '온보딩',
)
EXPLAIN_PHRASES = ('현재 화면', '이 화면', '여기가 어디', '무슨 화면', '화면 설명')
GREETING_PHRASES = ('안녕하세요', '안녕', '헬로', 'hello', 'hi')
HELP_HINTS = (
    '무슨 뜻', '어떤 뜻', '의미', '설명해 줘', '설명해줘', '설명해주세요',
    '도움말', '뭐야', '무엇인가요', '무슨 의미', '없어도', '수 있어',
)
HELP_DEFINITION_HINTS = ('무슨 뜻', '어떤 뜻', '의미', '뭐야', '무엇인가요', '무슨 의미')
DATA_HINTS = (
    '어때', '알려줘', '알려 줘', '알려', '얼마나', '요약', '진도', '또래',
    '비교', '학습일', '포인트', '독서', '완독', '관측', '며칠', '몇 권',
)
QUESTION_HINTS = (
    '어때', '알려', '얼마나', '요약', '무슨', '의미', '뭐야', '며칠',
    '몇 권', '비교', '또래',
)


def is_onboarding_request(text):
    raw = text or ''
    return any(phrase in raw for phrase in ONBOARDING_PHRASES)


def is_explain_request(text):
    raw = text or ''
    return any(phrase in raw for phrase in EXPLAIN_PHRASES)


def is_greeting(text):
    raw = (text or '').strip().casefold()
    if not raw:
        return False
    compact = raw.replace('!', '').replace('~', '').replace('.', '').strip()
    return compact in GREETING_PHRASES or compact.rstrip('요') in GREETING_PHRASES


def wants_help(text):
    raw = text or ''
    return any(phrase in raw for phrase in HELP_HINTS)


def is_help_definition(text):
    raw = text or ''
    return any(phrase in raw for phrase in HELP_DEFINITION_HINTS)


def wants_data(text):
    raw = text or ''
    if not any(phrase in raw for phrase in DATA_HINTS):
        return False
    if (
        is_explicit_go(raw)
        and match_destination_from_text(raw)
        and not any(phrase in raw for phrase in QUESTION_HINTS)
    ):
        return False
    return True


def quick_actions(page_context, role=None):
    role = current_role() if role is None else role
    page_context = page_context or {}
    actions = []
    if can_manage_settings(role):
        actions.append({
            'id': 'continue_setup',
            'label': QUICK_CONTINUE_SETUP,
            'intent': 'continue_setup',
        })
    actions.append({
        'id': 'explain_page',
        'label': QUICK_EXPLAIN_PAGE,
        'intent': 'explain_page',
    })
    if page_context.get('child_id'):
        actions.append({
            'id': 'child_summary',
            'label': QUICK_CHILD_SUMMARY,
            'intent': 'chat',
        })
        actions.append({
            'id': 'open_growth',
            'label': QUICK_OPEN_GROWTH,
            'intent': 'navigate',
            'destination': 'growth',
            'params': {'child_id': page_context['child_id']},
        })
        actions.append({
            'id': 'open_reading',
            'label': QUICK_OPEN_READING,
            'intent': 'navigate',
            'destination': 'reading_history',
            'params': {'child_id': page_context['child_id']},
        })
    else:
        actions.append({
            'id': 'open_growth',
            'label': QUICK_OPEN_GROWTH,
            'intent': 'navigate',
            'destination': 'growth',
        })
        actions.append({
            'id': 'open_reading',
            'label': QUICK_OPEN_READING,
            'intent': 'navigate',
            'destination': 'reading_history',
        })
    return actions


def bootstrap_payload(page_context, role=None):
    role = current_role() if role is None else role
    status = None
    if can_manage_settings(role):
        status = onboarding_status(role)
    return {
        'text': DRAWER_NOTICE,
        'actions': [],
        'status': status,
        'character_state': 'idle',
        'quick_actions': quick_actions(page_context, role),
        'handled': True,
        'source_kind': 'system',
    }


def explain_page_payload(page_context):
    endpoint = (page_context or {}).get('endpoint')
    text = page_description(endpoint)
    if not text:
        text = PAGE_GENERIC
    return {
        'text': text,
        'actions': [],
        'status': None,
        'character_state': 'help',
        'handled': True,
    }


def onboarding_status(role=None):
    role = current_role() if role is None else role
    if not can_manage_settings(role):
        return {
            'available': False,
            'message': SETUP_FORBIDDEN,
            'next': None,
        }
    try:
        presented = attach_setup_hrefs(build_center_setup_status())
    except Exception:
        return {
            'available': False,
            'message': ONBOARDING_UNAVAILABLE,
            'next': None,
        }
    nxt = presented.get('next')
    payload = {
        'available': True,
        'next': None,
        'complete': nxt is None,
    }
    if nxt:
        resolved = resolve_navigation(nxt.get('destination'), {}, role=role)
        payload['next'] = {
            'key': nxt.get('key'),
            'status': nxt.get('status'),
            'label': nxt.get('label'),
            'detail': nxt.get('detail'),
            'action_label': nxt.get('action_label'),
            'destination': nxt.get('destination'),
        }
        if resolved.get('ok'):
            payload['next']['url'] = resolved['url']
            payload['next']['nav_destination'] = resolved['destination']
    return payload


def onboarding_payload(role=None):
    role = current_role() if role is None else role
    if not can_manage_settings(role):
        return {
            'text': SETUP_FORBIDDEN,
            'actions': [],
            'status': {'onboarding': onboarding_status(role)},
            'character_state': 'help',
            'handled': True,
        }
    status = onboarding_status(role)
    if not status.get('available'):
        return {
            'text': status.get('message') or ONBOARDING_UNAVAILABLE,
            'actions': [],
            'status': {'onboarding': status},
            'character_state': 'error',
            'handled': True,
        }
    nxt = status.get('next')
    actions = []
    if nxt and nxt.get('url'):
        text = f"{SETUP_CONTINUE} 지금은 {nxt.get('label')}부터 보면 됩니다. {nxt.get('detail') or ''}".strip()
        actions.append({
            'type': 'navigate',
            'label': f"{nxt.get('label')} 열기",
            'url': nxt['url'],
            'destination': nxt.get('nav_destination'),
            'auto': False,
        })
        state = 'guide'
    else:
        text = ONBOARDING_DONE
        resolved = resolve_navigation('setup_hub', {}, role=role)
        if resolved.get('ok'):
            actions.append({
                'type': 'navigate',
                'label': '설정 화면 열기',
                'url': resolved['url'],
                'destination': 'setup_hub',
                'auto': False,
            })
        state = 'success'
    return {
        'text': text,
        'actions': actions,
        'status': {'onboarding': status},
        'character_state': state,
        'handled': True,
    }


def _choice_actions(children, destination, auto=False):
    actions = []
    spec = spec_for(destination)
    label_base = spec.label if spec else '화면'
    for child in children:
        if isinstance(child, dict):
            child_id = child.get('id')
            name = child.get('name')
            grade = child.get('grade')
        else:
            child_id = getattr(child, 'id', None)
            name = getattr(child, 'name', '')
            grade = getattr(child, 'grade', None)
        resolved = resolve_navigation(destination, {'child_id': child_id}, role=current_role())
        if not resolved.get('ok'):
            continue
        actions.append({
            'type': 'navigate',
            'label': f"{name} ({grade}학년) {label_base}",
            'url': resolved['url'],
            'destination': destination,
            'auto': False,
            'params': {'child_id': child_id},
        })
    return actions


def navigate_payload(destination, params=None, *, page_context=None, auto=False, role=None):
    role = current_role() if role is None else role
    params = dict(params or {})
    spec = spec_for(destination)
    if spec is None:
        resolved = resolve_navigation(destination, params, role=role)
        return {
            'text': resolved.get('message') or FALLBACK,
            'actions': [],
            'status': None,
            'character_state': 'help',
            'error': resolved.get('error'),
            'handled': True,
        }
    if spec.child_required and not params.get('child_id'):
        page_child = (page_context or {}).get('child_id')
        if page_child:
            params['child_id'] = page_child
    resolved = resolve_navigation(destination, params, role=role)
    if resolved.get('ok'):
        return {
            'text': opening_text(spec.key),
            'actions': [{
                'type': 'navigate',
                'label': f"{resolved['label']} 열기",
                'url': resolved['url'],
                'destination': spec.key,
                'auto': bool(auto),
                'params': {'child_id': resolved['child']['id']} if resolved.get('child') else {},
            }],
            'status': None,
            'character_state': 'working',
            'handled': True,
        }
    if resolved.get('error') == 'missing_child':
        return {
            'text': NAV_NEED_NAME,
            'actions': [],
            'status': None,
            'character_state': 'help',
            'error': 'missing_child',
            'destination': spec.key,
            'pending_hint': {
                'type': 'navigate',
                'destination': spec.key,
                'missing': ['child'],
                'awaiting': 'child',
            },
            'handled': True,
        }
    return {
        'text': resolved.get('message') or FALLBACK,
        'actions': [],
        'status': None,
        'character_state': 'help',
        'error': resolved.get('error'),
        'handled': True,
    }


def navigate_from_text(text, page_context, role=None):
    role = current_role() if role is None else role
    destination = match_destination_from_text(text)
    if destination is None:
        return None
    spec = spec_for(destination)
    auto = is_explicit_go(text)
    params = {}
    if spec and spec.child_required:
        query = extract_child_query(text)
        if query:
            resolved = resolve_children(query)
            matches = resolved.get('matches') or []
            if not matches:
                return {
                    'text': NAV_NO_MATCH,
                    'actions': [],
                    'status': None,
                    'character_state': 'help',
                    'error': 'no_child_match',
                    'handled': True,
                }
            if resolved.get('kind') == 'multiple':
                return {
                    'text': NAV_NEED_CHOICE,
                    'actions': _choice_actions(matches, destination),
                    'status': None,
                    'character_state': 'help',
                    'candidates': matches,
                    'pending_hint': {
                        'type': 'navigate',
                        'destination': destination,
                        'missing': ['child'],
                        'awaiting': 'child',
                    },
                    'handled': True,
                }
            if resolved.get('needs_confirmation') or resolved.get('kind') == 'fuzzy':
                child = matches[0]
                grade = child.get('grade')
                name = child.get('name')
                ask = (
                    f'{grade}학년 {name}을 말씀하시는 건가요?'
                    if grade not in (None, '')
                    else f'{name}을 말씀하시는 건가요?'
                )
                return {
                    'text': ask,
                    'actions': [
                        {
                            'type': 'reply',
                            'label': f'네, {name}이에요',
                            'content': '응',
                        },
                        {
                            'type': 'reply',
                            'label': '다른 아동 찾기',
                            'content': '아니',
                        },
                    ],
                    'status': None,
                    'character_state': 'help',
                    'pending_hint': {
                        'type': 'navigate',
                        'destination': destination,
                        'awaiting': 'child_confirmation',
                        'candidate_child_id': child.get('id'),
                        'candidate_nickname': name,
                    },
                    'handled': True,
                }
            params['child_id'] = matches[0]['id']
        elif (page_context or {}).get('child_id'):
            params['child_id'] = page_context['child_id']
    payload = navigate_payload(
        destination,
        params,
        page_context=page_context,
        auto=auto,
        role=role,
    )
    if payload.get('error') == 'missing_child':
        payload['pending_hint'] = {
            'type': 'navigate',
            'destination': destination,
            'missing': ['child'],
            'awaiting': 'child',
        }
    return payload


def interpret_user_text(text, page_context, role=None):
    role = current_role() if role is None else role
    raw = (text or '').strip()
    if not raw:
        return bootstrap_payload(page_context, role)
    if is_onboarding_request(raw):
        return onboarding_payload(role)
    if is_explain_request(raw):
        return explain_page_payload(page_context)
    if is_greeting(raw):
        return {
            'text': GREETING_REPLY,
            'actions': [],
            'status': None,
            'character_state': 'idle',
            'handled': False,
        }
    if wants_help(raw) and not is_explicit_go(raw):
        return _unhandled()
    if wants_data(raw):
        return _unhandled()
    nav = navigate_from_text(raw, page_context, role=role)
    if nav is not None:
        return nav
    return _unhandled()


def _unhandled():
    return {
        'text': FALLBACK,
        'actions': [],
        'status': None,
        'character_state': 'idle',
        'handled': False,
    }
