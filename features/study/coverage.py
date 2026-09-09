"""관측 기반 unique page coverage / 완료예상. DB write 없음.

정본: LearningStudySession + LearningWorkbookPlan + permanent exclusions.
진도 스냅샷과 planner leftover, 추정 제외 비율은 쓰지 않는다.
"""
from __future__ import annotations

import math
import statistics
from datetime import date, datetime, timedelta

from feature_models import LearningStudySession, LearningWorkbookPlan
from features.dates import kst_today
from features.planning.exclusions import count_pages_in_ranges, merge_page_ranges
from features.planning.timeline import (
    list_timeline_plans,
    resolve_canonical_workbook_plan,
)
from features.reading.access import get_child
from features.study.assignment import (
    assigned_page_count,
    permanently_excluded_ranges,
    physical_page_bounds,
)
from features.study.constants import STUDY_STATUS_STUDIED
from features.study.holidays import korean_public_holidays, year_system_holidays_initialized
from features.study.schedule import effective_weekdays, study_calendar_allows
from features.study.subjects import list_study_subjects

FORECAST_RECENT_N = 8
FORECAST_HORIZON_DAYS = 366 * 3
SLIGHT_DELAY_DAYS = 14

STATUS_NO_PLAN = 'no_plan'
STATUS_NO_STUDIED_SESSIONS = 'no_studied_sessions'
STATUS_EXCLUSIONS_UNCONFIRMED = 'exclusions_unconfirmed'
STATUS_EXACT = 'exact'
STATUS_INSUFFICIENT_SESSIONS = 'insufficient_sessions'
STATUS_UNSTABLE_PACE = 'unstable_or_non_positive_pace'
STATUS_ALREADY_COMPLETE = 'already_observed_complete'
STATUS_PLAN_SWITCH = 'plan_switch_before_completion'
STATUS_INSUFFICIENT_FUTURE = 'insufficient_future_schedule'
STATUS_NO_FUTURE_STUDY_DAYS = 'no_future_study_days'

VS_UNAVAILABLE = 'unavailable'
VS_ALREADY_COMPLETE = 'already_observed_complete'
VS_TARGET_PASSED = 'target_passed_not_observed_complete'
VS_OVERLAPS = 'overlaps_target'
VS_ON_OR_AHEAD = 'on_or_ahead'
VS_SLIGHT_DELAY = 'slight_delay'
VS_DELAY_2W = 'delay_2w_plus'


def _as_date(raw):
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    return date.fromisoformat(str(raw).strip()[:10])


def _load_plan(plan):
    if plan is None:
        return None
    if isinstance(plan, LearningWorkbookPlan):
        return plan
    return LearningWorkbookPlan.query.get(int(plan))


def _clip_range(start, end, lo, hi):
    clipped_start = max(int(start), int(lo))
    clipped_end = min(int(end), int(hi))
    if clipped_start > clipped_end:
        return None
    return {'start': clipped_start, 'end': clipped_end}


def _subtract_one(piece, exclusions):
    fragments = [piece]
    for excluded in exclusions:
        nxt = []
        for frag in fragments:
            if excluded['end'] < frag['start'] or excluded['start'] > frag['end']:
                nxt.append(frag)
                continue
            left_end = excluded['start'] - 1
            right_start = excluded['end'] + 1
            if frag['start'] <= left_end:
                nxt.append({'start': frag['start'], 'end': min(frag['end'], left_end)})
            if right_start <= frag['end']:
                nxt.append({'start': max(frag['start'], right_start), 'end': frag['end']})
        fragments = nxt
    return fragments


def _subtract_ranges(ranges, exclusions):
    if not exclusions:
        return merge_page_ranges(ranges)
    remaining = []
    merged_exclusions = merge_page_ranges(exclusions)
    for rng in merge_page_ranges(ranges):
        remaining.extend(_subtract_one(rng, merged_exclusions))
    return merge_page_ranges(remaining)


def _session_sort_key(row):
    created = row.created_at or datetime.min
    return (row.study_date, created, row.id or 0)


def _included_studied_sessions(child_id, plan_id, as_of):
    rows = (
        LearningStudySession.query
        .filter_by(
            child_id=int(child_id),
            learning_workbook_plan_id=int(plan_id),
            study_status=STUDY_STATUS_STUDIED,
        )
        .filter(LearningStudySession.study_date <= as_of)
        .all()
    )
    included = []
    for row in rows:
        if row.learning_workbook_plan_id is None:
            continue
        if row.start_page is None or row.end_page is None:
            continue
        included.append(row)
    included.sort(key=_session_sort_key)
    return included


def _physical_ranges(sessions, bounds):
    lo, hi = bounds
    clipped = []
    for row in sessions:
        piece = _clip_range(row.start_page, row.end_page, lo, hi)
        if piece is not None:
            clipped.append(piece)
    return merge_page_ranges(clipped)


def _session_assigned_ranges(row, bounds, exclusions):
    lo, hi = bounds
    clipped = _clip_range(row.start_page, row.end_page, lo, hi)
    if clipped is None:
        return []
    return _subtract_ranges([clipped], exclusions)


def unique_page_coverage(child_id, plan, as_of=None):
    """관측 unique coverage. snapshot page / planner leftover를 쓰지 않는다."""
    as_of = kst_today() if as_of is None else _as_date(as_of)
    plan = _load_plan(plan)
    empty = {
        'plan_id': None if plan is None else plan.id,
        'observed_ranges': [],
        'observed_page_count': None,
        'assigned_covered_ranges': None,
        'assigned_covered_page_count': None,
        'assigned_denominator': None,
        'coverage_ratio': None,
        'latest_observed_end_page': None,
        'studied_session_count': 0,
        'available': False,
        'status': STATUS_NO_PLAN if plan is None else STATUS_NO_STUDIED_SESSIONS,
        'exclusions_confirmed': False,
    }
    if plan is None:
        return empty
    bounds = physical_page_bounds(plan)
    if bounds is None:
        return empty
    sessions = _included_studied_sessions(child_id, plan.id, as_of)
    exclusions = permanently_excluded_ranges(plan)
    confirmed = exclusions is not None
    empty['exclusions_confirmed'] = confirmed
    empty['assigned_denominator'] = assigned_page_count(plan) if confirmed else None
    if not sessions:
        return empty

    observed_ranges = _physical_ranges(sessions, bounds)
    latest = None
    if observed_ranges:
        latest = max(row['end'] for row in observed_ranges)
    assigned_ranges = None
    assigned_count = None
    ratio = None
    status = STATUS_EXCLUSIONS_UNCONFIRMED
    available = False
    if confirmed:
        assigned_ranges = _subtract_ranges(observed_ranges, exclusions)
        assigned_count = count_pages_in_ranges(assigned_ranges)
        denom = empty['assigned_denominator']
        if denom:
            ratio = assigned_count / denom
        elif denom == 0:
            ratio = None
        status = STATUS_EXACT
        available = True
    return {
        'plan_id': plan.id,
        'observed_ranges': observed_ranges,
        'observed_page_count': count_pages_in_ranges(observed_ranges),
        'assigned_covered_ranges': assigned_ranges,
        'assigned_covered_page_count': assigned_count,
        'assigned_denominator': empty['assigned_denominator'],
        'coverage_ratio': ratio,
        'latest_observed_end_page': latest,
        'studied_session_count': len(sessions),
        'available': available,
        'status': status,
        'exclusions_confirmed': confirmed,
    }


def progress_for_plan(child_id, plan, as_of=None):
    as_of = kst_today() if as_of is None else _as_date(as_of)
    plan = _load_plan(plan)
    coverage = unique_page_coverage(child_id, plan, as_of=as_of)
    if plan is None:
        return {
            **coverage,
            'plan': None,
            'observed_complete': None,
            'remaining_assigned_pages': None,
        }
    remaining = None
    observed_complete = None
    denom = coverage['assigned_denominator']
    covered = coverage['assigned_covered_page_count']
    if (
        coverage['exclusions_confirmed']
        and denom is not None
        and covered is not None
        and coverage['studied_session_count']
    ):
        remaining = denom - covered
        observed_complete = remaining == 0
    return {
        **coverage,
        'plan': {
            'id': plan.id,
            'textbook_title': plan.textbook_title,
            'learning_subject_id': plan.learning_subject_id,
            'grade': plan.grade,
            'start_page': plan.start_page,
            'end_page': plan.end_page,
            'start_date': plan.start_date,
            'target_completion_date': plan.target_completion_date,
        },
        'observed_complete': observed_complete,
        'remaining_assigned_pages': remaining,
        'as_of': as_of,
    }


def _valid_forecast_sessions(child_id, plan, as_of):
    exclusions = permanently_excluded_ranges(plan)
    if exclusions is None:
        return None
    bounds = physical_page_bounds(plan)
    if bounds is None:
        return []
    sessions = _included_studied_sessions(child_id, plan.id, as_of)
    valid = []
    for row in sessions:
        assigned = _session_assigned_ranges(row, bounds, exclusions)
        if count_pages_in_ranges(assigned) < 1:
            continue
        valid.append({'row': row, 'assigned_ranges': assigned})
    return valid


def _new_pages_series(valid_sessions):
    prior = []
    series = []
    for item in valid_sessions:
        prior_count = count_pages_in_ranges(prior)
        combined = merge_page_ranges(list(prior) + list(item['assigned_ranges']))
        new_pages = count_pages_in_ranges(combined) - prior_count
        series.append({
            'session_id': item['row'].id,
            'study_date': item['row'].study_date,
            'new_pages': new_pages,
        })
        prior = combined
    return series


def _pace_stats(new_pages):
    samples = [int(value) for value in new_pages]
    quartiles = statistics.quantiles(samples, n=4, method='inclusive')
    return {
        'median_new_pages': statistics.median(samples),
        'p25_new_pages': quartiles[0],
        'p75_new_pages': quartiles[2],
        'sample_new_pages': samples,
    }


def _next_plan_start(plan):
    later = [
        row.start_date
        for row in list_timeline_plans(plan.grade, plan.learning_subject_id)
        if row.start_date > plan.start_date
    ]
    return min(later) if later else None


def _unseeded_year_holidays(year, cache):
    """시드되지 않은 연도만 provider를 read-only fallback으로 쓴다. DB write 없음.

    시드된 연도는 CenterNonStudyDay만 정본이다. 학습일로 복구한 날짜를 다시 제외하지 않는다.
    """
    if year in cache:
        return cache[year]
    if year_system_holidays_initialized(year):
        cache[year] = None
        return None
    try:
        cache[year] = frozenset(korean_public_holidays(year))
    except Exception:
        cache[year] = False
    return cache[year]


def _is_unseeded_legal_holiday(day, cache):
    holidays = _unseeded_year_holidays(day.year, cache)
    if holidays is None:
        return False
    if holidays is False:
        return True
    return day in holidays


def _collect_future_study_days(child, plan, as_of, needed):
    if not effective_weekdays(child.id, plan.learning_subject_id):
        return [], False
    day = as_of + timedelta(days=1)
    horizon = as_of + timedelta(days=FORECAST_HORIZON_DAYS)
    next_start = _next_plan_start(plan)
    collected = []
    saw_switch = False
    holiday_cache = {}
    while day <= horizon and len(collected) < needed:
        if next_start is not None and day >= next_start:
            saw_switch = True
            break
        canonical = resolve_canonical_workbook_plan(child, plan.learning_subject_id, day)
        if canonical is None:
            day += timedelta(days=1)
            continue
        if int(canonical.id) != int(plan.id):
            saw_switch = True
            break
        if (
            study_calendar_allows(child.id, plan.learning_subject_id, day)
            and not _is_unseeded_legal_holiday(day, holiday_cache)
        ):
            collected.append(day)
        day += timedelta(days=1)
    return collected, saw_switch


def _unavailable_forecast(*, reason, progress=None, extra=None):
    payload = {
        'available': False,
        'reason': reason,
        'earliest_date': None,
        'latest_date': None,
        'median_date': None,
        'earliest_sessions': None,
        'latest_sessions': None,
        'median_sessions': None,
        'median_new_pages': None,
        'p25_new_pages': None,
        'p75_new_pages': None,
        'remaining_assigned_pages': None if progress is None else progress.get('remaining_assigned_pages'),
        'observed_complete': None if progress is None else progress.get('observed_complete'),
        'vs_target': VS_UNAVAILABLE,
    }
    if extra:
        payload.update(extra)
    return payload


def compare_to_target(*, as_of, target, observed_complete, forecast_available, earliest, latest):
    if target is None:
        return VS_UNAVAILABLE
    target = _as_date(target)
    as_of = _as_date(as_of)
    if observed_complete is True:
        return VS_ALREADY_COMPLETE
    if as_of > target and observed_complete is not True:
        return VS_TARGET_PASSED
    if not forecast_available or earliest is None or latest is None:
        return VS_UNAVAILABLE
    if earliest <= target <= latest:
        return VS_OVERLAPS
    if latest <= target:
        return VS_ON_OR_AHEAD
    delay = (earliest - target).days
    if delay >= SLIGHT_DELAY_DAYS:
        return VS_DELAY_2W
    if delay > 0:
        return VS_SLIGHT_DELAY
    return VS_UNAVAILABLE


def completion_forecast(child_id, plan, as_of=None):
    as_of = kst_today() if as_of is None else _as_date(as_of)
    plan = _load_plan(plan)
    progress = progress_for_plan(child_id, plan, as_of=as_of)
    if plan is None:
        return _unavailable_forecast(reason=STATUS_NO_PLAN, progress=progress)
    if not progress['exclusions_confirmed']:
        forecast = _unavailable_forecast(reason=STATUS_EXCLUSIONS_UNCONFIRMED, progress=progress)
        forecast['vs_target'] = compare_to_target(
            as_of=as_of,
            target=plan.target_completion_date,
            observed_complete=progress['observed_complete'],
            forecast_available=False,
            earliest=None,
            latest=None,
        )
        return forecast
    if not progress['studied_session_count']:
        forecast = _unavailable_forecast(reason=STATUS_NO_STUDIED_SESSIONS, progress=progress)
        forecast['vs_target'] = compare_to_target(
            as_of=as_of,
            target=plan.target_completion_date,
            observed_complete=progress['observed_complete'],
            forecast_available=False,
            earliest=None,
            latest=None,
        )
        return forecast
    if progress['observed_complete'] is True:
        forecast = _unavailable_forecast(
            reason=STATUS_ALREADY_COMPLETE,
            progress=progress,
            extra={'remaining_assigned_pages': 0, 'observed_complete': True},
        )
        forecast['vs_target'] = compare_to_target(
            as_of=as_of,
            target=plan.target_completion_date,
            observed_complete=True,
            forecast_available=False,
            earliest=None,
            latest=None,
        )
        return forecast

    valid = _valid_forecast_sessions(child_id, plan, as_of) or []
    if len(valid) < FORECAST_RECENT_N:
        forecast = _unavailable_forecast(reason=STATUS_INSUFFICIENT_SESSIONS, progress=progress)
        forecast['vs_target'] = compare_to_target(
            as_of=as_of,
            target=plan.target_completion_date,
            observed_complete=progress['observed_complete'],
            forecast_available=False,
            earliest=None,
            latest=None,
        )
        return forecast

    series = _new_pages_series(valid)
    recent = series[-FORECAST_RECENT_N:]
    pace = _pace_stats(item['new_pages'] for item in recent)
    if (
        pace['median_new_pages'] <= 0
        or pace['p25_new_pages'] <= 0
        or pace['p75_new_pages'] <= 0
    ):
        forecast = _unavailable_forecast(
            reason=STATUS_UNSTABLE_PACE,
            progress=progress,
            extra=pace,
        )
        forecast['vs_target'] = compare_to_target(
            as_of=as_of,
            target=plan.target_completion_date,
            observed_complete=progress['observed_complete'],
            forecast_available=False,
            earliest=None,
            latest=None,
        )
        return forecast

    remaining = progress['remaining_assigned_pages']
    earliest_sessions = math.ceil(remaining / pace['p75_new_pages'])
    latest_sessions = math.ceil(remaining / pace['p25_new_pages'])
    median_sessions = math.ceil(remaining / pace['median_new_pages'])
    child = get_child(child_id)
    if child is None:
        return _unavailable_forecast(reason=STATUS_NO_PLAN, progress=progress)
    needed = max(earliest_sessions, latest_sessions, median_sessions)
    days, saw_switch = _collect_future_study_days(child, plan, as_of, needed)
    if len(days) < needed:
        if saw_switch:
            reason = STATUS_PLAN_SWITCH
        elif not days:
            reason = STATUS_NO_FUTURE_STUDY_DAYS
        else:
            reason = STATUS_INSUFFICIENT_FUTURE
        forecast = _unavailable_forecast(reason=reason, progress=progress, extra=pace)
        forecast['vs_target'] = compare_to_target(
            as_of=as_of,
            target=plan.target_completion_date,
            observed_complete=progress['observed_complete'],
            forecast_available=False,
            earliest=None,
            latest=None,
        )
        return forecast

    earliest_date = days[earliest_sessions - 1]
    latest_date = days[latest_sessions - 1]
    median_date = days[median_sessions - 1]
    vs_target = compare_to_target(
        as_of=as_of,
        target=plan.target_completion_date,
        observed_complete=progress['observed_complete'],
        forecast_available=True,
        earliest=earliest_date,
        latest=latest_date,
    )
    return {
        'available': True,
        'reason': None,
        'earliest_date': earliest_date,
        'latest_date': latest_date,
        'median_date': median_date,
        'earliest_sessions': earliest_sessions,
        'latest_sessions': latest_sessions,
        'median_sessions': median_sessions,
        'median_new_pages': pace['median_new_pages'],
        'p25_new_pages': pace['p25_new_pages'],
        'p75_new_pages': pace['p75_new_pages'],
        'sample_new_pages': pace['sample_new_pages'],
        'remaining_assigned_pages': remaining,
        'observed_complete': False,
        'vs_target': vs_target,
    }


def learning_progress_summary(child_id, as_of=None):
    """child + as_of 의 현재 canonical plan coverage/forecast 묶음."""
    as_of = kst_today() if as_of is None else _as_date(as_of)
    child = get_child(child_id)
    rows = []
    if child is None:
        return {'child_id': child_id, 'as_of': as_of, 'subjects': rows}
    for subject in list_study_subjects():
        plan = resolve_canonical_workbook_plan(child, subject.id, as_of)
        if plan is None:
            rows.append({
                'subject_id': subject.id,
                'subject_key': subject.key,
                'subject_name': subject.name,
                'available': False,
                'status': STATUS_NO_PLAN,
                'progress': None,
                'forecast': None,
                'vs_target': VS_UNAVAILABLE,
            })
            continue
        progress = progress_for_plan(child.id, plan, as_of=as_of)
        forecast = completion_forecast(child.id, plan, as_of=as_of)
        rows.append({
            'subject_id': subject.id,
            'subject_key': subject.key,
            'subject_name': subject.name,
            'available': progress['available'],
            'status': progress['status'],
            'progress': progress,
            'forecast': forecast,
            'vs_target': forecast.get('vs_target') or VS_UNAVAILABLE,
        })
    return {
        'child_id': child.id,
        'as_of': as_of,
        'subjects': rows,
    }
