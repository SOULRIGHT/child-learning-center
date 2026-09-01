"""교사용 개인 Growth 대시보드. viewer/NFC/기존 onepage는 건드리지 않는다."""
from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from features.dates import (
    actual_kst_today,
    is_dev_date_control_enabled,
    kst_today,
    parse_activity_date_text,
)
from features.growth.ai.copy import MSG_DISABLED, MSG_ERROR
from features.growth.ai.runtime import (
    FEEDBACK_MAX_LEN,
    can_use_teacher_ai,
    generate_teacher_growth_interpretation,
    load_teacher_ai_view,
    public_result_payload,
    save_teacher_ai_feedback,
)
from features.growth.service import build_growth_view_model
from features.reading.access import get_child

growth_bp = Blueprint('growth', __name__)


def _is_viewer():
    return getattr(current_user, 'role', None) == current_app.config.get(
        'VIEWER_ROLE_NAME', '학생열람'
    )


def _resolve_teacher_as_of():
    """production에서는 query as_of를 무시한다. 잘못된 개발 override는 400."""
    raw = request.args.get('as_of')
    if not is_dev_date_control_enabled():
        return kst_today(), False
    if raw is None or str(raw).strip() == '':
        as_of = kst_today()
        return as_of, as_of != actual_kst_today()
    parsed = parse_activity_date_text(raw)
    if parsed is None:
        abort(400)
    return parsed, True


@growth_bp.route('/children/<int:child_id>/growth')
@login_required
def teacher(child_id):
    if _is_viewer():
        return redirect(url_for('viewer_home'))
    child = get_child(child_id)
    if child is None:
        abort(404)
    as_of, dev_overridden = _resolve_teacher_as_of()
    view = build_growth_view_model(child, as_of=as_of, is_viewer_mode=False)
    bundle = view.get('bundle')
    view['ai'] = _safe_ai_view(child, as_of, bundle)
    view.pop('bundle', None)
    view['dev_as_of_overridden'] = dev_overridden
    view['dev_date_control_enabled'] = is_dev_date_control_enabled()
    return render_template('growth/report.html', **view)


@growth_bp.route('/children/<int:child_id>/growth/ai/generate', methods=['POST'])
@login_required
def generate_ai(child_id):
    blocked = _forbid_ai_user()
    if blocked:
        return blocked
    child = get_child(child_id)
    if child is None:
        abort(404)
    as_of, _ = _resolve_teacher_as_of()
    result = generate_teacher_growth_interpretation(
        child=child,
        user_id=current_user.id,
        as_of=as_of,
    )
    status = 200 if result.ok else _error_status(result.state)
    return jsonify(public_result_payload(result)), status


@growth_bp.route('/children/<int:child_id>/growth/ai/feedback', methods=['POST'])
@login_required
def feedback_ai(child_id):
    blocked = _forbid_ai_user()
    if blocked:
        return blocked
    child = get_child(child_id)
    if child is None:
        abort(404)
    payload = request.get_json(silent=True) or {}
    generation_id = payload.get('generation_id')
    try:
        generation_id = int(generation_id)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'message': MSG_ERROR}), 400
    generation = _generation_for_child(generation_id, child.id)
    if generation is None:
        return jsonify({'ok': False, 'message': MSG_ERROR}), 404
    helpful = payload.get('helpful')
    if helpful not in (True, False):
        return jsonify({'ok': False, 'message': MSG_ERROR}), 400
    comment = payload.get('comment')
    if comment is not None and not isinstance(comment, str):
        return jsonify({'ok': False, 'message': MSG_ERROR}), 400
    if isinstance(comment, str) and len(comment) > FEEDBACK_MAX_LEN:
        return jsonify({'ok': False, 'message': MSG_ERROR}), 400
    ok, _detail = save_teacher_ai_feedback(
        generation_id=generation_id,
        user_id=current_user.id,
        helpful=helpful,
        comment=comment,
    )
    if not ok:
        return jsonify({'ok': False, 'message': MSG_ERROR}), 400
    return jsonify({'ok': True})


def _forbid_ai_user():
    if _is_viewer():
        return redirect(url_for('viewer_home'))
    if not can_use_teacher_ai(getattr(current_user, 'role', None)):
        abort(403)
    return None


def _safe_ai_view(child, as_of, bundle):
    if not can_use_teacher_ai(getattr(current_user, 'role', None)):
        return None
    try:
        return load_teacher_ai_view(
            child,
            as_of=as_of,
            bundle=bundle,
            user_id=getattr(current_user, 'id', None),
        )
    except Exception:
        return {
            'state': 'disabled',
            'enabled': False,
            'message': MSG_DISABLED,
        }


def _generation_for_child(generation_id, child_id):
    from feature_models import GrowthAIGeneration
    row = GrowthAIGeneration.query.get(generation_id)
    if row is None or row.child_id != child_id:
        return None
    return row


def _error_status(state):
    if state == 'disabled':
        return 503
    if state == 'quota':
        return 429
    if state == 'in_progress':
        return 409
    return 200
