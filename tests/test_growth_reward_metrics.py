"""Deterministic reward/exemption/recommended-book Growth metrics. LLM 없음."""
from __future__ import annotations

import inspect
import json
import unittest
from datetime import date, timedelta

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    EVENT_RECOMMENDED_COMPLETE,
    POLICY_VERSION_GENERAL_V2,
    POLICY_VERSION_RECOMMENDED_V1,
    PROGRAM_TYPE_RECOMMENDED,
    STATUS_COMPLETED,
    TICKET_STATUS_USED,
    Book,
    ChildReading,
    ExemptionTicket,
    ExemptionUsage,
    ReadingDay,
    ReadingRewardEvent,
)
from features.growth.evidence_packet import build_teacher_evidence_packet
from features.growth.metrics import metrics_bundle
from features.growth.reward_metrics import reward_metrics


AS_OF = date(2026, 8, 22)
CURRENT_IN = date(2026, 8, 10)
PREV_IN = date(2026, 7, 10)
FUTURE = date(2026, 8, 23)


class RewardMetricsTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='reward_teacher',
            name='보상교사',
            role='돌봄선생님',
            email='reward-teacher@example.test',
            password_hash='',
        )
        self.child = Child(name='보상아동', grade=3, viewer_slug='rewardchildslugxxxxxxx')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _peer(self, name, slug):
        child = Child(name=name, grade=3, viewer_slug=slug)
        db.session.add(child)
        db.session.flush()
        return child

    def _used_ticket(self, child, used_on):
        ticket = ExemptionTicket(
            child_id=child.id,
            issued_on=used_on,
            expires_on=used_on + timedelta(days=30),
            status=TICKET_STATUS_USED,
            policy_version='v1',
            issued_by_user_id=self.teacher.id,
        )
        db.session.add(ticket)
        db.session.flush()
        db.session.add(ExemptionUsage(
            exemption_ticket_id=ticket.id,
            subject_key='math',
            subject_name='수학',
            used_on=used_on,
            recorded_by_user_id=self.teacher.id,
        ))
        return ticket

    def _manual(self, child, on, points, source_type='bonus'):
        history = json.dumps([{
            'id': 1,
            'subject': '추가 포인트',
            'points': points,
            'reason': '보너스',
            'source_type': source_type,
        }], ensure_ascii=False)
        db.session.add(DailyPoints(
            child_id=child.id,
            date=on,
            korean_points=0,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=points,
            manual_history=history,
            total_points=points,
            created_by=self.teacher.id,
        ))

    def _recommended(self, child, started_on, completed_on, day_on):
        book = Book(title='추천책', normalized_key='rec-' + str(child.id) + str(day_on), is_active=True)
        db.session.add(book)
        db.session.flush()
        reading = ChildReading(
            child_id=child.id,
            book_id=book.id,
            started_on=started_on,
            completed_on=completed_on,
            status=STATUS_COMPLETED,
            program_type=PROGRAM_TYPE_RECOMMENDED,
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        db.session.add(ReadingDay(
            child_reading_id=reading.id,
            date=day_on,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        ))
        return reading

    def test_current_previous_windows_and_future_exclusion(self):
        self._used_ticket(self.child, CURRENT_IN)
        self._used_ticket(self.child, PREV_IN)
        self._used_ticket(self.child, FUTURE)
        self._manual(self.child, CURRENT_IN, 50)
        self._manual(self.child, PREV_IN, 20)
        self._manual(self.child, FUTURE, 99)
        db.session.commit()
        payload = reward_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(payload['exemption_usage']['current'], 1)
        self.assertEqual(payload['exemption_usage']['previous'], 1)
        self.assertEqual(payload['exemption_usage']['delta'], 0)
        self.assertEqual(payload['manual_points']['event_count_current'], 1)
        self.assertEqual(payload['manual_points']['event_count_previous'], 1)
        self.assertEqual(payload['manual_points']['current'], 50)
        self.assertEqual(payload['manual_points']['previous'], 20)

    def test_reading_reward_source_is_not_manual_bonus(self):
        reading = self._recommended(self.child, CURRENT_IN, CURRENT_IN, CURRENT_IN)
        db.session.add(ReadingRewardEvent(
            child_reading_id=reading.id,
            event_type=EVENT_RECOMMENDED_COMPLETE,
            points=200,
            awarded_on=CURRENT_IN,
            policy_version=POLICY_VERSION_RECOMMENDED_V1,
            created_by_user_id=self.teacher.id,
        ))
        self._manual(self.child, CURRENT_IN, 200, source_type='recommended_reading')
        db.session.commit()
        payload = reward_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(payload['manual_points']['current'], 0)
        self.assertEqual(payload['manual_points']['event_count_current'], 0)
        self.assertEqual(payload['reading_reward_points']['current'], 200)

    def test_recommended_activity_and_completions(self):
        self._recommended(self.child, CURRENT_IN, CURRENT_IN, CURRENT_IN)
        self._recommended(self.child, PREV_IN, PREV_IN, PREV_IN)
        db.session.commit()
        payload = reward_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(payload['recommended']['activity_days']['current'], 1)
        self.assertEqual(payload['recommended']['activity_days']['previous'], 1)
        self.assertEqual(payload['recommended']['completions']['current'], 1)
        self.assertEqual(payload['recommended']['completions']['previous'], 1)

    def test_peer_excludes_self_and_requires_n(self):
        self._used_ticket(self.child, CURRENT_IN)
        peer_a = self._peer('또래A', 'rewardpeeraslugxxxxxxxx')
        peer_b = self._peer('또래B', 'rewardpeerbslugxxxxxxxx')
        self._used_ticket(peer_a, CURRENT_IN)
        self._used_ticket(peer_a, CURRENT_IN - timedelta(days=1))
        self._used_ticket(peer_b, CURRENT_IN)
        self._used_ticket(peer_b, CURRENT_IN - timedelta(days=2))
        db.session.commit()
        payload = reward_metrics(self.child.id, as_of=AS_OF, window_days=30)
        peer = payload['exemption_usage']['peer']
        self.assertEqual(peer['n'], 2)
        self.assertTrue(peer['available'])
        self.assertEqual(peer['median'], 2)
        other_grade = Child(name='다른학년', grade=4, viewer_slug='rewardothergradeslugxx')
        db.session.add(other_grade)
        db.session.commit()
        again = reward_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(again['exemption_usage']['peer']['n'], 2)

    def test_peer_n_one_median_unavailable(self):
        peer = self._peer('혼자', 'rewardlonelypeerxxxxxxxx')
        self._used_ticket(peer, CURRENT_IN)
        db.session.commit()
        payload = reward_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(payload['exemption_usage']['peer']['n'], 1)
        self.assertFalse(payload['exemption_usage']['peer']['available'])
        self.assertIsNone(payload['exemption_usage']['peer']['median'])

    def test_packet_whitelist_includes_reward_ids_without_raw_events(self):
        self._used_ticket(self.child, CURRENT_IN)
        db.session.commit()
        bundle = metrics_bundle(self.child.id, as_of=AS_OF)
        packet = build_teacher_evidence_packet(bundle, grade=3)
        rewards = packet['supporting_facts']['rewards']
        self.assertEqual(rewards['exemption_usage']['current']['evidence_id'], 'rewards.exemption.usage.current')
        self.assertEqual(rewards['exemption_usage']['current']['value'], 1)
        blob = json.dumps(packet, ensure_ascii=False)
        self.assertNotIn('review_text', blob)
        self.assertNotIn('exemption_ticket', blob)
        self.assertNotIn('manual_history', blob)

    def test_no_causal_claim_in_metric_code(self):
        source = inspect.getsource(inspect.getmodule(reward_metrics))
        self.assertNotIn('때문에', source)
        self.assertNotIn('동기가', source)
        self.assertNotIn('causal', source.lower())
