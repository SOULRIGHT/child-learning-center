"""현장 활동일은 KST 달력을 쓴다. 기존 UTC 혼용 코드는 일괄 변경하지 않는다."""
import os
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
DEV_ACTIVITY_DATE_SESSION_KEY = 'dev_activity_date'
DEV_DATE_CONTROL_ENV = 'CLC_DEV_DATE_CONTROL'


def actual_kst_today():
    """시스템 시계 기준 Asia/Seoul 달력 날짜. session override를 보지 않는다."""
    return datetime.now(KST).date()


def is_production_runtime():
    """app.py와 같은 production 신호: FLASK_ENV=production, PostgreSQL DATABASE_URL."""
    if (os.environ.get('FLASK_ENV') or '').strip().lower() == 'production':
        return True
    url = (os.environ.get('DATABASE_URL') or '').strip().lower()
    if url.startswith('postgresql://') or url.startswith('postgres://'):
        return True
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            uri = (current_app.config.get('SQLALCHEMY_DATABASE_URI') or '').strip().lower()
            if uri.startswith('postgresql://') or uri.startswith('postgres://'):
                return True
    except Exception:
        pass
    return False


def is_dev_date_control_enabled():
    """명시적 CLC_DEV_DATE_CONTROL=1 이고 production이 아닐 때만 True. 기본 OFF."""
    if (os.environ.get(DEV_DATE_CONTROL_ENV) or '').strip() != '1':
        return False
    if is_production_runtime():
        return False
    return True


def parse_activity_date_text(raw):
    text = '' if raw is None else str(raw).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _session_dev_activity_date():
    if not is_dev_date_control_enabled():
        return None
    try:
        from flask import has_request_context, session
    except ImportError:
        return None
    if not has_request_context():
        return None
    return parse_activity_date_text(session.get(DEV_ACTIVITY_DATE_SESSION_KEY))


def kst_today():
    override = _session_dev_activity_date()
    if override is not None:
        return override
    return actual_kst_today()


def dev_date_template_context():
    enabled = is_dev_date_control_enabled()
    actual = actual_kst_today()
    override = _session_dev_activity_date() if enabled else None
    return {
        'dev_date_control_enabled': enabled,
        'dev_activity_date': override or actual,
        'dev_activity_date_overridden': override is not None,
        'actual_kst_today': actual,
    }
