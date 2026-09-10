"""결정적 사용자 의도 해석. live LLM / data tool 없음."""
from __future__ import annotations

from features.assistant.config import can_manage_settings, current_role
from features.assistant.copy import (
    FALLBACK,
    GREETING,
    HELP_SCOPE,
    NAV_NEED_CHOICE,
    NAV_NEED_NAME,
    NAV_NO_MATCH,
    ONBOARDING_DONE,
    ONBOARDING_UNAVAILABLE,
    PAGE_GENERIC,
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
    child_public,
    extract_child_query,
    is_explicit_go,
    match_destination_from_text,
    resolve_navigation,
    search_children,
    spec_for,
)
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


def is_onboarding_request(text):
    raw = text or ''
    return any(phrase in raw for phrase in ONBOARDING_PHRASES)


def is_explain_request(text):
    raw = text or ''
    return any(phrase in raw for phrase in EXPLAIN_PHRASES)


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
        'text': GREETING,
        'actions': [],
        'status': status,
        'character_state': 'idle',
        'quick_actions': quick_actions(page_context, role),
        'handled': True,
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
        resolved = resolve_navigation(destination, {'child_id': child.id}, role=current_role())
        if not resolved.get('ok'):
            continue
        actions.append({
            'type': 'navigate',
            'label': f"{child.name} ({child.grade}학년) {label_base}",
            'url': resolved['url'],
            'destination': destination,
            'auto': False,
            'params': {'child_id': child.id},
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
            matches = search_children(query)
            if not matches:
                return {
                    'text': NAV_NO_MATCH,
                    'actions': [],
                    'status': None,
                    'character_state': 'help',
                    'error': 'no_child_match',
                    'handled': True,
                }
            if len(matches) > 1:
                return {
                    'text': NAV_NEED_CHOICE,
                    'actions': _choice_actions(matches, destination),
                    'status': None,
                    'character_state': 'help',
                    'candidates': [child_public(child) for child in matches],
                    'handled': True,
                }
            params['child_id'] = matches[0].id
        elif (page_context or {}).get('child_id'):
            params['child_id'] = page_context['child_id']
    return navigate_payload(
        destination,
        params,
        page_context=page_context,
        auto=auto,
        role=role,
    )


def interpret_user_text(text, page_context, role=None):
    role = current_role() if role is None else role
    raw = (text or '').strip()
    if not raw:
        return bootstrap_payload(page_context, role)
    if is_onboarding_request(raw):
        return onboarding_payload(role)
    if is_explain_request(raw):
        return explain_page_payload(page_context)
    nav = navigate_from_text(raw, page_context, role=role)
    if nav is not None:
        return nav
    return {
        'text': f'{HELP_SCOPE} {FALLBACK}',
        'actions': [],
        'status': None,
        'character_state': 'idle',
        'handled': False,
    }
