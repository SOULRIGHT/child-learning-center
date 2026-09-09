"""학습 계획 관리. Growth metric / UI / LLM 은 연결하지 않는다."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from extensions import db
from feature_models import (
    CenterStudyCalendar,
    ChildStudyWeekdays,
    LearningStudySession,
    LearningSubject,
    LearningWorkbookPlan,
    STUDY_STATUS_STUDIED,
)
from features.planning.exclusions import PlanningError, parse_exclusion_ranges
from features.planning.weekdays import (
    CALENDAR_SINGLETON_KEY,
    DEFAULT_STUDY_WEEKDAYS,
    WEEKDAY_CHOICES,
    canonicalize_weekdays,
    effective_study_weekdays,
    format_weekdays,
)
from features.planning.timeline import (
    assert_sessions_keep_canonical_plan,
    assert_unique_plan_start_dates,
    proposed_timeline_entries,
)
from features.progress.service import MAX_PAGE, MIN_PAGE, TITLE_MAX, list_active_subjects, normalize_textbook_title
from features.reading.access import get_child

PLAN_GRADES = tuple(range(1, 7))
EXCLUSION_STATUS_ESTIMATED = 'estimated'
EXCLUSION_STATUS_EXACT = 'exact'
PLAN_IDENTITY_FIELDS = ('grade', 'learning_subject_id', 'textbook_title')
PLAN_IDENTITY_LOCKED_MESSAGE = (
    '이미 학습 기록이 연결된 교재는 학년·과목·교재명을 바꿀 수 없습니다. '
    '다른 교재는 새 계획으로 추가하세요.'
)
PLAN_START_DATE_CONFLICT_MESSAGE = (
    '이미 학습 기록이 있는 날짜보다 늦은 시작일로 바꿀 수 없습니다.'
)
PLAN_PAGE_RANGE_CONFLICT_MESSAGE = (
    '이미 기록된 학습 페이지가 교재 범위를 벗어나도록 바꿀 수 없습니다.'
)
PLAN_REFERENCED_DELETE_MESSAGE = (
    '학습 기록이 연결된 교재 계획은 삭제할 수 없습니다.'
)
PLAN_REFERENCED_DELETE_HINT = '학습기록에서 사용 중'


def parse_weekdays_from_form(raw_values):
    parsed = []
    for item in raw_values or ():
        text = str(item).strip()
        if not text:
            continue
        try:
            parsed.append(int(text))
        except (TypeError, ValueError) as exc:
            raise PlanningError(
                '학습요일은 0부터 6 사이의 정수여야 합니다.',
                code='invalid_weekday',
            ) from exc
    return canonicalize_weekdays(parsed)


def get_center_calendar_row():
    return CenterStudyCalendar.query.filter_by(singleton_key=CALENDAR_SINGLETON_KEY).one_or_none()


def get_center_weekdays():
    """저장된 센터 기본값. row가 없으면 월~금 기본값을 반환하고 DB에는 쓰지 않는다."""
    row = get_center_calendar_row()
    if row is None or row.study_weekdays is None:
        return list(DEFAULT_STUDY_WEEKDAYS)
    return canonicalize_weekdays(row.study_weekdays)


def update_center_weekdays(raw_weekdays):
    days = canonicalize_weekdays(raw_weekdays)
    if not days:
        raise PlanningError(
            '센터 기본 학습요일은 하루 이상 선택해야 합니다.',
            code='center_weekdays_required',
        )
    now = datetime.utcnow()
    row = get_center_calendar_row()
    if row is None:
        row = CenterStudyCalendar(
            singleton_key=CALENDAR_SINGLETON_KEY,
            study_weekdays=days,
            created_at=now,
            updated_at=now,
        )
        db.session.add(row)
    else:
        row.study_weekdays = days
        row.updated_at = now
    db.session.commit()
    return row


def get_child_override_weekdays(child_id):
    row = ChildStudyWeekdays.query.filter_by(child_id=child_id).one_or_none()
    if row is None:
        return None
    return canonicalize_weekdays(row.study_weekdays)


WEEKDAY_SOURCE_CENTER_DEFAULT = 'center_default'
WEEKDAY_SOURCE_CHILD_OVERRIDE = 'child_override'


def resolve_child_study_weekdays(child_id):
    """canonical weekday resolution. planner/UI가 같이 쓴다. DB write 없음."""
    override = get_child_override_weekdays(child_id)
    if override is None:
        return list(get_center_weekdays()), WEEKDAY_SOURCE_CENTER_DEFAULT
    return list(override), WEEKDAY_SOURCE_CHILD_OVERRIDE


def effective_child_study_weekdays(child_id):
    """override row가 있으면 override, 없으면 센터 기본. UI와 향후 planner가 같이 쓴다."""
    days, _source = resolve_child_study_weekdays(child_id)
    return days


def child_study_weekdays_view(child_id):
    center = get_center_weekdays()
    override = get_child_override_weekdays(child_id)
    effective = effective_study_weekdays(center, override)
    return {
        'weekday_choices': WEEKDAY_CHOICES,
        'has_override': override is not None,
        'source': 'override' if override is not None else 'center',
        'effective_weekdays': effective,
        'center_weekdays': center,
        'override_weekdays': override,
        'center_weekdays_label': format_weekdays(center),
        'effective_weekdays_label': format_weekdays(effective),
        'custom_selected_weekdays': override if override is not None else center,
    }


def set_child_weekdays_override(child_id, raw_weekdays):
    _require_child(child_id)
    days = canonicalize_weekdays(raw_weekdays)
    now = datetime.utcnow()
    row = ChildStudyWeekdays.query.filter_by(child_id=child_id).one_or_none()
    if row is None:
        row = ChildStudyWeekdays(
            child_id=child_id,
            study_weekdays=days,
            created_at=now,
            updated_at=now,
        )
        db.session.add(row)
    else:
        row.study_weekdays = days
        row.updated_at = now
    db.session.commit()
    return row


def clear_child_weekdays_override(child_id):
    row = ChildStudyWeekdays.query.filter_by(child_id=child_id).one_or_none()
    if row is None:
        return False
    db.session.delete(row)
    db.session.commit()
    return True


def save_child_study_weekdays(child_id, mode, raw_weekdays):
    _require_child(child_id)
    selected = ('' if mode is None else str(mode)).strip()
    if selected == 'center':
        clear_child_weekdays_override(child_id)
        return child_study_weekdays_view(child_id)
    if selected == 'custom':
        set_child_weekdays_override(child_id, parse_weekdays_from_form(raw_weekdays))
        return child_study_weekdays_view(child_id)
    raise PlanningError('학습요일 설정을 선택해주세요.', code='weekday_mode_required')


def list_workbook_plans():
    return (
        LearningWorkbookPlan.query
        .options(joinedload(LearningWorkbookPlan.subject))
        .join(LearningSubject)
        .order_by(
            LearningWorkbookPlan.grade.asc(),
            LearningSubject.sort_order.asc(),
            LearningSubject.name.asc(),
            LearningWorkbookPlan.start_date.asc(),
            LearningWorkbookPlan.id.asc(),
        )
        .all()
    )


def plan_form_subjects(plan=None):
    subjects = list(list_active_subjects())
    current = getattr(plan, 'subject', None) if plan is not None else None
    if current is not None and all(row.id != current.id for row in subjects):
        subjects.append(current)
    return subjects


def get_workbook_plan(plan_id):
    return (
        LearningWorkbookPlan.query
        .options(joinedload(LearningWorkbookPlan.subject))
        .filter_by(id=plan_id)
        .one_or_none()
    )


def exclusion_status_key(plan):
    if plan.exclusion_ranges_json is None:
        return EXCLUSION_STATUS_ESTIMATED
    return EXCLUSION_STATUS_EXACT


def exclusion_status_label(plan):
    if exclusion_status_key(plan) == EXCLUSION_STATUS_ESTIMATED:
        return '20% 추정'
    return '정확한 제외 범위 있음'


def workbook_plan_list_rows():
    rows = []
    for plan in list_workbook_plans():
        rows.append({
            'plan': plan,
            'exclusion_status': exclusion_status_key(plan),
            'exclusion_label': exclusion_status_label(plan),
            'referenced': workbook_plan_is_referenced_by_study_session(plan),
        })
    return rows


def create_workbook_plan(
    *,
    grade,
    learning_subject_id,
    textbook_title,
    start_page,
    end_page,
    start_date,
    target_completion_date,
    exclusion_ranges_text=None,
):
    payload = _workbook_plan_payload(
        grade=grade,
        learning_subject_id=learning_subject_id,
        textbook_title=textbook_title,
        start_page=start_page,
        end_page=end_page,
        start_date=start_date,
        target_completion_date=target_completion_date,
        exclusion_ranges_text=exclusion_ranges_text,
        require_active_subject=True,
    )
    _assert_canonical_timeline_ok(
        grade=payload['grade'],
        learning_subject_id=payload['learning_subject_id'],
        extra_start_date=payload['start_date'],
    )
    now = datetime.utcnow()
    plan = LearningWorkbookPlan(
        created_at=now,
        updated_at=now,
        **payload,
    )
    db.session.add(plan)
    _commit_workbook_plan()
    return plan


def workbook_plan_is_referenced_by_study_session(plan):
    if plan is None or getattr(plan, 'id', None) is None:
        return False
    return (
        LearningStudySession.query
        .filter_by(learning_workbook_plan_id=plan.id)
        .first()
        is not None
    )


def update_workbook_plan(
    plan,
    *,
    grade,
    learning_subject_id,
    textbook_title,
    start_page,
    end_page,
    start_date,
    target_completion_date,
    exclusion_ranges_text=None,
):
    require_active = True
    try:
        new_subject_id = int(learning_subject_id)
    except (TypeError, ValueError):
        new_subject_id = None
    if new_subject_id == plan.learning_subject_id:
        require_active = False
    payload = _workbook_plan_payload(
        grade=grade,
        learning_subject_id=learning_subject_id,
        textbook_title=textbook_title,
        start_page=start_page,
        end_page=end_page,
        start_date=start_date,
        target_completion_date=target_completion_date,
        exclusion_ranges_text=exclusion_ranges_text,
        require_active_subject=require_active,
    )
    if workbook_plan_is_referenced_by_study_session(plan):
        for key in PLAN_IDENTITY_FIELDS:
            if payload[key] != getattr(plan, key):
                raise PlanningError(
                    PLAN_IDENTITY_LOCKED_MESSAGE,
                    code='plan_identity_locked',
                )
        _assert_referenced_plan_compatible(plan, payload)
    _assert_update_timeline(plan, payload)
    for key, value in payload.items():
        setattr(plan, key, value)
    plan.updated_at = datetime.utcnow()
    _commit_workbook_plan()
    return plan


def delete_workbook_plan(plan):
    if plan is None or getattr(plan, 'id', None) is None:
        raise PlanningError('교재 계획을 찾을 수 없습니다.', code='plan_not_found')
    if workbook_plan_is_referenced_by_study_session(plan):
        raise PlanningError(
            PLAN_REFERENCED_DELETE_MESSAGE,
            code='plan_referenced',
        )
    db.session.delete(plan)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise PlanningError(
            PLAN_REFERENCED_DELETE_MESSAGE,
            code='plan_referenced',
        ) from exc
    return True


def _assert_canonical_timeline_ok(
    *,
    grade,
    learning_subject_id,
    extra_start_date=None,
    override=None,
    exclude_id=None,
):
    entries = proposed_timeline_entries(
        grade,
        learning_subject_id,
        extra_start_date=extra_start_date,
        override=override,
        exclude_id=exclude_id,
    )
    assert_unique_plan_start_dates(entries)
    assert_sessions_keep_canonical_plan(entries)


def _assert_update_timeline(plan, payload):
    same_lane = (
        payload['grade'] == plan.grade
        and int(payload['learning_subject_id']) == int(plan.learning_subject_id)
    )
    if same_lane:
        _assert_canonical_timeline_ok(
            grade=payload['grade'],
            learning_subject_id=payload['learning_subject_id'],
            override={
                'id': plan.id,
                'start_date': payload['start_date'],
            },
        )
        return
    _assert_canonical_timeline_ok(
        grade=payload['grade'],
        learning_subject_id=payload['learning_subject_id'],
        extra_start_date=payload['start_date'],
    )
    _assert_canonical_timeline_ok(
        grade=plan.grade,
        learning_subject_id=plan.learning_subject_id,
        exclude_id=plan.id,
    )


def _assert_referenced_plan_compatible(plan, payload):
    if payload['start_date'] != plan.start_date:
        earliest = (
            db.session.query(func.min(LearningStudySession.study_date))
            .filter_by(learning_workbook_plan_id=plan.id)
            .scalar()
        )
        if earliest is not None and payload['start_date'] > earliest:
            raise PlanningError(
                PLAN_START_DATE_CONFLICT_MESSAGE,
                code='plan_start_date_conflicts_sessions',
            )
    pages_changed = (
        payload['start_page'] != plan.start_page
        or payload['end_page'] != plan.end_page
    )
    if not pages_changed:
        return
    session_start, session_end = (
        db.session.query(
            func.min(LearningStudySession.start_page),
            func.max(LearningStudySession.end_page),
        )
        .filter(LearningStudySession.learning_workbook_plan_id == plan.id)
        .filter(LearningStudySession.study_status == STUDY_STATUS_STUDIED)
        .filter(LearningStudySession.start_page.isnot(None))
        .filter(LearningStudySession.end_page.isnot(None))
        .one()
    )
    if session_start is None or session_end is None:
        return
    if payload['start_page'] > session_start or payload['end_page'] < session_end:
        raise PlanningError(
            PLAN_PAGE_RANGE_CONFLICT_MESSAGE,
            code='plan_page_range_conflicts_sessions',
        )


def _workbook_plan_payload(
    *,
    grade,
    learning_subject_id,
    textbook_title,
    start_page,
    end_page,
    start_date,
    target_completion_date,
    exclusion_ranges_text,
    require_active_subject,
):
    subject = _resolve_subject(learning_subject_id, require_active=require_active_subject)
    start = _parse_page(start_page, field_label='시작 페이지')
    end = _parse_page(end_page, field_label='마지막 페이지')
    if start > end:
        raise PlanningError('시작 페이지는 마지막 페이지 이하여야 합니다.', code='page_order')
    begin = _parse_date(start_date, field_label='학습 시작일')
    target = _parse_date(target_completion_date, field_label='목표 완료일')
    if target < begin:
        raise PlanningError('목표 완료일은 학습 시작일과 같거나 이후여야 합니다.', code='date_order')
    text, ranges = _exclusion_payload(exclusion_ranges_text, start_page=start, end_page=end)
    return {
        'grade': _parse_grade(grade),
        'learning_subject_id': subject.id,
        'textbook_title': _clean_textbook_title(textbook_title),
        'start_page': start,
        'end_page': end,
        'start_date': begin,
        'target_completion_date': target,
        'exclusion_ranges_text': text,
        'exclusion_ranges_json': ranges,
    }


def _exclusion_payload(raw_text, *, start_page, end_page):
    parsed = parse_exclusion_ranges(raw_text, start_page=start_page, end_page=end_page)
    if parsed is None:
        return None, None
    return str(raw_text).strip(), parsed


def _clean_textbook_title(raw):
    title = normalize_textbook_title(raw)
    if not title:
        raise PlanningError('교재명은 필수입니다.', code='title_required')
    return title[:TITLE_MAX]


def _parse_grade(raw):
    try:
        grade = int(raw)
    except (TypeError, ValueError) as exc:
        raise PlanningError('학년을 선택해주세요.', code='invalid_grade') from exc
    if grade not in PLAN_GRADES:
        raise PlanningError('학년은 1부터 6까지입니다.', code='invalid_grade')
    return grade


def _parse_page(raw, *, field_label):
    try:
        page = int(raw)
    except (TypeError, ValueError) as exc:
        raise PlanningError(f'{field_label}는 정수여야 합니다.', code='invalid_page') from exc
    if page < MIN_PAGE:
        raise PlanningError(f'{field_label}는 1 이상이어야 합니다.', code='page_range')
    if page > MAX_PAGE:
        raise PlanningError('페이지 범위를 확인해주세요.', code='page_range')
    return page


def _parse_date(raw, *, field_label):
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    text = '' if raw is None else str(raw).strip()
    if not text:
        raise PlanningError(f'{field_label}을 입력해주세요.', code='invalid_date')
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise PlanningError(f'{field_label}이 올바르지 않습니다.', code='invalid_date') from exc


def _resolve_subject(learning_subject_id, *, require_active):
    try:
        subject_id = int(learning_subject_id)
    except (TypeError, ValueError) as exc:
        raise PlanningError('과목을 선택해주세요.', code='subject_required') from exc
    subject = LearningSubject.query.get(subject_id)
    if subject is None:
        raise PlanningError('과목을 찾을 수 없습니다.', code='subject_not_found')
    if require_active and not subject.is_active:
        raise PlanningError('비활성 과목에는 새 계획을 등록할 수 없습니다.', code='subject_inactive')
    return subject


def _require_child(child_id):
    child = get_child(child_id)
    if child is None:
        raise PlanningError('아동을 찾을 수 없습니다.', code='child_not_found')
    return child


def _commit_workbook_plan():
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        detail = str(getattr(exc, 'orig', exc)).lower()
        if 'unique' in detail or 'uq_workbook_plan' in detail:
            raise PlanningError(
                '같은 학년·과목·교재·시작일의 계획이 이미 있습니다.',
                code='duplicate_plan',
            ) from exc
        raise PlanningError(
            '학습 계획을 저장하지 못했습니다. 입력값을 확인해주세요.',
            code='save_failed',
        ) from exc


def build_child_subject_plan_status(child, learning_subject, as_of=None):
    """canonical rolling planner. DB write 없음. Growth 연결 없음."""
    from features.planning.planner import build_child_subject_plan_status as impl
    return impl(child, learning_subject, as_of=as_of)


def build_child_learning_plan_statuses(child, as_of=None):
    """활성 과목 aggregator. Growth 연결 없음."""
    from features.planning.planner import build_child_learning_plan_statuses as impl
    return impl(child, as_of=as_of)
