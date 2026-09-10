"""센터 운영 설정 hub. 값은 기존 설정 화면에서만 저장한다."""
from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from features.setup.present import attach_setup_hrefs
from features.setup.status import build_center_setup_status

setup_bp = Blueprint('setup', __name__)


def _is_viewer():
    return getattr(current_user, 'role', None) == current_app.config.get(
        'VIEWER_ROLE_NAME', '학생열람'
    )


@setup_bp.route('/settings/setup')
@login_required
def hub():
    if _is_viewer():
        return redirect(url_for('viewer_home'))
    if getattr(current_user, 'role', None) in {'테스트사용자', '일반사용자'}:
        flash('설정 페이지에 접근할 권한이 없습니다.', 'error')
        return redirect(url_for('dashboard'))
    setup = attach_setup_hrefs(build_center_setup_status())
    return render_template('settings/setup.html', setup=setup)
