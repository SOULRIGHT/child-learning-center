"""Teacher assistant feature flag and role visibility. DB flag 없음."""
from __future__ import annotations

import os

from flask import current_app
from flask_login import current_user

TEACHER_ASSISTANT_ENABLED_ENV = 'TEACHER_ASSISTANT_ENABLED'
VIEWER_ROLE_FALLBACK = '학생열람'
SETTINGS_BLOCKED_ROLES = frozenset({'일반사용자', '테스트사용자', VIEWER_ROLE_FALLBACK})


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
