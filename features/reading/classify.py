"""아동+책 조합으로 추천독서 여부를 판정한다. UI 경로와 무관하게 동일해야 한다."""
from __future__ import annotations

from feature_models import (
    GRADE_BAND_2_3,
    GRADE_BAND_4_6,
    PROGRAM_TYPE_CHALLENGE,
    PROGRAM_TYPE_GENERAL,
    PROGRAM_TYPE_RECOMMENDED,
)

VALID_GRADE_BANDS = (GRADE_BAND_2_3, GRADE_BAND_4_6)

_BAND_ALIASES = {
    '2-3': GRADE_BAND_2_3,
    '2~3': GRADE_BAND_2_3,
    '2_3': GRADE_BAND_2_3,
    '23': GRADE_BAND_2_3,
    '2–3': GRADE_BAND_2_3,
    '2—3': GRADE_BAND_2_3,
    '2-3학년': GRADE_BAND_2_3,
    '2~3학년': GRADE_BAND_2_3,
    '2~3학년추천': GRADE_BAND_2_3,
    '4-6': GRADE_BAND_4_6,
    '4~6': GRADE_BAND_4_6,
    '4_6': GRADE_BAND_4_6,
    '46': GRADE_BAND_4_6,
    '4–6': GRADE_BAND_4_6,
    '4—6': GRADE_BAND_4_6,
    '4-6학년': GRADE_BAND_4_6,
    '4~6학년': GRADE_BAND_4_6,
    '4~6학년추천': GRADE_BAND_4_6,
}


def _parse_grade(raw):
    if raw is None or raw == '':
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def grade_band_for_child_grade(grade):
    parsed = _parse_grade(grade)
    if parsed in (2, 3):
        return GRADE_BAND_2_3
    if parsed in (4, 5, 6):
        return GRADE_BAND_4_6
    return None


def normalize_grade_band(raw):
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    compact = text.replace(' ', '').replace('학년', '').replace('추천도서', '').replace('추천', '')
    mapped = _BAND_ALIASES.get(text) or _BAND_ALIASES.get(compact)
    if mapped:
        return mapped
    lowered = compact.replace('～', '~')
    return _BAND_ALIASES.get(lowered)


def classify_program_type(child, book):
    """같은 Child + Book이면 교사/학생 UI와 무관하게 같은 결과를 반환한다.

    과거 ChildReading을 재분류하지 않는다. 새로 시작할 때만 호출한다.
    학생 request의 program_type은 사용하지 않는다.
    """
    if book is None:
        return PROGRAM_TYPE_GENERAL
    if bool(getattr(book, 'is_recommended', False)):
        child_band = grade_band_for_child_grade(getattr(child, 'grade', None))
        book_band = normalize_grade_band(getattr(book, 'grade_band', None))
        if child_band and book_band and child_band == book_band:
            return PROGRAM_TYPE_RECOMMENDED
        return PROGRAM_TYPE_GENERAL
    if bool(getattr(book, 'is_challenge_eligible', False)):
        if _parse_grade(getattr(child, 'grade', None)) in (5, 6):
            return PROGRAM_TYPE_CHALLENGE
        return PROGRAM_TYPE_GENERAL
    return PROGRAM_TYPE_GENERAL
