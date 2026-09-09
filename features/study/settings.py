"""학습 요일/비학습일 설정 UI 매핑. 정상학습일 계산식은 schedule.py만 쓴다."""
from __future__ import annotations

from calendar import monthrange
from datetime import date

from features.dates import kst_today
from features.planning.service import get_center_weekdays, parse_weekdays_from_form
from features.planning.weekdays import WEEKDAY_CHOICES, WEEKDAY_LABELS, format_weekdays
from features.study.calendar import (
    StudyCalendarError,
    delete_center_non_study_day,
    delete_subject_study_weekdays,
    get_subject_study_weekdays,
    list_center_non_study_days,
    save_center_non_study_day,
    save_subject_study_weekdays,
)
from features.study.constants import NON_STUDY_SOURCE_CENTER, NON_STUDY_SOURCE_SYSTEM_HOLIDAY
from features.study.holidays import ensure_system_holidays, restore_system_holidays
from features.study.subjects import list_study_subjects


SOURCE_LABELS = {
    NON_STUDY_SOURCE_SYSTEM_HOLIDAY: '법정공휴일',
    NON_STUDY_SOURCE_CENTER: '센터 지정',
}


def subject_weekdays_settings_rows():
    center = get_center_weekdays()
    rows = []
    for subject in list_study_subjects():
        stored = get_subject_study_weekdays(subject.id)
        has_override = stored is not None
        selected = stored if has_override else center
        rows.append({
            'subject': subject,
            'has_override': has_override,
            'selected_weekdays': selected,
            'selected_label': format_weekdays(selected),
            'center_label': format_weekdays(center),
            'field_name': f'study_weekdays_{subject.id}',
            'mode_name': f'weekday_mode_{subject.id}',
            'id_prefix': f'subject-wd-{subject.id}',
        })
    return {
        'weekday_choices': WEEKDAY_CHOICES,
        'center_weekdays': center,
        'center_label': format_weekdays(center),
        'rows': rows,
    }


def save_subject_weekdays_from_form(form):
    saved = 0
    for subject in list_study_subjects():
        mode = (form.get(f'weekday_mode_{subject.id}') or '').strip()
        if mode == 'center':
            delete_subject_study_weekdays(subject.id)
            saved += 1
            continue
        if mode != 'custom':
            raise StudyCalendarError('과목별 요일 설정을 선택해주세요.', code='weekday_mode_required')
        save_subject_study_weekdays(
            subject.id,
            parse_weekdays_from_form(form.getlist(f'study_weekdays_{subject.id}')),
        )
        saved += 1
    return saved


def parse_year_month(raw_year, raw_month, today=None):
    today = today or kst_today()
    try:
        year = int(raw_year) if raw_year not in (None, '') else today.year
        month = int(raw_month) if raw_month not in (None, '') else today.month
    except (TypeError, ValueError) as exc:
        raise StudyCalendarError('연월이 올바르지 않습니다.', code='invalid_month') from exc
    if year < 2000 or year > 2100 or month < 1 or month > 12:
        raise StudyCalendarError('연월이 올바르지 않습니다.', code='invalid_month')
    return year, month


def month_bounds(year, month):
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def previous_year_month(year, month):
    if month == 1:
        return year - 1, 12
    return year, month - 1


def next_year_month(year, month):
    if month == 12:
        return year + 1, 1
    return year, month + 1


def non_study_days_month_view(year, month):
    ensure_system_holidays(year)
    start, end = month_bounds(year, month)
    rows = []
    for row in list_center_non_study_days(start, end):
        rows.append({
            'day': row.day,
            'weekday_label': WEEKDAY_LABELS[row.day.weekday()],
            'source': row.source,
            'source_label': SOURCE_LABELS.get(row.source, row.source),
            'label': row.label or '',
            'is_holiday': row.source == NON_STUDY_SOURCE_SYSTEM_HOLIDAY,
        })
    prev_year, prev_month = previous_year_month(year, month)
    next_year, next_month = next_year_month(year, month)
    return {
        'year': year,
        'month': month,
        'start': start,
        'end': end,
        'rows': rows,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
    }


def add_center_non_study_day_from_form(form, *, created_by_user_id=None):
    text = (form.get('day') or '').strip()
    try:
        day = date.fromisoformat(text[:10])
    except ValueError as exc:
        raise StudyCalendarError('날짜가 올바르지 않습니다.', code='invalid_date') from exc
    label = form.get('label')
    return save_center_non_study_day(
        day,
        source=NON_STUDY_SOURCE_CENTER,
        label=label,
        created_by_user_id=created_by_user_id,
    )


def restore_non_study_day_from_form(form):
    text = (form.get('day') or '').strip()
    try:
        day = date.fromisoformat(text[:10])
    except ValueError as exc:
        raise StudyCalendarError('날짜가 올바르지 않습니다.', code='invalid_date') from exc
    if not delete_center_non_study_day(day):
        raise StudyCalendarError('해당 비학습일을 찾을 수 없습니다.', code='not_found')
    return day


def restore_year_system_holidays(year):
    """운영자가 명시한 해당 연도 법정공휴일 기본값 복원."""
    return restore_system_holidays(year)
