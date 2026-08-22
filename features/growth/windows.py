"""Growth 기간 창. 모든 날짜는 inclusive KST 달력이다."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from features.dates import kst_today

DEFAULT_WINDOW_DAYS = 30


def resolve_as_of(as_of=None):
    """as_of가 없으면 kst_today()를 쓴다."""
    if as_of is None:
        return kst_today()
    if isinstance(as_of, datetime):
        return as_of.date()
    if isinstance(as_of, date):
        return as_of
    raise TypeError('as_of는 date 이거나 None 이어야 합니다.')


def inclusive_window(end_date, window_days):
    """end_date를 포함한 연속 window_days일. start = end - (window_days - 1)."""
    days = int(window_days)
    if days < 1:
        raise ValueError('window_days는 1 이상이어야 합니다.')
    end = resolve_as_of(end_date)
    start = end - timedelta(days=days - 1)
    return {'start': start, 'end': end, 'days': days}


def current_window(as_of=None, window_days=DEFAULT_WINDOW_DAYS):
    return inclusive_window(resolve_as_of(as_of), window_days)


def previous_window(as_of=None, window_days=DEFAULT_WINDOW_DAYS):
    """current 바로 앞의 같은 길이 inclusive 창."""
    as_of = resolve_as_of(as_of)
    days = int(window_days)
    previous_end = as_of - timedelta(days=days)
    return inclusive_window(previous_end, days)


def date_in_window(value, window):
    return value is not None and window['start'] <= value <= window['end']


def on_or_before(value, as_of):
    """as_of 스냅샷에 포함되는 날짜인지. 이후 데이터는 어떤 결과에도 쓰지 않는다."""
    return value is not None and value <= as_of


def coverage_comparable(available_from, previous):
    """잔존 원장이 previous window 시작일을 덮는지 보는 보수적 heuristic.

    available_from은 현재 DB에 남아 있는 최초 관측일이다.
    정책 시작일/배포일/센터 개소일/실제 활동 시작일이 아니다.
    원장이 없으면 False. 부분 overlap은 보정하지 않는다.
    """
    if available_from is None:
        return False
    return available_from <= previous['start']
