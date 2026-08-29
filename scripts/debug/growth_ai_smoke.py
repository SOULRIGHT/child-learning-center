"""Developer-only Growth AI smoke. production DB/route에 연결하지 않는다.

OPENAI_API_KEY가 환경에 있을 때만 1회 호출한다.
.env를 읽지 않는다. instance DB를 읽지 않는다.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SYNTHETIC_PACKET = {
    'schema_version': 'growth_teacher_evidence_v1',
    'audience': 'teacher',
    'as_of': '2026-12-15',
    'grade': 3,
    'scope': {
        'window_days': 30,
        'current_window': {'start': '2026-11-16', 'end': '2026-12-15'},
        'previous_window': {'start': '2026-10-17', 'end': '2026-11-15'},
        'freshness': {'max_snapshot_age_days': 21},
    },
    'selected_insights': [
        {
            'id': 'READING_ACTIVITY_INCREASE',
            'category': 'reading_activity',
            'direction': 'increase',
            'metric_key': 'reading_days',
            'evidence_ids': [
                'reading.activity_days.current',
                'reading.activity_days.previous',
                'reading.activity_days.delta',
            ],
            'evidence': {
                'source': 'reading_day.date',
                'metric_key': 'reading_days',
                'current': 8,
                'previous': 3,
                'delta': 5,
                'comparable': True,
            },
        }
    ],
    'supporting_facts': {
        'reading': {
            'activity_days': {
                'comparable': True,
                'current': {'evidence_id': 'reading.activity_days.current', 'available': True, 'value': 8},
                'previous': {'evidence_id': 'reading.activity_days.previous', 'available': True, 'value': 3},
                'delta': {'evidence_id': 'reading.activity_days.delta', 'available': True, 'value': 5},
            }
        },
        'points': {
            'period': {
                'comparable': True,
                'current': {'evidence_id': 'points.period.current', 'available': True, 'value': 400},
                'previous': {'evidence_id': 'points.period.previous', 'available': True, 'value': 200},
                'delta': {'evidence_id': 'points.period.delta', 'available': True, 'value': 200},
            }
        },
        'learning': {
            'observed_study_days': {
                'source': 'daily_points.date',
                'proxy': 'point_activity_days',
                'attendance': False,
                'comparable': True,
                'current': {'evidence_id': 'learning.observed_study_days.current', 'available': True, 'value': 4},
                'previous': {'evidence_id': 'learning.observed_study_days.previous', 'available': True, 'value': 2},
                'delta': {'evidence_id': 'learning.observed_study_days.delta', 'available': True, 'value': 2},
            },
            'subjects': {
                'math': {
                    'subject_key': 'math',
                    'subject_label': '수학',
                    'plan': {
                        'status': 'active',
                        'workload_kind': 'estimated',
                        'remaining_workload': {
                            'evidence_id': 'learning.math.plan.remaining_workload',
                            'available': True,
                            'value': 80,
                        },
                    },
                }
            },
        },
    },
}


def main():
    if not os.environ.get('OPENAI_API_KEY'):
        print('not run: OPENAI_API_KEY is not set')
        return 0
    from features.growth.ai.openai_provider import OpenAIGrowthInterpretationProvider
    result = OpenAIGrowthInterpretationProvider().generate(SYNTHETIC_PACKET)
    print(json.dumps({
        'provider': result.provider,
        'model': result.model,
        'prompt_version': result.prompt_version,
        'output_schema_version': result.output_schema_version,
        'response_id': result.response_id,
        'usage': result.usage,
        'latency_ms': result.latency_ms,
        'parsed_output': result.parsed_output,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
