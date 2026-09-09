"""Deterministic Growth AI factual validator. 실제 네트워크 호출 없음."""
from __future__ import annotations

import unittest

from features.growth.ai.schema import OUTPUT_SCHEMA_VERSION
from features.growth.ai.validator import (
    CODE_EMPTY_EVIDENCE_IDS,
    CODE_ESTIMATED_AS_EXACT,
    CODE_FORGED_FORECAST_DATE,
    CODE_LIMITED_AS_MAJOR,
    CODE_NON_CONDITIONAL_SUGGESTION,
    CODE_RANK_LANGUAGE,
    CODE_RAW_READING_QUOTE,
    CODE_REFERENCE_ONLY_SOLE_NEXT_ACTION,
    CODE_REFERENCE_ONLY_SOLE_PRIORITY,
    CODE_STALE_READING_OBSERVATION,
    CODE_UNAVAILABLE_AS_ZERO,
    CODE_UNAVAILABLE_PEER,
    CODE_UNIT_MISMATCH,
    CODE_UNKNOWN_EVIDENCE_ID,
    CODE_UNSUPPORTED_NUMERIC_CLAIM,
    FACTUAL_VALIDATOR_VERSION,
    collect_evidence_index,
    validate_teacher_interpretation,
)
from features.growth.evidence_packet import SCHEMA_VERSION


def _fact(evidence_id, value, *, available=True):
    payload = {'evidence_id': evidence_id, 'available': available}
    if available:
        payload['value'] = value
    else:
        payload['status'] = 'insufficient_history'
    return payload


def _packet(**kwargs):
    days_available = kwargs.get('days_available', True)
    days_value = kwargs.get('days', 5)
    completions = kwargs.get('completions', 1)
    points = kwargs.get('points', 400)
    required = kwargs.get('required', 4)
    remaining = kwargs.get('remaining', 80)
    workload_kind = kwargs.get('workload_kind', 'estimated')
    return {
        'schema_version': SCHEMA_VERSION,
        'audience': 'teacher',
        'as_of': '2026-12-15',
        'grade': 3,
        'scope': {
            'window_days': 30,
            'current_window': {'start': '2026-11-16', 'end': '2026-12-15'},
            'previous_window': {'start': '2026-10-17', 'end': '2026-11-15'},
            'freshness': {'max_snapshot_age_days': 21},
        },
        'selected_insights': [],
        'supporting_facts': {
            'reading': {
                'activity_days': {
                    'comparable': days_available,
                    'current': _fact(
                        'reading.activity_days.current',
                        days_value,
                        available=days_available,
                    ),
                    'previous': _fact(
                        'reading.activity_days.previous',
                        kwargs.get('days_previous', 3),
                        available=days_available,
                    ),
                    'delta': _fact(
                        'reading.activity_days.delta',
                        kwargs.get('days_delta', 2),
                        available=days_available,
                    ),
                },
                'completions': {
                    'comparable': True,
                    'current': _fact('reading.completions.current', completions),
                    'previous': _fact(
                        'reading.completions.previous',
                        kwargs.get('completions_previous', 0),
                    ),
                    'delta': _fact(
                        'reading.completions.delta',
                        kwargs.get('completions_delta', completions),
                    ),
                },
            },
            'points': {
                'period': {
                    'comparable': True,
                    'current': _fact('points.period.current', points),
                    'previous': _fact(
                        'points.period.previous', kwargs.get('points_previous', 200),
                    ),
                    'delta': _fact('points.period.delta', kwargs.get('points_delta', 200)),
                },
            },
            'learning': {
                'progress_entry_count': {
                    'comparable': True,
                    'current': _fact(
                        'learning.progress_entry_count.current', kwargs.get('progress', 2),
                    ),
                    'previous': _fact('learning.progress_entry_count.previous', 1),
                    'delta': _fact('learning.progress_entry_count.delta', 1),
                },
                'observed_study_days': {
                    'source': 'daily_points.date',
                    'proxy': 'point_activity_days',
                    'attendance': False,
                    'comparable': True,
                    'current': _fact(
                        'learning.observed_study_days.current', kwargs.get('observed', 4),
                    ),
                    'previous': _fact('learning.observed_study_days.previous', 2),
                    'delta': _fact('learning.observed_study_days.delta', 2),
                },
                'subjects': {
                    'math': {
                        'subject_key': 'math',
                        'subject_label': '수학',
                        'plan': {
                            'status': 'active',
                            'effective_weekdays': [0, 1, 2, 3, 4],
                            'workload_kind': workload_kind,
                            'remaining_workload': _fact(
                                'learning.math.plan.remaining_workload', remaining,
                            ),
                            'required_per_planned_day': _fact(
                                'learning.math.plan.required_per_day', required,
                            ),
                        },
                    },
                },
            },
            'rewards': {
                'exemption_usage': {
                    'current': _fact(
                        'rewards.exemption.usage.current',
                        kwargs.get('exemption_current', 2),
                    ),
                    'previous': _fact(
                        'rewards.exemption.usage.previous',
                        kwargs.get('exemption_previous', 0),
                    ),
                },
                'manual_event_count': {
                    'current': _fact(
                        'rewards.manual.event_count.current',
                        kwargs.get('manual_events', 3),
                    ),
                },
            },
        },
    }


def _output(*, summary, summary_ids, observations=None, suggestions=None):
    return {
        'schema_version': OUTPUT_SCHEMA_VERSION,
        'priority_insight': {'text': summary, 'evidence_ids': summary_ids},
        'interpretation': {
            'text': '여러 기록을 함께 보면 우선 볼 변화가 분명해집니다.',
            'evidence_ids': ['reading.activity_days.current'],
        },
        'observations': observations if observations is not None else [],
        'next_actions': suggestions if suggestions is not None else [],
        'next_check': {
            'text': '다음 비교 시점에 같은 기록을 다시 보면 판단이 더 분명해집니다.',
            'evidence_ids': ['reading.activity_days.current'],
        },
    }


def _obs(text, evidence_ids):
    return {'text': text, 'evidence_ids': evidence_ids}


def _sug(text, evidence_ids, conditional=True):
    return {'text': text, 'evidence_ids': evidence_ids, 'conditional': conditional}


def _codes(result):
    return tuple(item.code for item in result.violations)


def _composition_unit_packet():
    return {
        'schema_version': SCHEMA_VERSION,
        'supporting_facts': {
            'reading': {
                'activity_days': {
                    'current': _fact('reading.activity_days.current', 5),
                },
            },
            'points': {
                'composition': {
                    'subjects': {
                        'korean': {
                            'points': {
                                'current': _fact(
                                    'points.composition.subjects.korean.points.current', 200,
                                ),
                            },
                            'active_days': {
                                'current': _fact(
                                    'points.composition.subjects.korean.active_days.current', 4,
                                ),
                            },
                        },
                    },
                },
            },
        },
    }


class GrowthAIValidatorTests(unittest.TestCase):
    def test_factual_validator_version(self):
        self.assertEqual(FACTUAL_VALIDATOR_VERSION, 'growth_teacher_factual_validator_v4')

    def test_empty_summary_evidence_ids_rejected(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(summary='최근 관찰을 정리합니다.', summary_ids=[]),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_EMPTY_EVIDENCE_IDS, _codes(result))
        self.assertEqual(result.violations[0].location, 'priority_insight')

    def test_empty_observation_evidence_ids_rejected(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='독서 활동일은 5일입니다.',
                summary_ids=['reading.activity_days.current'],
                observations=[_obs('독서 활동일은 5일입니다.', [])],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_EMPTY_EVIDENCE_IDS, _codes(result))
        self.assertEqual(result.violations[0].location, 'observations[0]')

    def test_empty_suggestion_evidence_ids_rejected(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='독서 활동일은 5일입니다.',
                summary_ids=['reading.activity_days.current'],
                suggestions=[_sug('다음 기록도 확인해 보세요.', [])],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_EMPTY_EVIDENCE_IDS, _codes(result))
        self.assertEqual(result.violations[0].location, 'next_actions[0]')

    def test_unknown_evidence_id_rejected(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='독서 활동일은 5일입니다.',
                summary_ids=['reading.activity_days.current', 'not.a.real.id'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNKNOWN_EVIDENCE_ID, _codes(result))

    def test_plan_status_field_name_is_unknown_evidence_id(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='계획이 있습니다.',
                summary_ids=['learning.math.plan.status'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertEqual(_codes(result), (CODE_UNKNOWN_EVIDENCE_ID,))
        self.assertNotIn('learning.math.plan.status', collect_evidence_index(_packet()))

    def test_ssen_plan_status_field_name_is_unknown_evidence_id(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='계획이 있습니다.',
                summary_ids=['reading.activity_days.current'],
                observations=[
                    _obs(
                        '수학과 쎈 계획 상태를 확인합니다.',
                        ['learning.math.plan.status', 'learning.ssen.plan.status'],
                    ),
                ],
                suggestions=[
                    _sug(
                        '계획이 있으면 페이지를 다시 기록해 주세요.',
                        ['learning.math.plan.status', 'learning.ssen.plan.status'],
                    ),
                ],
            ),
        )
        self.assertFalse(result.valid)
        self.assertEqual(_codes(result), (CODE_UNKNOWN_EVIDENCE_ID,) * 4)
        locations = [item.location for item in result.violations]
        self.assertEqual(locations, ['observations[0]', 'observations[0]', 'next_actions[0]', 'next_actions[0]'])
        ids = [item.evidence_id for item in result.violations]
        self.assertEqual(
            ids,
            [
                'learning.math.plan.status',
                'learning.ssen.plan.status',
                'learning.math.plan.status',
                'learning.ssen.plan.status',
            ],
        )
        index = collect_evidence_index(_packet())
        self.assertNotIn('learning.ssen.plan.status', index)
        self.assertNotIn('learning.math.plan.status', index)

    def test_effective_weekdays_field_name_is_unknown_evidence_id(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='주중 계획이 있습니다.',
                summary_ids=['learning.math.plan.effective_weekdays'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertEqual(_codes(result), (CODE_UNKNOWN_EVIDENCE_ID,))
        self.assertNotIn(
            'learning.math.plan.effective_weekdays',
            collect_evidence_index(_packet()),
        )

    def test_valid_evidence_ids_pass(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='독서 활동일은 5일입니다.',
                summary_ids=['reading.activity_days.current'],
            ),
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.violations, ())

    def test_matching_day_claim_passes(self):
        result = validate_teacher_interpretation(
            _packet(days=5),
            _output(
                summary='독서 활동일은 5일입니다.',
                summary_ids=['reading.activity_days.current'],
            ),
        )
        self.assertTrue(result.valid)

    def test_mismatched_day_claim_rejected(self):
        result = validate_teacher_interpretation(
            _packet(days=5),
            _output(
                summary='독서 활동일은 6일입니다.',
                summary_ids=['reading.activity_days.current'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNSUPPORTED_NUMERIC_CLAIM, _codes(result))

    def test_unrelated_metric_number_does_not_justify_claim(self):
        result = validate_teacher_interpretation(
            _packet(days=5, completions=6),
            _output(
                summary='독서 활동일은 6일입니다.',
                summary_ids=['reading.activity_days.current'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNSUPPORTED_NUMERIC_CLAIM, _codes(result))

    def test_activity_days_with_day_unit_passes(self):
        result = validate_teacher_interpretation(
            _packet(days=5),
            _output(
                summary='독서 활동일 5일',
                summary_ids=['reading.activity_days.current'],
            ),
        )
        self.assertTrue(result.valid)

    def test_activity_days_with_book_unit_rejected(self):
        result = validate_teacher_interpretation(
            _packet(days=5),
            _output(
                summary='독서 완료 5권',
                summary_ids=['reading.activity_days.current'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNIT_MISMATCH, _codes(result))

    def test_points_with_point_unit_passes(self):
        result = validate_teacher_interpretation(
            _packet(points=400),
            _output(
                summary='기간 포인트는 400점입니다.',
                summary_ids=['points.period.current'],
            ),
        )
        self.assertTrue(result.valid)

    def test_points_with_day_unit_rejected(self):
        result = validate_teacher_interpretation(
            _packet(points=400),
            _output(
                summary='기간 포인트는 400일입니다.',
                summary_ids=['points.period.current'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNIT_MISMATCH, _codes(result))

    def test_unavailable_zero_day_claim_rejected(self):
        result = validate_teacher_interpretation(
            _packet(days_available=False),
            _output(
                summary='독서 활동일은 0일입니다.',
                summary_ids=['reading.activity_days.current'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNAVAILABLE_AS_ZERO, _codes(result))

    def test_observed_zero_is_allowed(self):
        result = validate_teacher_interpretation(
            _packet(days=0),
            _output(
                summary='독서 활동일은 0일입니다.',
                summary_ids=['reading.activity_days.current'],
            ),
        )
        self.assertTrue(result.valid)

    def test_estimated_required_without_marker_rejected(self):
        result = validate_teacher_interpretation(
            _packet(workload_kind='estimated', required=4),
            _output(
                summary='하루 4쪽',
                summary_ids=['learning.math.plan.required_per_day'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_ESTIMATED_AS_EXACT, _codes(result))

    def test_estimated_required_with_marker_passes(self):
        result = validate_teacher_interpretation(
            _packet(workload_kind='estimated', required=4),
            _output(
                summary='하루 약 4쪽',
                summary_ids=['learning.math.plan.required_per_day'],
            ),
        )
        self.assertTrue(result.valid)

    def test_estimated_remaining_with_추정_passes(self):
        result = validate_teacher_interpretation(
            _packet(workload_kind='estimated', remaining=80),
            _output(
                summary='현재 추정 기준 남은 분량은 80쪽',
                summary_ids=['learning.math.plan.remaining_workload'],
            ),
        )
        self.assertTrue(result.valid)

    def test_exact_required_without_marker_passes(self):
        result = validate_teacher_interpretation(
            _packet(workload_kind='exact', required=4),
            _output(
                summary='하루 4쪽',
                summary_ids=['learning.math.plan.required_per_day'],
            ),
        )
        self.assertTrue(result.valid)

    def test_estimated_marker_is_per_item_not_summary(self):
        result = validate_teacher_interpretation(
            _packet(workload_kind='estimated', required=4),
            _output(
                summary='현재 추정 기준 하루 약 4쪽입니다.',
                summary_ids=['learning.math.plan.required_per_day'],
                observations=[_obs('하루 4쪽', ['learning.math.plan.required_per_day'])],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_ESTIMATED_AS_EXACT, _codes(result))
        self.assertEqual(result.violations[0].location, 'observations[0]')

    def test_suggestion_conditional_false_rejected(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='독서 활동일은 5일입니다.',
                summary_ids=['reading.activity_days.current'],
                suggestions=[_sug(
                    '다음에도 확인해 보세요.',
                    ['reading.activity_days.current'],
                    False,
                )],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_NON_CONDITIONAL_SUGGESTION, _codes(result))

    def test_suggestion_conditional_true_passes(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='독서 활동일은 5일입니다.',
                summary_ids=['reading.activity_days.current'],
                suggestions=[_sug(
                    '다음 기간에도 독서 활동일 5일을 참고해 보세요.',
                    ['reading.activity_days.current'],
                    True,
                )],
            ),
        )
        self.assertTrue(result.valid)

    def test_normal_multi_evidence_interpretation_passes(self):
        result = validate_teacher_interpretation(
            _packet(days=5, days_previous=3, points=400, points_previous=200),
            _output(
                summary='최근 30일 독서 활동일은 5일이고 기간 포인트는 400점입니다.',
                summary_ids=['reading.activity_days.current', 'points.period.current'],
                observations=[
                    _obs(
                        '독서 활동일은 이전 3일에서 5일로 늘었습니다.',
                        ['reading.activity_days.current', 'reading.activity_days.previous'],
                    ),
                    _obs(
                        '기간 포인트는 200점에서 400점으로 늘었습니다.',
                        ['points.period.current', 'points.period.previous'],
                    ),
                ],
                suggestions=[_sug(
                    '다음 기록에서도 독서 활동일과 기간 포인트를 함께 보면 좋겠습니다.',
                    ['reading.activity_days.current', 'points.period.current'],
                )],
            ),
        )
        self.assertTrue(result.valid)

    def test_unavailable_and_zero_mix_passes_when_worded_correctly(self):
        result = validate_teacher_interpretation(
            _packet(days_available=False, completions=0),
            _output(
                summary='읽기 완료 수는 0권입니다. 독서 활동일은 자료가 부족해 비교할 수 없습니다.',
                summary_ids=['reading.completions.current', 'reading.activity_days.current'],
            ),
        )
        self.assertTrue(result.valid)

    def test_mixed_increase_decrease_passes(self):
        result = validate_teacher_interpretation(
            _packet(days=3, days_previous=8, completions=2, completions_previous=1),
            _output(
                summary='독서 활동일은 8일에서 3일로 줄었지만 읽기 완료 수는 1권에서 2권으로 늘었습니다.',
                summary_ids=[
                    'reading.activity_days.current',
                    'reading.activity_days.previous',
                    'reading.completions.current',
                    'reading.completions.previous',
                ],
            ),
        )
        self.assertTrue(result.valid)

    def test_violation_repr_omits_packet_and_output_text(self):
        packet = _packet()
        output = _output(summary='비밀문장-ZX9', summary_ids=['learning.math.plan.status'])
        result = validate_teacher_interpretation(packet, output)
        dumped = repr(result)
        self.assertNotIn('비밀문장-ZX9', dumped)
        self.assertNotIn('supporting_facts', dumped)

    def test_cited_current_previous_difference_is_allowed(self):
        result = validate_teacher_interpretation(
            _packet(days=8, days_previous=3),
            _output(
                summary='독서 활동일은 3일에서 8일로 5일 늘었습니다.',
                summary_ids=['reading.activity_days.current', 'reading.activity_days.previous'],
            ),
        )
        self.assertTrue(result.valid)

    def test_completions_book_unit_passes(self):
        result = validate_teacher_interpretation(
            _packet(completions=1, completions_previous=4),
            _output(
                summary='완독 수는 4권에서 1권으로 줄었습니다.',
                summary_ids=['reading.completions.current', 'reading.completions.previous'],
            ),
        )
        self.assertTrue(result.valid)

    def test_completions_count_unit_rejected(self):
        result = validate_teacher_interpretation(
            _packet(completions=1, completions_previous=4),
            _output(
                summary='완독 수는 4회에서 1회로 줄었습니다.',
                summary_ids=['reading.completions.current', 'reading.completions.previous'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertEqual(_codes(result), (CODE_UNIT_MISMATCH, CODE_UNIT_MISMATCH))
        mismatches = [item for item in result.violations if item.code == CODE_UNIT_MISMATCH]
        self.assertEqual([item.location for item in mismatches], ['priority_insight', 'priority_insight'])
        self.assertEqual({item.claim for item in mismatches}, {'4회', '1회'})
        self.assertTrue(all(item.expected_unit == 'book/권' for item in mismatches))

    def test_activity_days_and_completion_books_in_same_text_pass(self):
        result = validate_teacher_interpretation(
            _packet(
                days=2,
                days_previous=15,
                days_delta=-13,
                completions=1,
                completions_previous=4,
                completions_delta=-3,
            ),
            _output(
                summary='독서 활동일은 15일에서 2일로 줄었고, 완독 수는 4권에서 1권으로 줄었습니다.',
                summary_ids=[
                    'reading.activity_days.current',
                    'reading.activity_days.previous',
                    'reading.completions.current',
                    'reading.completions.previous',
                ],
            ),
        )
        self.assertTrue(result.valid)

    def test_negative_delta_absolute_value_with_matching_unit_passes(self):
        result = validate_teacher_interpretation(
            _packet(completions=5, completions_previous=6, completions_delta=-1),
            _output(
                summary='읽기 완료 수는 6권에서 5권으로 1권 줄었습니다.',
                summary_ids=[
                    'reading.completions.current',
                    'reading.completions.previous',
                    'reading.completions.delta',
                ],
            ),
        )
        self.assertTrue(result.valid)

    def test_negative_delta_wrong_unit_rejected(self):
        result = validate_teacher_interpretation(
            _packet(completions=5, completions_previous=6, completions_delta=-1),
            _output(
                summary='읽기 완료 수는 1일 줄었습니다.',
                summary_ids=['reading.completions.delta'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNIT_MISMATCH, _codes(result))

    def test_index_uses_explicit_evidence_id_only(self):
        index = collect_evidence_index(_packet())
        self.assertIn('reading.activity_days.current', index)
        self.assertNotIn('learning.math.plan.status', index)
        self.assertNotIn('learning.math.plan.effective_weekdays', index)
        self.assertTrue(index['learning.math.plan.required_per_day'].estimated)
        exact = collect_evidence_index(_packet(workload_kind='exact'))
        self.assertFalse(exact['learning.math.plan.required_per_day'].estimated)
        self.assertEqual(index['reading.activity_days.current'].value, 5)
        self.assertEqual(index['reading.activity_days.current'].unit, 'day')
        self.assertEqual(index['points.period.current'].unit, 'point')
        self.assertEqual(index['reading.completions.current'].unit, 'book')
        self.assertEqual(index['rewards.exemption.usage.current'].unit, 'count')
        self.assertEqual(index['rewards.manual.event_count.current'].unit, 'count')

    def test_composition_active_days_are_day_unit(self):
        packet = _composition_unit_packet()
        index = collect_evidence_index(packet)
        self.assertEqual(
            index['points.composition.subjects.korean.points.current'].unit, 'point',
        )
        self.assertEqual(
            index['points.composition.subjects.korean.active_days.current'].unit, 'day',
        )

    def test_composition_active_days_day_claim_passes(self):
        result = validate_teacher_interpretation(
            _composition_unit_packet(),
            _output(
                summary='국어 포인트 활동일은 4일입니다.',
                summary_ids=['points.composition.subjects.korean.active_days.current'],
            ),
        )
        self.assertTrue(result.valid)

    def test_composition_active_days_point_claim_rejected(self):
        result = validate_teacher_interpretation(
            _composition_unit_packet(),
            _output(
                summary='국어 포인트 활동일은 4점입니다.',
                summary_ids=['points.composition.subjects.korean.active_days.current'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNIT_MISMATCH, _codes(result))

    def test_missing_next_check_rejected(self):
        output = _output(
            summary='독서 활동일은 5일입니다.',
            summary_ids=['reading.activity_days.current'],
        )
        del output['next_check']
        result = validate_teacher_interpretation(_packet(), output)
        self.assertFalse(result.valid)
        self.assertIn(CODE_EMPTY_EVIDENCE_IDS, _codes(result))
        self.assertTrue(any(item.location == 'next_check' for item in result.violations))

    def test_unknown_evidence_id_is_kept_for_attempt_diagnostics(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='계획이 있습니다.',
                summary_ids=['learning.math.plan.status'],
            ),
        )
        self.assertEqual(result.violations[0].evidence_id, 'learning.math.plan.status')

    def test_exemption_usage_count_unit_passes(self):
        result = validate_teacher_interpretation(
            _packet(exemption_current=2),
            _output(
                summary='최근 면제권 사용은 2회입니다.',
                summary_ids=['rewards.exemption.usage.current'],
            ),
        )
        self.assertTrue(result.valid)

    def test_exemption_usage_day_unit_rejected(self):
        result = validate_teacher_interpretation(
            _packet(exemption_current=2),
            _output(
                summary='최근 면제권 사용은 2일입니다.',
                summary_ids=['rewards.exemption.usage.current'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNIT_MISMATCH, _codes(result))

    def test_unavailable_data_does_not_allow_invented_zero(self):
        result = validate_teacher_interpretation(
            _packet(days_available=False),
            _output(
                summary='독서 활동일은 0일입니다.',
                summary_ids=['reading.activity_days.current'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNAVAILABLE_AS_ZERO, _codes(result))


def _peer_packet(*, display_tier='reference_only', available=True, ai_status='none'):
    packet = _packet()
    packet['supporting_facts']['learning']['subjects']['math']['coverage_peer'] = {
        'available': available,
        'display_tier': display_tier,
        'reason': 'reference_only',
        'child_value': _fact('learning.math.coverage_peer.child_value', 0.7),
        'peer_median': _fact('learning.math.coverage_peer.peer_median', 0.5, available=available),
        'difference': _fact('learning.math.coverage_peer.difference', 0.2, available=available),
        'peer_sample_count': _fact('learning.math.coverage_peer.n', 2),
    }
    packet['supporting_facts']['learning']['subjects']['math']['forecast'] = {
        'available': True,
        'reason': 'ok',
        'earliest_date': _fact('learning.math.forecast.earliest_date', '2026-12-20'),
        'latest_date': _fact('learning.math.forecast.latest_date', '2026-12-28'),
    }
    packet['supporting_facts']['reading']['analysis'] = {
        'ai_status': ai_status,
        'observations': [],
        'allowed_evidence_refs': [],
    }
    return packet


class GrowthAIValidatorV3Tests(unittest.TestCase):
    def test_invalid_evidence_ref_rejected(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(summary='최근 관찰입니다.', summary_ids=['learning.math.not_a_real_id']),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNKNOWN_EVIDENCE_ID, _codes(result))

    def test_unsupported_numeric_claim_rejected(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='독서 활동일은 99일입니다.',
                summary_ids=['reading.activity_days.current'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNSUPPORTED_NUMERIC_CLAIM, _codes(result))

    def test_forged_forecast_iso_date_rejected(self):
        result = validate_teacher_interpretation(
            _peer_packet(),
            _output(
                summary='완료 예상일은 2099-01-01 입니다.',
                summary_ids=['learning.math.forecast.earliest_date'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_FORGED_FORECAST_DATE, _codes(result))

    def test_forged_korean_forecast_date_rejected(self):
        result = validate_teacher_interpretation(
            _peer_packet(),
            _output(
                summary='10월 2일쯤 완료될 것으로 보입니다.',
                summary_ids=['learning.math.forecast.earliest_date'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_FORGED_FORECAST_DATE, _codes(result))

        full = validate_teacher_interpretation(
            _peer_packet(),
            _output(
                summary='2026년 10월 2일 완료될 것으로 보입니다.',
                summary_ids=['learning.math.forecast.earliest_date'],
            ),
        )
        self.assertFalse(full.valid)
        self.assertIn(CODE_FORGED_FORECAST_DATE, _codes(full))

    def test_packet_forecast_korean_dates_allowed(self):
        result = validate_teacher_interpretation(
            _peer_packet(),
            _output(
                summary='완료 예상 구간은 12월 20일부터 12월 28일입니다.',
                summary_ids=[
                    'learning.math.forecast.earliest_date',
                    'learning.math.forecast.latest_date',
                ],
            ),
        )
        self.assertTrue(result.valid)

    def test_reference_only_peer_sole_priority_rejected(self):
        result = validate_teacher_interpretation(
            _peer_packet(),
            _output(
                summary='또래 중앙값만 근거로 핵심 결론을 냅니다.',
                summary_ids=['learning.math.coverage_peer.peer_median'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_REFERENCE_ONLY_SOLE_PRIORITY, _codes(result))

    def test_reference_only_peer_sole_next_action_rejected(self):
        result = validate_teacher_interpretation(
            _peer_packet(),
            _output(
                summary='독서 활동일은 5일입니다.',
                summary_ids=['reading.activity_days.current'],
                suggestions=[{
                    'text': '또래 중앙값만 보고 행동을 정하면 좋겠습니다.',
                    'evidence_ids': ['learning.math.coverage_peer.peer_median'],
                    'conditional': True,
                }],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_REFERENCE_ONLY_SOLE_NEXT_ACTION, _codes(result))

    def test_reference_only_peer_as_supporting_observation_allowed(self):
        result = validate_teacher_interpretation(
            _peer_packet(),
            _output(
                summary='최근 독서 활동일은 5일입니다.',
                summary_ids=['reading.activity_days.current'],
                observations=[_obs(
                    '참고 자료로 동일 계획 중앙값 자료가 있습니다.',
                    ['learning.math.coverage_peer.peer_median'],
                )],
            ),
        )
        self.assertTrue(result.valid)

    def test_reference_only_peer_with_other_priority_evidence_allowed(self):
        result = validate_teacher_interpretation(
            _peer_packet(),
            _output(
                summary='최근 독서 활동일은 5일이고, 참고로 동일 계획 중앙값 자료가 있습니다.',
                summary_ids=[
                    'reading.activity_days.current',
                    'learning.math.coverage_peer.peer_median',
                ],
            ),
        )
        self.assertTrue(result.valid)

    def test_unavailable_peer_rejected(self):
        result = validate_teacher_interpretation(
            _peer_packet(display_tier='none', available=False),
            _output(
                summary='또래 비교를 핵심으로 봅니다.',
                summary_ids=['learning.math.coverage_peer.peer_median'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNAVAILABLE_PEER, _codes(result))

    def test_limited_peer_as_major_rejected(self):
        result = validate_teacher_interpretation(
            _peer_packet(display_tier='limited'),
            _output(
                summary='또래 중앙값만으로 강한 결론을 냅니다.',
                summary_ids=['learning.math.coverage_peer.peer_median'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_LIMITED_AS_MAJOR, _codes(result))

    def test_limited_peer_sole_next_action_rejected(self):
        result = validate_teacher_interpretation(
            _peer_packet(display_tier='limited'),
            _output(
                summary='최근 독서 활동일은 5일입니다.',
                summary_ids=['reading.activity_days.current'],
                suggestions=[{
                    'text': '제한된 또래 자료만으로 다음 행동을 정하면 좋겠습니다.',
                    'evidence_ids': ['learning.math.coverage_peer.peer_median'],
                    'conditional': True,
                }],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_LIMITED_AS_MAJOR, _codes(result))

    def test_limited_peer_as_observation_allowed(self):
        result = validate_teacher_interpretation(
            _peer_packet(display_tier='limited'),
            _output(
                summary='최근 독서 활동일은 5일입니다.',
                summary_ids=['reading.activity_days.current'],
                observations=[_obs(
                    '제한된 또래 중앙값 자료가 있습니다.',
                    ['learning.math.coverage_peer.peer_median'],
                )],
            ),
        )
        self.assertTrue(result.valid)

    def test_stale_reading_observation_rejected(self):
        packet = _peer_packet(ai_status='stale')
        packet['supporting_facts']['reading']['analysis']['observations'] = [{
            'evidence_id': 'reading.analysis.observation.1',
            'available': True,
            'value': 'stale-obs',
        }]
        result = validate_teacher_interpretation(
            packet,
            _output(
                summary='stale 관찰을 사용합니다.',
                summary_ids=['reading.analysis.observation.1'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_STALE_READING_OBSERVATION, _codes(result))

    def test_invented_stale_reading_observation_id_rejected(self):
        result = validate_teacher_interpretation(
            _peer_packet(ai_status='stale'),
            _output(
                summary='존재하지 않는 독서 관찰을 사용합니다.',
                summary_ids=['reading.analysis.observation.1'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNKNOWN_EVIDENCE_ID, _codes(result))

    def test_raw_reading_quote_rejected_derived_observation_allowed(self):
        packet = _peer_packet(ai_status='current')
        packet['supporting_facts']['reading']['analysis']['observations'] = [{
            'evidence_id': 'reading.analysis.observation.1',
            'available': True,
            'value': '문장 길이가 늘어난 기록이 있습니다.',
        }]
        quoted = validate_teacher_interpretation(
            packet,
            _output(
                summary='"이 책은 정말 재미있었고 주인공이 용감했다"',
                summary_ids=['reading.analysis.observation.1'],
            ),
        )
        self.assertFalse(quoted.valid)
        self.assertIn(CODE_RAW_READING_QUOTE, _codes(quoted))

        derived = validate_teacher_interpretation(
            packet,
            _output(
                summary='문장 길이가 늘어난 기록이 있습니다.',
                summary_ids=['reading.analysis.observation.1'],
            ),
        )
        self.assertTrue(derived.valid)

    def test_rank_language_rejected(self):
        result = validate_teacher_interpretation(
            _packet(),
            _output(
                summary='백분위로 상위권입니다.',
                summary_ids=['reading.activity_days.current'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_RANK_LANGUAGE, _codes(result))
