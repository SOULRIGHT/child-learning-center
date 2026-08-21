"""일반독서 정책 버전. created_at이 아니라 활동 날짜로 판정한다."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

from features.dates import kst_today

DEFAULT_V2_START_DATE = date(2099, 1, 1)
DEFAULT_WRITE_TTL_MINUTES = 15
POLICY_VERSION_GENERAL_V2 = 'general_v2'
PROGRAM_TYPE_GENERAL = 'general'
READING_INCENTIVES_ENV = 'CLC_READING_INCENTIVES_ENABLED'


def _parse_enabled_flag(raw, default=True):
    if raw is None:
        return default
    text = str(raw).strip().lower()
    if text == '':
        return default
    return text not in {'0', 'false', 'off', 'no'}


def reading_incentives_enabled():
    """추천/도전 추가포인트·면제권 프로그램 스위치. 기본 ON.

    OFF여도 Book/ChildReading/ReadingDay 원장과 DailyPoints 입력은 유지한다.
    """
    env_raw = os.environ.get(READING_INCENTIVES_ENV)
    if env_raw is not None and str(env_raw).strip() != '':
        return _parse_enabled_flag(env_raw, default=True)
    try:
        from flask import current_app
        configured = current_app.config.get(READING_INCENTIVES_ENV)
        if configured is not None:
            return bool(configured)
    except RuntimeError:
        pass
    return True


def now_utc():
    """TTL/본인확인 시각은 항상 timezone-aware UTC."""
    return datetime.now(timezone.utc)


def activity_today():
    """독서 활동일은 한국 현장 달력 날짜."""
    return kst_today()


def _parse_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    return date.fromisoformat(text)


def general_reading_v2_start_date():
    try:
        from flask import current_app
        configured = current_app.config.get('GENERAL_READING_V2_START_DATE')
        parsed = _parse_date(configured)
        if parsed:
            return parsed
    except RuntimeError:
        pass
    raw = (os.environ.get('GENERAL_READING_V2_START_DATE') or '').strip()
    parsed = _parse_date(raw) if raw else None
    return parsed or DEFAULT_V2_START_DATE


def viewer_write_ttl_minutes():
    try:
        from flask import current_app
        configured = current_app.config.get('VIEWER_CHILD_WRITE_TTL_MINUTES')
        if configured is not None:
            return int(configured)
    except RuntimeError:
        pass
    raw = (os.environ.get('VIEWER_CHILD_WRITE_TTL_MINUTES') or '').strip()
    if raw:
        return int(raw)
    return DEFAULT_WRITE_TTL_MINUTES


def is_general_reading_v2(activity_date):
    parsed = _parse_date(activity_date)
    if parsed is None:
        return False
    return parsed >= general_reading_v2_start_date()


def allowed_reading_points(activity_date):
    if is_general_reading_v2(activity_date):
        return (0, 100)
    return (0, 100, 200)


def validate_reading_points(activity_date, reading_points):
    allowed = allowed_reading_points(activity_date)
    if reading_points not in allowed:
        if is_general_reading_v2(activity_date):
            return False, '일반독서는 완료 100점 또는 미완료 0점만 입력할 수 있습니다.'
        return False, '허용되지 않은 독서 포인트입니다.'
    return True, None


def write_ttl_delta():
    return timedelta(minutes=viewer_write_ttl_minutes())
