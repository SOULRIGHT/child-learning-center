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
                            'performance': {
                                'current': {
                                    'rate': {
                                        'evidence_id': 'learning.math.performance.rate.current',
                                        'available': True,
                                        'value': 0.8,
                                    },
                                },
                            },
                            'progress': {
                                'coverage_ratio': {
                                    'evidence_id': 'learning.math.progress.coverage_ratio',
                                    'available': True,
                                    'value': 0.72,
                                },
                            },
                            'performance_peer': {
                                'peer_median': {
                                    'evidence_id': 'learning.math.performance_peer.peer_median',
                                    'available': True,
                                    'value': 0.75,
                                },
                                'n': {
                                    'evidence_id': 'learning.math.performance_peer.n',
                                    'available': True,
                                    'value': 6,
                                },
                            },
                            'plan': {
                                'target_completion_date': {
                                    'evidence_id': 'learning.math.plan.target_completion_date',
                                    'available': True,
                                    'value': '2026-12-20',
                                },
                            },
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
                    'learning.math.performance_peer.peer_median',
                    'learning.math.progress.coverage_ratio',
                    'learning.math.performance.rate.current',
                ],
            },
            'observations': [],
            'suggestions': [],
        }
        rows = present_cited_evidence(packet, parsed)
        blob = json.dumps(rows, ensure_ascii=False)
        self.assertNotIn('reading.activity_days.current', blob)
        self.assertNotIn('learning.math.performance_peer.peer_median', blob)
        labels = [row['label'] for row in rows]
        values = [row['value'] for row in rows]
        self.assertTrue(any('독서 활동일' in label for label in labels))
        self.assertTrue(any(row['value'] == '8일' for row in rows))
        self.assertTrue(any('수행률 중앙값' in label for label in labels))
        self.assertTrue(any(value == '75%' for value in values))
        self.assertTrue(any(value == '72%' for value in values))
        self.assertTrue(any(value == '80%' for value in values))

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
        self.assertEqual(by_key['reading']['count'], 5)
        self.assertEqual(by_key['korean']['count'], 5)
        self.assertEqual(by_key['math']['count'], 5)
        self.assertEqual(by_key['ssen']['count'], 5)
        self.assertNotIn('learning_activity', by_key)
        self.assertEqual(by_key['other']['count'], 4)
        self.assertIn('독서 5', bundle['chips'])
        math_compact = {row['label']: row['value'] for row in by_key['math']['compact']}
        self.assertEqual(math_compact['학습 수행률'], '80%')
        self.assertEqual(math_compact['관측 기반 진도율'], '50%')
        self.assertEqual(math_compact['같은 학년·같은 과목 수행률 중앙값'], '60%')
        self.assertEqual(math_compact['같은 교재 진도율 중앙값'], '40%')
        self.assertEqual(math_compact['완료예상'], '2026-09-29 예상')
        reading_compact = {row['label']: row['value'] for row in by_key['reading']['compact']}
        self.assertEqual(reading_compact['최근 30일'], '활동 0일 · 완독 0권')
        self.assertEqual(reading_compact['이전 30일'], '활동 12일 · 완독 4권')
        self.assertEqual(reading_compact['독서 관찰'], '문장이 짧아졌다')
        other_compact = {row['label']: row['value'] for row in by_key['other']['compact']}
        self.assertEqual(other_compact['최근'], '100점')
        self.assertEqual(other_compact['같은 학년 포인트 중앙값'], '90점')
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

    def test_compact_v3_unavailable_is_not_zero(self):
        packet = {
            'supporting_facts': {
                'learning': {
                    'subjects': {
                        'math': {
                            'subject_key': 'math',
                            'subject_label': '수학',
                            'progress': {
                                'coverage_ratio': _fact(
                                    'learning.math.progress.coverage_ratio',
                                    None,
                                    available=False,
                                    status='unavailable',
                                ),
                            },
                            'forecast': {
                                'earliest_date': _fact(
                                    'learning.math.forecast.earliest_date',
                                    None,
                                    available=False,
                                    status='no_plan',
                                ),
                                'latest_date': _fact(
                                    'learning.math.forecast.latest_date',
                                    None,
                                    available=False,
                                    status='no_plan',
                                ),
                            },
                            'coverage_peer': {
                                'peer_median': _fact(
                                    'learning.math.coverage_peer.peer_median',
                                    None,
                                    available=False,
                                    status='no_peers',
                                ),
                            },
                        },
                    },
                },
                'points': {
                    'period': {
                        'previous': _fact(
                            'points.period.previous',
                            None,
                            available=False,
                            status='insufficient_history',
                        ),
                    },
                },
            },
        }
        parsed = {
            'summary': {
                'text': '자료',
                'evidence_ids': [
                    'learning.math.progress.coverage_ratio',
                    'learning.math.forecast.earliest_date',
                    'learning.math.forecast.latest_date',
                    'learning.math.coverage_peer.peer_median',
                    'points.period.previous',
                ],
            },
        }
        bundle = present_cited_evidence_bundle(packet, parsed)
        blob = json.dumps(bundle, ensure_ascii=False)
        self.assertNotIn('learning.math.progress.coverage_ratio', blob)
        values = [row['value'] for row in bundle['items']]
        self.assertIn('계산할 수 없음', values)
        self.assertIn('교재 계획 없음', values)
        self.assertIn('또래 비교 자료 부족', values)
        self.assertIn('이전 기간 비교 자료 부족', values)
        self.assertNotIn('0%', values)
        self.assertNotIn('0점', values)
        math_compact = next(group['compact'] for group in bundle['groups'] if group['key'] == 'math')
        compact_values = [row['value'] for row in math_compact]
        self.assertIn('계산할 수 없음', compact_values)
        self.assertIn('교재 계획 없음', compact_values)
        self.assertNotIn('0%', compact_values)

    def test_compact_forecast_range_when_dates_differ(self):
        packet = {
            'supporting_facts': {
                'learning': {
                    'subjects': {
                        'math': {
                            'subject_key': 'math',
                            'subject_label': '수학',
                            'forecast': {
                                'earliest_date': _fact(
                                    'learning.math.forecast.earliest_date', '2026-09-29',
                                ),
                                'latest_date': _fact(
                                    'learning.math.forecast.latest_date', '2026-10-06',
                                ),
                            },
                        },
                    },
                },
            },
        }
        parsed = {
            'summary': {
                'text': '예상',
                'evidence_ids': [
                    'learning.math.forecast.earliest_date',
                    'learning.math.forecast.latest_date',
                ],
            },
        }
        bundle = present_cited_evidence_bundle(packet, parsed)
        math_compact = next(group['compact'] for group in bundle['groups'] if group['key'] == 'math')
        self.assertEqual(
            {row['label']: row['value'] for row in math_compact}['완료예상'],
            '2026-09-29 ~ 2026-10-06 예상',
        )


def _fact(evidence_id, value, available=True, status=None):
    payload = {'evidence_id': evidence_id, 'available': available}
    if available:
        payload['value'] = value
    if status is not None:
        payload['status'] = status
    return payload


def _subject(key, label, *, rate, coverage, perf_median, cov_median, n, forecast):
    prefix = f'learning.{key}'
    return {
        'subject_key': key,
        'subject_label': label,
        'performance': {
            'current': {
                'rate': _fact(f'{prefix}.performance.rate.current', rate),
            },
        },
        'progress': {
            'coverage_ratio': _fact(f'{prefix}.progress.coverage_ratio', coverage),
        },
        'performance_peer': {
            'peer_median': _fact(f'{prefix}.performance_peer.peer_median', perf_median),
            'n': _fact(f'{prefix}.performance_peer.n', n),
        },
        'coverage_peer': {
            'peer_median': _fact(f'{prefix}.coverage_peer.peer_median', cov_median),
        },
        'forecast': {
            'earliest_date': _fact(f'{prefix}.forecast.earliest_date', forecast),
            'latest_date': _fact(f'{prefix}.forecast.latest_date', forecast),
        },
    }


def _twenty_four_packet():
    ids = [
        'reading.activity_days.current',
        'reading.activity_days.previous',
        'reading.completions.current',
        'reading.completions.previous',
        'reading.analysis.observation.1',
        'learning.korean.performance.rate.current',
        'learning.korean.progress.coverage_ratio',
        'learning.korean.performance_peer.peer_median',
        'learning.korean.coverage_peer.peer_median',
        'learning.korean.forecast.earliest_date',
        'learning.math.performance.rate.current',
        'learning.math.progress.coverage_ratio',
        'learning.math.performance_peer.peer_median',
        'learning.math.coverage_peer.peer_median',
        'learning.math.forecast.earliest_date',
        'learning.ssen.performance.rate.current',
        'learning.ssen.progress.coverage_ratio',
        'learning.ssen.performance_peer.peer_median',
        'learning.ssen.coverage_peer.peer_median',
        'learning.ssen.forecast.earliest_date',
        'points.period.current',
        'points.period.previous',
        'points.peer.peer_median',
        'points.peer.n',
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
                'analysis': {
                    'observation': {
                        '1': _fact('reading.analysis.observation.1', '문장이 짧아졌다'),
                    },
                },
            },
            'points': {
                'period': {
                    'current': _fact('points.period.current', 100),
                    'previous': _fact('points.period.previous', 80),
                },
                'peer': {
                    'peer_median': _fact('points.peer.peer_median', 90),
                    'n': _fact('points.peer.n', 4),
                },
            },
            'learning': {
                'subjects': {
                    'korean': _subject(
                        'korean', '국어',
                        rate=0.7, coverage=0.4, perf_median=0.5, cov_median=0.3, n=2,
                        forecast='2026-10-01',
                    ),
                    'math': _subject(
                        'math', '수학',
                        rate=0.8, coverage=0.5, perf_median=0.6, cov_median=0.4, n=3,
                        forecast='2026-09-29',
                    ),
                    'ssen': _subject(
                        'ssen', '쎈',
                        rate=0.9, coverage=0.6, perf_median=0.7, cov_median=0.5, n=3,
                        forecast='2026-11-01',
                    ),
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
