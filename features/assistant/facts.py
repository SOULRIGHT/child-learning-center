"""Growth canonical facts를 assistant tool용으로 얇게 투영한다.

Evidence Packet 전체 dump / raw review / ORM 객체를 반환하지 않는다.
metrics를 다시 계산하지 않고 기존 packet builder를 읽는다.
"""
from __future__ import annotations

from features.assistant.navigation import lookup_child
from features.dates import parse_activity_date_text
from features.growth.ai.runtime import build_current_packet

MAX_FACTS = 24
BLOCKED_EVIDENCE_PREFIXES = (
    'reading.analysis.observation',
    'reading.analysis.limitation',
)
BLOCKED_KEYS = frozenset({
    'review_text', 'review', 'raw_output', 'packet', 'observations',
})
TOPIC_PREFIXES = {
    'learning': ('learning.',),
    'points': ('points.',),
    'reading': ('reading.',),
    'peer': ('peer',),
    'growth': (),
}

_LABELS = {
    'learning.math.performance.studied_days.current': '수학 학습일(최근)',
    'learning.korean.performance.studied_days.current': '국어 학습일(최근)',
    'learning.ssen.performance.studied_days.current': '쎈수학 학습일(최근)',
    'learning.math.progress.latest_observed_end_page': '수학 관측 끝 페이지',
    'learning.korean.progress.latest_observed_end_page': '국어 관측 끝 페이지',
    'points.period_total.current': '기간 포인트(최근)',
    'points.cumulative_as_of': '누적 포인트',
    'reading.activity_days.current': '최근 독서 활동일',
    'reading.completed_count': '완독 수',
}


def growth_facts_for_child(child_id, *, as_of=None, topic='growth', subject_key=None):
    child = lookup_child(child_id)
    if child is None:
        return {'ok': False, 'error': 'invalid_child'}
    parsed = _parse_as_of(as_of)
    packet = build_current_packet(child, as_of=parsed)
    facts = compact_facts(packet, topic=topic, subject_key=subject_key)
    return {
        'ok': True,
        'child': {
            'id': child.id,
            'name': child.name,
            'grade': getattr(child, 'grade', None),
        },
        'as_of': packet.get('as_of'),
        'facts': facts,
    }


def compact_facts(packet, *, topic='growth', subject_key=None):
    rows = []
    for node in _walk(packet.get('supporting_facts') or {}):
        evidence_id = node.get('evidence_id')
        if not isinstance(evidence_id, str) or not evidence_id:
            continue
        if any(evidence_id.startswith(prefix) for prefix in BLOCKED_EVIDENCE_PREFIXES):
            continue
        if not _topic_match(evidence_id, topic, subject_key):
            continue
        available = node.get('available') is True
        value = node.get('value') if available else None
        if _looks_like_review(value):
            continue
        rows.append({
            'evidence_id': evidence_id,
            'label': _label(evidence_id),
            'available': available,
            'value': _public_value(value) if available else None,
            'status': None if available else (node.get('status') or 'unavailable'),
        })
        if len(rows) >= MAX_FACTS:
            break
    return rows


def _topic_match(evidence_id, topic, subject_key):
    topic = (topic or 'growth').strip()
    if topic == 'peer':
        if 'peer' not in evidence_id:
            return False
        if subject_key:
            return f'.{subject_key}.' in evidence_id or f'learning.{subject_key}.' in evidence_id
        return True
    if subject_key:
        needle = f'learning.{subject_key}.'
        return evidence_id.startswith(needle) or f'.{subject_key}.' in evidence_id
    if topic == 'growth':
        return True
    prefixes = TOPIC_PREFIXES.get(topic)
    if not prefixes:
        return True
    return any(evidence_id.startswith(prefix) for prefix in prefixes)


def _walk(node):
    if isinstance(node, dict):
        if 'evidence_id' in node:
            yield node
        for key, value in node.items():
            if key in BLOCKED_KEYS:
                continue
            yield from _walk(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)


def _looks_like_review(value):
    if not isinstance(value, str):
        return False
    if len(value) > 160:
        return True
    lowered = value.casefold()
    return '감상' in lowered or 'review' in lowered


def _public_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, str):
            return value[:120]
        return value
    if isinstance(value, (list, tuple)):
        return [_public_value(item) for item in value[:8]]
    if isinstance(value, dict):
        return {
            str(key): _public_value(item)
            for key, item in list(value.items())[:8]
            if key not in BLOCKED_KEYS
        }
    return str(value)[:80]


def _label(evidence_id):
    if evidence_id in _LABELS:
        return _LABELS[evidence_id]
    parts = [part for part in evidence_id.split('.') if part]
    return ' '.join(parts[-3:]) if parts else evidence_id


def _parse_as_of(raw):
    if raw is None or raw == '':
        return None
    if hasattr(raw, 'isoformat') and not isinstance(raw, str):
        return raw
    return parse_activity_date_text(str(raw).strip())
