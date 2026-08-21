"""공용 태블릿 아동 본인확인 세션. POST body의 child_id는 쓰지 않는다."""
from datetime import datetime, timezone

from features.reading.policy import now_utc, viewer_write_ttl_minutes, write_ttl_delta

SESSION_CHILD_ID = 'viewer_child_id'
SESSION_CHILD_SLUG = 'viewer_child_slug'
SESSION_VERIFIED_AT = 'viewer_child_verified_at'


def _parse_verified_at(raw):
    if not raw:
        return None
    if isinstance(raw, datetime):
        verified = raw
    else:
        try:
            verified = datetime.fromisoformat(str(raw))
        except ValueError:
            return None
    if verified.tzinfo is None:
        verified = verified.replace(tzinfo=timezone.utc)
    return verified.astimezone(timezone.utc)


def set_verified_child(session, child):
    """다른 아동을 확인하면 기존 viewer_child_id를 즉시 교체한다."""
    session[SESSION_CHILD_ID] = int(child.id)
    session[SESSION_CHILD_SLUG] = getattr(child, 'viewer_slug', None)
    session[SESSION_VERIFIED_AT] = now_utc().isoformat()


def clear_verified_child(session):
    session.pop(SESSION_CHILD_ID, None)
    session.pop(SESSION_CHILD_SLUG, None)
    session.pop(SESSION_VERIFIED_AT, None)


def verified_child_id(session):
    raw = session.get(SESSION_CHILD_ID)
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def verification_age(session):
    verified_at = _parse_verified_at(session.get(SESSION_VERIFIED_AT))
    if verified_at is None:
        return None
    return now_utc() - verified_at


def is_write_fresh(session, child):
    if child is None:
        return False
    if verified_child_id(session) != int(child.id):
        return False
    age = verification_age(session)
    if age is None:
        return False
    return age <= write_ttl_delta()


def read_block_reason(session, child):
    """읽기 전용 조회. 검증된 child context는 필요하지만 write TTL은 요구하지 않는다."""
    if child is None:
        return 'child_missing'
    session_id = verified_child_id(session)
    if session_id is None:
        return 'unverified'
    if session_id != int(child.id):
        return 'child_mismatch'
    if session.get(SESSION_CHILD_SLUG) and getattr(child, 'viewer_slug', None):
        if str(session.get(SESSION_CHILD_SLUG)) != str(child.viewer_slug):
            return 'child_mismatch'
    return None


def write_block_reason(session, child):
    if child is None:
        return 'child_missing'
    session_id = verified_child_id(session)
    if session_id is None:
        return 'unverified'
    if session_id != int(child.id):
        return 'child_mismatch'
    age = verification_age(session)
    if age is None:
        return 'unverified'
    if age > write_ttl_delta():
        return 'ttl_expired'
    return None


def ttl_minutes():
    return viewer_write_ttl_minutes()
