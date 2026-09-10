"""Teacher assistant feature flag and role visibility. DB flag 없음."""
from __future__ import annotations

import hashlib
import hmac
import os

from flask import current_app, has_request_context, session
from flask_login import current_user

TEACHER_ASSISTANT_ENABLED_ENV = 'TEACHER_ASSISTANT_ENABLED'
TEACHER_ASSISTANT_PROVIDER_ENV = 'TEACHER_ASSISTANT_PROVIDER'
TEACHER_ASSISTANT_MODEL_ENV = 'TEACHER_ASSISTANT_MODEL'
TEACHER_ASSISTANT_LIVE_ENV = 'TEACHER_ASSISTANT_LIVE'
VIEWER_ROLE_FALLBACK = '학생열람'
SETTINGS_BLOCKED_ROLES = frozenset({'일반사용자', '테스트사용자', VIEWER_ROLE_FALLBACK})


def is_assistant_live_enabled():
    raw = (os.environ.get(TEACHER_ASSISTANT_LIVE_ENV) or '').strip().lower()
    return raw in ('1', 'true', 'yes', 'on')


def assistant_provider_name():
    raw = (os.environ.get(TEACHER_ASSISTANT_PROVIDER_ENV) or 'fake').strip().lower()
    if raw not in ('openai', 'live'):
        return 'fake'
    # unittest / browser QA는 명시적 live flag 없이 OpenAI를 쓰지 않는다.
    if os.environ.get('CLC_TESTING') == '1' and not is_assistant_live_enabled():
        return 'fake'
    return 'openai'


def is_teacher_assistant_enabled():
    raw = (os.environ.get(TEACHER_ASSISTANT_ENABLED_ENV) or '').strip().lower()
    return raw in ('1', 'true', 'yes', 'on')


def viewer_role_name():
    try:
        return current_app.config.get('VIEWER_ROLE_NAME', VIEWER_ROLE_FALLBACK)
    except RuntimeError:
        return VIEWER_ROLE_FALLBACK


def is_viewer_role(role):
    return role == viewer_role_name()


def current_role():
    if not getattr(current_user, 'is_authenticated', False):
        return None
    return getattr(current_user, 'role', None)


def is_teacher_ui_user(role=None):
    """학생열람이 아닌 현재 teacher UI 사용자."""
    role = current_role() if role is None else role
    if not role:
        return False
    return not is_viewer_role(role)


def can_show_teacher_assistant(role=None):
    return is_teacher_assistant_enabled() and is_teacher_ui_user(role)


def can_manage_settings(role=None):
    role = current_role() if role is None else role
    if not role or is_viewer_role(role):
        return False
    return role not in SETTINGS_BLOCKED_ROLES


def assistant_storage_scope():
    """JS에 쿠키/세션 원문을 주지 않는 계정+세션 바인딩 토큰."""
    if not getattr(current_user, 'is_authenticated', False):
        return ''
    if not has_request_context():
        return ''
    nonce = session.get('_assistant_scope')
    if not nonce:
        import secrets
        nonce = secrets.token_hex(8)
        session['_assistant_scope'] = nonce
    try:
        secret = current_app.secret_key
    except RuntimeError:
        secret = b'assistant-scope'
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    if not secret:
        secret = b'assistant-scope'
    user_id = str(current_user.get_id() or '')
    digest = hmac.new(
        secret,
        f'assistant-scope:{user_id}:{nonce}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return digest[:24]
