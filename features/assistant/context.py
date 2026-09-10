"""Current-page structured context. DOM 전체를 넘기지 않는다."""
from __future__ import annotations

from flask import request, has_request_context
from flask_login import current_user

from features.assistant.config import current_role, is_viewer_role
from features.assistant.copy import page_title
from features.assistant.navigation import lookup_child
from features.dates import (
    is_dev_date_control_enabled,
    kst_today,
    parse_activity_date_text,
)


def _growth_as_of_text():
    raw = request.args.get('as_of')
    if not is_dev_date_control_enabled():
        return kst_today().isoformat()
    if raw is None or str(raw).strip() == '':
        return kst_today().isoformat()
    parsed = parse_activity_date_text(raw)
    if parsed is None:
        return kst_today().isoformat()
    return parsed.isoformat()


def build_page_context():
    """현재 요청의 서버측 page context. 단일 테넌트라 center id를 만들지 않는다."""
    if not has_request_context():
        return {}
    if not getattr(current_user, 'is_authenticated', False):
        return {}
    role = current_role()
    if is_viewer_role(role):
        return {}
    endpoint = request.endpoint or ''
    context = {
        'endpoint': endpoint,
        'pathname': request.path or '',
        'page_title': page_title(endpoint),
        'role': role,
    }
    view_args = request.view_args or {}
    if 'child_id' in view_args:
        child = lookup_child(view_args.get('child_id'))
        if child is not None:
            context['child_id'] = child.id
            context['child_name'] = child.name
    if endpoint == 'growth.teacher':
        context['as_of'] = _growth_as_of_text()
    return context


def sanitize_page_context(raw):
    """클라이언트가 보낸 context. role은 버리고 child는 DB lookup만 신뢰."""
    data = raw if isinstance(raw, dict) else {}
    endpoint = data.get('endpoint')
    if not isinstance(endpoint, str):
        endpoint = ''
    endpoint = endpoint.strip()[:120]
    pathname = data.get('pathname')
    if not isinstance(pathname, str):
        pathname = ''
    pathname = pathname.strip()[:200]
    title = data.get('page_title')
    if not isinstance(title, str):
        title = page_title(endpoint)
    title = title.strip()[:80]
    cleaned = {
        'endpoint': endpoint,
        'pathname': pathname,
        'page_title': title or page_title(endpoint),
        'role': current_role(),
    }
    child = lookup_child(data.get('child_id'))
    if child is not None:
        cleaned['child_id'] = child.id
        cleaned['child_name'] = child.name
    as_of = data.get('as_of')
    if isinstance(as_of, str) and as_of.strip():
        parsed = parse_activity_date_text(as_of.strip())
        if parsed is not None:
            cleaned['as_of'] = parsed.isoformat()
    elif endpoint == 'growth.teacher' and cleaned.get('child_id'):
        cleaned['as_of'] = _growth_as_of_text() if has_request_context() else None
        if not cleaned.get('as_of'):
            cleaned.pop('as_of', None)
    return cleaned


def context_scope(page_context):
    page_context = page_context or {}
    scope = {
        'endpoint': page_context.get('endpoint') or '',
    }
    child_id = page_context.get('child_id')
    if child_id is not None:
        scope['child_id'] = child_id
    return scope
