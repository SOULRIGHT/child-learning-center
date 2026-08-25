"""Growth Data Contract: points isolation / XOR / stored-total.

이미 windows, MAX(id) dedupe, historical None, future ReadingDay,
latest progress snapshot은 test_growth_metrics.py가 잠근다.
여기서는 계약상 빠져 있던 points source 분리만 잠근다.
"""
from __future__ import annotations

import json
import unittest
from datetime import date

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, PointsHistory, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    EVENT_RECOMMENDED_COMPLETE,
    POLICY_VERSION_GENERAL_V2,
    POLICY_VERSION_RECOMMENDED_V1,
    PROGRAM_TYPE_RECOMMENDED,
    STATUS_COMPLETED,
    Book,
    ChildReading,
    ReadingRewardEvent,
)
from features.growth.metrics import points_metrics  # noqa: E402


AS_OF = date(2026, 8, 22)


class GrowthDataContractTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='contract_teacher',
            name='계약교사',
            role='돌봄선생님',
            email='contract-teacher@example.test',
            password_hash='',
        )
        self.child = Child(name='계약아동', grade=3, viewer_slug='cccccccccccccccccccccccc')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _daily(
        self,
        on,
        *,
        korean=0,
        manual=0,
        history='[]',
        total=None,
    ):
        row = DailyPoints(
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
            manual_points=manual,
            manual_history=history,
            total_points=total if total is not None else korean + manual,
            created_by=self.teacher.id,
        )
        db.session.add(row)
        db.session.flush()
        return row

    def _reading(self):
        book = Book(title='계약책', normalized_key='contract-book', is_active=True)
        db.session.add(book)
        db.session.flush()
        reading = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            started_on=AS_OF,
            completed_on=AS_OF,
            status=STATUS_COMPLETED,
            program_type=PROGRAM_TYPE_RECOMMENDED,
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        return reading

    def test_points_history_audit_does_not_change_period_points(self):
        self._daily(AS_OF, korean=100)
        db.session.commit()
        before = points_metrics(self.child.id, as_of=AS_OF, window_days=30)

        db.session.add(PointsHistory(
            child_id=self.child.id,
            date=AS_OF,
            old_korean_points=0,
            old_math_points=0,
            old_ssen_points=0,
            old_reading_points=0,
            old_piano_points=0,
            old_english_points=0,
            old_advanced_math_points=0,
            old_writing_points=0,
            old_total_points=0,
            new_korean_points=100,
            new_math_points=0,
            new_ssen_points=0,
            new_reading_points=0,
            new_piano_points=0,
            new_english_points=0,
            new_advanced_math_points=0,
            new_writing_points=0,
            new_total_points=100,
            change_type='update',
            changed_by=self.teacher.id,
            change_reason='감사 전용 audit row',
        ))
        db.session.commit()

        after = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(before, after)
        self.assertEqual(after['current']['period_points'], 100)

    def test_reward_event_without_daily_points_does_not_add_period_points(self):
        reading = self._reading()
        db.session.add(ReadingRewardEvent(
            child_reading_id=reading.id,
            event_type=EVENT_RECOMMENDED_COMPLETE,
            points=200,
            awarded_on=AS_OF,
            policy_version=POLICY_VERSION_RECOMMENDED_V1,
            created_by_user_id=self.teacher.id,
        ))
        db.session.commit()

        result = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['current']['period_points'], 0)
        self.assertEqual(result['current']['manual_points_sum'], 0)
        self.assertEqual(result['current']['point_activity_days'], 0)

    def test_reward_reflected_in_manual_history_is_counted_once(self):
        reading = self._reading()
        db.session.add(ReadingRewardEvent(
            child_reading_id=reading.id,
            event_type=EVENT_RECOMMENDED_COMPLETE,
            points=200,
            awarded_on=AS_OF,
            policy_version=POLICY_VERSION_RECOMMENDED_V1,
            created_by_user_id=self.teacher.id,
        ))
        db.session.flush()
        event = ReadingRewardEvent.query.one()
        history = json.dumps([{
            'id': 1,
            'subject': '추천독서 완독',
            'points': 200,
            'reason': '추천독서 완독 승인',
            'source_type': 'recommended_reading',
            'source_child_reading_id': reading.id,
            'source_event': 'complete',
            'source_event_id': event.id,
        }], ensure_ascii=False)
        self._daily(AS_OF, korean=100, manual=200, history=history, total=300)
        db.session.commit()

        result = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['current']['period_points'], 300)
        self.assertEqual(result['current']['manual_points_sum'], 200)
        self.assertNotEqual(result['current']['period_points'], 100 + 200 + 200)

    def test_manual_history_xor_does_not_add_column_and_history(self):
        history = json.dumps([{'id': 1, 'subject': '수동', 'points': 300}], ensure_ascii=False)
        self._daily(AS_OF, korean=100, manual=999, history=history, total=1099)
        db.session.commit()

        result = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['current']['period_points'], 400)
        self.assertEqual(result['current']['manual_points_sum'], 300)
        self.assertNotEqual(result['current']['period_points'], 100 + 999)
        self.assertNotEqual(result['current']['period_points'], 100 + 999 + 300)

    def test_empty_manual_history_uses_manual_points_column(self):
        self._daily(AS_OF, korean=100, manual=50, history='[]', total=150)
        db.session.commit()

        result = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['current']['period_points'], 150)
        self.assertEqual(result['current']['manual_points_sum'], 50)

    def test_stored_total_points_is_not_authoritative(self):
        self._daily(AS_OF, korean=100, manual=0, history='[]', total=9999)
        db.session.commit()

        result = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(result['current']['period_points'], 100)
        self.assertNotEqual(result['current']['period_points'], 9999)
        self.assertEqual(result['cumulative_as_of'], 100)


if __name__ == '__main__':
    unittest.main()
