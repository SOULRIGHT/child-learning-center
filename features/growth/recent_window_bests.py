"""Recent 3-window self-comparison facts. UI/insight/LLM/threshold 없음.

recent-window best
    최근 고정 30일 × 3개 비중첩 구간 안에서
    current가 두 과거 구간을 엄격히 초과하는가.
    lifetime personal best가 아니다.
"""
from __future__ import annotations

from collections import defaultdict

from features.growth.learning_metrics import page_advance_for_window
from features.growth.windows import (
    coverage_comparable,
    recent_fixed_windows,
    resolve_as_of,
)
from features.progress.service import list_active_subjects

WINDOW_COUNT = 3
STATUS_OK = 'ok'
STATUS_INSUFFICIENT_HISTORY = 'insufficient_history'
STATUS_BOOK_CHANGED = 'book_changed'

SOURCE_READING_DAYS = 'reading_day.date'
SOURCE_COMPLETIONS = 'child_reading.completed_on'
SOURCE_POINTS = 'daily_points.date'
SOURCE_PAGE_ADVANCE = 'learning_progress_entry.recorded_on'


def recent_window_bests(
    child_id,
    as_of=None,
    window_days=30,
    *,
    reading_payload=None,
    points_payload=None,
    learning_payload=None,
):
    """reading days / completions / points / page advance의 3구간 비교. DB write 없음."""
    as_of = resolve_as_of(as_of)
    windows = recent_fixed_windows(as_of, window_days, count=WINDOW_COUNT)
    current, previous_1, previous_2 = windows
    lookback_days = window_days * WINDOW_COUNT
    reading_days, reading_completions = _reading_bests(
        child_id, as_of, windows, reading_payload=reading_payload,
    )
    return {
        'as_of': as_of,
        'window_days': window_days,
        'window_count': WINDOW_COUNT,
        'lookback_days': lookback_days,
        'current_window': current,
        'previous_1_window': previous_1,
        'previous_2_window': previous_2,
        'reading_days': reading_days,
        'reading_completions': reading_completions,
        'points': _points_best(
            child_id, as_of, windows, points_payload=points_payload,
        ),
        'learning': _learning_bests(
            child_id, as_of, windows, learning_payload=learning_payload,
        ),
    }


def _reading_bests(child_id, as_of, windows, *, reading_payload):
    from features.growth.metrics import (
        _days_as_of,
        _load_readings_and_days,
        _reading_coverage,
        _reading_slice,
    )
    readings, days = _load_readings_and_days(child_id)
    visible_days, days_by_reading = _days_as_of(days, as_of)
    coverage = (reading_payload or {}).get('available_from') or _reading_coverage(
        readings, days, as_of,
    )
    slices = [
        _reading_slice(readings, visible_days, days_by_reading, window, as_of)
        for window in windows
    ]
    days_ok = coverage_comparable(coverage.get('reading_days'), windows[2])
    completed_ok = coverage_comparable(coverage.get('completed'), windows[2])
    reading_days = _strict_best([
        _window_fact(window, sliced['reading_days'], available=days_ok)
        for window, sliced in zip(windows, slices)
    ])
    reading_days['source'] = SOURCE_READING_DAYS
    completions = _strict_best([
        _window_fact(window, sliced['completed_count'], available=completed_ok)
        for window, sliced in zip(windows, slices)
    ])
    completions['source'] = SOURCE_COMPLETIONS
    return reading_days, completions


def _points_best(child_id, as_of, windows, *, points_payload):
    from features.growth.metrics import (
        _canonical_daily_point_records,
        _min_date,
        _points_slice,
        _records_as_of,
    )
    records_as_of = _records_as_of(_canonical_daily_point_records(child_id), as_of)
    available_from = ((points_payload or {}).get('available_from') or {}).get('points')
    if available_from is None:
        available_from = _min_date(row.get('date') for row in records_as_of)
    oldest_ok = coverage_comparable(available_from, windows[2])
    facts = []
    for window in windows:
        sliced = _points_slice(records_as_of, window)
        facts.append(_window_fact(window, sliced['period_points'], available=oldest_ok))
    result = _strict_best(facts)
    result['source'] = SOURCE_POINTS
    return result


def _learning_bests(child_id, as_of, windows, *, learning_payload):
    from features.growth.learning_metrics import _load_child_progress
    entries = _load_child_progress(child_id)
    by_subject = defaultdict(list)
    for entry in entries:
        by_subject[entry.learning_subject_id].append(entry)
    subjects = list_active_subjects()
    payload_subjects = (learning_payload or {}).get('subjects') or {}
    result = {}
    for subject in subjects:
        subject_entries = by_subject.get(subject.id, [])
        cached = payload_subjects.get(subject.key) or {}
        cached_pair = cached.get('page_advance') or {}
        advances = []
        if cached_pair.get('current') is not None and cached_pair.get('previous') is not None:
            advances.append(cached_pair['current'])
            advances.append(cached_pair['previous'])
            advances.append(page_advance_for_window(subject_entries, windows[2], as_of))
        else:
            advances = [
                page_advance_for_window(subject_entries, window, as_of)
                for window in windows
            ]
        facts = [
            _learning_window_fact(window, advance)
            for window, advance in zip(windows, advances)
        ]
        titles = [fact.get('textbook_title') for fact in facts]
        all_available = all(fact['available'] for fact in facts)
        extra = {'source': SOURCE_PAGE_ADVANCE, 'subject_key': subject.key}
        if all_available and len(set(titles)) != 1:
            result[subject.key] = _incomparable(
                facts, status=STATUS_BOOK_CHANGED, extra=extra,
            )
            continue
        compared = _strict_best(facts)
        compared.update(extra)
        result[subject.key] = compared
    return result


def _learning_window_fact(window, advance):
    available = advance.get('available') is True
    return _window_fact(
        window,
        advance.get('value'),
        available=available,
        extra={
            'textbook_title': advance.get('textbook_title'),
            'page_advance_status': advance.get('status'),
        },
    )


def _window_fact(window, value, *, available, extra=None):
    payload = {
        'start': window['start'],
        'end': window['end'],
        'value': value if available else None,
        'available': available,
        'comparable': available,
    }
    if extra:
        payload.update(extra)
    return payload


def _strict_best(facts):
    current_fact, previous_1, previous_2 = facts
    result = {
        'current': current_fact,
        'previous_1': previous_1,
        'previous_2': previous_2,
        'historical_best': None,
        'historical_best_window': None,
        'margin': None,
        'is_recent_window_best': None,
        'status': STATUS_INSUFFICIENT_HISTORY,
    }
    if not all(fact['available'] and fact['value'] is not None for fact in facts):
        return result
    historical_best, best_window = _historical_best(previous_1, previous_2)
    current_value = current_fact['value']
    result['historical_best'] = historical_best
    result['historical_best_window'] = best_window
    result['margin'] = current_value - historical_best
    result['is_recent_window_best'] = current_value > historical_best
    result['status'] = STATUS_OK
    return result


def _historical_best(previous_1, previous_2):
    """동률이면 더 최근 구간 previous_1."""
    if previous_1['value'] >= previous_2['value']:
        return previous_1['value'], {
            'start': previous_1['start'],
            'end': previous_1['end'],
        }
    return previous_2['value'], {
        'start': previous_2['start'],
        'end': previous_2['end'],
    }


def _incomparable(facts, *, status, extra=None):
    current_fact, previous_1, previous_2 = facts
    payload = {
        'current': current_fact,
        'previous_1': previous_1,
        'previous_2': previous_2,
        'historical_best': None,
        'historical_best_window': None,
        'margin': None,
        'is_recent_window_best': None,
        'status': status,
    }
    if extra:
        payload.update(extra)
    return payload
