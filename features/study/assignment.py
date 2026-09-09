"""교재 물리 구간 vs 영구 제외 배정. unique coverage / 진도율 계산은 하지 않는다."""
from __future__ import annotations

from features.planning.exclusions import count_overlapping_pages, merge_page_ranges


def physical_page_bounds(plan):
    """LearningWorkbookPlan 의 교재 물리 시작/끝 페이지."""
    if plan is None:
        return None
    return int(plan.start_page), int(plan.end_page)


def permanently_excluded_ranges(plan):
    """교사 계획상 영구 제외. None 은 '제외 목록을 아직 모름'이며 빈 제외 [] 와 다르다."""
    if plan is None:
        return None
    raw = plan.exclusion_ranges_json
    if raw is None:
        return None
    return merge_page_ranges(raw)


def assigned_page_count(plan):
    """물리 구간에서 영구 제외를 뺀 배정 페이지 수.

    제외 목록이 없으면 exact count를 만들지 않는다.
    학습 세션에 없는 페이지를 완료로 채우지 않는다.
    """
    bounds = physical_page_bounds(plan)
    if bounds is None:
        return None
    start, end = bounds
    exclusions = permanently_excluded_ranges(plan)
    if exclusions is None:
        return None
    total = end - start + 1
    return total - count_overlapping_pages(start, end, exclusions)
