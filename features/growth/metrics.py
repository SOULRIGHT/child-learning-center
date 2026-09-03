"""아동 한 명의 Growth 확정 집계. HTTP/세션/LLM에 의존하지 않는다.

available_from
    해당 metric source에서 현재 DB에 남아 있는 최초 관측 날짜.
    정책 공식 시작일, 수집 시스템 배포일, 센터 운영 시작일,
    실제 활동 시작일을 의미하지 않는다.
    comparability는 잔존 원장이 previous window 전체를 덮는지
    보는 보수적 heuristic이다. schema에 policy/epoch가 없어
    이번 Step에서는 더 정교하게 풀지 않는다.

cumulative_as_of
    Growth 분석 정본. 0은 원장이 있고 합이 0인 경우,
    None은 해당 시점 누적을 현재 잔존 원장으로 확정할 수 없는 경우.
    child_cumulative_points는 live cache일 뿐이며
    comparison/insight/historical snapshot/AI evidence에 쓰지 않는다.

paired_experience_rating
    한 ChildReading에 difficulty와 fun이 모두 있는 completed 표본.
    개별 difficulty_rating / fun_rating 평균과 다를 수 있다.
    cross insight는 이 paired family(experience_rating_pair)만 쓴다.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import joinedload

from feature_models import (
    PROGRAM_TYPE_CHALLENGE,
    PROGRAM_TYPE_GENERAL,
    PROGRAM_TYPE_RECOMMENDED,
    STATUS_ABANDONED,
    STATUS_COMPLETED,
    ChildReading,
    LearningProgressEntry,
    ReadingDay,
)
from features.dates import kst_today
from features.growth.windows import (
    coverage_comparable,
    current_window,
    date_in_window,
    on_or_before,
    previous_window,
    resolve_as_of,
)
from features.reading.access import get_child
from features.subjects import CURRENT_SUBJECTS

PROGRAM_TYPES = (
    PROGRAM_TYPE_GENERAL,
    PROGRAM_TYPE_RECOMMENDED,
    PROGRAM_TYPE_CHALLENGE,
)
SUBJECT_KEYS = tuple(CURRENT_SUBJECTS.keys())


def _min_date(values):
    dates = [value for value in values if value is not None]
    return min(dates) if dates else None


def _mean_or_none(values):
    if not values:
        return None
    return sum(values) / len(values)


def _coverage_maps(previous, available_from):
    """family별 available_from / comparable 맵.

    available_from 값은 잔존 원장의 최초 관측일이다.
    공식 epoch가 아니므로 comparable=false를 숨기지 않는다.
    """
    return {
        'available_from': available_from,
        'comparable': {
            key: coverage_comparable(value, previous)
            for key, value in available_from.items()
        },
    }


def _snapshot_meta(as_of, window_days, previous, available_from):
    payload = {
        'as_of': as_of,
        'window_days': window_days,
        'current_window': current_window(as_of, window_days),
        'previous_window': previous,
    }
    payload.update(_coverage_maps(previous, available_from))
    return payload


def _canonical_daily_point_records(child_id):
    from app import fetch_child_daily_point_records
    return fetch_child_daily_point_records(child_id)


def _records_as_of(records, as_of):
    return [row for row in records if on_or_before(row.get('date'), as_of)]


def _load_readings_and_days(child_id):
    readings = (
        ChildReading.query
        .filter_by(child_id=child_id)
        .all()
    )
    reading_ids = [reading.id for reading in readings]
    days = []
    if reading_ids:
        days = (
            ReadingDay.query
            .filter(ReadingDay.child_reading_id.in_(reading_ids))
            .all()
        )
    return readings, days


def _days_as_of(days, as_of):
    visible = [day for day in days if on_or_before(day.date, as_of)]
    days_by_reading = defaultdict(list)
    for day in visible:
        days_by_reading[day.child_reading_id].append(day)
    return visible, days_by_reading


def _reading_coverage(readings, days, as_of):
    completed = [
        reading for reading in readings
        if reading.status == STATUS_COMPLETED and on_or_before(reading.completed_on, as_of)
    ]
    abandoned = [
        reading for reading in readings
        if reading.status == STATUS_ABANDONED and on_or_before(reading.ended_on, as_of)
    ]
    return {
        'reading_days': _min_date(day.date for day in days if on_or_before(day.date, as_of)),
        'started': _min_date(
            reading.started_on for reading in readings
            if on_or_before(reading.started_on, as_of)
        ),
        'completed': _min_date(reading.completed_on for reading in completed),
        'abandoned': _min_date(reading.ended_on for reading in abandoned),
        'difficulty_rating': _min_date(
            reading.completed_on for reading in completed
            if reading.difficulty_rating is not None
        ),
        'fun_rating': _min_date(
            reading.completed_on for reading in completed
            if reading.fun_rating is not None
        ),
        'experience_rating_pair': _min_date(
            reading.completed_on for reading in completed
            if reading.difficulty_rating is not None and reading.fun_rating is not None
        ),
    }


def _rating_stats(values):
    sample = [int(value) for value in values if value is not None]
    return {
        'average': _mean_or_none(sample),
        'sample_count': len(sample),
    }


def _reading_slice(readings, days, days_by_reading, window, as_of):
    reading_dates = {
        day.date for day in days
        if on_or_before(day.date, as_of) and date_in_window(day.date, window)
    }
    recommended_ids = {
        reading.id for reading in readings
        if reading.program_type == PROGRAM_TYPE_RECOMMENDED
    }
    recommended_dates = {
        day.date for day in days
        if day.child_reading_id in recommended_ids
        and on_or_before(day.date, as_of)
        and date_in_window(day.date, window)
    }
    completed = [
        reading for reading in readings
        if reading.status == STATUS_COMPLETED
        and on_or_before(reading.completed_on, as_of)
        and date_in_window(reading.completed_on, window)
    ]
    started_count = sum(
        1 for reading in readings
        if on_or_before(reading.started_on, as_of) and date_in_window(reading.started_on, window)
    )
    abandoned_count = sum(
        1 for reading in readings
        if reading.status == STATUS_ABANDONED
        and on_or_before(reading.ended_on, as_of)
        and date_in_window(reading.ended_on, window)
    )
    completed_by_program = {key: 0 for key in PROGRAM_TYPES}
    for reading in completed:
        program = reading.program_type
        if program in completed_by_program:
            completed_by_program[program] += 1

    day_counts = [len(days_by_reading[reading.id]) for reading in completed]
    spans = []
    for reading in completed:
        if reading.started_on is None or reading.completed_on is None:
            continue
        spans.append((reading.completed_on - reading.started_on).days + 1)

    difficulty = _rating_stats(reading.difficulty_rating for reading in completed)
    fun = _rating_stats(reading.fun_rating for reading in completed)
    paired = [
        reading for reading in completed
        if reading.difficulty_rating is not None and reading.fun_rating is not None
    ]
    return {
        'reading_days': len(reading_dates),
        'recommended_reading_days': len(recommended_dates),
        'started_count': started_count,
        'completed_count': len(completed),
        'abandoned_count': abandoned_count,
        'completed_by_program': completed_by_program,
        'days_per_completed_book': {
            'average': _mean_or_none(day_counts),
            'sample_count': len(day_counts),
        },
        'span_per_completed_book': {
            'average': _mean_or_none(spans),
            'sample_count': len(spans),
            'inclusive': True,
        },
        'difficulty_rating': difficulty,
        'fun_rating': fun,
        'paired_experience_rating': {
            'sample_count': len(paired),
            'difficulty_average': _mean_or_none(
                [int(reading.difficulty_rating) for reading in paired]
            ),
            'fun_average': _mean_or_none(
                [int(reading.fun_rating) for reading in paired]
            ),
        },
    }


def reading_metrics(child_id, as_of=None, window_days=30):
    as_of = resolve_as_of(as_of)
    previous = previous_window(as_of, window_days)
    readings, days = _load_readings_and_days(child_id)
    visible_days, days_by_reading = _days_as_of(days, as_of)
    payload = _snapshot_meta(
        as_of,
        window_days,
        previous,
        _reading_coverage(readings, days, as_of),
    )
    payload['current'] = _reading_slice(
        readings, visible_days, days_by_reading, payload['current_window'], as_of,
    )
    payload['previous'] = _reading_slice(
        readings, visible_days, days_by_reading, previous, as_of,
    )
    return payload


def _load_progress_entries(child_id):
    return (
        LearningProgressEntry.query
        .options(joinedload(LearningProgressEntry.subject))
        .filter_by(child_id=child_id)
        .all()
    )


def _subject_key(entry):
    subject = entry.subject
    return subject.key if subject is not None else None


def _progress_slice(entries, window, as_of):
    in_window = [
        entry for entry in entries
        if on_or_before(entry.recorded_on, as_of) and date_in_window(entry.recorded_on, window)
    ]
    by_subject = defaultdict(int)
    for entry in in_window:
        key = _subject_key(entry)
        if key:
            by_subject[key] += 1
    return {
        'progress_entry_count': len(in_window),
        'progress_entry_count_by_subject': dict(by_subject),
    }


def _latest_snapshot_as_of(entries, as_of):
    latest = {}
    ordered = sorted(
        (entry for entry in entries if on_or_before(entry.recorded_on, as_of)),
        key=lambda entry: (entry.recorded_on, entry.id),
    )
    for entry in ordered:
        key = _subject_key(entry)
        if not key:
            continue
        latest[key] = {
            'textbook_title': entry.textbook_title,
            'page': entry.page,
            'recorded_on': entry.recorded_on,
        }
    return latest


def progress_metrics(child_id, as_of=None, window_days=30):
    as_of = resolve_as_of(as_of)
    previous = previous_window(as_of, window_days)
    entries = _load_progress_entries(child_id)
    payload = _snapshot_meta(
        as_of,
        window_days,
        previous,
        {
            'progress': _min_date(
                entry.recorded_on for entry in entries
                if on_or_before(entry.recorded_on, as_of)
            ),
        },
    )
    payload['current'] = _progress_slice(entries, payload['current_window'], as_of)
    payload['previous'] = _progress_slice(entries, previous, as_of)
    payload['latest_snapshot_by_subject'] = _latest_snapshot_as_of(entries, as_of)
    return payload


def _points_slice(records, window):
    in_window = [row for row in records if date_in_window(row.get('date'), window)]
    subject_active_days = {}
    for key in SUBJECT_KEYS:
        subject_active_days[key] = sum(
            1 for row in in_window
            if (row.get('subjects') or {}).get(key, 0) > 0
        )
    return {
        'period_points': sum(row.get('total_points') or 0 for row in in_window),
        'point_activity_days': len(in_window),
        'subject_active_days': subject_active_days,
        'manual_points_sum': sum(row.get('manual_points') or 0 for row in in_window),
    }


def _cumulative_as_of(records_as_of, child_id, as_of):
    """as_of 시점 Growth 누적. Optional[int].

    today + ledger 있음 → as_of 이하 canonical 합 (0도 확정값)
    today + ledger 없음 → Child.cumulative_points (원페이지 빈 원장)
    historical + ledger 있음 → as_of 이하 canonical 합
    historical + ledger 없음 → None
        잔존 원장이 없다고 그 시점 누적이 0이었다고 증명할 수 없다.
        reset_data로 과거 DailyPoints가 사라진 경우도 같다.
    """
    if records_as_of:
        return int(round(sum((row.get('total_points') or 0) for row in records_as_of)))
    if as_of == kst_today():
        child = get_child(child_id)
        if child is None:
            return 0
        return int(child.cumulative_points or 0)
    return None


def points_metrics(child_id, as_of=None, window_days=30):
    """포인트 window 집계와 as_of 누적.

    분석 정본은 cumulative_as_of (current_cumulative는 동일 Optional alias).
    child_cumulative_points는 오늘 시점 live cache다. Growth 비교,
    insight, historical snapshot, AI evidence에 사용하지 않는다.
    """
    as_of = resolve_as_of(as_of)
    previous = previous_window(as_of, window_days)
    records_as_of = _records_as_of(_canonical_daily_point_records(child_id), as_of)
    child = get_child(child_id)
    payload = _snapshot_meta(
        as_of,
        window_days,
        previous,
        {'points': _min_date(row.get('date') for row in records_as_of)},
    )
    payload['current'] = _points_slice(records_as_of, payload['current_window'])
    payload['previous'] = _points_slice(records_as_of, previous)
    payload['cumulative_as_of'] = _cumulative_as_of(records_as_of, child_id, as_of)
    payload['current_cumulative'] = payload['cumulative_as_of']
    # live cache only. not Growth evidence.
    payload['child_cumulative_points'] = int(child.cumulative_points or 0) if child is not None else 0
    return payload


def point_composition_metrics(child_id, as_of=None, window_days=30):
    """canonical DailyPoints → PointEvent → window composition.

    Evidence Packet / prompt는 이 payload를 읽지 않는다.
    current-center mapping은 features.points 경계에서만 주입한다.
    """
    from features.growth.point_composition import point_composition_from_events
    from features.points import project_current_center_events
    as_of = resolve_as_of(as_of)
    records = _records_as_of(_canonical_daily_point_records(child_id), as_of)
    events = project_current_center_events(records)
    return point_composition_from_events(
        events, as_of=as_of, window_days=window_days,
    )


def metrics_bundle(child_id, as_of=None, window_days=30):
    """reading/progress/points/learning/recent_window_bests 스냅샷을 한 묶음으로 모은다."""
    from features.growth.learning_metrics import learning_metrics
    from features.growth.recent_window_bests import recent_window_bests
    from features.growth.reward_metrics import reward_metrics
    as_of = resolve_as_of(as_of)
    reading = reading_metrics(child_id, as_of=as_of, window_days=window_days)
    points = points_metrics(child_id, as_of=as_of, window_days=window_days)
    learning = learning_metrics(
        child_id,
        as_of=as_of,
        window_days=window_days,
        points_payload=points,
    )
    return {
        'reading': reading,
        'progress': progress_metrics(child_id, as_of=as_of, window_days=window_days),
        'points': points,
        'learning': learning,
        'recent_window_bests': recent_window_bests(
            child_id,
            as_of=as_of,
            window_days=window_days,
            reading_payload=reading,
            points_payload=points,
            learning_payload=learning,
        ),
        'rewards': reward_metrics(child_id, as_of=as_of, window_days=window_days),
        'point_composition': point_composition_metrics(
            child_id, as_of=as_of, window_days=window_days,
        ),
    }
