"""현재 센터 manual 표현 → category. 금액으로 추론하지 않는다."""
from __future__ import annotations

from features.points.events import (
    CATEGORY_ACTIVITY_MATERIAL,
    CATEGORY_PRAISE,
    CATEGORY_STATIONERY,
    CATEGORY_TEXTBOOK_COMPLETE,
    ManualClassification,
    UNCLASSIFIED,
)
from features.points.text import compact_lookup, normalize_lookup

_PRESET_CATEGORY = {
    'textbook': CATEGORY_TEXTBOOK_COMPLETE,
    'print': CATEGORY_ACTIVITY_MATERIAL,
    'pencil': CATEGORY_STATIONERY,
    'eraser': CATEGORY_STATIONERY,
    'pencil_case': CATEGORY_STATIONERY,
}

_PRESET_ITEM = {
    'print': 'print',
    'pencil': 'pencil',
    'eraser': 'eraser',
    'pencil_case': 'pencil_case',
}

_SUBJECT_TOKENS = (
    ('국어', 'korean'),
    ('수학', 'math'),
    ('쎈', 'ssen'),
    ('영어', 'english'),
)

_MATERIAL_TOKENS = (
    ('아이클레이', 'clay'),
    ('클레이', 'clay'),
    ('프린트', 'print'),
    ('비즈', 'beads'),
)

_STATIONERY_TOKENS = (
    ('연필', 'pencil'),
    ('지우개', 'eraser'),
    ('필통', 'pencil_case'),
)

_CONFLICT = object()


def _classification(category, subject_key=None, item_key=None):
    return ManualClassification(
        category=category,
        subject_key=subject_key,
        item_key=item_key,
    )


def _alias_map():
    mapping = {}

    def add(keys, result):
        for key in keys:
            compact = compact_lookup(key)
            if compact:
                mapping[compact] = result

    add(
        ('국어교재완료', '국어 교재 완료', '교재완료(국어)', '교재완료국어'),
        _classification(CATEGORY_TEXTBOOK_COMPLETE, subject_key='korean'),
    )
    add(
        ('수학교재완료', '수학 교재 완료', '교재완료(수학)', '교재완료수학'),
        _classification(CATEGORY_TEXTBOOK_COMPLETE, subject_key='math'),
    )
    add(
        ('쎈교재완료', '쎈 교재 완료', '교재완료(쎈)', '교재완료쎈'),
        _classification(CATEGORY_TEXTBOOK_COMPLETE, subject_key='ssen'),
    )
    add(
        ('영어교재완료', '영어 교재 완료', '교재완료(영어)', '교재완료영어', '영어교재'),
        _classification(CATEGORY_TEXTBOOK_COMPLETE, subject_key='english'),
    )
    add(
        ('칭찬', '칭찬점수', '칭찬 점수', '선생님 칭찬', '오늘 잘함', '오늘잘함'),
        _classification(CATEGORY_PRAISE),
    )
    add(('프린트',), _classification(CATEGORY_ACTIVITY_MATERIAL, item_key='print'))
    add(('클레이', '아이클레이'), _classification(CATEGORY_ACTIVITY_MATERIAL, item_key='clay'))
    add(('비즈',), _classification(CATEGORY_ACTIVITY_MATERIAL, item_key='beads'))
    add(('연필',), _classification(CATEGORY_STATIONERY, item_key='pencil'))
    add(('지우개',), _classification(CATEGORY_STATIONERY, item_key='eraser'))
    add(('필통',), _classification(CATEGORY_STATIONERY, item_key='pencil_case'))
    add(
        ('학용품 구입', '학용품구입', '문구류 구입', '문구류구입'),
        _classification(CATEGORY_STATIONERY),
    )
    return mapping


_EXACT_ALIASES = _alias_map()


def classify_manual(item):
    """manual JSON item → ManualClassification. points 필드는 읽지 않는다."""
    if not isinstance(item, dict):
        return UNCLASSIFIED
    preset = str(item.get('presetKey') or item.get('preset_key') or '').strip().casefold()
    subject = item.get('subject') or ''
    reason = item.get('reason') or ''
    blobs = _blobs(subject, reason)

    if preset in _PRESET_CATEGORY:
        return _from_preset(preset, blobs)

    exact = _exact(blobs)
    if exact is _CONFLICT:
        return UNCLASSIFIED
    if exact is not None:
        return exact
    return _keyword(blobs)


def _blobs(subject, reason):
    parts = (subject, reason, f'{subject} {reason}'.strip())
    compact = []
    normalized = []
    for part in parts:
        compact_value = compact_lookup(part)
        normalized_value = normalize_lookup(part)
        if compact_value:
            compact.append(compact_value)
        if normalized_value:
            normalized.append(normalized_value)
    return {
        'compact': tuple(dict.fromkeys(compact)),
        'normalized': tuple(dict.fromkeys(normalized)),
        'haystack_compact': compact_lookup(f'{subject} {reason}'),
        'haystack_normalized': normalize_lookup(f'{subject} {reason}'),
    }


def _from_preset(preset, blobs):
    category = _PRESET_CATEGORY[preset]
    item_key = _PRESET_ITEM.get(preset)
    subject_key = None
    if category == CATEGORY_TEXTBOOK_COMPLETE:
        subject_key = _one_textbook_subject(blobs['haystack_compact'])
        if subject_key is _CONFLICT:
            return UNCLASSIFIED
    return _classification(category, subject_key=subject_key, item_key=item_key)


def _exact(blobs):
    found = []
    seen = set()
    for key in blobs['compact']:
        result = _EXACT_ALIASES.get(key)
        if result is None:
            continue
        identity = (result.category, result.subject_key, result.item_key)
        if identity in seen:
            continue
        seen.add(identity)
        found.append(result)
    if not found:
        return None
    if len(found) > 1:
        return _CONFLICT
    return found[0]


def _keyword(blobs):
    compact = blobs['haystack_compact']
    normalized = blobs['haystack_normalized']
    hits = []

    if _looks_textbook(compact, normalized):
        subject_key = _one_textbook_subject(compact)
        if subject_key is _CONFLICT:
            return UNCLASSIFIED
        hits.append(_classification(CATEGORY_TEXTBOOK_COMPLETE, subject_key=subject_key))
    if _looks_praise(compact, normalized):
        hits.append(_classification(CATEGORY_PRAISE))

    material = _one_token(_MATERIAL_TOKENS, compact)
    if material is _CONFLICT:
        return UNCLASSIFIED
    if material:
        hits.append(_classification(CATEGORY_ACTIVITY_MATERIAL, item_key=material))

    stationery = _one_token(_STATIONERY_TOKENS, compact)
    if stationery is _CONFLICT:
        return UNCLASSIFIED
    if stationery:
        hits.append(_classification(CATEGORY_STATIONERY, item_key=stationery))

    if len(hits) != 1:
        return UNCLASSIFIED
    return hits[0]


def _looks_textbook(compact, normalized):
    return '교재완료' in compact or '교재 완료' in normalized


def _looks_praise(compact, normalized):
    if '칭찬' in compact:
        return True
    return '오늘잘함' in compact or '오늘 잘함' in normalized


def _one_textbook_subject(compact):
    found = []
    for token, key in _SUBJECT_TOKENS:
        if token in compact:
            found.append(key)
    if not found:
        return None
    if len(found) > 1:
        return _CONFLICT
    return found[0]


def _one_token(tokens, compact):
    found = []
    for token, key in tokens:
        if token in compact and key not in found:
            found.append(key)
    if not found:
        return None
    if len(found) > 1:
        return _CONFLICT
    return found[0]
