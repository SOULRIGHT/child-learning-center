"""명목 예정 학습일. 공휴일/행사/출석은 보지 않는다."""
from __future__ import annotations

from datetime import timedelta

from features.planning.exclusions import PlanningError

DEFAULT_STUDY_WEEKDAYS = (0, 1, 2, 3, 4)
CALENDAR_SINGLETON_KEY = 'default'


def canonicalize_weekdays(raw):
    """Python date.weekday() 값 0=월 … 6=일. 빈 배열은 '예정일 없음' override로 허용한다."""
    if raw is None:
        raise PlanningError('학습요일은 필수입니다.', code='weekdays_required')
    if isinstance(raw, (str, bytes)) or not hasattr(raw, '__iter__'):
        raise PlanningError('학습요일 형식이 올바르지 않습니다.', code='invalid_weekdays')
    seen = set()
    result = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, int):
            raise PlanningError('학습요일은 0부터 6 사이의 정수여야 합니다.', code='invalid_weekday')
        if item < 0 or item > 6:
            raise PlanningError('학습요일은 0부터 6 사이의 정수여야 합니다.', code='invalid_weekday')
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    result.sort()
    return result


def effective_study_weekdays(center_weekdays, child_override=None):
    """child_override is None → 센터 기본. 빈 목록은 명시적 0일로 유지한다."""
    if child_override is None:
        return canonicalize_weekdays(center_weekdays)
    return canonicalize_weekdays(child_override)


def count_planned_study_days(as_of, target_completion_date, weekdays):
    """(as_of, target] 구간의 명목 예정 학습일 수. target <= as_of 이면 0."""
    allowed = set(canonicalize_weekdays(weekdays))
    if target_completion_date is None or as_of is None:
        raise PlanningError('날짜가 올바르지 않습니다.', code='invalid_date')
    if target_completion_date <= as_of:
        return 0
    count = 0
    cursor = as_of + timedelta(days=1)
    while cursor <= target_completion_date:
        if cursor.weekday() in allowed:
            count += 1
        cursor += timedelta(days=1)
    return count
