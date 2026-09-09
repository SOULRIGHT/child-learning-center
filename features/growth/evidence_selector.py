"""Overall Growth AI v3 deterministic evidence selector.

LLM이 tier를 정하지 않는다. Product Contract threshold만 사용한다.
중요도 0~100 heuristic / POINTS_PERIOD_DELTA_MIN 승격 / 통계적 이상치 제거를 하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from features.reading.analysis import TIER_LIMITED, TIER_MAJOR, TIER_NO_CHANGE
from features.study.metrics import MAJOR_DELTA_PP
from features.study.peer import (
    DISPLAY_LIMITED,
    DISPLAY_NONE,
    DISPLAY_PRIMARY,
    DISPLAY_REFERENCE,
)

TIER_MAJOR_LABEL = 'major'
TIER_SUPPORTING = 'supporting'
TIER_REFERENCE = 'reference'
TIER_UNAVAILABLE = 'unavailable'

SELECTED_MAJOR_LIMIT = 4

COVERAGE_REFERENCE_PP = 5.0
COVERAGE_SUPPORTING_PP = 10.0

READING_MAJOR_MIN = 5
READING_SUPPORTING_MIN = 3


@dataclass(frozen=True)
class EvidenceCandidate:
    id: str
    category: str
    tier: str
    direction: str
    metric_key: str
    evidence_ids: tuple
    evidence: dict


def select_evidence_candidates(supporting_facts):
    """supporting_facts → 모든 candidate. 높은/낮다는 이유로 제거하지 않는다."""
    facts = supporting_facts or {}
    found = []
    found.extend(_learning_candidates(facts.get('learning') or {}))
    found.extend(_peer_candidates(facts.get('learning') or {}))
    found.extend(_points_candidates(facts.get('points') or {}))
    found.extend(_reading_candidates(facts.get('reading') or {}))
    return found


def select_major_insights(supporting_facts, limit=SELECTED_MAJOR_LIMIT):
    majors = [
        item for item in select_evidence_candidates(supporting_facts)
        if item.tier == TIER_MAJOR_LABEL
    ]
    return majors[: max(0, int(limit))]


def _learning_candidates(learning):
    found = []
    for key, payload in (learning.get('subjects') or {}).items():
        compare = (payload or {}).get('compare') or {}
        performance = (payload or {}).get('performance') or {}
        prefix = f'learning.{key}.performance'
        ids = (
            f'{prefix}.rate.current',
            f'{prefix}.rate.previous',
            f'{prefix}.delta_pp',
            f'{prefix}.confirmation.current',
            f'{prefix}.enough_days',
        )
        band = compare.get('confirmation_band')
        enough = compare.get('enough_days') is True
        eligible = compare.get('major_insight_eligible') is True
        delta = _fact_value(compare.get('performance_delta_pp'))
        if not enough:
            tier = TIER_UNAVAILABLE
        elif band in ('unavailable', 'forbidden'):
            tier = TIER_UNAVAILABLE
        elif band == 'limited':
            tier = TIER_SUPPORTING
        elif eligible:
            tier = TIER_MAJOR_LABEL
        elif delta is not None and abs(float(delta)) < MAJOR_DELTA_PP:
            tier = TIER_REFERENCE
        else:
            tier = TIER_SUPPORTING
        found.append(EvidenceCandidate(
            id=f'learning.{key}.period_change.performance',
            category='learning',
            tier=tier,
            direction=_direction(delta),
            metric_key='performance_rate',
            evidence_ids=ids,
            evidence={
                'subject_key': key,
                'confirmation_band': band,
                'enough_days': enough,
                'major_insight_eligible': eligible,
                'performance_delta_pp': delta,
                'current_rate': _fact_value((performance.get('current') or {}).get('performance_rate')),
            },
        ))
    return found


def _peer_candidates(learning):
    found = []
    for key, payload in (learning.get('subjects') or {}).items():
        found.append(_one_peer_candidate(
            subject_key=key,
            metric='performance_rate',
            peer=(payload or {}).get('performance_peer') or {},
            prefix=f'learning.{key}.performance_peer',
            coverage=False,
        ))
        found.append(_one_peer_candidate(
            subject_key=key,
            metric='coverage_ratio',
            peer=(payload or {}).get('coverage_peer') or {},
            prefix=f'learning.{key}.coverage_peer',
            coverage=True,
        ))
    return found


def _one_peer_candidate(*, subject_key, metric, peer, prefix, coverage):
    n = _peer_n(peer)
    display = peer.get('display_tier') or DISPLAY_NONE
    diff = _peer_diff_pp(peer) if coverage else None
    ids = (
        f'{prefix}.child_value',
        f'{prefix}.peer_median',
        f'{prefix}.difference',
        f'{prefix}.n',
    )
    if display == DISPLAY_NONE or n <= 1:
        tier = TIER_UNAVAILABLE
    elif display == DISPLAY_REFERENCE or n == 2:
        tier = TIER_REFERENCE
    elif coverage:
        if display == DISPLAY_LIMITED:
            if diff is None or abs(diff) < COVERAGE_REFERENCE_PP:
                tier = TIER_REFERENCE
            else:
                tier = TIER_SUPPORTING
        elif diff is None or abs(diff) < COVERAGE_REFERENCE_PP:
            tier = TIER_REFERENCE
        elif abs(diff) < COVERAGE_SUPPORTING_PP:
            tier = TIER_SUPPORTING
        elif display == DISPLAY_PRIMARY:
            tier = TIER_MAJOR_LABEL
        else:
            tier = TIER_SUPPORTING
    else:
        # performance peer: 계약에 없는 major threshold를 만들지 않는다.
        if display == DISPLAY_PRIMARY:
            tier = TIER_SUPPORTING
        elif display == DISPLAY_LIMITED:
            tier = TIER_SUPPORTING
        else:
            tier = TIER_REFERENCE
    return EvidenceCandidate(
        id=f'learning.{subject_key}.peer.{metric}',
        category='peer',
        tier=tier,
        direction=_direction(peer.get('difference')),
        metric_key=metric,
        evidence_ids=ids,
        evidence={
            'subject_key': subject_key,
            'display_tier': display,
            'peer_sample_count': n,
            'difference': peer.get('difference'),
            'difference_pp': diff,
            'reason': peer.get('reason'),
        },
    )


def _points_candidates(points):
    peer = points.get('peer') or {}
    n = _peer_n(peer)
    display = peer.get('display_tier') or DISPLAY_NONE
    if display == DISPLAY_NONE or n <= 1:
        tier = TIER_UNAVAILABLE
    elif display == DISPLAY_REFERENCE or n == 2:
        tier = TIER_REFERENCE
    else:
        tier = TIER_SUPPORTING
    period = points.get('period') or {}
    delta = ((period.get('delta') or {}).get('value') if isinstance(period.get('delta'), dict) else None)
    return [
        EvidenceCandidate(
            id='points.period.supporting',
            category='points',
            tier=TIER_SUPPORTING if (period.get('comparable') is True) else TIER_REFERENCE,
            direction=_direction(delta),
            metric_key='period_points',
            evidence_ids=('points.period.current', 'points.period.previous', 'points.period.delta'),
            evidence={'delta': delta},
        ),
        EvidenceCandidate(
            id='points.peer.period_points',
            category='peer',
            tier=tier,
            direction=_direction(peer.get('difference')),
            metric_key='period_points',
            evidence_ids=(
                'points.peer.child_value',
                'points.peer.peer_median',
                'points.peer.difference',
                'points.peer.n',
            ),
            evidence={
                'display_tier': display,
                'peer_sample_count': n,
                'difference': peer.get('difference'),
                'reason': peer.get('reason'),
            },
        ),
    ]


def _reading_candidates(reading):
    analysis = reading.get('analysis') or {}
    ai_status = analysis.get('ai_status')
    recent = _count(analysis.get('recent_count'))
    previous = _count(analysis.get('previous_count'))
    sufficiency = analysis.get('sufficiency')
    ids = []
    observations = analysis.get('observations') or []
    for index, _row in enumerate(observations):
        ids.append(f'reading.analysis.observation.{index + 1}')
    if not ids:
        ids = (
            'reading.analysis.recent_count',
            'reading.analysis.previous_count',
            'reading.analysis.sufficiency',
        )
    if ai_status != 'current' or not observations:
        return [EvidenceCandidate(
            id='reading.ai.observation',
            category='reading',
            tier=TIER_UNAVAILABLE,
            direction='none',
            metric_key='reading_observation',
            evidence_ids=('reading.analysis.ai_status', 'reading.analysis.sufficiency'),
            evidence={
                'ai_status': ai_status,
                'sufficiency': sufficiency,
                'recent_count': recent,
                'previous_count': previous,
            },
        )]
    if recent is None or previous is None or recent <= 2 or previous <= 2 or sufficiency == TIER_NO_CHANGE:
        tier = TIER_UNAVAILABLE
    elif recent >= READING_MAJOR_MIN and previous >= READING_MAJOR_MIN and sufficiency == TIER_MAJOR:
        tier = TIER_MAJOR_LABEL
    elif recent >= READING_SUPPORTING_MIN and previous >= READING_SUPPORTING_MIN:
        tier = TIER_SUPPORTING
    else:
        tier = TIER_UNAVAILABLE
    return [EvidenceCandidate(
        id='reading.ai.observation',
        category='reading',
        tier=tier,
        direction='none',
        metric_key='reading_observation',
        evidence_ids=tuple(ids),
        evidence={
            'ai_status': ai_status,
            'sufficiency': sufficiency,
            'recent_count': recent,
            'previous_count': previous,
        },
    )]


def _peer_n(peer):
    n_fact = peer.get('peer_sample_count')
    if isinstance(n_fact, dict):
        value = n_fact.get('value') if n_fact.get('available') is not False else n_fact.get('value')
        if value is None:
            value = 0
        return int(value)
    if n_fact is None:
        return 0
    try:
        return int(n_fact)
    except (TypeError, ValueError):
        return 0


def _peer_diff_pp(peer):
    diff_fact = peer.get('difference')
    if isinstance(diff_fact, dict):
        value = diff_fact.get('value') if diff_fact.get('available') else None
    else:
        value = diff_fact
    if value is None:
        return None
    try:
        return abs(float(value)) * 100.0
    except (TypeError, ValueError):
        return None


def _count(value):
    if isinstance(value, dict):
        return value.get('value') if value.get('available') is not False else None
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _fact_value(node):
    if isinstance(node, dict) and ('available' in node or 'value' in node or 'evidence_id' in node):
        if node.get('available') is False:
            return None
        return node.get('value')
    return node


def _direction(delta):
    if delta is None:
        return 'none'
    try:
        number = float(delta)
    except (TypeError, ValueError):
        return 'none'
    if number > 0:
        return 'up'
    if number < 0:
        return 'down'
    return 'none'
