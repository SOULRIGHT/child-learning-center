"""교재 제외 페이지 파서. route/model/app.py 에 두지 않는다."""
from __future__ import annotations

import re

RANGE_TOKEN_RE = re.compile(r'^(\d+)(?:\s*-\s*(\d+))?$')


class PlanningError(Exception):
    def __init__(self, message, code='error'):
        super().__init__(message)
        self.message = message
        self.code = code


def merge_page_ranges(ranges):
    """겹치거나 인접한 inclusive range를 합친다. page count가 중복되지 않게 한다."""
    normalized = []
    for item in ranges or ():
        start = int(item['start'])
        end = int(item['end'])
        if start > end:
            raise PlanningError('제외 구간의 시작이 끝보다 큽니다.', code='reversed_range')
        normalized.append({'start': start, 'end': end})
    normalized.sort(key=lambda row: (row['start'], row['end']))
    merged = []
    for row in normalized:
        if not merged or row['start'] > merged[-1]['end'] + 1:
            merged.append({'start': row['start'], 'end': row['end']})
            continue
        merged[-1]['end'] = max(merged[-1]['end'], row['end'])
    return merged


def parse_exclusion_ranges(raw, *, start_page, end_page):
    """원문 → DB payload.

    None/공백(미입력)은 None 이다. 빈 리스트 [] 가 아니다.
    유효 입력만 merged [{'start', 'end'}, ...] 를 반환한다.
    명시적 제외 0개는 파서가 만들지 않고, storage에 [] 를 직접 넣을 때만 생긴다.
    """
    try:
        plan_start = int(start_page)
        plan_end = int(end_page)
    except (TypeError, ValueError) as exc:
        raise PlanningError('계획 페이지 범위가 올바르지 않습니다.', code='invalid_plan_pages') from exc
    if plan_start < 1 or plan_end < plan_start:
        raise PlanningError('계획 페이지 범위가 올바르지 않습니다.', code='invalid_plan_pages')

    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    parsed = []
    for token in text.split(','):
        piece = token.strip()
        if not piece:
            raise PlanningError('빈 제외 구간이 있습니다.', code='empty_range_token')
        match = RANGE_TOKEN_RE.fullmatch(piece)
        if match is None:
            raise PlanningError('제외 페이지 형식이 올바르지 않습니다.', code='invalid_range_syntax')
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) is not None else start
        if start < 1 or end < 1:
            raise PlanningError('페이지는 1 이상이어야 합니다.', code='page_range')
        if start > end:
            raise PlanningError('제외 구간의 시작이 끝보다 큽니다.', code='reversed_range')
        if start < plan_start or end > plan_end:
            raise PlanningError('제외 구간이 교재 계획 범위를 벗어났습니다.', code='range_outside_plan')
        parsed.append({'start': start, 'end': end})
    return merge_page_ranges(parsed)


def count_pages_in_ranges(ranges):
    total = 0
    for row in merge_page_ranges(ranges):
        total += row['end'] - row['start'] + 1
    return total


def count_overlapping_pages(lo, hi, ranges):
    """[lo, hi] inclusive 안에서 제외되는 페이지 수."""
    if lo > hi:
        return 0
    total = 0
    for row in merge_page_ranges(ranges):
        start = max(row['start'], lo)
        end = min(row['end'], hi)
        if start <= end:
            total += end - start + 1
    return total
