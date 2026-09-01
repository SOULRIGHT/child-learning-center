"""Friendly evidence presenter. raw evidence_id를 UI row에 넣지 않는다."""
from __future__ import annotations

import json
import unittest

from features.growth.ai.presenter import present_cited_evidence, present_cited_evidence_bundle


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

    def test_group_counts_preserve_all_cited_evidence(self):
        packet, parsed, expected_ids = _twenty_four_packet()
        bundle = present_cited_evidence_bundle(packet, parsed)
        self.assertEqual(bundle['total'], 24)
        self.assertEqual(len(bundle['items']), 24)
        self.assertEqual(sum(group['count'] for group in bundle['groups']), 24)
        grouped_items = [item for group in bundle['groups'] for item in group['items']]
        self.assertEqual(len(grouped_items), 24)
        blob = json.dumps(bundle, ensure_ascii=False)
        for evidence_id in expected_ids:
            self.assertNotIn(evidence_id, blob)
        by_key = {group['key']: group for group in bundle['groups']}
        self.assertEqual(by_key['reading']['count'], 4)
        self.assertEqual(by_key['korean']['count'], 5)
        self.assertEqual(by_key['math']['count'], 5)
        self.assertEqual(by_key['ssen']['count'], 5)
        self.assertEqual(by_key['learning_activity']['count'], 3)
        self.assertEqual(by_key['other']['count'], 2)
        self.assertIn('독서 4', bundle['chips'])
        math_compact = {row['label']: row['value'] for row in by_key['math']['compact']}
        self.assertEqual(math_compact['현재'], '6페이지')
        self.assertEqual(math_compact['동일 학년·동일 교재 중앙값'], '18페이지')
        self.assertEqual(math_compact['비교 인원'], '3명')
        self.assertEqual(math_compact['최근 진도 변화'], '자료 없음')
        reading_compact = {row['label']: row['value'] for row in by_key['reading']['compact']}
        self.assertEqual(reading_compact['최근 30일'], '활동 0일 · 완독 0권')
        self.assertEqual(reading_compact['이전 30일'], '활동 12일 · 완독 4권')
        activity = {row['label']: row['value'] for row in by_key['learning_activity']['compact']}
        self.assertEqual(activity['최근'], '19일')
        self.assertEqual(activity['이전'], '19일')
        self.assertIn('출석일', by_key['learning_activity']['note'])
        for group in bundle['groups']:
            self.assertEqual(len(group['items']), group['count'])

    def test_rewards_compact_rows(self):
        packet = {
            'scope': {
                'current_window': {'start': '2026-11-16', 'end': '2026-12-15'},
                'previous_window': {'start': '2026-10-17', 'end': '2026-11-15'},
            },
            'supporting_facts': {
                'rewards': {
                    'exemption_usage': {
                        'current': _fact('rewards.exemption.usage.current', 2),
                        'previous': _fact('rewards.exemption.usage.previous', 0),
                    },
                    'manual_event_count': {
                        'current': _fact('rewards.manual.event_count.current', 3),
                        'previous': _fact('rewards.manual.event_count.previous', 1),
                    },
                },
            },
        }
        parsed = {
            'priority_insight': {
                'text': '최근 면제권 사용이 늘었습니다.',
                'evidence_ids': [
                    'rewards.exemption.usage.current',
                    'rewards.exemption.usage.previous',
                    'rewards.manual.event_count.current',
                    'rewards.manual.event_count.previous',
                ],
            },
        }
        bundle = present_cited_evidence_bundle(packet, parsed)
        by_key = {group['key']: group for group in bundle['groups']}
        self.assertEqual(by_key['rewards']['label'], '보상/활동')
        compact = {row['label']: row['value'] for row in by_key['rewards']['compact']}
        self.assertEqual(compact['최근 30일'], '면제권 2회 · 추가 포인트 3회')
        self.assertEqual(compact['이전 30일'], '면제권 0회 · 추가 포인트 1회')
        blob = json.dumps(bundle, ensure_ascii=False)
        self.assertNotIn('rewards.exemption.usage.current', blob)


def _fact(evidence_id, value, available=True):
    payload = {'evidence_id': evidence_id, 'available': available}
    if available:
        payload['value'] = value
    return payload


def _subject(key, label, page, median, n):
    prefix = f'learning.{key}'
    return {
        'subject_key': key,
        'subject_label': label,
        'snapshot': {
            'current_page': _fact(f'{prefix}.snapshot.current_page', page),
        },
        'peer': {
            'median': _fact(f'{prefix}.peer.median', median),
            'n': _fact(f'{prefix}.peer.n', n),
        },
        'page_advance': {
            'delta': _fact(f'{prefix}.page_advance.delta', None, available=False),
            'current': _fact(f'{prefix}.page_advance.current', 2),
        },
        'plan': {
            'remaining_workload': _fact(f'{prefix}.plan.remaining_workload', 10),
        },
    }


def _twenty_four_packet():
    ids = [
        'reading.activity_days.current',
        'reading.activity_days.previous',
        'reading.completions.current',
        'reading.completions.previous',
        'learning.korean.snapshot.current_page',
        'learning.korean.peer.median',
        'learning.korean.peer.n',
        'learning.korean.page_advance.delta',
        'learning.korean.plan.remaining_workload',
        'learning.math.snapshot.current_page',
        'learning.math.peer.median',
        'learning.math.peer.n',
        'learning.math.page_advance.delta',
        'learning.math.plan.remaining_workload',
        'learning.ssen.snapshot.current_page',
        'learning.ssen.peer.median',
        'learning.ssen.peer.n',
        'learning.ssen.page_advance.delta',
        'learning.ssen.plan.remaining_workload',
        'learning.observed_study_days.current',
        'learning.observed_study_days.previous',
        'learning.progress_entry_count.current',
        'points.period.current',
        'points.cumulative_as_of',
    ]
    packet = {
        'scope': {
            'current_window': {'start': '2026-11-16', 'end': '2026-12-15'},
            'previous_window': {'start': '2026-10-17', 'end': '2026-11-15'},
        },
        'supporting_facts': {
            'reading': {
                'activity_days': {
                    'current': _fact('reading.activity_days.current', 0),
                    'previous': _fact('reading.activity_days.previous', 12),
                },
                'completions': {
                    'current': _fact('reading.completions.current', 0),
                    'previous': _fact('reading.completions.previous', 4),
                },
            },
            'points': {
                'period': {'current': _fact('points.period.current', 100)},
                'cumulative_as_of': _fact('points.cumulative_as_of', 500),
            },
            'learning': {
                'progress_entry_count': {
                    'current': _fact('learning.progress_entry_count.current', 2),
                },
                'observed_study_days': {
                    'attendance': False,
                    'current': _fact('learning.observed_study_days.current', 19),
                    'previous': _fact('learning.observed_study_days.previous', 19),
                },
                'subjects': {
                    'korean': _subject('korean', '국어', 4, 10, 2),
                    'math': _subject('math', '수학', 6, 18, 3),
                    'ssen': _subject('ssen', '쎈', 8, 12, 3),
                },
            },
        },
    }
    parsed = {
        'summary': {'text': '요약', 'evidence_ids': ids},
        'observations': [],
        'suggestions': [],
    }
    return packet, parsed, ids
