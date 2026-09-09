"""I-2 학습 수행률 / 데이터 확인률. Growth AI/Evidence와 연결하지 않는다.

verification(observed/verified)은 이 공식에 넣지 않는다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from features.study.constants import (
    STUDY_STATUS_EXPLICIT_NOT_STUDIED,
    STUDY_STATUS_STUDIED,
    STUDY_STATUS_UNKNOWN,
)
from features.study.records import list_child_sessions_in_range
from features.study.schedule import normal_study_day
from features.study.subjects import list_study_subjects

INTERPRETATION_UNAVAILABLE = 'unavailable'
INTERPRETATION_FORBIDDEN = 'forbidden'
INTERPRETATION_LIMITED = 'limited'
INTERPRETATION_PRIMARY = 'primary'

CONFIRMATION_FORBIDDEN_BELOW = 0.50
CONFIRMATION_PRIMARY_AT = 0.70
MIN_EXPECTED_DAYS_FOR_PERIOD_CHANGE = 8
MAJOR_DELTA_PP = 10.0

UNKNOWN_KIND_MISSING = 'missing'
UNKNOWN_KIND_EXPLICIT = 'explicit_unknown'


def _as_date(raw):
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError as exc:
        raise TypeError('date가 필요합니다.') from exc


def _iter_days(start_date, end_date):
    start = _as_date(start_date)
    end = _as_date(end_date)
    if end < start:
        return
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def _sessions_by_subject_day(sessions):
    grouped = {}
    for row in sessions:
        key = (row.learning_subject_id, row.study_date)
        grouped.setdefault(key, []).append(row)
    return grouped


def subject_day_state(child_id, subject_id, day, sessions=None):
    """정상학습 subject-day의 학습상태. 비예정/비학습일은 expected=False."""
    day = _as_date(day)
    expected = normal_study_day(child_id, subject_id, day)
    rows = [] if sessions is None else list(sessions)
    studied_rows = [row for row in rows if row.study_status == STUDY_STATUS_STUDIED]
    not_studied_rows = [
        row for row in rows if row.study_status == STUDY_STATUS_EXPLICIT_NOT_STUDIED
    ]
    unknown_rows = [row for row in rows if row.study_status == STUDY_STATUS_UNKNOWN]
    extra_studied = (not expected) and bool(studied_rows)
    if not expected:
        return {
            'expected': False,
            'outcome': None,
            'unknown_kind': None,
            'extra_studied': extra_studied,
        }
    if studied_rows:
        outcome = STUDY_STATUS_STUDIED
        unknown_kind = None
    elif not_studied_rows:
        outcome = STUDY_STATUS_EXPLICIT_NOT_STUDIED
        unknown_kind = None
    else:
        outcome = STUDY_STATUS_UNKNOWN
        unknown_kind = (
            UNKNOWN_KIND_EXPLICIT if unknown_rows else UNKNOWN_KIND_MISSING
        )
    return {
        'expected': True,
        'outcome': outcome,
        'unknown_kind': unknown_kind,
        'extra_studied': False,
    }


def _empty_counts():
    return {
        'expected_days': 0,
        'studied_days': 0,
        'explicit_not_studied_days': 0,
        'unknown_days': 0,
        'extra_studied_days': 0,
        'missing_days': 0,
        'explicit_unknown_days': 0,
    }


def _rates_from_counts(counts):
    expected = counts['expected_days']
    if expected == 0:
        performance_rate = None
        confirmation_rate = None
        interpretation = INTERPRETATION_UNAVAILABLE
    else:
        performance_rate = counts['studied_days'] / expected
        confirmation_rate = (
            counts['studied_days'] + counts['explicit_not_studied_days']
        ) / expected
        interpretation = confirmation_band(confirmation_rate, expected)
    return {
        **counts,
        'performance_rate': performance_rate,
        'confirmation_rate': confirmation_rate,
        'interpretation': interpretation,
        'eligibility': {
            'enough_days': expected >= MIN_EXPECTED_DAYS_FOR_PERIOD_CHANGE,
            'confirmation_band': interpretation,
        },
    }


def confirmation_band(confirmation_rate, expected_days):
    if expected_days is None or int(expected_days) <= 0 or confirmation_rate is None:
        return INTERPRETATION_UNAVAILABLE
    if confirmation_rate < CONFIRMATION_FORBIDDEN_BELOW:
        return INTERPRETATION_FORBIDDEN
    if confirmation_rate < CONFIRMATION_PRIMARY_AT:
        return INTERPRETATION_LIMITED
    return INTERPRETATION_PRIMARY


def _add_state(counts, state):
    if state['extra_studied']:
        counts['extra_studied_days'] += 1
    if not state['expected']:
        return
    counts['expected_days'] += 1
    outcome = state['outcome']
    if outcome == STUDY_STATUS_STUDIED:
        counts['studied_days'] += 1
    elif outcome == STUDY_STATUS_EXPLICIT_NOT_STUDIED:
        counts['explicit_not_studied_days'] += 1
    else:
        counts['unknown_days'] += 1
        if state['unknown_kind'] == UNKNOWN_KIND_EXPLICIT:
            counts['explicit_unknown_days'] += 1
        else:
            counts['missing_days'] += 1


def subject_period(child_id, subject_id, start_date, end_date, *, grouped_sessions=None):
    """한 과목의 [start_date, end_date] inclusive I-2 지표."""
    start = _as_date(start_date)
    end = _as_date(end_date)
    if grouped_sessions is None:
        grouped_sessions = _sessions_by_subject_day(
            list_child_sessions_in_range(child_id, start, end)
        )
    counts = _empty_counts()
    for day in _iter_days(start, end):
        sessions = grouped_sessions.get((int(subject_id), day), [])
        state = subject_day_state(child_id, subject_id, day, sessions)
        _add_state(counts, state)
    payload = _rates_from_counts(counts)
    payload['child_id'] = int(child_id)
    payload['learning_subject_id'] = int(subject_id)
    payload['start_date'] = start
    payload['end_date'] = end
    return payload


def overall_period(child_id, start_date, end_date):
    """과목-날 slot 합산. 같은 날 두 과목이 예정이면 분모 +2."""
    start = _as_date(start_date)
    end = _as_date(end_date)
    grouped = _sessions_by_subject_day(
        list_child_sessions_in_range(child_id, start, end)
    )
    counts = _empty_counts()
    subjects = []
    for subject in list_study_subjects():
        item = subject_period(
            child_id,
            subject.id,
            start,
            end,
            grouped_sessions=grouped,
        )
        subjects.append(item)
        for key in _empty_counts():
            counts[key] += item[key]
    payload = _rates_from_counts(counts)
    payload['child_id'] = int(child_id)
    payload['learning_subject_id'] = None
    payload['start_date'] = start
    payload['end_date'] = end
    payload['subjects'] = subjects
    return payload


def _percentage_points(current_rate, previous_rate):
    if current_rate is None or previous_rate is None:
        return None
    return round((current_rate - previous_rate) * 100.0, 4)


def _worst_band(left, right):
    order = (
        INTERPRETATION_UNAVAILABLE,
        INTERPRETATION_FORBIDDEN,
        INTERPRETATION_LIMITED,
        INTERPRETATION_PRIMARY,
    )
    return order[min(order.index(left), order.index(right))]


def compare_periods(current, previous):
    """LEARN-004/005/006 eligibility. AI 문구는 만들지 않는다."""
    performance_delta = _percentage_points(
        current.get('performance_rate'),
        previous.get('performance_rate'),
    )
    confirmation_delta = _percentage_points(
        current.get('confirmation_rate'),
        previous.get('confirmation_rate'),
    )
    enough_days = (
        int(current.get('expected_days') or 0) >= MIN_EXPECTED_DAYS_FOR_PERIOD_CHANGE
        and int(previous.get('expected_days') or 0) >= MIN_EXPECTED_DAYS_FOR_PERIOD_CHANGE
    )
    band = _worst_band(
        current.get('interpretation') or INTERPRETATION_UNAVAILABLE,
        previous.get('interpretation') or INTERPRETATION_UNAVAILABLE,
    )
    period_change_allowed = enough_days and band in {
        INTERPRETATION_LIMITED,
        INTERPRETATION_PRIMARY,
    }
    major_delta = (
        performance_delta is not None and abs(performance_delta) >= MAJOR_DELTA_PP
    )
    major_insight_eligible = (
        period_change_allowed
        and band == INTERPRETATION_PRIMARY
        and major_delta
    )
    return {
        'current': current,
        'previous': previous,
        'performance_delta_pp': performance_delta,
        'confirmation_delta_pp': confirmation_delta,
        'enough_days': enough_days,
        'confirmation_band': band,
        'period_change_allowed': period_change_allowed,
        'major_insight_eligible': major_insight_eligible,
    }


def compare_subject_periods(
    child_id,
    subject_id,
    current_start,
    current_end,
    previous_start,
    previous_end,
):
    return compare_periods(
        subject_period(child_id, subject_id, current_start, current_end),
        subject_period(child_id, subject_id, previous_start, previous_end),
    )


def compare_overall_periods(
    child_id,
    current_start,
    current_end,
    previous_start,
    previous_end,
):
    return compare_periods(
        overall_period(child_id, current_start, current_end),
        overall_period(child_id, previous_start, previous_end),
    )
