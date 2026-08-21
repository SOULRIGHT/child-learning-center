"""아동/교사 공용 독서기록 HTTP. 권한·세션 검증만 담당하고 저장은 service에 둔다."""
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

from feature_models import ChildReading, STATUS_COMPLETED
from features.exemption.policy import REWARD_MODE_EXEMPTION, REWARD_MODE_POINTS, grade_supports_reward_choice
from features.exemption.service import (
    child_exemption_snapshot,
    consuming_ticket_for_reading,
    reward_mode_change_block,
)
from features.reading.access import get_child, resolve_viewer_child
from features.reading.classify import grade_band_for_child_grade
from features.reading.policy import activity_today, is_general_reading_v2
from features.reading.rewards import (
    ALL_REWARD_EVENT_TYPES,
    RewardError,
    approve_recommended_reward,
    reward_status_for_reading,
    revoke_recommended_reward,
)
from features.reading.service import (
    ReadingError,
    abandon_current,
    actor_type_for_user,
    get_day,
    list_days,
    list_readings_for_child,
    save_today,
    snapshot_for_date,
    start_book,
)
from features.reading import session as viewer_session

reading_bp = Blueprint('reading', __name__)


def _is_viewer():
    return getattr(current_user, 'role', None) == current_app.config.get(
        'VIEWER_ROLE_NAME', '학생열람'
    )


def _parse_activity_date(raw, *, allow_client_date):
    today = activity_today()
    if not allow_client_date:
        return today
    if not raw:
        return today
    try:
        from datetime import date
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return today


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
        flash('독서기록을 저장할 수 없어요.', 'error')
        return _redirect_confirm(view_token)
    return None


def _assert_reading_child(child, expected_reading_id):
    if not expected_reading_id:
        return None
    from feature_models import ChildReading
    try:
        reading_id = int(expected_reading_id)
    except (TypeError, ValueError):
        abort(403)
    target = ChildReading.query.get(reading_id)
    if target is None or int(target.child_id) != int(child.id):
        abort(403)
    return target


def _with_mode_blocks(reward_status, reading):
    if not reward_status or reading is None:
        return reward_status
    ticket = consuming_ticket_for_reading(reading.id)
    reward_status['exemption_applied'] = ticket is not None
    reward_status['exemption_pending'] = bool(
        reading.reward_mode == REWARD_MODE_EXEMPTION
        and reading.status == STATUS_COMPLETED
        and reading.completed_on is not None
        and ticket is None
    )
    if not reward_status.get('can_choose_mode'):
        return reward_status
    points_code, points_msg = reward_mode_change_block(reading, REWARD_MODE_POINTS)
    exemption_code, exemption_msg = reward_mode_change_block(reading, REWARD_MODE_EXEMPTION)
    reward_status['mode_blocks'] = {
        'points': {'code': points_code, 'message': points_msg},
        'exemption': {'code': exemption_code, 'message': exemption_msg},
    }
    return reward_status


def _editor_context(child, activity_date, *, mode, view_token=None):
    snapshot = snapshot_for_date(child.id, activity_date)
    current = snapshot['current_reading']
    today_day = None
    if current is not None:
        today_day = get_day(current.id, activity_date)
    reward_status = None if current is None else _with_mode_blocks(
        reward_status_for_reading(current, child),
        current,
    )
    exemption_status = None
    if grade_supports_reward_choice(getattr(child, 'grade', None)):
        exemption_status = child_exemption_snapshot(child.id)
    return {
        'child': child,
        'activity_date': activity_date,
        'activity_date_iso': activity_date.isoformat(),
        'mode': mode,
        'view_token': view_token,
        'current_reading': current,
        'current_book': snapshot['current_book'],
        'today_day': today_day,
        'has_today_other_book': (
            snapshot['has_today_record']
            and current is not None
            and snapshot['today_day'] is not None
            and snapshot['today_day'].child_reading_id != current.id
        ),
        'has_today_record': snapshot['has_today_record'],
        'is_viewer_mode': mode == 'viewer',
        'child_grade_band': grade_band_for_child_grade(getattr(child, 'grade', None)),
        'reward_status': reward_status,
        'exemption_status': exemption_status,
    }


@reading_bp.route('/viewer/report/<string:view_token>/reading/confirm', methods=['GET', 'POST'])
@login_required
def viewer_confirm(view_token):
    child, slug = resolve_viewer_child(view_token)
    if not child:
        flash('유효하지 않은 리포트 링크입니다.', 'error')
        return redirect(url_for('viewer_home') if _is_viewer() else url_for('dashboard'))

    if request.method == 'POST':
        answer = (request.form.get('confirm') or '').strip().lower()
        if answer in {'yes', 'y', '1'}:
            viewer_session.set_verified_child(session, child)
            return redirect(url_for('reading.viewer_editor', view_token=slug or view_token))
        viewer_session.clear_verified_child(session)
        flash('올바른 아동의 QR을 다시 스캔해 주세요.', 'info')
        return redirect(url_for('viewer_home') if _is_viewer() else url_for('dashboard'))

    return render_template(
        'reading/confirm.html',
        child=child,
        view_token=slug or view_token,
    )


@reading_bp.route('/viewer/report/<string:view_token>/reading', methods=['GET'])
@login_required
def viewer_editor(view_token):
    child, slug = resolve_viewer_child(view_token)
    if not child:
        flash('유효하지 않은 리포트 링크입니다.', 'error')
        return redirect(url_for('viewer_home') if _is_viewer() else url_for('dashboard'))

    blocked = _viewer_write_guard(child, slug or view_token)
    if blocked:
        return blocked

    activity_date = activity_today()
    return render_template(
        'reading/editor.html',
        **_editor_context(child, activity_date, mode='viewer', view_token=slug or view_token),
    )


def _handle_viewer_write(view_token, action):
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

    expected_reading_id = request.form.get('child_reading_id') or None
    posted_child_id = request.form.get('child_id')
    if posted_child_id and int(posted_child_id) != int(child.id):
        abort(403)

    actor = actor_type_for_user(current_user)
    activity_date = activity_today()
    try:
        if action == 'start':
            start_book(
                child.id,
                current_user.id,
                actor,
                activity_date=activity_date,
                book_id=request.form.get('book_id') or None,
                title=request.form.get('title'),
                author=request.form.get('author'),
                review_text=request.form.get('review_text'),
                allow_create_book=True,
            )
            flash('오늘 독서기록을 저장했어요.', 'success')
        elif action == 'save':
            _assert_reading_child(child, expected_reading_id)
            mark_completed = request.form.get('completed') in {'1', 'on', 'true', 'yes'}
            save_today(
                child.id,
                current_user.id,
                actor,
                activity_date=activity_date,
                review_text=request.form.get('review_text'),
                mark_completed=mark_completed,
                expected_reading_id=expected_reading_id,
            )
            flash('오늘 독서기록을 저장했어요.', 'success')
        elif action == 'abandon':
            _assert_reading_child(child, expected_reading_id)
            abandon_current(
                child.id,
                current_user.id,
                actor,
                activity_date=activity_date,
                expected_reading_id=expected_reading_id,
            )
            flash('이 책 읽기를 그만두었어요.', 'success')
    except ReadingError as exc:
        flash(exc.message, 'error')
    return redirect(url_for('reading.viewer_editor', view_token=token))


@reading_bp.route('/viewer/report/<string:view_token>/reading/start', methods=['POST'])
@login_required
def viewer_start(view_token):
    return _handle_viewer_write(view_token, 'start')


@reading_bp.route('/viewer/report/<string:view_token>/reading/save', methods=['POST'])
@login_required
def viewer_save(view_token):
    return _handle_viewer_write(view_token, 'save')


@reading_bp.route('/viewer/report/<string:view_token>/reading/abandon', methods=['POST'])
@login_required
def viewer_abandon(view_token):
    return _handle_viewer_write(view_token, 'abandon')


@reading_bp.route('/children/<int:child_id>/reading', methods=['GET'])
@login_required
def teacher_editor(child_id):
    if _is_viewer():
        return redirect(url_for('viewer_home'))
    child = get_child(child_id)
    if child is None:
        abort(404)
    activity_date = _parse_activity_date(request.args.get('date'), allow_client_date=True)
    return render_template(
        'reading/editor.html',
        **_editor_context(child, activity_date, mode='teacher'),
    )


@reading_bp.route('/children/<int:child_id>/reading/history', methods=['GET'])
@login_required
def teacher_history(child_id):
    # TODO: Viewer self reading history (read-only)
    # 학생열람은 작성만 가능하고, 자기 독서기록 읽기 전용 조회는 후속 Step에서 구현한다.
    # 기존 QR/viewer 권한과 검증된 child session(viewer_child_id / viewer_slug) 범위만 사용한다.
    # 자기 아동만, 다른 아동 접근 금지. ReadingRewardEvent / ExemptionTicketSource /
    # 승인자 / policy_version 등 관리자 audit 은 노출하지 않는다.
    if _is_viewer():
        return redirect(url_for('viewer_home'))
    child = get_child(child_id)
    if child is None:
        abort(404)
    readings = list_readings_for_child(child.id)
    items = []
    for reading in readings:
        items.append({
            'reading': reading,
            'book': reading.book,
            'days': list_days(reading.id),
            'reward_status': _with_mode_blocks(reward_status_for_reading(reading, child), reading),
        })
    exemption_status = None
    if grade_supports_reward_choice(getattr(child, 'grade', None)):
        exemption_status = child_exemption_snapshot(child.id)
    return render_template(
        'reading/history.html',
        child=child,
        items=items,
        exemption_status=exemption_status,
        is_viewer_mode=False,
    )


def _handle_teacher_write(child_id, action):
    if _is_viewer():
        return redirect(url_for('viewer_home'))
    child = get_child(child_id)
    if child is None:
        abort(404)

    activity_date = _parse_activity_date(request.form.get('date'), allow_client_date=True)
    if not is_general_reading_v2(activity_date):
        flash('새 독서기록은 정책 적용일 이후부터 작성할 수 있습니다.', 'error')
        return redirect(url_for('reading.teacher_editor', child_id=child.id, date=activity_date.isoformat()))

    expected_reading_id = request.form.get('child_reading_id') or None
    posted_child_id = request.form.get('child_id')
    if posted_child_id and int(posted_child_id) != int(child.id):
        abort(403)

    actor = actor_type_for_user(current_user)
    try:
        if action == 'start':
            start_book(
                child.id,
                current_user.id,
                actor,
                activity_date=activity_date,
                book_id=request.form.get('book_id') or None,
                title=request.form.get('title'),
                author=request.form.get('author'),
                review_text=request.form.get('review_text'),
                allow_create_book=True,
            )
            flash('오늘 독서기록을 저장했습니다.', 'success')
        elif action == 'save':
            save_today(
                child.id,
                current_user.id,
                actor,
                activity_date=activity_date,
                review_text=request.form.get('review_text'),
                mark_completed=request.form.get('completed') in {'1', 'on', 'true', 'yes'},
                expected_reading_id=expected_reading_id,
            )
            flash('오늘 독서기록을 저장했습니다.', 'success')
        elif action == 'abandon':
            abandon_current(
                child.id,
                current_user.id,
                actor,
                activity_date=activity_date,
                expected_reading_id=expected_reading_id,
            )
            flash('이 책 읽기를 중단했습니다.', 'success')
    except ReadingError as exc:
        flash(exc.message, 'error')
    return redirect(url_for(
        'reading.teacher_editor',
        child_id=child.id,
        date=activity_date.isoformat(),
    ))


@reading_bp.route('/children/<int:child_id>/reading/start', methods=['POST'])
@login_required
def teacher_start(child_id):
    return _handle_teacher_write(child_id, 'start')


@reading_bp.route('/children/<int:child_id>/reading/save', methods=['POST'])
@login_required
def teacher_save(child_id):
    return _handle_teacher_write(child_id, 'save')


@reading_bp.route('/children/<int:child_id>/reading/abandon', methods=['POST'])
@login_required
def teacher_abandon(child_id):
    return _handle_teacher_write(child_id, 'abandon')


def _handle_teacher_reward(child_id, action):
    if _is_viewer():
        return redirect(url_for('viewer_home'))
    child = get_child(child_id)
    if child is None:
        abort(404)
    try:
        reading_id = int(request.form.get('child_reading_id') or 0)
    except (TypeError, ValueError):
        abort(400)
    reading = ChildReading.query.get(reading_id)
    if reading is None or int(reading.child_id) != int(child.id):
        abort(403)
    event_type = request.form.get('event_type')
    if event_type not in ALL_REWARD_EVENT_TYPES:
        flash('알 수 없는 보상 유형입니다.', 'error')
        return redirect(request.referrer or url_for('reading.teacher_history', child_id=child.id))
    try:
        if action == 'approve':
            approve_recommended_reward(reading, current_user, event_type)
            flash('독서 보상을 승인했습니다.', 'success')
        else:
            revoke_recommended_reward(reading, current_user, event_type)
            flash('독서 보상을 취소했습니다.', 'success')
    except RewardError as exc:
        flash(exc.message, 'error')
    next_url = request.form.get('next') or request.referrer
    if next_url:
        return redirect(next_url)
    return redirect(url_for('reading.teacher_history', child_id=child.id))


@reading_bp.route('/children/<int:child_id>/reading/reward/approve', methods=['POST'])
@login_required
def teacher_reward_approve(child_id):
    return _handle_teacher_reward(child_id, 'approve')


@reading_bp.route('/children/<int:child_id>/reading/reward/revoke', methods=['POST'])
@login_required
def teacher_reward_revoke(child_id):
    return _handle_teacher_reward(child_id, 'revoke')

