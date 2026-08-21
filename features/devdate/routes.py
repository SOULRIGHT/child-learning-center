"""로컬 DEV 활동일 변경. production 및 미설정 환경에서는 404."""
from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, request, session, url_for
from flask_login import current_user

from features.dates import (
    DEV_ACTIVITY_DATE_SESSION_KEY,
    dev_date_template_context,
    is_dev_date_control_enabled,
    kst_today,
    parse_activity_date_text,
)

devdate_bp = Blueprint('devdate', __name__)


@devdate_bp.record_once
def _register_template_context(state):
    state.app.context_processor(dev_date_template_context)


def _safe_next():
    raw = request.form.get('next') or request.referrer
    if not raw:
        return url_for('dashboard')
    text = str(raw)
    if not text.startswith('/') or text.startswith('//'):
        return url_for('dashboard')
    if text.startswith('/dev/'):
        return url_for('dashboard')
    return text


@devdate_bp.route('/dev/activity-date', methods=['GET', 'POST'])
def set_activity_date():
    if request.method != 'POST' or not is_dev_date_control_enabled():
        abort(404)
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    action = (request.form.get('action') or '').strip()
    if action == 'today':
        session.pop(DEV_ACTIVITY_DATE_SESSION_KEY, None)
        flash('DEV 활동일을 실제 오늘로 되돌렸습니다.', 'success')
        return redirect(_safe_next())

    if action == 'prev':
        chosen = kst_today() - timedelta(days=1)
    elif action == 'next':
        chosen = kst_today() + timedelta(days=1)
    elif action == 'set':
        chosen = parse_activity_date_text(request.form.get('date'))
        if chosen is None:
            flash('날짜 형식이 올바르지 않습니다. YYYY-MM-DD로 입력하세요.', 'error')
            return redirect(_safe_next())
    else:
        flash('알 수 없는 날짜 변경 요청입니다.', 'error')
        return redirect(_safe_next())

    session[DEV_ACTIVITY_DATE_SESSION_KEY] = chosen.isoformat()
    flash(f'DEV 활동일: {chosen.isoformat()}', 'success')
    return redirect(_safe_next())
