"""Friendly evidence presenter. raw evidence_id를 UI row에 넣지 않는다."""
from __future__ import annotations

import json
import unittest

from features.growth.ai.presenter import present_cited_evidence


class PresenterTests(unittest.TestCase):
    def test_activity_days_and_peer_median(self):
        packet = {
            'scope': {
                'current_window': {'start': '2026-11-16', 'end': '2026-12-15'},
            },
            'supporting_facts': {
                'reading': {
                    'activity_days': {
                        'current': {
                            'evidence_id': 'reading.activity_days.current',
                            'available': True,
                            'value': 8,
                        },
                    },
                },
                'learning': {
                    'subjects': {
                        'math': {
                            'subject_key': 'math',
                            'subject_label': '수학',
                            'textbook_title': '수학 3-1',
                            'peer': {
                                'median': {
                                    'evidence_id': 'learning.math.peer.median',
                                    'available': True,
                                    'value': 35,
                                },
                                'n': {
                                    'evidence_id': 'learning.math.peer.n',
                                    'available': True,
                                    'value': 6,
                                },
                            },
                            'plan': {
                                'workload_kind': 'estimated',
                                'required_per_planned_day': {
                                    'evidence_id': 'learning.math.plan.required_per_day',
                                    'available': True,
                                    'value': 4,
                                },
                            },
                        },
                    },
                    'observed_study_days': {
                        'attendance': False,
                        'current': {
                            'evidence_id': 'learning.observed_study_days.current',
                            'available': True,
                            'value': 5,
                        },
                    },
                },
            },
        }
        parsed = {
            'summary': {
                'text': '최근 독서 활동일은 8일입니다.',
                'evidence_ids': [
                    'reading.activity_days.current',
                    'learning.math.peer.median',
                    'learning.math.plan.required_per_day',
                    'learning.observed_study_days.current',
                ],
            },
            'observations': [],
            'suggestions': [],
        }
        rows = present_cited_evidence(packet, parsed)
        blob = json.dumps(rows, ensure_ascii=False)
        self.assertNotIn('reading.activity_days.current', blob)
        self.assertNotIn('learning.math.peer.median', blob)
        labels = [row['label'] for row in rows]
        values = [row['value'] for row in rows]
        self.assertTrue(any('독서 활동일' in label for label in labels))
        self.assertTrue(any(row['value'] == '8일' for row in rows))
        self.assertTrue(any('동일 학년·동일 교재' in label for label in labels))
        self.assertTrue(any('중앙값 35페이지 / 비교 인원 6명' in value for value in values))
        self.assertTrue(any('학습일당 약 4페이지' in value for value in values))
        self.assertTrue(any(row.get('note') and '출석일' in row['note'] for row in rows))
