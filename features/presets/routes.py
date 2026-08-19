"""수동 포인트 프리셋 관리. 실제 지급 API는 기존 /api/manual-points 를 유지한다."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from features.presets.service import (
    PresetError,
    create_preset,
    get_preset,
    list_presets,
    set_preset_active,
    update_preset,
)

presets_bp = Blueprint('presets', __name__)


def _is_viewer():
    return getattr(current_user, 'role', None) == current_app.config.get(
        'VIEWER_ROLE_NAME', '학생열람'
    )


def _forbid_viewer():
    if _is_viewer():
        return redirect(url_for('viewer_home'))
    return None


@presets_bp.route('/settings/manual-presets', methods=['GET'])
@login_required
def manage_presets():
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    presets = list_presets(include_inactive=True)
    return render_template('settings/manual_presets.html', presets=presets)


@presets_bp.route('/settings/manual-presets', methods=['POST'])
@login_required
def create_preset_route():
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    try:
        create_preset(
            key=request.form.get('key'),
            label=request.form.get('label'),
            default_points=request.form.get('default_points'),
            default_reason=request.form.get('default_reason'),
            is_active=request.form.get('is_active') == '1',
            sort_order=request.form.get('sort_order') or 0,
        )
        flash('프리셋을 추가했습니다.', 'success')
    except PresetError as exc:
        flash(exc.message, 'error')
    return redirect(url_for('presets.manage_presets'))


@presets_bp.route('/settings/manual-presets/<int:preset_id>', methods=['POST'])
@login_required
def update_preset_route(preset_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    preset = get_preset(preset_id)
    if preset is None:
        abort(404)
    action = (request.form.get('action') or 'update').strip()
    try:
        if action == 'deactivate':
            set_preset_active(preset, False)
            flash('프리셋을 비활성화했습니다.', 'success')
        elif action == 'activate':
            set_preset_active(preset, True)
            flash('프리셋을 다시 활성화했습니다.', 'success')
        else:
            update_preset(
                preset,
                label=request.form.get('label'),
                default_points=request.form.get('default_points'),
                default_reason=request.form.get('default_reason', ''),
                sort_order=request.form.get('sort_order'),
            )
            flash('프리셋을 수정했습니다.', 'success')
    except PresetError as exc:
        flash(exc.message, 'error')
    return redirect(url_for('presets.manage_presets'))
