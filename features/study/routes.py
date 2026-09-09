"""학습 세션 HTTP. 교사 입력/확인과 아동 viewer 입력을 분리한다."""
from datetime import date

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

from feature_models import LearningStudySession
from features.dates import kst_today
from features.reading.access import get_child, resolve_viewer_child
from features.reading import session as viewer_session
from features.study.child_input import save_child_study_form
from features.study.records import (
    StudyRecordError,
    mark_sessions_verified,
    update_study_session,
)
from features.study.teacher_input import (
    create_teacher_study_session,
    save_teacher_post_entry_form,
)
from features.study.view import (
    CHILD_NO_PLAN_MESSAGE,
    list_child_study_rows,
    list_teacher_post_entry_rows,
)

study_bp = Blueprint('study', __name__)


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


def _redirect_confirm(view_token, next_name='study'):
    return redirect(url_for('reading.viewer_confirm', view_token=view_token, next=next_name))


def _viewer_write_guard(child, view_token):
    reason = viewer_session.write_block_reason(session, child)
    if reason in {'unverified', 'ttl_expired'}:
        flash('다시 본인 확인이 필요해요. QR을 스캔해 주세요.', 'warning')
        return _redirect_confirm(view_token)
    if reason == 'child_mismatch':
        flash('다른 아동의 기록은 저장할 수 없어요.', 'error')
        abort(403)
    if reason:
        flash('학습 기록을 저장할 수 없어요.', 'error')
        return _redirect_confirm(view_token)
    return None


def _parse_study_date(raw):
    today = kst_today()
    text = '' if raw is None else str(raw).strip()
    if not text:
        return today
    try:
        day = date.fromisoformat(text[:10])
    except ValueError:
        return today
    if day > today:
        return today
    return day


def redirect_after_study_save(child_id):
    target = (request.form.get('return_to') or '').strip()
    if target == 'points':
        return redirect(url_for('points_input', child_id=child_id))
    if target == 'history':
        return redirect(url_for('progress.history', child_id=child_id))
    return redirect(url_for('child_detail', child_id=child_id))


@study_bp.route('/children/<int:child_id>/study-sessions', methods=['POST'])
@login_required
def save_study_session(child_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    _child_or_404(child_id)
    try:
        create_teacher_study_session(child_id, current_user.id, request.form)
        flash('학습 기록을 저장했습니다.', 'success')
    except StudyRecordError as exc:
        flash(exc.message, 'error')
    return redirect_after_study_save(child_id)


@study_bp.route('/children/<int:child_id>/study-sessions/<int:session_id>', methods=['POST'])
@login_required
def update_teacher_study_session_route(child_id, session_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    _child_or_404(child_id)
    row = LearningStudySession.query.filter_by(id=session_id, child_id=child_id).one_or_none()
    if row is None:
        abort(404)
    try:
        kwargs = {}
        if request.form.get('study_status'):
            kwargs['study_status'] = request.form.get('study_status')
        if 'start_page' in request.form:
            kwargs['start_page'] = request.form.get('start_page')
        if 'end_page' in request.form:
            kwargs['end_page'] = request.form.get('end_page')
        if request.form.get('learning_workbook_plan_id'):
            kwargs['learning_workbook_plan_id'] = request.form.get('learning_workbook_plan_id')
        update_study_session(row, changed_by_user_id=current_user.id, **kwargs)
        flash('학습 기록을 수정했습니다.', 'success')
    except StudyRecordError as exc:
        flash(exc.message, 'error')
    return redirect_after_study_save(child_id)


@study_bp.route('/children/<int:child_id>/study-sessions/verify', methods=['POST'])
@login_required
def verify_study_sessions(child_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    _child_or_404(child_id)
    try:
        mark_sessions_verified(
            request.form.getlist('session_id'),
            child_id=child_id,
            changed_by_user_id=current_user.id,
        )
        flash('선택한 기록을 실제 교재 확인으로 저장했습니다.', 'success')
    except StudyRecordError as exc:
        flash(exc.message, 'error')
    return redirect_after_study_save(child_id)


@study_bp.route('/viewer/report/<string:view_token>/study', methods=['GET'])
@login_required
def viewer_form(view_token):
    child, slug = resolve_viewer_child(view_token)
    if not child:
        flash('유효하지 않은 리포트 링크입니다.', 'error')
        return redirect(url_for('viewer_home') if _is_viewer() else url_for('dashboard'))
    token = slug or view_token
    blocked = _viewer_write_guard(child, token)
    if blocked:
        return blocked
    study_date = _parse_study_date(request.args.get('study_date'))
    return render_template(
        'study/child_form.html',
        child=child,
        view_token=token,
        study_date=study_date,
        kst_today=kst_today(),
        rows=list_child_study_rows(child, study_date),
        no_plan_message=CHILD_NO_PLAN_MESSAGE,
    )


@study_bp.route('/viewer/report/<string:view_token>/study', methods=['POST'])
@login_required
def viewer_save(view_token):
    child, slug = resolve_viewer_child(view_token)
    if not child:
        flash('유효하지 않은 리포트 링크입니다.', 'error')
        return redirect(url_for('viewer_home') if _is_viewer() else url_for('dashboard'))
    token = slug or view_token
    blocked = _viewer_write_guard(child, token)
    if blocked:
        return blocked
    study_date = _parse_study_date(request.form.get('study_date'))
    try:
        saved = save_child_study_form(child.id, current_user.id, request.form)
        if saved:
            flash('학습 페이지를 저장했어요.', 'success')
        else:
            flash('선택한 과목이 없어 저장하지 않았어요.', 'info')
    except StudyRecordError as exc:
        flash(exc.message, 'error')
    return redirect(url_for('study.viewer_form', view_token=token, study_date=study_date.isoformat()))


@study_bp.route('/children/<int:child_id>/study-post-entry', methods=['GET', 'POST'])
@login_required
def teacher_post_entry(child_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    child = _child_or_404(child_id)
    study_date = _parse_study_date(
        request.form.get('study_date') if request.method == 'POST' else request.args.get('study_date')
    )
    if request.method == 'POST':
        try:
            saved = save_teacher_post_entry_form(child.id, current_user.id, request.form)
            if saved:
                flash('빠진 학습 기록을 저장했습니다.', 'success')
            else:
                flash('저장할 과목을 선택하지 않았습니다.', 'info')
        except StudyRecordError as exc:
            flash(exc.message, 'error')
        return redirect(
            url_for('study.teacher_post_entry', child_id=child.id, study_date=study_date.isoformat())
        )
    return render_template(
        'study/teacher_post_entry.html',
        child=child,
        study_date=study_date,
        kst_today=kst_today(),
        rows=list_teacher_post_entry_rows(child, study_date),
        no_plan_message=CHILD_NO_PLAN_MESSAGE,
    )
