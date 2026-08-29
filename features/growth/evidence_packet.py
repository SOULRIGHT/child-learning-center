"""Teacher Growth → sanitized whitelist evidence packet.

READ-ONLY projection. metrics/insight/planner를 다시 계산하지 않는다.
DB/ORM query를 하지 않는다. LLM/prompt/validator가 아니다.
"""
from __future__ import annotations

from datetime import date, datetime

from features.growth.copy import (
    HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN,
    LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST,
    POINTS_PERIOD_RECENT_WINDOW_BEST,
    READING_COMPLETIONS_RECENT_WINDOW_BEST,
    READING_DAYS_RECENT_WINDOW_BEST,
)
from features.growth.insights import (
    InsightCandidate,
    generate_insight_candidates,
    top_candidates,
)
from features.growth.learning_metrics import MAX_PROGRESS_SNAPSHOT_AGE_DAYS

# features.growth.service.INSIGHT_LIMIT 과 같아야 한다. service를 import 하지 않는다.
SELECTED_INSIGHT_LIMIT = 3

SCHEMA_VERSION = 'growth_teacher_evidence_v1'
AUDIENCE_TEACHER = 'teacher'

STATUS_INSUFFICIENT_HISTORY = 'insufficient_history'
STATUS_UNAVAILABLE = 'unavailable'

_RWB_READING_DAYS = READING_DAYS_RECENT_WINDOW_BEST
_RWB_COMPLETIONS = READING_COMPLETIONS_RECENT_WINDOW_BEST
_RWB_POINTS = POINTS_PERIOD_RECENT_WINDOW_BEST
_RWB_LEARNING = LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST

_JSON_SCALARS = (str, int, float, bool, type(None))


def build_teacher_evidence_packet(bundle, selected_candidates=None, *, grade=None):
    """deterministic bundle + top candidates → teacher whitelist packet.

    selected_candidates가 없으면 service와 같은 top_candidates(limit=3)를 쓴다.
    계산/원장 조회는 하지 않는다.
    """
    bundle = bundle or {}
    selected = _selected(bundle, selected_candidates)
    selected_ids = {item.id for item in selected}
    reading = bundle.get('reading') or {}
    points = bundle.get('points') or {}
    progress = bundle.get('progress') or {}
    learning = bundle.get('learning') or {}
    recent = bundle.get('recent_window_bests') or {}

    scope = _scope(reading, learning, recent, selected_ids)
    supporting = {
        'reading': _reading_facts(reading, recent, selected_ids),
        'points': _points_facts(points, recent, selected_ids),
        'learning': _learning_facts(
            progress, points, learning, recent, selected_ids, selected,
        ),
    }
    packet = {
        'schema_version': SCHEMA_VERSION,
        'audience': AUDIENCE_TEACHER,
        'as_of': _iso_date(_as_of(bundle)),
        'scope': scope,
        'selected_insights': [_insight_entry(item) for item in selected],
        'supporting_facts': supporting,
    }
    grade_value = _grade(grade)
    if grade_value is not None:
        packet['grade'] = grade_value
    return _to_jsonable(packet)


def _selected(bundle, selected_candidates):
    if selected_candidates is not None:
        return list(selected_candidates)
    return top_candidates(generate_insight_candidates(bundle), limit=SELECTED_INSIGHT_LIMIT)


def _as_of(bundle):
    for key in ('reading', 'points', 'progress', 'learning', 'recent_window_bests'):
        value = (bundle.get(key) or {}).get('as_of')
        if value is not None:
            return value
    return None


def _scope(reading, learning, recent, selected_ids):
    scope = {
        'window_days': reading.get('window_days') or learning.get('window_days') or 30,
        'current_window': _window(reading.get('current_window') or learning.get('current_window')),
        'previous_window': _window(reading.get('previous_window') or learning.get('previous_window')),
        'freshness': {
            'max_snapshot_age_days': int(
                learning.get('max_snapshot_age_days') or MAX_PROGRESS_SNAPSHOT_AGE_DAYS
            ),
        },
    }
    if selected_ids & {_RWB_READING_DAYS, _RWB_COMPLETIONS, _RWB_POINTS, _RWB_LEARNING}:
        scope['recent_windows'] = {
            'window_days': recent.get('window_days') or 30,
            'window_count': recent.get('window_count') or 3,
            'lookback_days': recent.get('lookback_days') or 90,
            'current_window': _window(recent.get('current_window')),
            'previous_1_window': _window(recent.get('previous_1_window')),
            'previous_2_window': _window(recent.get('previous_2_window')),
        }
    return scope


def _reading_facts(reading, recent, selected_ids):
    comparable = (reading.get('comparable') or {}).get('reading_days') is True
    completed_ok = (reading.get('comparable') or {}).get('completed') is True
    current = reading.get('current') or {}
    previous = reading.get('previous') or {}
    facts = {
        'activity_days': _period_pair(
            'reading.activity_days',
            current.get('reading_days'),
            previous.get('reading_days'),
            comparable=comparable,
        ),
        'completions': _period_pair(
            'reading.completions',
            current.get('completed_count'),
            previous.get('completed_count'),
            comparable=completed_ok,
        ),
    }
    if _RWB_READING_DAYS in selected_ids:
        facts['recent_window_activity_days'] = _rwb_block(
            'reading.rwb.activity_days', recent.get('reading_days') or {},
        )
    if _RWB_COMPLETIONS in selected_ids:
        facts['recent_window_completions'] = _rwb_block(
            'reading.rwb.completions', recent.get('reading_completions') or {},
        )
    pair_ok = (reading.get('comparable') or {}).get('experience_rating_pair') is True
    if pair_ok and HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN in selected_ids:
        facts['experience_rating_pair'] = _rating_pair(reading)
    return facts


def _rating_pair(reading):
    current = (reading.get('current') or {}).get('paired_experience_rating') or {}
    previous = (reading.get('previous') or {}).get('paired_experience_rating') or {}
    n_current = current.get('sample_count')
    n_previous = previous.get('sample_count')
    return {
        'comparable': True,
        'n_current': _measured('reading.experience.n.current', n_current, available=n_current is not None),
        'n_previous': _measured('reading.experience.n.previous', n_previous, available=n_previous is not None),
        'difficulty': _period_pair(
            'reading.experience.difficulty',
            current.get('difficulty_average'),
            previous.get('difficulty_average'),
            comparable=True,
        ),
        'fun': _period_pair(
            'reading.experience.fun',
            current.get('fun_average'),
            previous.get('fun_average'),
            comparable=True,
        ),
    }


def _points_facts(points, recent, selected_ids):
    comparable = (points.get('comparable') or {}).get('points') is True
    current = points.get('current') or {}
    previous = points.get('previous') or {}
    facts = {
        'period': _period_pair(
            'points.period',
            current.get('period_points'),
            previous.get('period_points'),
            comparable=comparable,
        ),
        'cumulative_as_of': _cumulative_fact(points.get('cumulative_as_of')),
    }
    if _RWB_POINTS in selected_ids:
        facts['recent_window'] = _rwb_block('points.rwb.period', recent.get('points') or {})
    return facts


def _cumulative_fact(value):
    if value is None:
        return _measured('points.cumulative_as_of', None, available=False, status=STATUS_UNAVAILABLE)
    return _measured('points.cumulative_as_of', value, available=True)


def _learning_facts(progress, points, learning, recent, selected_ids, selected):
    progress_comparable = (progress.get('comparable') or {}).get('progress') is True
    current = progress.get('current') or {}
    previous = progress.get('previous') or {}
    observed = learning.get('observed_study_days') or {}
    points_comparable = (points.get('comparable') or {}).get('points') is True
    rwb_subjects = set()
    if _RWB_LEARNING in selected_ids:
        for item in selected:
            if item.id != _RWB_LEARNING:
                continue
            for row in (item.evidence or {}).get('subjects') or []:
                key = row.get('subject_key')
                if key:
                    rwb_subjects.add(key)
    subjects = {}
    rwb_learning = recent.get('learning') or {}
    for key, payload in (learning.get('subjects') or {}).items():
        subjects[key] = _subject_facts(
            key,
            payload,
            rwb_learning.get(key) if key in rwb_subjects else None,
        )
    return {
        'progress_entry_count': _period_pair(
            'learning.progress_entry_count',
            current.get('progress_entry_count'),
            previous.get('progress_entry_count'),
            comparable=progress_comparable,
        ),
        'observed_study_days': _observed_study_days(observed, comparable=points_comparable),
        'subjects': subjects,
    }


def _observed_study_days(observed, *, comparable):
    return {
        'source': observed.get('source') or 'daily_points.date',
        'proxy': observed.get('proxy') or 'point_activity_days',
        'attendance': False,
        **_period_pair(
            'learning.observed_study_days',
            observed.get('current'),
            observed.get('previous'),
            comparable=comparable,
        ),
    }


def _subject_facts(subject_key, payload, rwb_fact):
    snapshot = payload.get('current_snapshot') or {}
    advance = payload.get('page_advance') or {}
    peer = payload.get('peer') or {}
    plan = payload.get('plan') or {}
    facts = {
        'subject_key': subject_key,
        'subject_label': payload.get('subject_name') or subject_key,
        'current_snapshot': _snapshot_facts(subject_key, snapshot),
        'page_advance': _page_advance_facts(subject_key, advance),
        'peer': _peer_facts(subject_key, peer),
        'plan': _plan_facts(subject_key, plan),
    }
    if rwb_fact:
        facts['recent_window'] = _rwb_block(
            f'learning.{subject_key}.rwb.page_advance', rwb_fact,
        )
    return facts


def _snapshot_facts(subject_key, snapshot):
    prefix = f'learning.{subject_key}.snapshot'
    available = snapshot.get('available') is True
    stale = snapshot.get('stale')
    status = 'stale' if stale else ('ok' if available else 'no_snapshot')
    facts = {
        'available': available,
        'status': status,
        'stale': bool(stale) if stale is not None else None,
        'page': _measured(
            f'{prefix}.current_page',
            snapshot.get('page'),
            available=available and snapshot.get('page') is not None,
            status=None if available else status,
        ),
        'recorded_on': _measured(
            f'{prefix}.recorded_on',
            _iso_date(snapshot.get('recorded_on')),
            available=available and snapshot.get('recorded_on') is not None,
            status=None if available else status,
        ),
    }
    title = snapshot.get('textbook_title')
    if title:
        facts['textbook_title'] = title
    return facts


def _page_advance_facts(subject_key, advance):
    prefix = f'learning.{subject_key}.page_advance'
    current = advance.get('current') or {}
    previous = advance.get('previous') or {}
    trend_ok = advance.get('comparable') is True
    return {
        'comparable': trend_ok,
        'status': advance.get('status') or STATUS_UNAVAILABLE,
        'current': _advance_side(f'{prefix}.current', current),
        'previous': _advance_side(f'{prefix}.previous', previous),
        'delta': _measured(
            f'{prefix}.delta',
            advance.get('delta'),
            available=trend_ok and advance.get('delta') is not None,
            status=None if trend_ok else (advance.get('status') or STATUS_INSUFFICIENT_HISTORY),
        ),
    }


def _advance_side(evidence_id, side):
    available = side.get('available') is True
    status = side.get('status') or (None if available else STATUS_UNAVAILABLE)
    fact = _measured(
        evidence_id,
        side.get('value'),
        available=available,
        status=None if available else status,
    )
    window = _window(side.get('window'))
    if window:
        fact['window'] = window
    title = side.get('textbook_title')
    if title:
        fact['textbook_title'] = title
    if status:
        fact['status'] = status if not available else side.get('status') or 'ok'
    return fact


def _peer_facts(subject_key, peer):
    prefix = f'learning.{subject_key}.peer'
    available = peer.get('available') is True
    status = peer.get('status') or (None if available else STATUS_UNAVAILABLE)
    n = peer.get('peer_n')
    facts = {
        'available': available,
        'status': status,
        'n': _measured(f'{prefix}.n', n if n is not None else 0, available=True),
    }
    title = peer.get('textbook_title')
    if title:
        facts['textbook_title'] = title
    if peer.get('current_page') is not None:
        facts['current_page'] = _measured(
            f'{prefix}.current_page', peer.get('current_page'), available=True,
        )
    if available:
        facts['median'] = _measured(f'{prefix}.median', peer.get('peer_median'), available=True)
        if peer.get('gap') is not None:
            facts['gap'] = _measured(f'{prefix}.gap', peer.get('gap'), available=True)
    return facts


def _plan_facts(subject_key, plan):
    prefix = f'learning.{subject_key}.plan'
    status = plan.get('status') or 'no_snapshot'
    facts = {'status': status}
    title = plan.get('textbook_title')
    if title:
        facts['textbook_title'] = title
    kind = plan.get('workload_kind')
    if kind in ('exact', 'estimated'):
        facts['workload_kind'] = kind
        facts['workload_kind_fact'] = _measured(
            f'{prefix}.workload_kind', kind, available=True,
        )
    remaining = plan.get('remaining_workload')
    if remaining is not None:
        facts['remaining_workload'] = _measured(
            f'{prefix}.remaining_workload', remaining, available=True,
        )
    days = plan.get('remaining_planned_study_days')
    if days is not None:
        facts['remaining_planned_days'] = _measured(
            f'{prefix}.remaining_planned_days', days, available=True,
        )
    required = plan.get('required_per_planned_day')
    if required is not None:
        facts['required_per_planned_day'] = _measured(
            f'{prefix}.required_per_day', required, available=True,
        )
    target = plan.get('target_completion_date')
    if target is not None:
        facts['target_completion_date'] = _measured(
            f'{prefix}.target_completion_date', _iso_date(target), available=True,
        )
    source = plan.get('weekday_source')
    if source:
        facts['weekday_source'] = source
    weekdays = plan.get('effective_weekdays')
    if weekdays is not None:
        facts['effective_weekdays'] = list(weekdays)
    return facts


def _rwb_block(prefix, fact):
    status = fact.get('status') or STATUS_INSUFFICIENT_HISTORY
    current = fact.get('current') or {}
    ok = status == 'ok' and fact.get('is_recent_window_best') is not None
    block = {
        'status': status,
        'is_recent_window_best': fact.get('is_recent_window_best'),
        'current': _rwb_side(f'{prefix}.current', current, available=ok or current.get('available') is True),
        'previous_1': _rwb_side(f'{prefix}.previous_1', fact.get('previous_1') or {}),
        'previous_2': _rwb_side(f'{prefix}.previous_2', fact.get('previous_2') or {}),
        'historical_best': _measured(
            f'{prefix}.historical_best',
            fact.get('historical_best'),
            available=fact.get('historical_best') is not None,
            status=None if fact.get('historical_best') is not None else status,
        ),
        'margin': _measured(
            f'{prefix}.margin',
            fact.get('margin'),
            available=fact.get('margin') is not None,
            status=None if fact.get('margin') is not None else status,
        ),
    }
    best_window = _window(fact.get('historical_best_window'))
    if best_window:
        block['historical_best_window'] = best_window
    title = current.get('textbook_title') or fact.get('textbook_title')
    if title:
        block['textbook_title'] = title
    return block


def _rwb_side(evidence_id, side, available=None):
    if available is None:
        available = side.get('available') is True and side.get('value') is not None
    fact = _measured(
        evidence_id,
        side.get('value'),
        available=available,
        status=None if available else (STATUS_INSUFFICIENT_HISTORY if side.get('available') is False else STATUS_UNAVAILABLE),
    )
    window = _window(side) if side.get('start') is not None else _window({
        'start': side.get('start'),
        'end': side.get('end'),
    })
    if side.get('start') is not None and side.get('end') is not None:
        fact['window'] = {'start': _iso_date(side.get('start')), 'end': _iso_date(side.get('end'))}
    elif window:
        fact['window'] = window
    return fact


def _period_pair(prefix, current, previous, *, comparable):
    current_ok = comparable and current is not None
    previous_ok = comparable and previous is not None
    delta = None
    delta_ok = current_ok and previous_ok
    if delta_ok:
        delta = current - previous
    return {
        'comparable': bool(comparable),
        'current': _measured(
            f'{prefix}.current',
            current,
            available=current_ok,
            status=None if current_ok else STATUS_INSUFFICIENT_HISTORY,
        ),
        'previous': _measured(
            f'{prefix}.previous',
            previous,
            available=previous_ok,
            status=None if previous_ok else STATUS_INSUFFICIENT_HISTORY,
        ),
        'delta': _measured(
            f'{prefix}.delta',
            delta,
            available=delta_ok,
            status=None if delta_ok else STATUS_INSUFFICIENT_HISTORY,
        ),
    }


def _insight_entry(candidate):
    evidence = dict(candidate.evidence or {})
    evidence.pop('relative_change', None)
    payload = {
        'id': candidate.id,
        'category': candidate.category,
        'direction': candidate.direction,
        'metric_key': candidate.metric_key,
        'evidence_ids': _insight_evidence_ids(candidate),
        'evidence': _insight_evidence(evidence),
    }
    return payload


def _insight_evidence_ids(candidate):
    metric = candidate.metric_key
    evidence = candidate.evidence or {}
    kind = evidence.get('kind')
    if kind == 'recent_window_best':
        if candidate.id == _RWB_READING_DAYS:
            return _rwb_ids('reading.rwb.activity_days')
        if candidate.id == _RWB_COMPLETIONS:
            return _rwb_ids('reading.rwb.completions')
        if candidate.id == _RWB_POINTS:
            return _rwb_ids('points.rwb.period')
        if candidate.id == _RWB_LEARNING:
            ids = []
            for row in evidence.get('subjects') or []:
                key = row.get('subject_key')
                if key:
                    ids.extend(_rwb_ids(f'learning.{key}.rwb.page_advance'))
            return ids
    if metric == 'reading_days':
        return _period_ids('reading.activity_days')
    if metric == 'completed_count':
        return _period_ids('reading.completions')
    if metric == 'period_points':
        return _period_ids('points.period')
    if metric == 'progress_entry_count':
        return _period_ids('learning.progress_entry_count')
    if metric == 'paired_experience_rating':
        return [
            'reading.experience.difficulty.current',
            'reading.experience.difficulty.previous',
            'reading.experience.fun.current',
            'reading.experience.fun.previous',
            'reading.experience.n.current',
            'reading.experience.n.previous',
        ]
    return []


def _period_ids(prefix):
    return [f'{prefix}.current', f'{prefix}.previous', f'{prefix}.delta']


def _rwb_ids(prefix):
    return [
        f'{prefix}.current',
        f'{prefix}.previous_1',
        f'{prefix}.previous_2',
        f'{prefix}.historical_best',
        f'{prefix}.margin',
    ]


def _insight_evidence(evidence):
    payload = {}
    for key in (
        'kind', 'source', 'metric_key', 'comparable',
        'window_days', 'window_count', 'lookback_days', 'comparison_window_count',
        'current', 'previous', 'delta', 'historical_best', 'margin',
        'n_current', 'n_previous',
    ):
        if key in evidence:
            payload[key] = _json_leaf(evidence.get(key))
    for key in (
        'current_window', 'previous_window', 'historical_best_window',
        'previous_1_window', 'previous_2_window',
    ):
        if key in evidence:
            payload[key] = _window(evidence.get(key)) or _json_leaf(evidence.get(key))
    subjects = evidence.get('subjects')
    if subjects:
        payload['subjects'] = [_insight_subject(row) for row in subjects]
    return payload


def _insight_subject(row):
    return {
        'subject_key': row.get('subject_key'),
        'subject_label': row.get('subject_label'),
        'textbook_title': row.get('textbook_title'),
        'current_advance': row.get('current_advance'),
        'historical_best': row.get('historical_best'),
        'margin': row.get('margin'),
        'current_window': _window(row.get('current_window')),
        'historical_best_window': _window(row.get('historical_best_window')),
    }


def _measured(evidence_id, value, *, available, status=None):
    fact = {
        'evidence_id': evidence_id,
        'available': bool(available),
    }
    if available:
        fact['value'] = value
    elif status:
        fact['status'] = status
    return fact


def _window(window):
    if not isinstance(window, dict):
        return None
    start = window.get('start')
    end = window.get('end')
    if start is None or end is None:
        return None
    return {'start': _iso_date(start), 'end': _iso_date(end)}


def _iso_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value
    raise TypeError(f'unsupported date type: {type(value)!r}')


def _grade(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    return None


def _json_leaf(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, _JSON_SCALARS):
        return value
    if isinstance(value, dict):
        return {str(key): _json_leaf(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_leaf(item) for item in value]
    return value


def _to_jsonable(value):
    if isinstance(value, _JSON_SCALARS):
        return value
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if getattr(value, '_sa_instance_state', None) is not None:
        raise TypeError('ORM object is not allowed in evidence packet')
    if isinstance(value, InsightCandidate):
        raise TypeError('InsightCandidate is not allowed in evidence packet')
    raise TypeError(f'unsupported packet type: {type(value)!r}')


def collect_evidence_ids(packet):
    """packet 안의 evidence_id 필드 값. 등장 순서를 유지한다."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            evidence_id = node.get('evidence_id')
            if isinstance(evidence_id, str):
                found.append(evidence_id)
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(packet)
    return found
