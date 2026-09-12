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
TEACHER_ASSISTANT_REASONING_ENV = 'TEACHER_ASSISTANT_REASONING_EFFORT'
TEACHER_ASSISTANT_REQUEST_TIMEOUT_ENV = 'TEACHER_ASSISTANT_REQUEST_TIMEOUT_S'
TEACHER_ASSISTANT_PRIMARY_TIMEOUT_ENV = 'TEACHER_ASSISTANT_PRIMARY_TIMEOUT_S'
TEACHER_ASSISTANT_FALLBACK_ENABLED_ENV = 'TEACHER_ASSISTANT_FALLBACK_ENABLED'
TEACHER_ASSISTANT_FALLBACK_MODEL_ENV = 'TEACHER_ASSISTANT_FALLBACK_MODEL'
ANTHROPIC_API_KEY_ENV = 'ANTHROPIC_API_KEY'
DEFAULT_REASONING_EFFORT = 'medium'
DEFAULT_REQUEST_TIMEOUT_S = 20.0
DEFAULT_PRIMARY_TIMEOUT_S = 10.0
DEFAULT_FALLBACK_MODEL = 'claude-sonnet-5'
# GPT-5.6 Luna Responses API reasoning.effort. 잘못된 값은 조용히 바꾸지 않는다.
ALLOWED_REASONING_EFFORTS = frozenset({'none', 'low', 'medium', 'high', 'xhigh'})
VIEWER_ROLE_FALLBACK = '학생열람'
SETTINGS_BLOCKED_ROLES = frozenset({'일반사용자', '테스트사용자', VIEWER_ROLE_FALLBACK})


def _truthy_env(name, default=''):
    raw = (os.environ.get(name) or default).strip().lower()
    return raw in ('1', 'true', 'yes', 'on')


def assistant_reasoning_effort():
    raw = (os.environ.get(TEACHER_ASSISTANT_REASONING_ENV) or DEFAULT_REASONING_EFFORT).strip().lower()
    if raw not in ALLOWED_REASONING_EFFORTS:
        from features.assistant.provider import AssistantProviderConfigError
        raise AssistantProviderConfigError('invalid TEACHER_ASSISTANT_REASONING_EFFORT')
    return raw


def assistant_request_timeout_s():
    return _positive_timeout(TEACHER_ASSISTANT_REQUEST_TIMEOUT_ENV, DEFAULT_REQUEST_TIMEOUT_S)


def assistant_primary_timeout_s():
    request_s = assistant_request_timeout_s()
    primary_s = _positive_timeout(TEACHER_ASSISTANT_PRIMARY_TIMEOUT_ENV, DEFAULT_PRIMARY_TIMEOUT_S)
    if primary_s > request_s:
        from features.assistant.provider import AssistantProviderConfigError
        raise AssistantProviderConfigError('invalid TEACHER_ASSISTANT_PRIMARY_TIMEOUT_S')
    return primary_s


def is_assistant_fallback_enabled():
    return _truthy_env(TEACHER_ASSISTANT_FALLBACK_ENABLED_ENV, 'false')


def assistant_fallback_model():
    raw = (os.environ.get(TEACHER_ASSISTANT_FALLBACK_MODEL_ENV) or DEFAULT_FALLBACK_MODEL).strip()
    return raw[:80] or DEFAULT_FALLBACK_MODEL


def _positive_timeout(name, default):
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return float(default)
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        from features.assistant.provider import AssistantProviderConfigError
        raise AssistantProviderConfigError(f'invalid {name}') from None
    if value <= 0:
        from features.assistant.provider import AssistantProviderConfigError
        raise AssistantProviderConfigError(f'invalid {name}')
    return value


def is_assistant_live_enabled():
    return _truthy_env(TEACHER_ASSISTANT_LIVE_ENV)


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
