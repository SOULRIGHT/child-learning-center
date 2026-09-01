"""Developer-only: 5 synthetic Luna probes for B3 design notes.

instance DB / Growth route / production code를 사용하지 않는다.
기존 test fixture 형태를 복제하고 build_teacher_evidence_packet()만 재사용한다.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features.growth.evidence_packet import build_teacher_evidence_packet
from features.growth.windows import current_window, previous_window
from features.planning.workload import WORKLOAD_KIND_ESTIMATED
from scripts.debug.growth_ai_smoke import load_local_env

AS_OF = date(2026, 12, 15)
CURRENT = current_window(AS_OF, 30)
PREV = previous_window(AS_OF, 30)


def _windows():
    return CURRENT, PREV


def _reading(*, days=(4, 2), completed=(1, 0), comparable=True):
    current, previous = _windows()
    empty_pair = {'sample_count': 0, 'difficulty_average': None, 'fun_average': None}
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current,
        'previous_window': previous,
        'available_from': {
            'reading_days': PREV['start'] if comparable else CURRENT['start'],
            'completed': PREV['start'] if comparable else CURRENT['start'],
            'experience_rating_pair': None,
        },
        'comparable': {
            'reading_days': comparable,
            'completed': comparable,
            'experience_rating_pair': False,
        },
        'current': {
            'reading_days': days[0],
            'completed_count': completed[0],
            'paired_experience_rating': empty_pair,
        },
        'previous': {
            'reading_days': days[1],
            'completed_count': completed[1],
            'paired_experience_rating': empty_pair,
        },
    }


def _progress(*, counts=(3, 1), comparable=True):
    current, previous = _windows()
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current,
        'previous_window': previous,
        'available_from': {'progress': PREV['start'] if comparable else None},
        'comparable': {'progress': comparable},
        'current': {'progress_entry_count': counts[0], 'progress_entry_count_by_subject': {}},
        'previous': {'progress_entry_count': counts[1], 'progress_entry_count_by_subject': {}},
        'latest_snapshot_by_subject': {},
    }


def _points(*, values=(400, 100), comparable=True, cumulative=1200):
    current, previous = _windows()
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current,
        'previous_window': previous,
        'available_from': {'points': PREV['start'] if comparable else None},
        'comparable': {'points': comparable},
        'current': {'period_points': values[0], 'point_activity_days': 4, 'manual_points_sum': 0},
        'previous': {'period_points': values[1], 'point_activity_days': 2, 'manual_points_sum': 0},
        'cumulative_as_of': cumulative,
        'current_cumulative': cumulative,
        'child_cumulative_points': 99999,
    }


def _advance(value, *, status='ok', available=True, title='수학 3-2', window=None):
    return {
        'value': value if available else None,
        'available': available,
        'comparable': available,
        'status': status,
        'textbook_title': title,
        'window': window or dict(CURRENT),
    }


def _subject(
    key='math',
    name='수학',
    *,
    page=40,
    title='수학 3-2',
    recorded_on=date(2026, 12, 10),
    stale=False,
    snapshot_available=True,
    current_advance=20,
    previous_advance=10,
    delta=10,
    advance_status='ok',
    current_available=True,
    previous_available=True,
    trend_comparable=True,
    peer_n=0,
    peer_median=None,
    peer_gap=None,
    peer_available=False,
    peer_status='no_peers',
    plan_status='no_plan',
    workload_kind=None,
    remaining=None,
    days=None,
    required=None,
    target=None,
    weekday_source='center_default',
    weekdays=(0, 1, 2, 3, 4),
):
    return {
        'subject_key': key,
        'subject_name': name,
        'current_snapshot': {
            'textbook_title': title if snapshot_available else None,
            'page': page if snapshot_available else None,
            'recorded_on': recorded_on if snapshot_available else None,
            'age_days': 5 if snapshot_available else None,
            'stale': stale,
            'available': snapshot_available,
        },
        'page_advance': {
            'current': _advance(
                current_advance,
                status=advance_status if current_available else advance_status,
                available=current_available,
                title=title,
                window=dict(CURRENT),
            ),
            'previous': _advance(
                previous_advance,
                status='ok' if previous_available else 'no_baseline',
                available=previous_available,
                title=title,
                window=dict(PREV),
            ),
            'delta': delta if trend_comparable else None,
            'comparable': trend_comparable,
            'status': advance_status,
        },
        'peer': {
            'textbook_title': title,
            'current_page': page,
            'peer_median': peer_median,
            'peer_n': peer_n,
            'gap': peer_gap,
            'available': peer_available,
            'status': peer_status,
        },
        'plan': {
            'status': plan_status,
            'plan_id': 40404,
            'snapshot_id': 50505,
            'textbook_title': title,
            'workload_kind': workload_kind,
            'remaining_workload': remaining,
            'remaining_planned_study_days': days,
            'required_per_planned_day': required,
            'target_completion_date': target,
            'weekday_source': weekday_source,
            'effective_weekdays': list(weekdays) if weekdays is not None else None,
        },
    }


def _learning(*, subjects=None, observed=(4, 2)):
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': dict(CURRENT),
        'previous_window': dict(PREV),
        'max_snapshot_age_days': 21,
        'observed_study_days': {
            'current': observed[0],
            'previous': observed[1],
            'source': 'daily_points.date',
            'proxy': 'point_activity_days',
            'attendance': False,
        },
        'subjects': subjects if subjects is not None else {'math': _subject()},
    }


def _recent():
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'window_count': 3,
        'lookback_days': 90,
        'current_window': dict(CURRENT),
        'previous_1_window': {'start': date(2026, 10, 17), 'end': date(2026, 11, 15)},
        'previous_2_window': {'start': date(2026, 9, 17), 'end': date(2026, 10, 16)},
        'reading_days': {
            'current': {'start': CURRENT['start'], 'end': CURRENT['end'], 'value': None, 'available': False},
            'previous_1': {'start': date(2026, 10, 17), 'end': date(2026, 11, 15), 'value': None, 'available': False},
            'previous_2': {'start': date(2026, 9, 17), 'end': date(2026, 10, 16), 'value': None, 'available': False},
            'historical_best': None,
            'historical_best_window': None,
            'margin': None,
            'is_recent_window_best': None,
            'status': 'insufficient_history',
        },
        'reading_completions': {
            'current': {'start': CURRENT['start'], 'end': CURRENT['end'], 'value': None, 'available': False},
            'previous_1': {'start': date(2026, 10, 17), 'end': date(2026, 11, 15), 'value': None, 'available': False},
            'previous_2': {'start': date(2026, 9, 17), 'end': date(2026, 10, 16), 'value': None, 'available': False},
            'historical_best': None,
            'historical_best_window': None,
            'margin': None,
            'is_recent_window_best': None,
            'status': 'insufficient_history',
        },
        'points': {
            'current': {'start': CURRENT['start'], 'end': CURRENT['end'], 'value': None, 'available': False},
            'previous_1': {'start': date(2026, 10, 17), 'end': date(2026, 11, 15), 'value': None, 'available': False},
            'previous_2': {'start': date(2026, 9, 17), 'end': date(2026, 10, 16), 'value': None, 'available': False},
            'historical_best': None,
            'historical_best_window': None,
            'margin': None,
            'is_recent_window_best': None,
            'status': 'insufficient_history',
        },
        'learning': {},
    }


def _bundle(**kwargs):
    return {
        'reading': kwargs.get('reading', _reading()),
        'progress': kwargs.get('progress', _progress()),
        'points': kwargs.get('points', _points()),
        'learning': kwargs.get('learning', _learning()),
        'recent_window_bests': kwargs.get('recent', _recent()),
    }


def _packet(bundle, grade=3):
    return build_teacher_evidence_packet(bundle, grade=grade)


def case1_normal_mixed():
    return _packet(_bundle(
        reading=_reading(days=(8, 3), completed=(2, 1)),
        points=_points(values=(400, 200), cumulative=1800),
        progress=_progress(counts=(3, 1)),
        learning=_learning(
            observed=(5, 3),
            subjects={'math': _subject(
                page=40,
                current_advance=20,
                previous_advance=10,
                delta=10,
                peer_n=6,
                peer_median=35,
                peer_gap=5,
                peer_available=True,
                peer_status='ok',
                plan_status='active',
                workload_kind=WORKLOAD_KIND_ESTIMATED,
                remaining=80,
                days=20,
                required=4,
                target=date(2026, 12, 20),
            )},
        ),
    ))


def case2_unavailable_vs_zero():
    reading = _reading(days=(4, 2), completed=(0, 0), comparable=True)
    reading['comparable']['reading_days'] = False
    return _packet(_bundle(
        reading=reading,
        points=_points(values=(0, 120), comparable=True, cumulative=None),
        progress=_progress(counts=(0, 2), comparable=True),
        learning=_learning(
            observed=(0, 3),
            subjects={'math': _subject(
                stale=True,
                current_available=False,
                previous_available=True,
                previous_advance=12,
                delta=None,
                trend_comparable=False,
                advance_status='stale',
                plan_status='no_plan',
            )},
        ),
    ))


def case3_estimated_planning():
    return _packet(_bundle(
        reading=_reading(days=(4, 4), completed=(1, 1)),
        points=_points(values=(220, 210), cumulative=900),
        progress=_progress(counts=(2, 2)),
        learning=_learning(
            observed=(4, 4),
            subjects={'math': _subject(
                page=48,
                current_advance=12,
                previous_advance=10,
                delta=2,
                plan_status='active',
                workload_kind=WORKLOAD_KIND_ESTIMATED,
                remaining=80,
                days=20,
                required=4,
                target=date(2026, 12, 20),
            )},
        ),
    ))


def case4_decrease_mixed():
    return _packet(_bundle(
        reading=_reading(days=(3, 8), completed=(2, 1)),
        points=_points(values=(150, 300), cumulative=1100),
        progress=_progress(counts=(1, 3)),
        learning=_learning(
            observed=(2, 5),
            subjects={'math': _subject(
                page=52,
                current_advance=25,
                previous_advance=18,
                delta=7,
                plan_status='active',
                workload_kind='exact',
                remaining=40,
                days=10,
                required=4,
                target=date(2026, 12, 31),
            )},
        ),
    ))


def case5_adversarial_numbers():
    return _packet(_bundle(
        reading=_reading(days=(6, 5), completed=(5, 6)),
        points=_points(values=(6, 5), cumulative=60),
        progress=_progress(counts=(5, 6)),
        learning=_learning(
            observed=(6, 5),
            subjects={
                'math': _subject(
                    key='math',
                    name='수학',
                    title='수학 3-2',
                    page=6,
                    current_advance=5,
                    previous_advance=6,
                    delta=-1,
                    peer_n=6,
                    peer_median=5,
                    peer_gap=1,
                    peer_available=True,
                    peer_status='ok',
                    plan_status='no_plan',
                ),
                'korean': _subject(
                    key='korean',
                    name='국어',
                    title='국어 3-2',
                    page=5,
                    current_advance=6,
                    previous_advance=5,
                    delta=1,
                    peer_n=5,
                    peer_median=6,
                    peer_gap=-1,
                    peer_available=True,
                    peer_status='ok',
                    plan_status='no_plan',
                ),
            },
        ),
    ))


CASES = [
    {
        'id': 'CASE 1',
        'name': 'normal mixed growth',
        'purpose': 'reading / points / learning가 모두 available이고 증가가 섞인 일반 해석',
        'builder': case1_normal_mixed,
    },
    {
        'id': 'CASE 2',
        'name': 'unavailable / zero distinction',
        'purpose': 'available=false와 실제 0을 한 packet에서 구분하는지',
        'builder': case2_unavailable_vs_zero,
    },
    {
        'id': 'CASE 3',
        'name': 'estimated planning',
        'purpose': 'estimated workload를 exact처럼 말하지 않는지',
        'builder': case3_estimated_planning,
    },
    {
        'id': 'CASE 4',
        'name': 'decrease / mixed direction',
        'purpose': '증가/감소 방향을 유지하고 능력·의욕 추론을 하지 않는지',
        'builder': case4_decrease_mixed,
    },
    {
        'id': 'CASE 5',
        'name': 'confusion/adversarial numeric case',
        'purpose': '비슷한 숫자(5/6)를 metric·과목·window에 섞어 hallucination을 보는지',
        'builder': case5_adversarial_numbers,
    },
]


def main():
    load_local_env()
    if not os.environ.get('OPENAI_API_KEY'):
        print('not run: OPENAI_API_KEY is not set')
        return 0
    from features.growth.ai.openai_provider import OpenAIGrowthInterpretationProvider
    from features.growth.ai.validator import validate_teacher_interpretation

    provider = OpenAIGrowthInterpretationProvider()
    rows = []
    for case in CASES:
        packet = case['builder']()
        result = provider.generate(packet)
        validation = validate_teacher_interpretation(packet, result.parsed_output)
        rows.append({
            'id': case['id'],
            'name': case['name'],
            'purpose': case['purpose'],
            'packet': packet,
            'parsed_output': result.parsed_output,
            'metadata': {
                'provider': result.provider,
                'model': result.model,
                'prompt_version': result.prompt_version,
                'output_schema_version': result.output_schema_version,
                'response_id': result.response_id,
                'usage': result.usage,
                'latency_ms': result.latency_ms,
            },
            'validator': {
                'valid': validation.valid,
                'codes': [item.code for item in validation.violations],
                'locations': [item.location for item in validation.violations],
            },
        })
    print(json.dumps({'calls': len(rows), 'cases': rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
