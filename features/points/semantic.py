"""Stored semantic mapping lookup/upsert. LLM을 호출하지 않는다.

deterministic current-center mapping과 DB를 한 함수에 섞지 않는다.
Projector / mapping/current.py 는 이 모듈을 import하지 않는다.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from features.points.events import (
    CATEGORY_ACTIVITY_MATERIAL,
    CATEGORY_EXTRA_LEARNING,
    CATEGORY_HELP_CONTRIBUTION,
    CATEGORY_PRAISE,
    CATEGORY_STATIONERY,
    CATEGORY_TEXTBOOK_COMPLETE,
    CATEGORY_UNCLASSIFIED,
    ManualClassification,
    UNCLASSIFIED,
    READING_REWARD_MIRROR_SOURCE_TYPES,
)
from features.points.text import compact_lookup

SOURCE_SEMANTIC_LLM = 'semantic_llm'
SOURCE_MANUAL_OVERRIDE = 'manual_override'

ALLOWED_SOURCES = frozenset((SOURCE_SEMANTIC_LLM, SOURCE_MANUAL_OVERRIDE))

ALLOWED_CATEGORIES = frozenset((
    CATEGORY_TEXTBOOK_COMPLETE,
    CATEGORY_PRAISE,
    CATEGORY_HELP_CONTRIBUTION,
    CATEGORY_EXTRA_LEARNING,
    CATEGORY_ACTIVITY_MATERIAL,
    CATEGORY_STATIONERY,
    CATEGORY_UNCLASSIFIED,
))

ALLOWED_SUBJECT_KEYS = frozenset((
    'korean', 'math', 'ssen', 'english',
    'reading', 'piano', 'advanced_math', 'writing',
))

ALLOWED_ITEM_KEYS = frozenset((
    'print', 'clay', 'beads', 'pencil', 'eraser', 'pencil_case',
))

MAX_CANDIDATE_LABEL_LEN = 40


@dataclass(frozen=True)
class StoredSemanticMapping:
    normalized_label: str
    category: str
    subject_key: str | None = None
    item_key: str | None = None
    source: str | None = None


def get_semantic_mapping(normalized_label):
    """normalized_label → stored row 또는 None. 개인정보를 반환하지 않는다."""
    key = compact_lookup(normalized_label)
    if not key:
        return None
    row = _query_row(key)
    if row is None:
        return None
    return StoredSemanticMapping(
        normalized_label=row.normalized_label,
        category=row.category,
        subject_key=row.subject_key,
        item_key=row.item_key,
        source=row.source,
    )


def semantic_classification_for(item):
    """manual JSON item → stored mapping classification. 금액은 읽지 않는다."""
    if not isinstance(item, dict):
        return UNCLASSIFIED
    key = compact_lookup(item.get('subject') or '')
    if not key:
        return UNCLASSIFIED
    stored = get_semantic_mapping(key)
    return classification_from_stored(stored)


def classification_from_stored(stored):
    """잘못된 저장값이 있어도 crash하지 않고 UNCLASSIFIED로 떨어진다."""
    if stored is None:
        return UNCLASSIFIED
    category = getattr(stored, 'category', None)
    if category not in ALLOWED_CATEGORIES:
        return UNCLASSIFIED
    subject_key = getattr(stored, 'subject_key', None)
    if subject_key not in ALLOWED_SUBJECT_KEYS:
        subject_key = None
    item_key = getattr(stored, 'item_key', None)
    if item_key not in ALLOWED_ITEM_KEYS:
        item_key = None
    return ManualClassification(
        category=category,
        subject_key=subject_key,
        item_key=item_key,
    )


def upsert_semantic_mapping(
    label,
    category,
    subject_key=None,
    item_key=None,
    source=SOURCE_SEMANTIC_LLM,
):
    """같은 normalized_label이면 update. LLM을 호출하지 않는다."""
    from extensions import db
    from feature_models import PointSemanticMapping

    key = compact_lookup(label)
    if not key:
        raise ValueError('normalized_label이 비어 있습니다.')
    source_value = str(source or SOURCE_SEMANTIC_LLM)
    if source_value not in ALLOWED_SOURCES:
        source_value = SOURCE_SEMANTIC_LLM
    now = datetime.utcnow()
    row = _query_row(key)
    if row is None:
        row = PointSemanticMapping(
            normalized_label=key,
            category=str(category or ''),
            subject_key=_optional_key(subject_key),
            item_key=_optional_key(item_key),
            source=source_value,
            created_at=now,
            updated_at=now,
        )
        db.session.add(row)
    else:
        row.category = str(category or '')
        row.subject_key = _optional_key(subject_key)
        row.item_key = _optional_key(item_key)
        row.source = source_value
        row.updated_at = now
    db.session.flush()
    return row


def unmapped_manual_label_counts(records):
    """deterministic·semantic 모두에 없는 unique compact label. 외부 API 없음."""
    from features.points.mapping.current import classify_manual

    known = _known_semantic_labels()
    counts = Counter()
    for record in records or ():
        if not isinstance(record, dict):
            continue
        for item in record.get('manual_items') or ():
            if not isinstance(item, dict):
                continue
            if _is_mirror(item):
                continue
            try:
                amount = int(item.get('points') or 0)
            except (TypeError, ValueError):
                amount = 0
            if amount == 0:
                continue
            key = compact_lookup(item.get('subject') or '')
            if not key or len(key) > MAX_CANDIDATE_LABEL_LEN:
                continue
            if key in known:
                continue
            classified = classify_manual({'subject': key})
            if (
                isinstance(classified, ManualClassification)
                and classified.category != CATEGORY_UNCLASSIFIED
            ):
                continue
            counts[key] += 1
    return tuple(
        {'label': label, 'count': count}
        for label, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    )


def _query_row(normalized_label):
    try:
        from feature_models import PointSemanticMapping
        return (
            PointSemanticMapping.query
            .filter_by(normalized_label=normalized_label)
            .first()
        )
    except Exception:
        return None


def _known_semantic_labels():
    try:
        from feature_models import PointSemanticMapping
        return {
            row.normalized_label
            for row in PointSemanticMapping.query.all()
            if row.normalized_label
        }
    except Exception:
        return set()


def _optional_key(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_mirror(item):
    source_type = item.get('source_type')
    if source_type in READING_REWARD_MIRROR_SOURCE_TYPES:
        return True
    return item.get('source_event_id') is not None
