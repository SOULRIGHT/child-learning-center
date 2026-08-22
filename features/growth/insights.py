"""Step 1 metrics → comparison → gate → insight candidate → evidence.

importance는 화면 우선순위(0~100)이지 통계적 confidence가 아니다.
copy는 evidence 밖 사실을 만들지 않는다. None은 0으로 바꾸지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from features.growth.copy import (
    HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN,
    POINTS_PERIOD_INCREASE,
    PROGRESS_ENTRIES_DECREASE,
    PROGRESS_ENTRIES_INCREASE,
    READING_ACTIVITY_DECREASE,
    READING_ACTIVITY_INCREASE,
    READING_COMPLETIONS_DECREASE,
    READING_COMPLETIONS_INCREASE,
    fallback_copy,
)

# 절대 변화. 한 칸(+1일)은 후보로 쓰지 않는다.
READING_DAYS_DELTA_MIN = 2
PROGRESS_ENTRY_DELTA_MIN = 2
COMPLETION_DELTA_MIN = 1
# 일일 과목 포인트가 보통 100 근처라 그 미만 변동은 무시한다.
POINTS_PERIOD_DELTA_MIN = 100
DIFFICULTY_UP_MIN = 0.5
FUN_DROP_MAX = -0.3
RATING_SAMPLE_MIN = 3


@dataclass(frozen=True)
class InsightCandidate:
    id: str
    category: str
    direction: str
    importance: int
    evidence: dict
    metric_key: str = ''
    secondary_metric_key: str = ''


def _relative_change(previous, delta):
    if previous is None or previous == 0:
        return None
    return delta / previous


def _payload(bundle, name):
    return bundle.get(name) or {}


def _comparable(payload, key):
    flags = payload.get('comparable') or {}
    return flags.get(key) is True


def _slice(payload, side):
    return payload.get(side) or {}


def _number(value):
    """비교에 쓸 확정 숫자. None/비숫자는 unknown."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _delta(current, previous):
    if current is None or previous is None:
        return None
    return current - previous


def _count_evidence(payload, *, source, metric_key, current, previous, delta, n_current, n_previous, comparable):
    return {
        'source': source,
        'metric_key': metric_key,
        'window_days': payload.get('window_days'),
        'current_window': payload.get('current_window'),
        'previous_window': payload.get('previous_window'),
        'current': current,
        'previous': previous,
        'delta': delta,
        'relative_change': _relative_change(previous, delta),
        'n_current': n_current,
        'n_previous': n_previous,
        'comparable': comparable,
    }


def _priority(base, magnitude, large_at, bump_cap=12, large_bonus=8):
    """화면 노출 순서용 정수. p-value/신뢰도가 아니다."""
    bump = min(bump_cap, max(0, int(magnitude)))
    extra = large_bonus if magnitude >= large_at else 0
    return min(100, base + bump + extra)


def _candidate(candidate_id, category, direction, importance, evidence, metric_key, secondary=''):
    return InsightCandidate(
        id=candidate_id,
        category=category,
        direction=direction,
        importance=importance,
        evidence=evidence,
        metric_key=metric_key,
        secondary_metric_key=secondary,
    )


def _reading_activity(reading):
    if not _comparable(reading, 'reading_days'):
        return []
    current = _number(_slice(reading, 'current').get('reading_days'))
    previous = _number(_slice(reading, 'previous').get('reading_days'))
    delta = _delta(current, previous)
    if delta is None:
        return []
    evidence = _count_evidence(
        reading,
        source='reading_day.date',
        metric_key='reading_days',
        current=current,
        previous=previous,
        delta=delta,
        n_current=current,
        n_previous=previous,
        comparable=True,
    )
    # previous=0이면 출석 원장 없이 "0에서 늘었다"고 단정하지 않는다.
    if delta >= READING_DAYS_DELTA_MIN and previous > 0:
        return [_candidate(
            READING_ACTIVITY_INCREASE,
            'reading_activity',
            'increase',
            _priority(50, delta, large_at=6),
            evidence,
            'reading_days',
        )]
    if delta <= -READING_DAYS_DELTA_MIN:
        return [_candidate(
            READING_ACTIVITY_DECREASE,
            'reading_activity',
            'decrease',
            _priority(50, abs(delta), large_at=6),
            evidence,
            'reading_days',
        )]
    return []


def _reading_completions(reading):
    if not _comparable(reading, 'completed'):
        return []
    current = _number(_slice(reading, 'current').get('completed_count'))
    previous = _number(_slice(reading, 'previous').get('completed_count'))
    delta = _delta(current, previous)
    if delta is None:
        return []
    evidence = _count_evidence(
        reading,
        source='child_reading.completed_on',
        metric_key='completed_count',
        current=current,
        previous=previous,
        delta=delta,
        n_current=current,
        n_previous=previous,
        comparable=True,
    )
    if delta >= COMPLETION_DELTA_MIN:
        return [_candidate(
            READING_COMPLETIONS_INCREASE,
            'reading_completions',
            'increase',
            _priority(46, delta * 4, large_at=12),
            evidence,
            'completed_count',
        )]
    if delta <= -COMPLETION_DELTA_MIN:
        return [_candidate(
            READING_COMPLETIONS_DECREASE,
            'reading_completions',
            'decrease',
            _priority(46, abs(delta) * 4, large_at=12),
            evidence,
            'completed_count',
        )]
    return []


def _progress_entries(progress):
    if not _comparable(progress, 'progress'):
        return []
    current = _number(_slice(progress, 'current').get('progress_entry_count'))
    previous = _number(_slice(progress, 'previous').get('progress_entry_count'))
    delta = _delta(current, previous)
    if delta is None:
        return []
    evidence = _count_evidence(
        progress,
        source='learning_progress_entry.recorded_on',
        metric_key='progress_entry_count',
        current=current,
        previous=previous,
        delta=delta,
        n_current=current,
        n_previous=previous,
        comparable=True,
    )
    # 기록 횟수 변화만 말한다. previous=0은 "공부를 시작했다"로 해석하지 않는다.
    if delta >= PROGRESS_ENTRY_DELTA_MIN and previous > 0:
        return [_candidate(
            PROGRESS_ENTRIES_INCREASE,
            'progress_entries',
            'increase',
            _priority(42, delta, large_at=6),
            evidence,
            'progress_entry_count',
        )]
    if delta <= -PROGRESS_ENTRY_DELTA_MIN:
        return [_candidate(
            PROGRESS_ENTRIES_DECREASE,
            'progress_entries',
            'decrease',
            _priority(42, abs(delta), large_at=6),
            evidence,
            'progress_entry_count',
        )]
    return []


def _points_period(points):
    if not _comparable(points, 'points'):
        return []
    previous_slice = _slice(points, 'previous')
    current_slice = _slice(points, 'current')
    activity_days = _number(previous_slice.get('point_activity_days'))
    if activity_days is None or activity_days <= 0:
        return []
    current = _number(current_slice.get('period_points'))
    previous = _number(previous_slice.get('period_points'))
    delta = _delta(current, previous)
    if delta is None or delta < POINTS_PERIOD_DELTA_MIN:
        return []
    evidence = _count_evidence(
        points,
        source='daily_points.date',
        metric_key='period_points',
        current=current,
        previous=previous,
        delta=delta,
        n_current=_number(current_slice.get('point_activity_days')),
        n_previous=activity_days,
        comparable=True,
    )
    evidence['point_activity_days_current'] = evidence['n_current']
    evidence['point_activity_days_previous'] = activity_days
    return [_candidate(
        POINTS_PERIOD_INCREASE,
        'points_period',
        'increase',
        _priority(44, delta / 50, large_at=8),
        evidence,
        'period_points',
    )]


def _paired_stats(slice_):
    stats = slice_.get('paired_experience_rating') or {}
    return (
        _number(stats.get('difficulty_average')),
        _number(stats.get('fun_average')),
        _number(stats.get('sample_count')),
    )


def _rating_cross(reading):
    """같은 ChildReading에서 두 rating이 모두 있는 paired 표본만 쓴다."""
    if not _comparable(reading, 'experience_rating_pair'):
        return []
    current_diff, current_fun, n_current = _paired_stats(_slice(reading, 'current'))
    previous_diff, previous_fun, n_previous = _paired_stats(_slice(reading, 'previous'))
    if n_current is None or n_previous is None:
        return []
    if n_current < RATING_SAMPLE_MIN or n_previous < RATING_SAMPLE_MIN:
        return []
    diff_delta = _delta(current_diff, previous_diff)
    fun_delta = _delta(current_fun, previous_fun)
    if diff_delta is None or fun_delta is None:
        return []
    if diff_delta < DIFFICULTY_UP_MIN:
        return []
    if fun_delta < FUN_DROP_MAX:
        return []
    evidence = {
        'source': 'child_reading.paired_experience_rating',
        'metric_key': 'paired_experience_rating',
        'secondary_metric_key': '',
        'window_days': reading.get('window_days'),
        'current_window': reading.get('current_window'),
        'previous_window': reading.get('previous_window'),
        'current': {
            'difficulty_average': current_diff,
            'fun_average': current_fun,
            'sample_count': n_current,
        },
        'previous': {
            'difficulty_average': previous_diff,
            'fun_average': previous_fun,
            'sample_count': n_previous,
        },
        'delta': {
            'difficulty': diff_delta,
            'fun': fun_delta,
        },
        'relative_change': None,
        'n_current': n_current,
        'n_previous': n_previous,
        'comparable': True,
    }
    return [_candidate(
        HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN,
        'reading_experience',
        'higher_perceived_difficulty_stable_fun',
        82,
        evidence,
        'paired_experience_rating',
    )]


def generate_insight_candidates(metrics_bundle):
    """metrics_bundle → 후보 리스트. importance desc, id asc."""
    bundle = metrics_bundle or {}
    candidates = []
    candidates.extend(_reading_activity(_payload(bundle, 'reading')))
    candidates.extend(_reading_completions(_payload(bundle, 'reading')))
    candidates.extend(_progress_entries(_payload(bundle, 'progress')))
    candidates.extend(_points_period(_payload(bundle, 'points')))
    candidates.extend(_rating_cross(_payload(bundle, 'reading')))
    return sorted(candidates, key=lambda item: (-item.importance, item.id))


def top_candidates(candidates, limit=3):
    """importance 순으로 최대 limit개. 같은 category는 하나만."""
    picked = []
    seen = set()
    for item in sorted(candidates, key=lambda row: (-row.importance, row.id)):
        if item.category in seen:
            continue
        seen.add(item.category)
        picked.append(item)
        if len(picked) >= limit:
            break
    return picked


def candidate_copy(candidate):
    return fallback_copy(candidate.id)
