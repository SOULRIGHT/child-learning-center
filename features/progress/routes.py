"""학습 진도 입력/이력 및 과목 관리. DailyPoints 지급 API는 사용하지 않는다."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from features.reading.access import get_child
from features.study.view import teacher_study_template_vars
from features.progress.service import (
    ProgressError,
    create_subject,
    current_progress_for_child,
    get_subject,
    history_for_child,
    kst_today,
    list_progress_input_subjects,
    list_subjects,
    set_subject_active,
    update_subject,
)

progress_bp = Blueprint('progress', __name__)

LEGACY_PROGRESS_POST_MESSAGE = (
    '이 진도 입력 방식은 더 이상 사용하지 않습니다. '
    '학습 기록에서 시작~끝 페이지를 입력해 주세요. '
    '과거 페이지 값은 학습 기록으로 자동 변환되지 않습니다.'
)


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


@progress_bp.route('/settings/learning-subjects', methods=['GET'])
@login_required
def manage_subjects():
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    subjects = list_subjects(include_inactive=True)
    return render_template('settings/learning_subjects.html', subjects=subjects)


@progress_bp.route('/settings/learning-subjects', methods=['POST'])
@login_required
def create_subject_route():
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    try:
        create_subject(
            key=request.form.get('key'),
            name=request.form.get('name'),
            is_active=request.form.get('is_active') == '1',
            sort_order=request.form.get('sort_order') or 0,
        )
        flash('학습 과목을 추가했습니다.', 'success')
    except ProgressError as exc:
        flash(exc.message, 'error')
    return redirect(url_for('progress.manage_subjects'))


@progress_bp.route('/settings/learning-subjects/<int:subject_id>', methods=['POST'])
@login_required
def update_subject_route(subject_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    subject = get_subject(subject_id)
    if subject is None:
        abort(404)
    action = (request.form.get('action') or 'update').strip()
    try:
        if action == 'deactivate':
            set_subject_active(subject, False)
            flash('과목을 비활성화했습니다.', 'success')
        elif action == 'activate':
            set_subject_active(subject, True)
            flash('과목을 다시 활성화했습니다.', 'success')
        else:
            update_subject(
                subject,
                name=request.form.get('name'),
                sort_order=request.form.get('sort_order'),
            )
            flash('과목을 수정했습니다.', 'success')
    except ProgressError as exc:
        flash(exc.message, 'error')
    return redirect(url_for('progress.manage_subjects'))


@progress_bp.route('/children/<int:child_id>/progress', methods=['GET'])
@login_required
def history(child_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    child = _child_or_404(child_id)
    return render_template(
        'progress/history.html',
        child=child,
        rows=history_for_child(child_id),
        current_rows=current_progress_for_child(child_id),
        active_subjects=list_progress_input_subjects(),
        kst_today=kst_today(),
        **teacher_study_template_vars(child, recent_limit=40),
    )


@progress_bp.route('/children/<int:child_id>/progress', methods=['POST'])
@login_required
def save_progress(child_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    _child_or_404(child_id)
    flash(LEGACY_PROGRESS_POST_MESSAGE, 'error')
    if (request.form.get('return_to') or '').strip() == 'points':
        return redirect(url_for('points_input', child_id=child_id))
    if (request.form.get('return_to') or '').strip() == 'history':
        return redirect(url_for('progress.history', child_id=child_id))
    return redirect(url_for('child_detail', child_id=child_id))
