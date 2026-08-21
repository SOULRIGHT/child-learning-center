"""면제권 발급/사용/취소와 5~6학년 보상 방식 선택. 실제 지급은 교사만."""
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from feature_models import ChildReading
from features.exemption.service import (
    ExemptionError,
    child_exemption_snapshot,
    get_ticket,
    issue_exemption_ticket,
    revoke_exemption_ticket,
    set_reward_mode,
    use_exemption_ticket,
)
from features.reading.access import get_child, resolve_viewer_child
from features.reading import session as viewer_session


exemption_bp = Blueprint('exemption', __name__)


def _is_viewer():
    return getattr(current_user, 'role', None) == current_app.config.get(
        'VIEWER_ROLE_NAME', '학생열람'
    )


def _forbid_viewer():
    if _is_viewer():
        return redirect(url_for('viewer_home'))
    return None


def _child_or_404(child_id):
    child = get_child(child_id)
    if child is None:
        abort(404)
    return child


def _safe_next(default):
    raw = request.form.get('next') or request.referrer
    if not raw:
        return default
    if not str(raw).startswith('/') or str(raw).startswith('//'):
        return default
    return raw


def _redirect_confirm(view_token):
    return redirect(url_for('reading.viewer_confirm', view_token=view_token))


def _viewer_write_guard(child, view_token):
    reason = viewer_session.write_block_reason(session, child)
    if reason in {'unverified', 'ttl_expired'}:
        flash('다시 본인 확인이 필요해요. QR을 스캔해 주세요.', 'warning')
        return _redirect_confirm(view_token)
    if reason == 'child_mismatch':
        flash('다른 아동의 기록은 저장할 수 없어요.', 'error')
        abort(403)
    if reason:
        flash('보상 방식을 저장할 수 없어요.', 'error')
        return _redirect_confirm(view_token)
    return None


def _reading_for_child(child, reading_id):
    try:
        reading_id = int(reading_id or 0)
    except (TypeError, ValueError):
        abort(400)
    reading = ChildReading.query.get(reading_id)
    if reading is None or int(reading.child_id) != int(child.id):
        abort(403)
    return reading


@exemption_bp.route('/children/<int:child_id>/reading/reward-mode', methods=['POST'])
@login_required
def teacher_set_reward_mode(child_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    child = _child_or_404(child_id)
    reading = _reading_for_child(child, request.form.get('child_reading_id'))
    try:
        set_reward_mode(reading, (request.form.get('reward_mode') or '').strip(), current_user)
        flash('보상 방식을 저장했습니다.', 'success')
    except ExemptionError as exc:
        flash(exc.message, 'error')
    return redirect(_safe_next(url_for('reading.teacher_editor', child_id=child.id)))


@exemption_bp.route('/viewer/report/<string:view_token>/reading/reward-mode', methods=['POST'])
@login_required
def viewer_set_reward_mode(view_token):
    child, slug = resolve_viewer_child(view_token)
    if not child:
        flash('유효하지 않은 리포트 링크입니다.', 'error')
        return redirect(url_for('viewer_home') if _is_viewer() else url_for('dashboard'))
    blocked = _viewer_write_guard(child, slug or view_token)
    if blocked:
        return blocked
    token = slug or view_token
    if int(child.id) != viewer_session.verified_child_id(session):
        abort(403)
    reading = _reading_for_child(child, request.form.get('child_reading_id'))
    try:
        set_reward_mode(reading, (request.form.get('reward_mode') or '').strip(), current_user)
        flash('보상 방식을 저장했어요.', 'success')
    except ExemptionError as exc:
        flash(exc.message, 'error')
    return redirect(url_for('reading.viewer_editor', view_token=token))


@exemption_bp.route('/children/<int:child_id>/exemption/issue', methods=['POST'])
@login_required
def issue_ticket(child_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    child = _child_or_404(child_id)
    try:
        issue_exemption_ticket(child.id, current_user)
        flash('면제권을 발급했습니다. 종이 면제권 1장을 전달하세요.', 'success')
    except ExemptionError as exc:
        flash(exc.message, 'error')
    return redirect(_safe_next(url_for('child_detail', child_id=child.id)))


@exemption_bp.route('/children/<int:child_id>/exemption/<int:ticket_id>/use', methods=['POST'])
@login_required
def use_ticket(child_id, ticket_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    child = _child_or_404(child_id)
    ticket = get_ticket(ticket_id)
    if ticket is None or int(ticket.child_id) != int(child.id):
        abort(403)
    try:
        use_exemption_ticket(
            ticket.id,
            request.form.get('subject_key'),
            current_user,
            used_on=request.form.get('used_on'),
        )
        flash('면제권 사용을 기록했습니다. 종이 면제권을 회수하세요.', 'success')
    except ExemptionError as exc:
        flash(exc.message, 'error')
    return redirect(_safe_next(url_for('child_detail', child_id=child.id)))


@exemption_bp.route('/children/<int:child_id>/exemption/<int:ticket_id>/revoke', methods=['POST'])
@login_required
def revoke_ticket(child_id, ticket_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    child = _child_or_404(child_id)
    ticket = get_ticket(ticket_id)
    if ticket is None or int(ticket.child_id) != int(child.id):
        abort(403)
    try:
        revoke_exemption_ticket(ticket.id, current_user)
        flash('면제권 발급을 취소했습니다.', 'success')
    except ExemptionError as exc:
        flash(exc.message, 'error')
    return redirect(_safe_next(url_for('exemption.history', child_id=child.id)))


@exemption_bp.route('/children/<int:child_id>/exemption', methods=['GET'])
@login_required
def history(child_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    child = _child_or_404(child_id)
    snapshot = child_exemption_snapshot(child.id)
    return render_template(
        'exemption/history.html',
        child=child,
        snapshot=snapshot,
    )
