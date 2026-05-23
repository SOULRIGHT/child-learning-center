import re
import secrets
from urllib.parse import unquote

VIEWER_SLUG_LENGTH = 24
VIEWER_SLUG_RE = re.compile(r'(?P<slug>[a-f0-9]{24})', re.IGNORECASE)


def generate_viewer_slug():
    """QR 링크용 랜덤 slug 생성"""
    return secrets.token_hex(VIEWER_SLUG_LENGTH // 2)


def extract_viewer_slug(raw_value):
    """깨진 문자열에서도 slug 토큰만 복구 추출"""
    if raw_value is None:
        return None
    decoded = unquote(str(raw_value)).strip().lower()
    match = VIEWER_SLUG_RE.search(decoded)
    if not match:
        return None
    return match.group('slug')
