"""Teacher assistant grounding validator. live API 호출 없음."""
from __future__ import annotations

import unittest

from features.assistant.copy import NO_RANK_REPLY, NO_RAW_READING_REPLY, POINT_AVERAGE_UNSUPPORTED
from features.assistant.grounding import (
    CODE_CROSS_CHILD_FACTS,
    CODE_DELTA_DIRECTION,
    CODE_FACT_FAMILY_MISMATCH,
    CODE_INFERRED_FACT_TYPE,
    CODE_PEER_MISMATCH,
    CODE_RANK_LANGUAGE,
    CODE_RAW_READING,
    CODE_UNAVAILABLE_AS_VALUE,
    CODE_UNSUPPORTED_NUMERIC,
    CODE_WRONG_CHILD,
    SOURCE_COMPOSE,
    SOURCE_LLM,
    SOURCE_PENDING,
    validate_grounding,
)
from features.assistant.safety import sanitize_output


def _fact(evidence_id, value, *, available=True, label=None, display_value=None):
    row = {
        'evidence_id': evidence_id,
        'available': available,
        'value': value if available else None,
        'label': label or evidence_id,
    }
    if available and display_value is not None:
        row['display_value'] = display_value
    elif available and value is not None:
        row['display_value'] = str(value)
    return row


def _points_tools(child_name='시드-포인트하위', child_id=11, facts=None):
    return [{
        'name': 'get_points_facts',
        'arguments': {'child_id': child_id},
        'result': {
            'ok': True,
            'child': {'id': child_id, 'name': child_name, 'grade': 5},
            'facts': facts or [
                _fact('points.period_total.current', 1700, label='최근 기간 포인트', display_value='1,700점'),
                _fact('points.period_total.previous', 300, label='이전 기간 포인트', display_value='300점'),
                _fact('points.period_total.delta', 1400, label='포인트 변화', display_value='1,400 증가'),
            ],
        },
    }]


class GroundingValidatorTests(unittest.TestCase):
    def test_fabricated_number_fails(self):
        result = validate_grounding(
            user_text='포인트 알려줘',
            draft_text='이전 기간은 500점입니다.',
            tool_results=_points_tools(),
            answer_source=SOURCE_LLM,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.status, 'fail')
        self.assertIn(CODE_UNSUPPORTED_NUMERIC, result.codes())

    def test_comma_and_delta_normalization_pass(self):
        text = '최근 기간 포인트는 1,700점이고, +1,400점 증가했습니다.'
        result = validate_grounding(
            user_text='포인트 알려줘',
            draft_text=text,
            tool_results=_points_tools(),
            answer_source=SOURCE_COMPOSE,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.status, 'pass')

    def test_unavailable_as_zero_fails(self):
        tools = [{
            'name': 'get_reading_facts',
            'result': {
                'ok': True,
                'child': {'id': 2, 'name': '시드-독서감소'},
                'facts': [_fact('reading.completions.current', None, available=False, label='최근 기간 완독')],
            },
        }]
        result = validate_grounding(
            user_text='완독 알려줘',
            draft_text='최근 기간 완독은 0권입니다.',
            tool_results=tools,
            answer_source=SOURCE_LLM,
        )
        self.assertFalse(result.ok)
        self.assertIn(CODE_UNAVAILABLE_AS_VALUE, result.codes())

    def test_wrong_child_fails(self):
        result = validate_grounding(
            user_text='포인트 알려줘',
            draft_text='수진의 최근 기간 포인트는 1,700점입니다.',
            tool_results=_points_tools(),
            conversation_state={'active_child_id': 11, 'active_child_nickname': '시드-포인트하위'},
            page_context={'child_id': 3, 'child_name': '수진'},
            answer_source=SOURCE_LLM,
        )
        self.assertFalse(result.ok)
        self.assertIn(CODE_WRONG_CHILD, result.codes())

    def test_delta_direction_reversal_fails(self):
        result = validate_grounding(
            user_text='포인트 변화',
            draft_text='포인트가 1,400점 감소했습니다.',
            tool_results=_points_tools(),
            answer_source=SOURCE_LLM,
        )
        self.assertFalse(result.ok)
        self.assertIn(CODE_DELTA_DIRECTION, result.codes())

    def test_presenter_output_passes(self):
        text = (
            '시드-포인트하위 아동의 최근 기간 포인트는 1,700점입니다.\n'
            '이전 기간 포인트는 300점이고, 포인트 변화는 1,400 증가입니다.'
        )
        result = validate_grounding(
            user_text='포인트 알려줘',
            draft_text=text,
            tool_results=_points_tools(),
            conversation_state={'active_child_nickname': '시드-포인트하위'},
            answer_source=SOURCE_COMPOSE,
        )
        self.assertTrue(result.ok, result.codes())

    def test_general_conversation_minutes_are_skipped(self):
        result = validate_grounding(
            user_text='잠깐 쉬자',
            draft_text='10분 정도 쉬어보세요. 두 가지 방법이 있어요.',
            tool_results=[],
            answer_source=SOURCE_LLM,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.status, 'skipped')

    def test_pending_source_is_skipped(self):
        result = validate_grounding(
            user_text='2번째',
            draft_text='시드-포인트하위 아동을 확인했어요.',
            tool_results=[],
            answer_source=SOURCE_PENDING,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.status, 'skipped')

    def test_factual_multi_child_comparison_passes(self):
        tools = _points_tools() + _points_tools(
            child_name='수진',
            child_id=3,
            facts=[_fact('points.period_total.current', 500, label='최근 기간 포인트', display_value='500점')],
        )
        result = validate_grounding(
            user_text='시드-포인트하위와 수진 포인트 알려줘',
            draft_text='시드-포인트하위 최근 기간 포인트는 1,700점이고, 수진은 500점입니다.',
            tool_results=tools,
            answer_source=SOURCE_COMPOSE,
        )
        self.assertTrue(result.ok)
        self.assertNotIn(CODE_CROSS_CHILD_FACTS, result.codes())
        self.assertNotIn(CODE_RANK_LANGUAGE, result.codes())

    def test_rank_language_with_multi_child_facts_fails(self):
        tools = _points_tools() + _points_tools(
            child_name='수진',
            child_id=3,
            facts=[_fact('points.period_total.current', 500, label='최근 기간 포인트', display_value='500점')],
        )
        result = validate_grounding(
            user_text='누가 제일 공부 못해?',
            draft_text='수진이 제일 못하고 꼴등입니다.',
            tool_results=tools,
            answer_source=SOURCE_LLM,
        )
        self.assertFalse(result.ok)
        self.assertIn(CODE_RANK_LANGUAGE, result.codes())

    def test_learning_question_with_learning_evidence_passes(self):
        tools = [{
            'name': 'get_learning_facts',
            'result': {
                'ok': True,
                'child': {'id': 11, 'name': '시드-진도증가', 'grade': 5},
                'facts': [_fact('learning.math.performance.studied_days.current', 4, label='수학 학습일')],
            },
        }]
        result = validate_grounding(
            user_text='이번 주 학습 기록 어때?',
            draft_text='수학 학습일은 4일입니다.',
            tool_results=tools,
            answer_source=SOURCE_COMPOSE,
        )
        self.assertTrue(result.ok)
        self.assertNotIn(CODE_FACT_FAMILY_MISMATCH, result.codes())

    def test_learning_question_with_attendance_only_fails(self):
        tools = [{
            'name': 'get_learning_facts',
            'result': {
                'ok': True,
                'child': {'id': 11, 'name': '시드-진도증가'},
                'facts': [_fact('attendance.days.current', 4, label='출석일')],
            },
        }]
        result = validate_grounding(
            user_text='이번 주 학습 기록 어때?',
            draft_text='이번 주 꾸준히 학습했어요. 출석일 4일입니다.',
            tool_results=tools,
            answer_source=SOURCE_LLM,
        )
        self.assertFalse(result.ok)
        self.assertIn(CODE_FACT_FAMILY_MISMATCH, result.codes())

    def test_attendance_question_with_learning_only_fails(self):
        tools = [{
            'name': 'get_learning_facts',
            'result': {
                'ok': True,
                'child': {'id': 11, 'name': '시드-진도증가'},
                'facts': [_fact('learning.math.performance.studied_days.current', 4, label='수학 학습일')],
            },
        }]
        result = validate_grounding(
            user_text='이번 주 출석 어때?',
            draft_text='수학 학습일은 4일이라 출석한 거예요.',
            tool_results=tools,
            answer_source=SOURCE_LLM,
        )
        self.assertFalse(result.ok)
        self.assertIn(CODE_INFERRED_FACT_TYPE, result.codes())

    def test_rank_and_raw_reading_fail(self):
        ranked = validate_grounding(
            draft_text='이 아동은 1등입니다.',
            tool_results=[],
            answer_source=SOURCE_LLM,
        )
        self.assertIn(CODE_RANK_LANGUAGE, ranked.codes())
        raw = validate_grounding(
            draft_text='review_text를 보여드릴게요.',
            tool_results=[],
            answer_source=SOURCE_LLM,
        )
        self.assertIn(CODE_RAW_READING, raw.codes())

    def test_existing_safety_replies_still_sanitize(self):
        self.assertEqual(sanitize_output('등수 3위', user_text='몇 등이야?'), NO_RANK_REPLY)
        self.assertIn('감상문 원문', NO_RAW_READING_REPLY)
        self.assertIn('평균', POINT_AVERAGE_UNSUPPORTED)


def _peer_points_tools(
    *,
    child_name='시드-포인트하위',
    child_id=11,
    current=1700,
    previous=300,
    delta=1400,
    cumulative=2500,
    median=3050,
    sample=4,
    difference=-1350,
):
    return [{
        'name': 'get_points_facts',
        'arguments': {'child_id': child_id},
        'result': {
            'ok': True,
            'child': {'id': child_id, 'name': child_name, 'grade': 5},
            'facts': [
                _fact('points.period_total.current', current, label='최근 기간 포인트', display_value=f'{current:,}점'),
                _fact('points.period_total.previous', previous, label='이전 기간 포인트', display_value=f'{previous:,}점'),
                _fact('points.period_total.delta', delta, label='포인트 변화'),
                _fact('points.cumulative_as_of', cumulative, label='현재 누적 포인트', display_value=f'{cumulative:,}점'),
                _fact('points.peer.child_value', current, label='최근 기간 포인트', display_value=f'{current:,}점'),
                _fact('points.peer.peer_median', median, label='같은 학년 최근 기간 중앙값', display_value=f'{median:,}점'),
                _fact('points.peer.n', sample, label='비교 인원', display_value=f'{sample}명'),
                _fact('points.peer.difference', difference, label='최근 기간 중앙값과 차이', display_value=f'{difference:,}점'),
            ],
        },
    }]


class PointPeerBasisGroundingTests(unittest.TestCase):
    def test_cumulative_as_peer_operand_fails_seed_points_low(self):
        result = validate_grounding(
            user_text='시드-포인트하위 포인트 알려줘',
            draft_text=(
                '시드-포인트하위 아동의 현재 누적: 2,500점\n'
                '- 같은 학년 중앙값: 3,050점\n'
                '같은 학년 중앙값보다 -1,350점 낮게 관측됩니다.'
            ),
            tool_results=_peer_points_tools(),
            answer_source=SOURCE_LLM,
        )
        self.assertFalse(result.ok)
        self.assertIn(CODE_PEER_MISMATCH, result.codes())

    def test_recent_period_peer_comparison_passes_seed_points_low(self):
        result = validate_grounding(
            user_text='시드-포인트하위 포인트 알려줘',
            draft_text=(
                '시드-포인트하위 아동은 최근 기간에 1,700점을 기록했습니다.\n'
                '- 최근 기간: **1,700점**\n'
                '- 같은 학년 최근 기간 중앙값: **3,050점** (비교 인원 4명)\n'
                '- 차이: **1,350점 낮음**\n'
                '- 현재 누적: **2,500점**'
            ),
            tool_results=_peer_points_tools(),
            answer_source=SOURCE_COMPOSE,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.status, 'pass')

    def test_cumulative_as_peer_operand_fails_seed_reading_decrease(self):
        tools = _peer_points_tools(
            child_name='시드-독서감소',
            child_id=22,
            current=5000,
            previous=5050,
            delta=-50,
            cumulative=13200,
            median=5050,
            sample=4,
            difference=-50,
        )
        result = validate_grounding(
            user_text='시드-독서감소 포인트 알려줘',
            draft_text=(
                '현재 누적: 13,200점\n'
                '- 같은 학년 중앙값: 5,050점\n'
                '같은 학년 중앙값보다 -50점 낮게 관측됩니다.'
            ),
            tool_results=tools,
            answer_source=SOURCE_LLM,
        )
        self.assertFalse(result.ok)
        self.assertIn(CODE_PEER_MISMATCH, result.codes())

    def test_recent_period_peer_comparison_passes_seed_reading_decrease(self):
        tools = _peer_points_tools(
            child_name='시드-독서감소',
            child_id=22,
            current=5000,
            previous=5050,
            delta=-50,
            cumulative=13200,
            median=5050,
            sample=4,
            difference=-50,
        )
        result = validate_grounding(
            user_text='시드-독서감소 포인트 알려줘',
            draft_text=(
                '- 최근 기간: **5,000점**\n'
                '- 같은 학년 최근 기간 중앙값: **5,050점** (비교 인원 4명)\n'
                '- 차이: **50점 낮음**\n'
                '- 현재 누적: **13,200점**'
            ),
            tool_results=tools,
            answer_source=SOURCE_COMPOSE,
        )
        self.assertTrue(result.ok)

    def test_positive_and_zero_peer_delta_pass(self):
        higher = validate_grounding(
            user_text='포인트 알려줘',
            draft_text=(
                '- 최근 기간: **3,100점**\n'
                '- 같은 학년 최근 기간 중앙값: **3,050점**\n'
                '- 차이: **50점 높음**\n'
                '- 현재 누적: **4,000점**'
            ),
            tool_results=_peer_points_tools(
                current=3100, previous=3000, delta=100,
                cumulative=4000, median=3050, sample=4, difference=50,
            ),
            answer_source=SOURCE_COMPOSE,
        )
        self.assertTrue(higher.ok)
        same = validate_grounding(
            user_text='포인트 알려줘',
            draft_text=(
                '- 최근 기간: **3,050점**\n'
                '- 같은 학년 최근 기간 중앙값: **3,050점**\n'
                '- 차이: **같음**\n'
                '- 현재 누적: **4,000점**'
            ),
            tool_results=_peer_points_tools(
                current=3050, previous=3000, delta=50,
                cumulative=4000, median=3050, sample=4, difference=0,
            ),
            answer_source=SOURCE_COMPOSE,
        )
        self.assertTrue(same.ok)


if __name__ == '__main__':
    unittest.main()
