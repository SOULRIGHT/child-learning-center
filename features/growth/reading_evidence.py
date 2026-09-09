"""Overall Growth용 Reading safe adapter.

ReadingDay.review_text / raw selected records / prompt / Guardrail / fingerprint
raw_texts 를 Overall Evidence로 넘기지 않는다.
"""
from __future__ import annotations

from features.reading.analysis import build_public_facts
from features.reading.ai.runtime import load_reading_ai_view
from features.growth.windows import resolve_as_of

AI_STATUS_CURRENT = 'current'
AI_STATUS_STALE = 'stale'
AI_STATUS_NONE = 'none'
AI_STATUS_UNAVAILABLE = 'unavailable'
AI_STATUS_INSUFFICIENT = 'insufficient'

_SAFE_FACT_KEYS = (
    'as_of',
    'analyzer_version',
    'window',
    'text_record_count',
    'recent_count',
    'previous_count',
    'sufficiency',
    'character_count',
    'sentence_count',
    'completed_count',
    'completion_duration_median',
    'recent_records',
    'previous_records',
)

_SAFE_RECORD_KEYS = ('record_id', 'date', 'book_title', 'status', 'program_type')
_SAFE_OBSERVATION_KEYS = ('dimension', 'observation', 'evidence_refs')
_SAFE_REF_KEYS = ('record_id', 'date', 'book_title')


def growth_reading_evidence(child_id, as_of=None):
    """Overall Growth packet이 쓸 수 있는 safe reading facts + current observation.

    Overall 생성 자체를 Reading AI 상태 때문에 막지 않는다.
    stale SUCCESS observation 은 포함하지 않는다.
    """
    as_of = resolve_as_of(as_of)
    facts = _safe_public_facts(child_id, as_of)
    payload = {
        'as_of': as_of.isoformat() if hasattr(as_of, 'isoformat') else str(as_of),
        'facts': facts,
        'ai_status': AI_STATUS_UNAVAILABLE,
        'observations': [],
        'limitations': [],
        'allowed_evidence_refs': _record_refs(facts),
    }
    try:
        view = load_reading_ai_view(child_id, as_of=as_of)
    except Exception:
        _assert_no_raw(payload)
        return payload

    status = _ai_status_from_view(view)
    payload['ai_status'] = status
    if status == AI_STATUS_CURRENT:
        output = view.get('output') or {}
        payload['observations'] = _safe_observations(output.get('observations') or [])
        payload['limitations'] = _safe_limitations(output.get('limitations') or [])
    _assert_no_raw(payload)
    return payload


def _safe_public_facts(child_id, as_of):
    try:
        facts = build_public_facts(child_id, as_of=as_of)
    except Exception:
        return {
            'as_of': as_of.isoformat() if hasattr(as_of, 'isoformat') else str(as_of),
            'recent_count': 0,
            'previous_count': 0,
            'sufficiency': None,
            'recent_records': [],
            'previous_records': [],
            'available': False,
        }
    safe = {key: facts.get(key) for key in _SAFE_FACT_KEYS if key in facts}
    safe['recent_records'] = [_safe_record(row) for row in (facts.get('recent_records') or [])]
    safe['previous_records'] = [_safe_record(row) for row in (facts.get('previous_records') or [])]
    return safe


def _ai_status_from_view(view):
    state = (view or {}).get('state')
    if state == 'current':
        return AI_STATUS_CURRENT
    if state == 'stale':
        return AI_STATUS_STALE
    if state == 'insufficient':
        return AI_STATUS_INSUFFICIENT
    if state in ('none',):
        return AI_STATUS_NONE
    return AI_STATUS_UNAVAILABLE


def _safe_record(row):
    if not isinstance(row, dict):
        return {}
    return {key: row.get(key) for key in _SAFE_RECORD_KEYS if key in row}


def _safe_observations(rows):
    found = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = {key: row.get(key) for key in _SAFE_OBSERVATION_KEYS if key in row}
        refs = []
        for ref in item.get('evidence_refs') or []:
            if not isinstance(ref, dict):
                continue
            refs.append({key: ref.get(key) for key in _SAFE_REF_KEYS if key in ref})
        item['evidence_refs'] = refs
        found.append(item)
    return found


def _safe_limitations(rows):
    found = []
    for row in rows:
        if isinstance(row, str) and row.strip():
            found.append(row.strip())
    return found


def _record_refs(facts):
    refs = []
    for key in ('recent_records', 'previous_records'):
        for row in facts.get(key) or []:
            if isinstance(row, dict) and row.get('record_id') is not None:
                refs.append({
                    'record_id': row.get('record_id'),
                    'date': row.get('date'),
                    'book_title': row.get('book_title'),
                })
    return refs


def _assert_no_raw(value):
    blob = value if isinstance(value, str) else _json_blob(value)
    lowered = blob.lower()
    if 'review_text' in lowered or 'raw_texts' in lowered:
        raise RuntimeError('growth reading evidence must not contain raw reading text')


def _json_blob(value):
    import json
    return json.dumps(value, ensure_ascii=False, default=str)
