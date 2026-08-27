"""Deterministic learning Growth metrics. UI/insight/LLM 없음.

MAX_PROGRESS_SNAPSHOT_AGE_DAYS
    교사 주 1회 기록 cadence에 대한 data freshness policy다.
    psych/education threshold가 아니다.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median

from sqlalchemy.orm import joinedload

from feature_models import LearningProgressEntry
from features.growth.windows import current_window, previous_window, resolve_as_of
from features.planning.planner import build_child_learning_plan_statuses
from features.progress.service import list_active_subjects, normalize_textbook_title
from features.reading.access import get_child, model_named

MAX_PROGRESS_SNAPSHOT_AGE_DAYS = 21

STATUS_OK = 'ok'
STATUS_NO_SNAPSHOT = 'no_snapshot'
STATUS_NO_BASELINE = 'no_baseline'
STATUS_CROSS_BOOK = 'cross_book'
STATUS_STALE_BASELINE = 'stale_baseline'
STATUS_STALE_ENDPOINT = 'stale_endpoint'
STATUS_STALE_TARGET = 'stale_target'
STATUS_NO_PEERS = 'no_peers'
STATUS_INSUFFICIENT = 'insufficient'
STATUS_BOOK_CHANGED = 'book_changed'
OBSERVED_STUDY_DAYS_SOURCE = 'daily_points.date'


def snapshot_age_days(recorded_on, reference):
    if recorded_on is None or reference is None:
        return None
    return (reference - recorded_on).days


def is_stale_snapshot(recorded_on, reference, *, max_age_days=MAX_PROGRESS_SNAPSHOT_AGE_DAYS):
    age = snapshot_age_days(recorded_on, reference)
    if age is None:
        return True
    return age > max_age_days


def learning_metrics(child_id, as_of=None, window_days=30, *, points_payload=None):
    """page advance / peer / observed study days / planner facts. DB write 없음."""
    as_of = resolve_as_of(as_of)
    current = current_window(as_of, window_days)
    previous = previous_window(as_of, window_days)
    child = get_child(child_id)
    points = points_payload if points_payload is not None else _points_payload(
        child_id, as_of=as_of, window_days=window_days,
    )
    entries = _load_child_progress(child_id)
    by_subject = defaultdict(list)
    for entry in entries:
        by_subject[entry.learning_subject_id].append(entry)

    subjects = list_active_subjects()
    peer_pages_by_subject = _peer_latest_pages(
        child=child,
        subjects=subjects,
        as_of=as_of,
    )
    plan_by_key = _plan_by_subject_key(child, as_of)

    subject_payloads = {}
    for subject in subjects:
        subject_entries = by_subject.get(subject.id, [])
        latest = _latest_on_or_before(subject_entries, as_of)
        current_advance = _page_advance(subject_entries, current, as_of)
        previous_advance = _page_advance(subject_entries, previous, as_of)
        subject_payloads[subject.key] = {
            'subject_key': subject.key,
            'subject_name': subject.name,
            'current_snapshot': _latest_snapshot_payload(latest, as_of),
            'page_advance': _page_advance_pair(current_advance, previous_advance),
            'peer': _peer_payload(latest, as_of, peer_pages_by_subject.get(subject.id, ())),
            'plan': plan_by_key.get(subject.key) or _empty_plan(),
        }

    return {
        'as_of': as_of,
        'window_days': window_days,
        'current_window': current,
        'previous_window': previous,
        'max_snapshot_age_days': MAX_PROGRESS_SNAPSHOT_AGE_DAYS,
        'observed_study_days': _observed_study_days(points),
        'subjects': subject_payloads,
    }


def _points_payload(child_id, as_of, window_days):
    from features.growth.metrics import points_metrics
    return points_metrics(child_id, as_of=as_of, window_days=window_days)


def _load_child_progress(child_id):
    return (
        LearningProgressEntry.query
        .options(joinedload(LearningProgressEntry.subject))
        .filter_by(child_id=child_id)
        .all()
    )


def _latest_on_or_before(entries, bound):
    visible = [entry for entry in entries if entry.recorded_on is not None and entry.recorded_on <= bound]
    if not visible:
        return None
    return max(visible, key=lambda entry: (entry.recorded_on, entry.id))


def _entry_title(entry):
    return normalize_textbook_title(entry.textbook_title)


def _entry_ref(entry, reference):
    if entry is None:
        return None
    return {
        'recorded_on': entry.recorded_on,
        'page': entry.page,
        'textbook_title': _entry_title(entry),
        'age_days': snapshot_age_days(entry.recorded_on, reference),
    }


def _latest_snapshot_payload(entry, as_of):
    if entry is None:
        return {
            'textbook_title': None,
            'page': None,
            'recorded_on': None,
            'age_days': None,
            'stale': None,
            'available': False,
        }
    age = snapshot_age_days(entry.recorded_on, as_of)
    return {
        'textbook_title': _entry_title(entry),
        'page': entry.page,
        'recorded_on': entry.recorded_on,
        'age_days': age,
        'stale': is_stale_snapshot(entry.recorded_on, as_of),
        'available': True,
    }


def _page_advance(entries, window, as_of):
    endpoint_bound = window['end'] if window['end'] <= as_of else as_of
    endpoint = _latest_on_or_before(entries, endpoint_bound)
    payload = {
        'value': None,
        'available': False,
        'comparable': False,
        'status': STATUS_NO_SNAPSHOT,
        'reason': STATUS_NO_SNAPSHOT,
        'textbook_title': None,
        'baseline': None,
        'endpoint': None,
        'window': {'start': window['start'], 'end': window['end']},
    }
    if endpoint is None:
        return payload

    payload['endpoint'] = _entry_ref(endpoint, window['end'])
    payload['textbook_title'] = _entry_title(endpoint)
    if is_stale_snapshot(endpoint.recorded_on, window['end']):
        payload['status'] = STATUS_STALE_ENDPOINT
        payload['reason'] = STATUS_STALE_ENDPOINT
        return payload

    same_title = _entry_title(endpoint)
    baseline_candidates = [
        entry for entry in entries
        if entry.recorded_on is not None
        and entry.recorded_on < window['start']
        and entry.recorded_on <= as_of
        and _entry_title(entry) == same_title
    ]
    other_title_before = [
        entry for entry in entries
        if entry.recorded_on is not None
        and entry.recorded_on < window['start']
        and entry.recorded_on <= as_of
        and _entry_title(entry) != same_title
    ]
    if not baseline_candidates:
        if other_title_before:
            latest_other = max(other_title_before, key=lambda entry: (entry.recorded_on, entry.id))
            payload['baseline'] = _entry_ref(latest_other, window['start'])
            payload['status'] = STATUS_CROSS_BOOK
            payload['reason'] = STATUS_CROSS_BOOK
            return payload
        payload['status'] = STATUS_NO_BASELINE
        payload['reason'] = STATUS_NO_BASELINE
        return payload

    baseline = max(baseline_candidates, key=lambda entry: (entry.recorded_on, entry.id))
    payload['baseline'] = _entry_ref(baseline, window['start'])
    if is_stale_snapshot(baseline.recorded_on, window['start']):
        payload['status'] = STATUS_STALE_BASELINE
        payload['reason'] = STATUS_STALE_BASELINE
        return payload

    value = endpoint.page - baseline.page
    payload['value'] = value
    payload['available'] = True
    payload['comparable'] = True
    payload['status'] = STATUS_OK
    payload['reason'] = STATUS_OK
    return payload


def _page_advance_pair(current_advance, previous_advance):
    trend_status = STATUS_INSUFFICIENT
    trend_comparable = False
    delta = None
    if current_advance['available'] and previous_advance['available']:
        if current_advance['textbook_title'] == previous_advance['textbook_title']:
            delta = current_advance['value'] - previous_advance['value']
            trend_comparable = True
            trend_status = STATUS_OK
        else:
            trend_status = STATUS_BOOK_CHANGED
    return {
        'current': current_advance,
        'previous': previous_advance,
        'delta': delta,
        'comparable': trend_comparable,
        'status': trend_status,
        'reason': trend_status,
    }


def _peer_latest_pages(*, child, subjects, as_of):
    result = {subject.id: [] for subject in subjects}
    if child is None or not subjects:
        return result
    Child = model_named('Child')
    peers = (
        Child.query
        .filter(Child.grade == child.grade)
        .filter(Child.include_in_stats.is_(True))
        .filter(Child.id != child.id)
        .all()
    )
    peer_ids = [row.id for row in peers]
    if not peer_ids:
        return result
    subject_ids = [subject.id for subject in subjects]
    rows = (
        LearningProgressEntry.query
        .filter(LearningProgressEntry.child_id.in_(peer_ids))
        .filter(LearningProgressEntry.learning_subject_id.in_(subject_ids))
        .filter(LearningProgressEntry.recorded_on <= as_of)
        .all()
    )
    grouped = defaultdict(list)
    for entry in rows:
        grouped[(entry.child_id, entry.learning_subject_id)].append(entry)
    for subject in subjects:
        pages = []
        for peer_id in peer_ids:
            latest = _latest_on_or_before(grouped.get((peer_id, subject.id), ()), as_of)
            if latest is None:
                continue
            if is_stale_snapshot(latest.recorded_on, as_of):
                continue
            pages.append((_entry_title(latest), latest.page, latest.recorded_on, peer_id))
        result[subject.id] = pages
    return result


def _peer_payload(target_latest, as_of, peer_rows):
    if target_latest is None:
        return {
            'textbook_title': None,
            'current_page': None,
            'current_snapshot_date': None,
            'peer_median': None,
            'peer_n': 0,
            'gap': None,
            'available': False,
            'comparable': False,
            'status': STATUS_NO_SNAPSHOT,
            'reason': STATUS_NO_SNAPSHOT,
        }
    title = _entry_title(target_latest)
    payload = {
        'textbook_title': title,
        'current_page': target_latest.page,
        'current_snapshot_date': target_latest.recorded_on,
        'peer_median': None,
        'peer_n': 0,
        'gap': None,
        'available': False,
        'comparable': False,
        'status': STATUS_OK,
        'reason': STATUS_OK,
    }
    if is_stale_snapshot(target_latest.recorded_on, as_of):
        payload['status'] = STATUS_STALE_TARGET
        payload['reason'] = STATUS_STALE_TARGET
        return payload

    cohort = [page for peer_title, page, _recorded_on, _peer_id in peer_rows if peer_title == title]
    payload['peer_n'] = len(cohort)
    if not cohort:
        payload['status'] = STATUS_NO_PEERS
        payload['reason'] = STATUS_NO_PEERS
        return payload
    peer_median = median(cohort)
    payload['peer_median'] = peer_median
    payload['gap'] = target_latest.page - peer_median
    payload['available'] = True
    payload['comparable'] = True
    return payload


def _plan_by_subject_key(child, as_of):
    if child is None:
        return {}
    rows = build_child_learning_plan_statuses(child, as_of=as_of)
    return {row.subject_key: _plan_payload(row) for row in rows if row.subject_key}


def _plan_payload(row):
    return {
        'status': row.status,
        'current_page': row.current_page,
        'start_page': row.start_page,
        'end_page': row.end_page,
        'plan_id': row.plan_id,
        'plan_start_date': row.plan_start_date,
        'target_completion_date': row.target_completion_date,
        'textbook_title': row.textbook_title,
        'snapshot_date': row.snapshot_date,
        'workload_kind': row.workload_kind,
        'remaining_workload': row.remaining_workload,
        'nominal_remaining_pages': row.nominal_remaining_pages,
        'remaining_planned_study_days': row.remaining_planned_study_days,
        'required_per_planned_day': row.required_per_planned_day,
        'weekday_source': row.weekday_source,
        'effective_weekdays': list(row.effective_weekdays) if row.effective_weekdays is not None else None,
    }


def _empty_plan():
    return {
        'status': STATUS_NO_SNAPSHOT,
        'current_page': None,
        'start_page': None,
        'end_page': None,
        'plan_id': None,
        'plan_start_date': None,
        'target_completion_date': None,
        'textbook_title': None,
        'snapshot_date': None,
        'workload_kind': None,
        'remaining_workload': None,
        'nominal_remaining_pages': None,
        'remaining_planned_study_days': None,
        'required_per_planned_day': None,
        'weekday_source': None,
        'effective_weekdays': None,
    }


def _observed_study_days(points_payload):
    current = (points_payload or {}).get('current') or {}
    previous = (points_payload or {}).get('previous') or {}
    return {
        'current': current.get('point_activity_days'),
        'previous': previous.get('point_activity_days'),
        'source': OBSERVED_STUDY_DAYS_SOURCE,
        'proxy': 'point_activity_days',
        'attendance': False,
    }
