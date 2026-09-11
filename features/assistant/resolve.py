"""Nickname resolution. fuzzy는 후보만, 실행은 confirmation 후."""
from __future__ import annotations

from difflib import SequenceMatcher
import unicodedata

from features.assistant.navigation import child_public
from features.reading.access import model_named

CHILD_POOL_LIMIT = 200
SEARCH_LIMIT = 8
FUZZY_MIN_RATIO = 0.78
FUZZY_SECOND_MAX = 0.72
MIN_PARTIAL_LEN = 2
MIN_FUZZY_LEN = 3


def normalize_nickname(value):
    text = unicodedata.normalize('NFKC', str(value or ''))
    for dash in ('‐', '‑', '‒', '–', '—', '―'):
        text = text.replace(dash, '-')
    text = ' '.join(text.split()).strip()
    return text.replace(' -', '-').replace('- ', '-')


def resolve_children(query):
    """exact → unique partial → unique fuzzy(확인 필요) → multiple → none."""
    text = normalize_nickname(query)
    if not text:
        return _result('none', [])

    Child = model_named('Child')
    exact = (
        Child.query.filter(Child.name == text)
        .order_by(Child.grade, Child.name, Child.id)
        .limit(SEARCH_LIMIT)
        .all()
    )
    if len(exact) == 1:
        return _result('exact', exact)
    if len(exact) > 1:
        return _result('multiple', exact, match_type='exact')

    if len(text) >= MIN_PARTIAL_LEN:
        partial = (
            Child.query.filter(Child.name.contains(text))
            .order_by(Child.grade, Child.name, Child.id)
            .limit(SEARCH_LIMIT)
            .all()
        )
        if len(partial) == 1:
            return _result('partial', partial)
        if len(partial) > 1:
            return _result('multiple', partial, match_type='partial')

    if len(text) < MIN_FUZZY_LEN:
        return _result('none', [])

    pool = (
        Child.query.order_by(Child.grade, Child.name, Child.id)
        .limit(CHILD_POOL_LIMIT)
        .all()
    )
    scored = []
    for child in pool:
        name = normalize_nickname(getattr(child, 'name', ''))
        if not name:
            continue
        ratio = SequenceMatcher(None, text, name).ratio()
        if ratio >= FUZZY_MIN_RATIO:
            scored.append((ratio, child))
    scored.sort(key=lambda item: (-item[0], item[1].id))
    if not scored:
        return _result('none', [])
    best_ratio = scored[0][0]
    second_ratio = scored[1][0] if len(scored) > 1 else 0.0
    if best_ratio >= FUZZY_MIN_RATIO and second_ratio < FUZZY_SECOND_MAX:
        return _result('fuzzy', [scored[0][1]], needs_confirmation=True)
    close = [child for ratio, child in scored if ratio >= FUZZY_MIN_RATIO][:SEARCH_LIMIT]
    if len(close) > 1:
        return _result('multiple', close, match_type='fuzzy')
    return _result('none', [])


def select_child_resolution(results):
    """여러 LLM search 요청 중 resolver 단계가 가장 확정적인 결과 하나만 선택한다."""
    rows = [row for row in results or () if isinstance(row, dict)]

    exact = [row for row in rows if row.get('kind') == 'exact']
    if exact:
        return _merge_unique_matches('exact', exact)
    exact_multiple = [
        row for row in rows
        if row.get('kind') == 'multiple' and row.get('match_type') == 'exact'
    ]
    if exact_multiple:
        return exact_multiple[-1]

    partial = [row for row in rows if row.get('kind') == 'partial']
    if partial:
        return _merge_unique_matches('partial', partial)
    partial_multiple = [
        row for row in rows
        if row.get('kind') == 'multiple' and row.get('match_type') in (None, 'partial')
    ]
    if partial_multiple:
        return partial_multiple[-1]

    fuzzy_multiple = [
        row for row in rows
        if row.get('kind') == 'multiple' and row.get('match_type') == 'fuzzy'
    ]
    if fuzzy_multiple:
        return fuzzy_multiple[-1]
    fuzzy = [row for row in rows if row.get('kind') == 'fuzzy']
    if fuzzy:
        return _merge_unique_matches('fuzzy', fuzzy, needs_confirmation=True)
    return rows[-1] if rows else None


def _merge_unique_matches(kind, rows, *, needs_confirmation=False):
    matches = {}
    for row in rows:
        for child in row.get('matches') or ():
            child_id = child.get('id') if isinstance(child, dict) else None
            if child_id is not None:
                matches[child_id] = child
    if len(matches) == 1:
        return {
            'ok': True,
            'kind': kind,
            'match_type': kind,
            'matches': list(matches.values()),
            'count': 1,
            'needs_confirmation': bool(needs_confirmation),
        }
    return {
        'ok': True,
        'kind': 'multiple',
        'match_type': kind,
        'matches': list(matches.values())[:SEARCH_LIMIT],
        'count': len(matches),
        'needs_confirmation': False,
    }


def _result(kind, children, *, needs_confirmation=False, match_type=None):
    matches = [child_public(child) for child in children if child is not None]
    return {
        'ok': True,
        'kind': kind,
        'match_type': match_type or kind,
        'matches': matches,
        'count': len(matches),
        'needs_confirmation': bool(needs_confirmation and kind == 'fuzzy' and len(matches) == 1),
    }
