"""전역 teacher assistant HTTP boundary. CSRF 앱 전역 도입은 하지 않는다."""
from __future__ import annotations

from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, request, url_for
from flask_login import current_user, login_required

from features.assistant.config import (
    can_manage_settings,
    can_show_teacher_assistant,
    current_role,
    is_teacher_assistant_enabled,
    is_viewer_role,
)
from features.assistant.context import build_page_context
from features.assistant.copy import DISABLED, PROVIDER_ERROR
from features.assistant.provider import AssistantProviderError
from features.assistant.runtime import AssistantRequestError, complete_assistant

assistant_bp = Blueprint('assistant', __name__)


def _is_viewer():
    return is_viewer_role(getattr(current_user, 'role', None))


def _same_origin_json():
    if request.mimetype != 'application/json':
        return False
    origin = request.headers.get('Origin')
    if not origin:
        return True
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    return parsed.netloc == request.host


def _assistant_template_context():
    visible = bool(
        getattr(current_user, 'is_authenticated', False)
        and can_show_teacher_assistant()
    )
    if not visible:
        return {
            'teacher_assistant_visible': False,
            'assistant_boot': None,
        }
    page = build_page_context()
    return {
        'teacher_assistant_visible': True,
        'assistant_boot': {
            'page': page,
            'message_url': url_for('assistant.message'),
            'can_manage_settings': can_manage_settings(current_role()),
        },
    }


@assistant_bp.app_context_processor
def inject_teacher_assistant():
    try:
        return _assistant_template_context()
    except Exception:
        return {
            'teacher_assistant_visible': False,
            'assistant_boot': None,
        }


@assistant_bp.route('/assistant/message', methods=['POST'])
@login_required
def message():
    if not is_teacher_assistant_enabled():
        return jsonify({'ok': False, 'error': 'disabled', 'message': DISABLED}), 404
    if _is_viewer():
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    if not _same_origin_json():
        return jsonify({'ok': False, 'error': 'invalid_request'}), 400

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'ok': False, 'error': 'invalid_request'}), 400

    try:
        result = complete_assistant(
            messages=payload.get('messages'),
            page_context=payload.get('page_context'),
            intent=payload.get('intent') or 'chat',
            destination=payload.get('destination'),
            params=payload.get('params') if isinstance(payload.get('params'), dict) else {},
        )
    except AssistantRequestError:
        return jsonify({'ok': False, 'error': 'invalid_request'}), 400
    except AssistantProviderError:
        current_app.logger.warning('teacher assistant provider failed')
        return jsonify({'ok': False, 'error': 'provider_error', 'message': PROVIDER_ERROR}), 500
    except Exception:
        current_app.logger.exception('teacher assistant failed')
        return jsonify({'ok': False, 'error': 'provider_error', 'message': PROVIDER_ERROR}), 500
    return jsonify(result)
