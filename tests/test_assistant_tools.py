"""Step 8C3: assistant tools, compact facts, help RAG, fake provider."""
from __future__ import annotations

import inspect
import json
import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from tests.helpers import PROJECT_ROOT, bootstrap_test_app

app, db = bootstrap_test_app()

from app import VIEWER_ROLE_NAME, Child, DailyPoints, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    POLICY_VERSION_GENERAL_V2,
    Book,
    ChildReading,
    LearningProgressEntry,
    LearningSubject,
    ReadingDay,
)
from features.assistant.config import (
    TEACHER_ASSISTANT_ENABLED_ENV,
    TEACHER_ASSISTANT_LIVE_ENV,
    TEACHER_ASSISTANT_PROVIDER_ENV,
    assistant_provider_name,
)
from features.assistant.copy import (
    CONTEXT_REPAIR_FALLBACK,
    FALLBACK,
    MSG_FOCUS_UNAVAILABLE,
    POINT_AVERAGE_UNSUPPORTED,
    SETUP_FORBIDDEN,
)
from features.assistant.facts import (
    READING_ALLOWED_EVIDENCE_IDS,
    compact_facts,
    facts_matching_focus,
    growth_facts_for_child,
)
from features.assistant.help import search_help
from features.assistant.navigation import (
    classify_remainder_domain,
    extract_child_query,
    split_child_request,
)
from features.assistant.navigation import lookup_child
from features.assistant.openai_provider import OpenAIAssistantProvider, SYSTEM_PROMPT
from features.assistant.persona import MUON_NAME, MUON_NAME_EN
from features.assistant.policy import gated_execute
from features.assistant.provider import FakeAssistantProvider, compose_from_tools, get_assistant_provider
from features.assistant.safety import sanitize_output
from features.assistant.tools import ALLOWED_TOOLS, TOOL_SCHEMAS, dump_tool_result, execute_tool
from features.growth.ai.runtime import build_current_packet
from features.progress.service import ensure_default_subjects

AS_OF = date(2026, 9, 10)
FLAG_ON = {
    TEACHER_ASSISTANT_ENABLED_ENV: 'true',
    TEACHER_ASSISTANT_PROVIDER_ENV: 'fake',
    'CLC_TESTING': '1',
}
SENTINEL_REVIEW = 'SENTINEL_READING_REVIEW_TEXT_DO_NOT_LEAK'


class AssistantToolsCase(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='tools_teacher',
            name='도구교사',
            role='돌봄선생님',
            email='tools-teacher@example.test',
            password_hash='',
        )
        self.general = User(
            username='tools_general',
            name='도구일반',
            role='일반사용자',
            email='tools-general@example.test',
            password_hash='',
        )
        self.child = Child(name='민수', grade=2, viewer_slug='toolsminsuchildslugxx')
        self.other = Child(name='수진', grade=3, viewer_slug='toolssujinchildslugxx')
        db.session.add_all([self.teacher, self.general, self.child, self.other])
        db.session.commit()
        ensure_default_subjects()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.client = app.test_client()
        self.env = patch.dict(os.environ, FLAG_ON, clear=False)
        self.env.start()
        os.environ.pop(TEACHER_ASSISTANT_LIVE_ENV, None)

    def tearDown(self):
        self.env.stop()
        db.session.remove()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def _post(self, payload, user=None):
        if user is not None:
            self._login(user)
        return self.client.post(
            '/assistant/message',
            json=payload,
            headers={'Accept': 'application/json'},
        )

    def _progress(self, on, *, page=40):
        db.session.add(LearningProgressEntry(
            child_id=self.child.id,
            learning_subject_id=self.math.id,
            recorded_on=on,
            textbook_title='수학',
            page=page,
            created_by_user_id=self.teacher.id,
        ))
        db.session.commit()

    def _daily(self, on, *, korean=120):
        db.session.add(DailyPoints(
            child_id=self.child.id,
            date=on,
            korean_points=korean,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=0,
            manual_history='[]',
            total_points=korean,
            created_by=self.teacher.id,
        ))
        db.session.commit()

    def _reading(self, on):
        book = Book(title='도구책', normalized_key='도구책', is_active=True, grade_band='2-3')
        db.session.add(book)
        db.session.flush()
        reading = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            started_on=on,
            status='in_progress',
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        db.session.add(ReadingDay(
            child_reading_id=reading.id,
            date=on,
            review_text=SENTINEL_REVIEW,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        ))
        db.session.commit()


class FactsToolTests(AssistantToolsCase):
    def test_facts_include_evidence_id_and_available(self):
        self._progress(date(2026, 9, 1), page=40)
        self._daily(date(2026, 9, 2), korean=120)
        payload = growth_facts_for_child(self.child.id, as_of=AS_OF, topic='growth')
        self.assertTrue(payload['ok'])
        self.assertTrue(payload['facts'])
        for fact in payload['facts']:
            self.assertIn('evidence_id', fact)
            self.assertIn('available', fact)
            self.assertIn('label', fact)
            if not fact['available']:
                self.assertIsNone(fact.get('value'))
                self.assertNotEqual(fact.get('value'), 0)

    def test_unavailable_is_not_coerced_to_zero(self):
        payload = growth_facts_for_child(self.child.id, as_of=AS_OF, topic='points')
        self.assertTrue(payload['ok'])
        for fact in payload['facts']:
            if fact['available'] is False:
                self.assertIsNone(fact.get('value'))

    def test_point_average_is_not_a_canonical_capability(self):
        self._daily(date(2026, 9, 2), korean=120)
        result = execute_tool(
            'get_points_facts',
            {
                'child_id': self.child.id,
                'requested_metric': 'average',
            },
            page_context={'endpoint': 'dashboard'},
            role='돌봄선생님',
        )
        self.assertTrue(result['ok'])
        self.assertFalse(result['metric_supported'])
        self.assertEqual(result['requested_metric'], 'average')
        self.assertIn('평균', result['capability_note'])
        self.assertFalse(any('평균' in (fact.get('label') or '') for fact in result['facts']))

        with app.test_request_context('/'):
            completion = compose_from_tools([{
                'name': 'get_points_facts',
                'arguments': {
                    'child_id': self.child.id,
                    'requested_metric': 'average',
                },
                'result': result,
            }])
        self.assertEqual(completion.text, POINT_AVERAGE_UNSUPPORTED)
        self.assertNotIn('확인하고 싶은 아동 기록', completion.text)

    def test_reading_facts_exclude_review_text(self):
        self._reading(date(2026, 9, 3))
        raw = ReadingDay.query.filter_by(review_text=SENTINEL_REVIEW).one()
        self.assertEqual(raw.review_text, SENTINEL_REVIEW)
        payload = growth_facts_for_child(self.child.id, as_of=AS_OF, topic='reading')
        dumped = json.dumps(payload, ensure_ascii=False)
        provider_payload = dump_tool_result(payload)
        self.assertNotIn(SENTINEL_REVIEW, dumped)
        self.assertNotIn(SENTINEL_REVIEW, provider_payload)
        self.assertNotIn('review_text', dumped)
        self.assertNotIn('review_text', provider_payload)
        for fact in payload['facts']:
            self.assertIn(fact['evidence_id'], READING_ALLOWED_EVIDENCE_IDS)
            self.assertFalse(str(fact.get('evidence_id') or '').startswith('reading.analysis.observation'))

    def test_peer_facts_come_from_existing_packet(self):
        packet = build_current_packet(self.child, as_of=AS_OF)
        expected_ids = {
            node['evidence_id']
            for node in _walk_ids(packet.get('supporting_facts') or {})
            if 'peer' in node['evidence_id']
        }
        payload = growth_facts_for_child(self.child.id, as_of=AS_OF, topic='peer')
        got = {fact['evidence_id'] for fact in payload['facts']}
        self.assertTrue(got)
        self.assertTrue(got <= expected_ids)

    def test_reading_facts_use_korean_presentation_without_internal_keys(self):
        packet = {
            'scope': {},
            'supporting_facts': {
                'reading': {
                    'activity_days': {
                        'current': _fact('reading.activity_days.current', 0, unit='day'),
                        'previous': _fact('reading.activity_days.previous', 13, unit='day'),
                        'delta': _fact('reading.activity_days.delta', -13, unit='day'),
                    },
                    'completions': {
                        'current': _fact('reading.completions.current', 0, unit='book'),
                        'previous': _fact('reading.completions.previous', 4, unit='book'),
                    },
                    'analysis': {
                        'recent_count': _fact('reading.analysis.recent_count', 0),
                    },
                },
            },
        }
        facts = compact_facts(packet, topic='reading')
        by_id = {fact['evidence_id']: fact for fact in facts}
        self.assertEqual(by_id['reading.activity_days.current']['label'], '최근 기간 독서 활동')
        self.assertEqual(by_id['reading.activity_days.current']['display_value'], '0일')
        self.assertEqual(by_id['reading.activity_days.previous']['display_value'], '13일')
        self.assertEqual(by_id['reading.activity_days.delta']['display_value'], '13일 감소')
        self.assertEqual(by_id['reading.completions.current']['display_value'], '0권')
        self.assertEqual(by_id['reading.completions.previous']['display_value'], '4권')
        self.assertEqual(by_id['reading.analysis.recent_count']['label'], '최근 기간 독서 기록')
        self.assertEqual(by_id['reading.analysis.recent_count']['display_value'], '0건')

        result = {
            'ok': True,
            'child': {'id': self.child.id, 'name': self.child.name, 'grade': self.child.grade},
            'facts': facts,
        }
        with app.test_request_context('/'):
            completion = compose_from_tools([{
                'name': 'get_reading_facts',
                'arguments': {'child_id': self.child.id},
                'result': result,
            }])
        provider_payload = dump_tool_result(result)
        visible = completion.text + provider_payload
        self.assertNotIn('activity_days', visible)
        self.assertNotIn('reading.completions', visible)
        self.assertNotIn('reading_completions_current', visible)
        self.assertIn('독서 활동', completion.text)
        self.assertIn('13일 → 0일', completion.text)
        self.assertNotIn('변화 기간', completion.text)
        self.assertNotIn('성장 자료', completion.text)
        self.assertLessEqual(len(completion.sources), 5)

    def test_nickname_domain_words_stay_in_child_query(self):
        self.assertEqual(extract_child_query('시드-독서감소 정보 좀'), '시드-독서감소')
        self.assertEqual(extract_child_query('시드-포인트하위 정보 좀'), '시드-포인트하위')
        self.assertEqual(extract_child_query('시드-진도증가 정보 좀'), '시드-진도증가')
        split = split_child_request('시드-독서감소 포인트 알려줘')
        self.assertEqual(split['child_query'], '시드-독서감소')
        self.assertIn('포인트', split['remainder'])
        self.assertIsNone(classify_remainder_domain(split_child_request('시드-포인트하위 정보 좀')['remainder']))
        self.assertEqual(
            classify_remainder_domain(split_child_request('시드-포인트하위 독서 알려줘')['remainder'])['kind'],
            'reading',
        )
        self.assertEqual(
            classify_remainder_domain(split_child_request('시드-독서감소 포인트 알려줘')['remainder'])['kind'],
            'points',
        )
        self.assertEqual(
            classify_remainder_domain(split_child_request('시드-진도증가 수학 알려줘')['remainder'])['kind'],
            'learning',
        )

    def test_point_summary_is_readable_and_avoids_internal_labels(self):
        facts = [
            {
                'evidence_id': 'points.period_total.current',
                'label': '최근 기간 포인트',
                'value': 1700,
                'display_value': '1,700점',
                'available': True,
            },
            {
                'evidence_id': 'points.period_total.previous',
                'label': '이전 기간 포인트',
                'value': 300,
                'display_value': '300점',
                'available': True,
            },
            {
                'evidence_id': 'points.period_total.delta',
                'label': '포인트 변화',
                'value': 1400,
                'display_value': '1,400점 증가',
                'available': True,
            },
            {
                'evidence_id': 'points.cumulative_as_of',
                'label': '현재 누적 포인트',
                'value': 2500,
                'display_value': '2,500점',
                'available': True,
            },
        ]
        with app.test_request_context('/'):
            completion = compose_from_tools([{
                'name': 'get_points_facts',
                'arguments': {'child_id': self.child.id},
                'result': {
                    'ok': True,
                    'child': {'id': self.child.id, 'name': '시드-포인트하위'},
                    'facts': facts,
                },
            }])
        self.assertIn('\n', completion.text)
        self.assertIn('1,700점', completion.text)
        self.assertIn('이전 기간', completion.text)
        self.assertIn('변화', completion.text)
        self.assertNotIn('변화 기간 포인트', completion.text)
        self.assertNotIn('성장 자료', completion.text)
        self.assertLessEqual(len(completion.sources), 5)
        labels = [item.get('label') for item in completion.sources]
        self.assertEqual(len(labels), len(set(labels)))

    def _peer_point_facts(self, *, current, previous, delta, cumulative, median, sample, difference):
        return [
            {
                'evidence_id': 'points.period_total.current',
                'label': '최근 기간 포인트',
                'value': current,
                'display_value': f'{current:,}점',
                'available': True,
            },
            {
                'evidence_id': 'points.period_total.previous',
                'label': '이전 기간 포인트',
                'value': previous,
                'display_value': f'{previous:,}점',
                'available': True,
            },
            {
                'evidence_id': 'points.period_total.delta',
                'label': '포인트 변화',
                'value': delta,
                'display_value': f'{abs(delta):,}점 {"증가" if delta > 0 else "감소"}' if delta else '변화 없음',
                'available': True,
            },
            {
                'evidence_id': 'points.cumulative_as_of',
                'label': '현재 누적 포인트',
                'value': cumulative,
                'display_value': f'{cumulative:,}점',
                'available': True,
            },
            {
                'evidence_id': 'points.peer.peer_median',
                'label': '같은 학년 최근 기간 중앙값',
                'value': median,
                'display_value': f'{median:,}점',
                'available': True,
            },
            {
                'evidence_id': 'points.peer.n',
                'label': '비교 인원',
                'value': sample,
                'display_value': f'{sample}명',
                'available': True,
            },
            {
                'evidence_id': 'points.peer.difference',
                'label': '최근 기간 중앙값과 차이',
                'value': difference,
                'display_value': f'{difference:,}점',
                'available': True,
            },
        ]

    def _compose_points(self, child_name, facts):
        with app.test_request_context('/'):
            return compose_from_tools([{
                'name': 'get_points_facts',
                'arguments': {'child_id': self.child.id},
                'result': {
                    'ok': True,
                    'child': {'id': self.child.id, 'name': child_name},
                    'facts': facts,
                },
            }])

    def test_point_peer_comparison_uses_recent_period_not_cumulative(self):
        completion = self._compose_points(
            '시드-포인트하위',
            self._peer_point_facts(
                current=1700, previous=300, delta=1400,
                cumulative=2500, median=3050, sample=4, difference=-1350,
            ),
        )
        text = completion.text
        self.assertIn('최근 기간: **1,700점**', text)
        self.assertIn('같은 학년 최근 기간 중앙값: **3,050점**', text)
        self.assertIn('차이: **1,350점 낮음**', text)
        self.assertIn('현재 누적: **2,500점**', text)
        self.assertNotIn('-1,350점 낮', text)
        self.assertLess(text.find('1,700점'), text.find('3,050점'))
        self.assertLess(text.find('3,050점'), text.find('2,500점'))
        self.assertNotRegex(text, r'2,500점[\s\S]{0,80}3,050점[\s\S]{0,80}1,350점 낮')

    def test_point_peer_comparison_seed_reading_decrease(self):
        completion = self._compose_points(
            '시드-독서감소',
            self._peer_point_facts(
                current=5000, previous=5050, delta=-50,
                cumulative=13200, median=5050, sample=4, difference=-50,
            ),
        )
        text = completion.text
        self.assertIn('최근 기간: **5,000점**', text)
        self.assertIn('같은 학년 최근 기간 중앙값: **5,050점**', text)
        self.assertIn('차이: **50점 낮음**', text)
        self.assertIn('현재 누적: **13,200점**', text)
        self.assertNotIn('-50점 낮', text)
        self.assertLess(text.find('5,000점'), text.find('5,050점'))
        self.assertLess(text.find('5,050점'), text.find('13,200점'))

    def test_point_peer_positive_and_zero_delta_copy(self):
        higher = self._compose_points(
            '시드-포인트하위',
            self._peer_point_facts(
                current=3100, previous=3000, delta=100,
                cumulative=4000, median=3050, sample=4, difference=50,
            ),
        )
        self.assertIn('차이: **50점 높음**', higher.text)
        self.assertNotIn('+50점 높', higher.text)
        same = self._compose_points(
            '시드-포인트하위',
            self._peer_point_facts(
                current=3050, previous=3000, delta=50,
                cumulative=4000, median=3050, sample=4, difference=0,
            ),
        )
        self.assertIn('차이: **같음**', same.text)
        self.assertNotIn('0점 낮', same.text)
        self.assertNotIn('0점 높', same.text)

    def test_focused_metric_does_not_dump_unrelated_facts(self):
        facts = [
            {
                'evidence_id': 'reading.recommended.completions.current',
                'label': '최근 기간 추천도서 완독',
                'value': 0,
                'display_value': '0권',
                'available': True,
            },
            {
                'evidence_id': 'reading.recommended.completions.previous',
                'label': '이전 기간 추천도서 완독',
                'value': 1,
                'display_value': '1권',
                'available': True,
            },
            {
                'evidence_id': 'reading.recommended.completions.delta',
                'label': '추천도서 완독 변화',
                'value': -1,
                'display_value': '1권 감소',
                'available': True,
            },
            {
                'evidence_id': 'reading.activity_days.current',
                'label': '최근 기간 독서 활동',
                'value': 0,
                'display_value': '0일',
                'available': True,
            },
        ]
        with app.test_request_context('/'):
            completion = compose_from_tools([{
                'name': 'get_reading_facts',
                'arguments': {'child_id': self.child.id, 'focus': '추천도서 완독 변화는?'},
                'result': {
                    'ok': True,
                    'child': {'id': self.child.id, 'name': self.child.name},
                    'facts': facts,
                    'focus': '추천도서 완독 변화는?',
                },
            }], user_text='추천도서 완독 변화는?')
        self.assertIn('추천도서 완독', completion.text)
        self.assertNotIn('독서 활동', completion.text)
        self.assertLess(completion.text.count('\n'), 4)
        self.assertLessEqual(len(completion.sources), 3)

    def test_learning_facts_do_not_include_point_composition(self):
        packet = {
            'scope': {},
            'supporting_facts': {
                'points': {
                    'composition': {
                        'subjects': {
                            'math': {
                                'points': {
                                    'current': _fact(
                                        'points.composition.subjects.math.points.current', 2000,
                                    ),
                                    'previous': _fact(
                                        'points.composition.subjects.math.points.previous', 1900,
                                    ),
                                },
                                'active_days': {
                                    'current': _fact(
                                        'points.composition.subjects.math.active_days.current', 13,
                                    ),
                                },
                            },
                        },
                    },
                },
                'learning': {
                    'subjects': {
                        'math': {
                            'subject_key': 'math',
                            'subject_label': '수학',
                            'performance': {
                                'current': {
                                    'expected_days': _fact(
                                        'learning.math.performance.expected_days.current', 10,
                                    ),
                                    'studied_days': _fact(
                                        'learning.math.performance.studied_days.current', 1,
                                    ),
                                    'rate': _fact(
                                        'learning.math.performance.rate.current', 0.1,
                                    ),
                                },
                            },
                        },
                    },
                },
            },
        }
        learning = compact_facts(packet, topic='learning', subject_key='math')
        ids = [fact['evidence_id'] for fact in learning]
        self.assertTrue(ids)
        self.assertTrue(all(item.startswith('learning.math.') for item in ids))
        self.assertFalse(any(item.startswith('points.') for item in ids))
        self.assertFalse(any(fact.get('label') == '성장 자료' for fact in learning))
        by_id = {fact['evidence_id']: fact for fact in learning}
        self.assertEqual(by_id['learning.math.performance.expected_days.current']['label'], '최근 수학 예정 학습일')
        self.assertEqual(by_id['learning.math.performance.studied_days.current']['label'], '최근 수학 학습 기록일')

        points = compact_facts(packet, topic='points')
        point_ids = [fact['evidence_id'] for fact in points]
        self.assertIn('points.composition.subjects.math.points.current', point_ids)
        self.assertIn('points.composition.subjects.math.active_days.current', point_ids)
        by_point = {fact['evidence_id']: fact for fact in points}
        self.assertEqual(
            by_point['points.composition.subjects.math.points.current']['label'],
            '최근 기간 수학 포인트',
        )
        self.assertEqual(
            by_point['points.composition.subjects.math.active_days.current']['label'],
            '최근 기간 수학 포인트 활동일',
        )
        self.assertFalse(any(fact.get('label') == '성장 자료' for fact in points))

    def test_focused_metric_does_not_repeat_full_summary(self):
        facts = [
            {
                'evidence_id': 'reading.activity_days.current',
                'label': '최근 기간 독서 활동',
                'available': True,
                'value': 2,
                'display_value': '2일',
            },
            {
                'evidence_id': 'reading.recommended.completions.current',
                'label': '최근 기간 추천도서 완독',
                'available': True,
                'value': 3,
                'display_value': '3권',
            },
            {
                'evidence_id': 'reading.recommended.completions.previous',
                'label': '이전 기간 추천도서 완독',
                'available': True,
                'value': 5,
                'display_value': '5권',
            },
            {
                'evidence_id': 'reading.recommended.completions.delta',
                'label': '추천도서 완독 변화',
                'available': True,
                'value': -2,
                'display_value': '2권 감소',
            },
        ]
        focused = facts_matching_focus(facts, '추천도서 완독 변화는?')
        self.assertTrue(any(item['evidence_id'].endswith('.delta') for item in focused))
        self.assertFalse(any(item['evidence_id'] == 'reading.activity_days.current' for item in focused))
        with app.test_request_context('/'):
            completion = compose_from_tools([{
                'name': 'get_reading_facts',
                'arguments': {'child_id': self.child.id},
                'result': {
                    'ok': True,
                    'child': {'id': self.child.id, 'name': self.child.name},
                    'facts': facts,
                },
            }], user_text='추천도서 완독 변화는?')
        self.assertIn('추천도서 완독', completion.text)
        self.assertIn('2권 감소', completion.text)
        self.assertNotIn('최근 기간 독서 활동', completion.text)
        self.assertNotIn('확인된 기록입니다', completion.text)

    def test_missing_metric_is_not_invented(self):
        with app.test_request_context('/'):
            completion = compose_from_tools([{
                'name': 'get_reading_facts',
                'arguments': {'child_id': self.child.id, 'focus': '없는지표변화'},
                'result': {
                    'ok': True,
                    'child': {'id': self.child.id, 'name': self.child.name},
                    'facts': [{
                        'evidence_id': 'reading.activity_days.current',
                        'label': '최근 기간 독서 활동',
                        'available': True,
                        'value': 2,
                        'display_value': '2일',
                    }],
                    'focus': '없는지표변화',
                    'focus_unmatched': True,
                },
            }], user_text='없는지표변화는?')
        self.assertEqual(completion.text, MSG_FOCUS_UNAVAILABLE)
        self.assertNotIn('2일', completion.text)

    def test_navigate_success_text_matches_action(self):
        with app.test_request_context('/'):
            completion = compose_from_tools([{
                'name': 'navigate',
                'arguments': {'destination': 'points_detail'},
                'result': {
                    'ok': True,
                    'url': '/children/1/points',
                    'destination': 'points_detail',
                    'label': '포인트 상세',
                    'child': {'id': self.child.id, 'name': self.child.name},
                },
            }], user_text='그럼 포인트 화면으로 가줘')
        self.assertNotEqual(completion.text, FALLBACK)
        self.assertIn('포인트 상세 화면으로 이동할게요', completion.text)
        self.assertTrue(completion.actions)
        self.assertEqual(completion.actions[0]['destination'], 'points_detail')

    def test_unavailable_presentation_is_not_zero(self):
        packet = {
            'scope': {},
            'supporting_facts': {
                'reading': {
                    'activity_days': {
                        'current': {
                            'evidence_id': 'reading.activity_days.current',
                            'available': False,
                            'status': 'insufficient_history',
                            'unit': 'day',
                        },
                    },
                },
            },
        }
        fact = compact_facts(packet, topic='reading')[0]
        self.assertIsNone(fact['value'])
        self.assertNotEqual(fact['unavailable_reason'], '0')
        dumped = dump_tool_result({'ok': True, 'facts': [fact]})
        self.assertNotIn('0일', dumped)

    def test_available_zero_does_not_mask_unrelated_point_summary(self):
        tool_results = [{
            'name': 'get_points_facts',
            'result': {
                'ok': True,
                'facts': [
                    {
                        'label': '최근 추가 포인트',
                        'available': True,
                        'value': 0,
                    },
                    {
                        'label': '이전 기간 포인트',
                        'available': False,
                        'value': None,
                    },
                ],
            },
        }]
        text = '최근 추가 포인트: 0점\n이전 기간 포인트: 비교 자료 부족'
        self.assertEqual(sanitize_output(text, tool_results=tool_results), text)
        invalid = '이전 기간 포인트: 0점'
        self.assertNotEqual(sanitize_output(invalid, tool_results=tool_results), invalid)

    def test_search_child_schema_requires_extracted_child_query(self):
        schema = next(item for item in TOOL_SCHEMAS if item.get('name') == 'search_child')
        params = schema['parameters']
        self.assertEqual(params['required'], ['query', 'continuation'])
        self.assertIn('child_query', params['properties']['query']['description'])


class HelpAndRoutingTests(AssistantToolsCase):
    def test_help_source_kind_is_not_data(self):
        self._login(self.teacher)
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '기본 학습요일이 무슨 뜻이야?'}],
            'page_context': {'endpoint': 'dashboard'},
        }).get_json()
        self.assertIn('월~금', payload['message']['content'])
        self.assertTrue(payload['sources'])
        self.assertTrue(all(item['kind'] == 'help' for item in payload['sources']))
        self.assertFalse(any(item.get('auto') for item in payload['actions']))
        self.assertFalse(any(item.get('destination') == 'study_calendar' and item.get('auto') for item in payload['actions']))

    def test_data_source_kind_is_not_help(self):
        self._progress(date(2026, 9, 1), page=40)
        self._login(self.teacher)
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '민수 수학 진도 알려줘'}],
            'page_context': {'endpoint': 'dashboard'},
        }).get_json()
        self.assertTrue(payload['sources'])
        self.assertTrue(all(item['kind'] == 'data' for item in payload['sources']))
        self.assertTrue(any(item.get('evidence_id') for item in payload['sources']))

    def test_help_search_does_not_invent_missing_docs(self):
        self.assertEqual(search_help('존재하지않는정책문서쿼리xyz'), [])


class ChildLookupRegistryTests(AssistantToolsCase):
    def test_child_lookup_survives_unmapped_mapper_registry(self):
        from sqlalchemy.orm.exc import UnmappedClassError
        from extensions import db as ext_db

        class BoomRegistry:
            @property
            def mappers(self):
                raise UnmappedClassError("Class 'app.User' is not mapped")

        with patch.object(ext_db.Model, 'registry', BoomRegistry()):
            found = lookup_child(self.child.id)
        self.assertEqual(found.id, self.child.id)
        self.assertEqual(found.name, '민수')

    def test_tool_result_binds_correct_child(self):
        self._daily(date(2026, 9, 3), korean=80)
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '민수 포인트 알려줘'}],
            'page_context': {'endpoint': 'dashboard'},
        }, user=self.teacher).get_json()
        self.assertTrue(payload.get('ok'))
        self.assertEqual(
            payload['status']['conversation_state']['active_child_id'],
            self.child.id,
        )
        self.assertEqual(
            payload['status']['conversation_state']['active_child_nickname'],
            '민수',
        )

    def test_metrics_does_not_reimport_app_module(self):
        from features.growth.metrics import _canonical_daily_point_records
        source = inspect.getsource(_canonical_daily_point_records)
        self.assertNotIn('from app import fetch_child_daily_point_records', source)
        from features.points import routes as points_routes
        self.assertNotIn(
            'from app import db, fetch_child_daily_point_records',
            inspect.getsource(points_routes._collect_canonical_records),
        )

    def test_invalid_child_id_is_denied_without_rebind(self):
        self._login(self.teacher)
        with app.test_request_context('/'):
            result = gated_execute(
                'get_points_facts',
                {'child_id': 999999},
                page_context={},
                role='돌봄선생님',
                conversation_state={'active_child_id': self.child.id},
            )
        self.assertEqual(result.get('error'), 'invalid_child')
        self.assertNotEqual((result.get('child') or {}).get('id'), self.child.id)


class PermissionAndSafetyTests(AssistantToolsCase):
    def test_unknown_tool_rejected(self):
        self._login(self.teacher)
        with app.test_request_context('/'):
            result = execute_tool('delete_child', {}, page_context={}, role='돌봄선생님')
        self.assertEqual(result['error'], 'unknown_tool')
        self.assertNotIn('delete_child', ALLOWED_TOOLS)

    def test_settings_forbidden_for_general_user_via_tool(self):
        self._login(self.general)
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '민수 수학 진도 알려주고 교재 계획 화면도 열어줘'}],
        }).get_json()
        self.assertIn(SETUP_FORBIDDEN, payload['message']['content'])
        self.assertFalse(any('/settings/' in (item.get('url') or '') for item in payload['actions']))

    def test_duplicate_names_are_not_auto_selected_for_facts(self):
        twin = Child(name='민수', grade=5, viewer_slug='toolsminsutwinchildxx')
        db.session.add(twin)
        db.session.commit()
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '민수 수학 진도 알려줘'}],
        }, user=self.teacher).get_json()
        self.assertIn('여러 명', payload['message']['content'])
        self.assertEqual(payload.get('sources') or [], [])
        self.assertFalse(any(action.get('auto') for action in payload['actions']))

    def test_mix_facts_and_navigate_without_auto_jump(self):
        self._progress(date(2026, 9, 1), page=40)
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '민수 수학 진도 알려주고 교재 계획 화면도 열어줘'}],
        }, user=self.teacher).get_json()
        self.assertTrue(any(item.get('kind') == 'data' for item in payload['sources']))
        dests = [item.get('destination') for item in payload['actions']]
        self.assertIn('workbook_plans', dests)
        self.assertFalse(any(item.get('auto') for item in payload['actions']))
        self.assertIn('/settings/workbook-plans', payload['actions'][0]['url'])

    def test_navigate_tool_ignores_invented_url(self):
        self._login(self.teacher)
        with app.test_request_context('/'):
            result = execute_tool(
                'navigate',
                {'destination': 'growth', 'child_id': self.child.id, 'url': 'https://evil.example/x'},
                page_context={},
                role='돌봄선생님',
            )
        self.assertTrue(result['ok'])
        self.assertEqual(result['url'], f'/children/{self.child.id}/growth')
        self.assertNotIn('evil', result['url'])


class ProviderBoundaryTests(AssistantToolsCase):
    def test_default_provider_is_fake(self):
        self.assertIsInstance(get_assistant_provider(), FakeAssistantProvider)

    def test_testing_env_does_not_auto_enable_openai(self):
        with patch.dict(os.environ, {
            TEACHER_ASSISTANT_PROVIDER_ENV: 'openai',
            'CLC_TESTING': '1',
        }, clear=False):
            os.environ.pop(TEACHER_ASSISTANT_LIVE_ENV, None)
            self.assertEqual(assistant_provider_name(), 'fake')

    def test_openai_tool_loop_uses_server_tools(self):
        calls = []

        class Responses:
            def __init__(self):
                self.queue = [
                    SimpleNamespace(
                        output=[SimpleNamespace(
                            type='function_call',
                            name='search_help',
                            arguments=json.dumps({'query': '기본 학습요일'}),
                            call_id='call_help',
                            model_dump=lambda: {
                                'type': 'function_call',
                                'name': 'search_help',
                                'arguments': json.dumps({'query': '기본 학습요일'}),
                                'call_id': 'call_help',
                            },
                        )],
                        output_text='',
                    ),
                    SimpleNamespace(output=[], output_text='기본 학습요일이 없으면 월~금을 사용합니다.'),
                ]

            def create(self, **kwargs):
                calls.append(kwargs)
                return self.queue.pop(0)

        client = SimpleNamespace(responses=Responses())
        self._login(self.teacher)
        with app.test_request_context('/'):
            completion = OpenAIAssistantProvider(client=client).complete(
                messages=[{'role': 'user', 'content': '기본 학습요일이 무슨 뜻이야?'}],
                page_context={'endpoint': 'dashboard'},
                role='돌봄선생님',
            )
        self.assertIn('월~금', completion.text)
        self.assertTrue(any(item['kind'] == 'help' for item in completion.sources))
        self.assertEqual(calls[0]['store'], False)
        self.assertIn('tools', calls[0])

    def test_search_child_continuation_runs_canonical_tool_after_exact(self):
        self._progress(date(2026, 9, 1), page=40)

        class Responses:
            def __init__(self):
                self.queue = [
                    SimpleNamespace(
                        output=[SimpleNamespace(
                            type='function_call',
                            name='search_child',
                            arguments=json.dumps({
                                'query': '민수',
                                'continuation': 'get_learning_facts',
                                'subject_key': 'math',
                            }),
                            call_id='search',
                            model_dump=lambda: {
                                'type': 'function_call',
                                'name': 'search_child',
                                'arguments': json.dumps({
                                    'query': '민수',
                                    'continuation': 'get_learning_facts',
                                    'subject_key': 'math',
                                }),
                                'call_id': 'search',
                            },
                        )],
                        output_text='',
                    ),
                    SimpleNamespace(output=[], output_text='민수의 수학 학습 기록입니다.'),
                ]

            def create(self, **_kwargs):
                return self.queue.pop(0)

        provider = OpenAIAssistantProvider(
            client=SimpleNamespace(responses=Responses()),
            api_key='test-key',
            model='test-model',
        )
        self._login(self.teacher)
        with app.test_request_context('/'):
            completion = provider.complete(
                messages=[{'role': 'user', 'content': '민수 수학 진도 알려줘'}],
                page_context={'endpoint': 'dashboard'},
                role='돌봄선생님',
            )
        self.assertEqual(
            [item['name'] for item in completion.tool_results],
            ['search_child', 'get_learning_facts'],
        )
        self.assertTrue(completion.sources)

    def test_point_average_request_continues_to_explicit_unsupported_result(self):
        self.child.name = '시드-난이도재미유지'
        db.session.commit()
        self._daily(date(2026, 9, 2), korean=120)

        class Responses:
            def __init__(self):
                self.queue = [
                    SimpleNamespace(
                        output=[SimpleNamespace(
                            type='function_call',
                            name='search_child',
                            arguments=json.dumps({
                                'query': '시드-난이도재미유지',
                                'continuation': 'get_points_facts',
                                'requested_metric': 'average',
                            }),
                            call_id='search',
                            model_dump=lambda: {
                                'type': 'function_call',
                                'name': 'search_child',
                                'arguments': json.dumps({
                                    'query': '시드-난이도재미유지',
                                    'continuation': 'get_points_facts',
                                    'requested_metric': 'average',
                                }),
                                'call_id': 'search',
                            },
                        )],
                        output_text='',
                    ),
                    SimpleNamespace(output=[], output_text=''),
                ]

            def create(self, **_kwargs):
                return self.queue.pop(0)

        provider = OpenAIAssistantProvider(
            client=SimpleNamespace(responses=Responses()),
            api_key='test-key',
            model='test-model',
        )
        self._login(self.teacher)
        with app.test_request_context('/'):
            completion = provider.complete(
                messages=[{
                    'role': 'user',
                    'content': '시드-난이도재미유지 아동 포인트기록 평균보여줘',
                }],
                page_context={'endpoint': 'dashboard'},
                role='돌봄선생님',
            )
        self.assertEqual(
            [item['name'] for item in completion.tool_results],
            ['search_child', 'get_points_facts'],
        )
        self.assertEqual(
            completion.tool_results[-1]['arguments']['requested_metric'],
            'average',
        )
        self.assertEqual(completion.text, POINT_AVERAGE_UNSUPPORTED)

    def test_muon_identity_and_point_vocabulary_are_in_provider_contract(self):
        self.assertIn(MUON_NAME, SYSTEM_PROMPT)
        self.assertIn(MUON_NAME_EN, SYSTEM_PROMPT)
        self.assertIn('고정값', SYSTEM_PROMPT)
        self.assertIn('말했잖아', SYSTEM_PROMPT)
        points = next(item for item in TOOL_SCHEMAS if item.get('name') == 'get_points_facts')
        description = points['description']
        for phrase in ('포인트 기록', '포인트 요약', '포인트 통계', '포인트 평균'):
            self.assertIn(phrase, description)

    def test_standalone_nickname_gets_natural_record_clarification(self):
        result = execute_tool(
            'search_child',
            {'query': '민수', 'continuation': 'search_only'},
            page_context={'endpoint': 'dashboard'},
            role='돌봄선생님',
        )
        completion = compose_from_tools([{
            'name': 'search_child',
            'arguments': {'query': '민수', 'continuation': 'search_only'},
            'result': result,
        }])
        self.assertIn('민수 아동을 확인했어요', completion.text)
        self.assertIn('어떤 기록을 볼까요?', completion.text)
        self.assertIn('학습, 포인트, 독서, 성장 기록', completion.text)
        self.assertNotIn('확인하고 싶은 아동 기록', completion.text)

    def test_empty_provider_output_after_repair_uses_contextual_fallback(self):
        class Responses:
            def create(self, **_kwargs):
                return SimpleNamespace(output=[], output_text='')

        provider = OpenAIAssistantProvider(
            client=SimpleNamespace(responses=Responses()),
            api_key='test-key',
            model='test-model',
        )
        completion = provider.complete(
            messages=[
                {
                    'role': 'user',
                    'content': '시드-난이도재미유지 아동 포인트기록 평균보여줘',
                },
                {
                    'role': 'assistant',
                    'content': '요청을 제대로 처리하지 못했어요.',
                },
                {'role': 'user', 'content': '말했잖아이미'},
            ],
            page_context={'endpoint': 'dashboard'},
            role='돌봄선생님',
        )
        self.assertEqual(completion.text, CONTEXT_REPAIR_FALLBACK)
        self.assertNotIn('확인하고 싶은 아동 기록', completion.text)

    def test_provider_failure_does_not_break_page(self):
        self._login(self.teacher)
        with patch('features.assistant.runtime.get_assistant_provider') as get_provider:
            from features.assistant.provider import AssistantProviderError
            get_provider.return_value.complete.side_effect = AssistantProviderError('boom')
            failed = self._post({
                'intent': 'chat',
                'messages': [{'role': 'user', 'content': '민수 수학 진도 알려줘'}],
            })
            self.assertEqual(failed.status_code, 500)
        page = self.client.get('/dashboard')
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-testid="teacher-assistant-launcher"', page.get_data(as_text=True))


class SessionAndCharacterTests(AssistantToolsCase):
    def test_session_storage_does_not_keep_packet_dump(self):
        js = (PROJECT_ROOT / 'static' / 'js' / 'assistant.js').read_text(encoding='utf-8')
        self.assertIn('function compactSources', js)
        self.assertNotIn('supporting_facts', js)
        self.assertNotIn('review_text', js)
        self.assertNotIn('packet', js)

    def test_character_asset_is_resolved_when_present(self):
        self._login(self.teacher)
        html = self.client.get('/dashboard').get_data(as_text=True)
        self.assertIn('assistant/mark.svg', html)
        template = (PROJECT_ROOT / 'templates' / 'assistant' / '_drawer.html').read_text(encoding='utf-8')
        self.assertNotIn('<img', template)


class RuntimeFixTests(AssistantToolsCase):
    LEGACY = '학습·포인트 숫자 질문은 아직 연결되지 않았습니다'

    def test_legacy_disconnected_copy_is_not_used(self):
        source = (PROJECT_ROOT / 'features' / 'assistant' / 'copy.py').read_text(encoding='utf-8')
        self.assertNotIn(self.LEGACY, source)
        self._login(self.teacher)
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '안녕'}],
            'page_context': {'endpoint': 'dashboard'},
        }).get_json()
        text = payload['message']['content']
        self.assertNotIn(self.LEGACY, text)
        self.assertNotIn('지금은 화면 이동, 센터 설정 안내', text)
        hello = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '안녕하세요'}],
        })
        self.assertEqual(hello.status_code, 200)
        self.assertTrue(hello.get_json()['ok'])
        self.assertIn('안녕하세요', hello.get_json()['message']['content'])

    def test_page_child_alias_uses_canonical_learning_tool(self):
        self._progress(date(2026, 9, 1), page=40)
        with patch('features.assistant.policy.execute_tool', wraps=execute_tool) as wrapped:
            payload = self._post({
                'intent': 'chat',
                'messages': [{'role': 'user', 'content': '이 아이 수학 진도 알려줘'}],
                'page_context': {
                    'endpoint': 'child_detail',
                    'child_id': self.child.id,
                },
            }, user=self.teacher).get_json()
        names = [call.args[0] for call in wrapped.call_args_list]
        self.assertIn('get_learning_facts', names)
        self.assertTrue(any(item.get('kind') == 'data' for item in payload['sources']))
        self.assertNotIn(self.LEGACY, payload['message']['content'])

    def test_points_question_uses_points_tool(self):
        self._daily(date(2026, 9, 2), korean=120)
        with patch('features.assistant.policy.execute_tool', wraps=execute_tool) as wrapped:
            payload = self._post({
                'intent': 'chat',
                'messages': [{'role': 'user', 'content': '최근 포인트 알려줘'}],
                'page_context': {
                    'endpoint': 'child_detail',
                    'child_id': self.child.id,
                },
            }, user=self.teacher).get_json()
        names = [call.args[0] for call in wrapped.call_args_list]
        self.assertIn('get_points_facts', names)
        self.assertTrue(any(item.get('kind') == 'data' for item in payload['sources']))

    def test_observed_progress_help_does_not_require_child(self):
        payload = self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '관측 기반 진도가 뭐야?'}],
            'page_context': {'endpoint': 'dashboard'},
        }, user=self.teacher).get_json()
        self.assertEqual(self._post({
            'intent': 'chat',
            'messages': [{'role': 'user', 'content': '관측 기반 진도가 뭐야?'}],
        }, user=self.teacher).status_code, 200)
        self.assertIn('관측 기반 진도', payload['message']['content'])
        self.assertTrue(all(item['kind'] == 'help' for item in payload['sources']))
        self.assertNotIn('어느 아동의 기록을 볼까요', payload['message']['content'])

    def test_reset_and_retry_controls_exist_after_provider_error(self):
        self._login(self.teacher)
        html = self.client.get('/dashboard').get_data(as_text=True)
        self.assertIn('data-testid="assistant-reset"', html)
        self.assertIn('data-testid="assistant-retry"', html)
        js = (PROJECT_ROOT / 'static' / 'js' / 'assistant.js').read_text(encoding='utf-8')
        self.assertIn('function resetConversation', js)
        self.assertIn('function retryLast', js)
        self.assertIn('state.generalMessages = []', js)
        self.assertIn('state.childMessages = []', js)
        self.assertIn('intent: \'bootstrap\'', js)
        with patch('features.assistant.runtime.get_assistant_provider') as get_provider:
            from features.assistant.provider import AssistantProviderError
            get_provider.return_value.complete.side_effect = AssistantProviderError('boom')
            failed = self._post({
                'intent': 'chat',
                'messages': [{'role': 'user', 'content': '안녕'}],
            })
        self.assertEqual(failed.status_code, 500)
        self.assertIn('지금은 답변을 준비하지 못했어요', failed.get_json()['message'])
        page = self.client.get('/dashboard')
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-testid="assistant-reset"', page.get_data(as_text=True))


def _fact(evidence_id, value=None, *, available=True, unit=None):
    fact = {
        'evidence_id': evidence_id,
        'available': available,
    }
    if available:
        fact['value'] = value
    if unit:
        fact['unit'] = unit
    return fact


def _walk_ids(node):
    if isinstance(node, dict):
        if isinstance(node.get('evidence_id'), str):
            yield node
        for value in node.values():
            yield from _walk_ids(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk_ids(item)


if __name__ == '__main__':
    unittest.main()
