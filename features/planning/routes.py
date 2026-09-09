"""학습 계획 관리 UI. Growth metric / planner / LLM 은 연결하지 않는다."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from features.dates import kst_today
from features.planning.exclusions import PlanningError
from features.planning.service import (
    PLAN_GRADES,
    create_workbook_plan,
    delete_workbook_plan,
    get_center_weekdays,
    get_workbook_plan,
    parse_weekdays_from_form,
    plan_form_subjects,
    save_child_study_weekdays,
    update_center_weekdays,
    update_workbook_plan,
    workbook_plan_is_referenced_by_study_session,
    workbook_plan_list_rows,
)
from features.planning.weekdays import WEEKDAY_CHOICES, format_weekdays
from features.reading.access import get_child
from features.study.calendar import StudyCalendarError
from features.study.settings import (
    add_center_non_study_day_from_form,
    non_study_days_month_view,
    parse_year_month,
    restore_non_study_day_from_form,
    restore_year_system_holidays,
    save_subject_weekdays_from_form,
    subject_weekdays_settings_rows,
)

planning_bp = Blueprint('planning', __name__)


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


@planning_bp.route('/settings/study-calendar', methods=['GET', 'POST'])
@login_required
def manage_study_calendar():
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    if request.method == 'POST':
        try:
            update_center_weekdays(parse_weekdays_from_form(request.form.getlist('study_weekdays')))
            flash('센터 기본 학습요일을 저장했습니다.', 'success')
        except PlanningError as exc:
            flash(exc.message, 'error')
        return redirect(url_for('planning.manage_study_calendar'))
    selected = get_center_weekdays()
    return render_template(
        'settings/study_calendar.html',
        weekday_choices=WEEKDAY_CHOICES,
        selected_weekdays=selected,
        selected_label=format_weekdays(selected),
    )


@planning_bp.route('/settings/subject-weekdays', methods=['GET', 'POST'])
@login_required
def manage_subject_weekdays():
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    if request.method == 'POST':
        try:
            save_subject_weekdays_from_form(request.form)
            flash('과목별 예정 학습요일을 저장했습니다.', 'success')
        except (PlanningError, StudyCalendarError) as exc:
            flash(exc.message, 'error')
        return redirect(url_for('planning.manage_subject_weekdays'))
    return render_template(
        'settings/subject_weekdays.html',
        **subject_weekdays_settings_rows(),
    )


@planning_bp.route('/settings/non-study-days', methods=['GET', 'POST'])
@login_required
def manage_non_study_days():
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    today = kst_today()
    try:
        year, month = parse_year_month(
            request.values.get('year'),
            request.values.get('month'),
            today=today,
        )
    except StudyCalendarError as exc:
        flash(exc.message, 'error')
        year, month = today.year, today.month
    if request.method == 'POST':
        action = (request.form.get('action') or 'add').strip()
        try:
            if action == 'restore':
                restore_non_study_day_from_form(request.form)
                flash('해당 날짜를 학습일로 복구했습니다.', 'success')
            elif action == 'restore_year_holidays':
                created = restore_year_system_holidays(year)
                if created:
                    flash(f'{year}년 법정공휴일 기본값을 {created}건 다시 채웠습니다.', 'success')
                else:
                    flash(f'{year}년 법정공휴일 기본값은 이미 반영되어 있습니다.', 'info')
            else:
                add_center_non_study_day_from_form(
                    request.form,
                    created_by_user_id=current_user.id,
                )
                flash('센터 비학습일을 추가했습니다.', 'success')
        except StudyCalendarError as exc:
            flash(exc.message, 'error')
        return redirect(url_for('planning.manage_non_study_days', year=year, month=month))
    return render_template(
        'settings/non_study_days.html',
        **non_study_days_month_view(year, month),
    )


@planning_bp.route('/settings/workbook-plans', methods=['GET', 'POST'])
@login_required
def manage_workbook_plans():
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    if request.method == 'POST':
        try:
            create_workbook_plan(**_plan_form_kwargs())
            flash('교재 계획을 추가했습니다.', 'success')
        except PlanningError as exc:
            flash(exc.message, 'error')
        return redirect(url_for('planning.manage_workbook_plans'))
    return render_template(
        'settings/workbook_plans.html',
        plans=workbook_plan_list_rows(),
        subjects=plan_form_subjects(),
        grades=PLAN_GRADES,
        plan=None,
    )


@planning_bp.route('/settings/workbook-plans/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def edit_workbook_plan(plan_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    plan = get_workbook_plan(plan_id)
    if plan is None:
        abort(404)
    if request.method == 'POST':
        try:
            update_workbook_plan(plan, **_plan_form_kwargs())
            flash('교재 계획을 수정했습니다.', 'success')
            return redirect(url_for('planning.manage_workbook_plans'))
        except PlanningError as exc:
            flash(exc.message, 'error')
    return render_template(
        'settings/workbook_plan_edit.html',
        plan=plan,
        subjects=plan_form_subjects(plan),
        grades=PLAN_GRADES,
        plan_identity_locked=workbook_plan_is_referenced_by_study_session(plan),
    )


@planning_bp.route('/settings/workbook-plans/<int:plan_id>/delete', methods=['POST'])
@login_required
def delete_workbook_plan_route(plan_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    plan = get_workbook_plan(plan_id)
    if plan is None:
        abort(404)
    confirm = (request.form.get('confirm_delete') or '').strip().lower()
    if confirm not in {'yes', 'y', '1', 'on'}:
        flash('삭제를 확인해주세요.', 'error')
        return redirect(url_for('planning.edit_workbook_plan', plan_id=plan.id))
    try:
        delete_workbook_plan(plan)
        flash('교재 계획을 삭제했습니다.', 'success')
        return redirect(url_for('planning.manage_workbook_plans'))
    except PlanningError as exc:
        flash(exc.message, 'error')
        return redirect(url_for('planning.edit_workbook_plan', plan_id=plan.id))


@planning_bp.route('/children/<int:child_id>/study-weekdays', methods=['POST'])
@login_required
def save_child_study_weekdays_route(child_id):
    blocked = _forbid_viewer()
    if blocked:
        return blocked
    _child_or_404(child_id)
    try:
        save_child_study_weekdays(
            child_id,
            request.form.get('weekday_mode'),
            request.form.getlist('study_weekdays'),
        )
        flash('학습 예정 요일을 저장했습니다.', 'success')
    except PlanningError as exc:
        flash(exc.message, 'error')
    return redirect(url_for('child_detail', child_id=child_id))


def _plan_form_kwargs():
    return {
        'grade': request.form.get('grade'),
        'learning_subject_id': request.form.get('learning_subject_id'),
        'textbook_title': request.form.get('textbook_title'),
        'start_page': request.form.get('start_page'),
        'end_page': request.form.get('end_page'),
        'start_date': request.form.get('start_date'),
        'target_completion_date': request.form.get('target_completion_date'),
        'exclusion_ranges_text': request.form.get('exclusion_ranges_text'),
    }
