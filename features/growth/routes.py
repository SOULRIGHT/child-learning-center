"""교사용 개인 Growth 대시보드. viewer/NFC/기존 onepage는 건드리지 않는다."""
from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from features.dates import (
    actual_kst_today,
    is_dev_date_control_enabled,
    kst_today,
    parse_activity_date_text,
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
    view.pop('bundle', None)
    view['dev_as_of_overridden'] = dev_overridden
    view['dev_date_control_enabled'] = is_dev_date_control_enabled()
    return render_template('growth/report.html', **view)
