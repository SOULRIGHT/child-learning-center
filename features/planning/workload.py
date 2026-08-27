"""Rolling remaining workload 순수 계산. Growth/DB 조회는 하지 않는다."""
from __future__ import annotations

from dataclasses import dataclass

from features.planning.exclusions import PlanningError, count_overlapping_pages, merge_page_ranges

DEFAULT_EXCLUDED_RATIO = 0.20
USABLE_RATIO = 1.0 - DEFAULT_EXCLUDED_RATIO
WORKLOAD_KIND_EXACT = 'exact'
WORKLOAD_KIND_ESTIMATED = 'estimated'


@dataclass(frozen=True)
class RemainingWorkload:
    start_page: int
    end_page: int
    current_page: int
    remaining_start: int | None
    remaining_end: int | None
    nominal_total_pages: int
    usable_total_pages: int | float
    nominal_remaining_pages: int
    remaining_workload: int | float
    workload_kind: str


def remaining_page_span(start_page, end_page, current_page):
    """남은 inclusive 구간. (current, end] 이되 current < start 이면 전체 plan.

    current >= end 이면 None. 음수 구간을 만들지 않는다.
    """
    try:
        start = int(start_page)
        end = int(end_page)
        current = int(current_page)
    except (TypeError, ValueError) as exc:
        raise PlanningError('페이지는 정수여야 합니다.', code='invalid_page') from exc
    if start < 1 or end < start:
        raise PlanningError('계획 페이지 범위가 올바르지 않습니다.', code='invalid_plan_pages')
    if current >= end:
        return None
    if current < start:
        return (start, end)
    return (current + 1, end)


def compute_remaining_workload(
    *,
    start_page,
    end_page,
    current_page,
    exclusion_ranges=None,
):
    span = remaining_page_span(start_page, end_page, current_page)
    start = int(start_page)
    end = int(end_page)
    current = int(current_page)
    nominal_total = end - start + 1
    if span is None:
        remaining_start = remaining_end = None
        nominal_remaining = 0
    else:
        remaining_start, remaining_end = span
        nominal_remaining = remaining_end - remaining_start + 1

    if exclusion_ranges is None:
        usable_total = 0 if nominal_total == 0 else nominal_total * USABLE_RATIO
        remaining = 0 if nominal_remaining == 0 else nominal_remaining * USABLE_RATIO
        kind = WORKLOAD_KIND_ESTIMATED
    else:
        merged = merge_page_ranges(exclusion_ranges)
        usable_total = nominal_total - count_overlapping_pages(start, end, merged)
        if span is None:
            remaining = 0
        else:
            excluded = count_overlapping_pages(remaining_start, remaining_end, merged)
            remaining = nominal_remaining - excluded
        kind = WORKLOAD_KIND_EXACT

    if remaining < 0:
        remaining = 0
    if usable_total < 0:
        usable_total = 0

    return RemainingWorkload(
        start_page=start,
        end_page=end,
        current_page=current,
        remaining_start=remaining_start,
        remaining_end=remaining_end,
        nominal_total_pages=nominal_total,
        usable_total_pages=usable_total,
        nominal_remaining_pages=nominal_remaining,
        remaining_workload=remaining,
        workload_kind=kind,
    )
