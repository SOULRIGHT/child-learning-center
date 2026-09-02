"""PointEvent v1 projection. DB 원장/Growth/AI에 연결하지 않는다."""
from __future__ import annotations

import importlib
import inspect
import sys
import unittest
from datetime import date, datetime

from features.points.events import (
    CATEGORY_ACTIVITY_MATERIAL,
    CATEGORY_PRAISE,
    CATEGORY_STATIONERY,
    CATEGORY_TEXTBOOK_COMPLETE,
    CATEGORY_UNCLASSIFIED,
    DIRECTION_EARN,
    DIRECTION_SPEND,
    PROVENANCE_DAILY_COLUMN,
    PROVENANCE_MANUAL_JSON,
    PROVENANCE_MANUAL_SUM,
    SOURCE_DAILY_SUBJECT,
    SOURCE_MANUAL,
    ManualClassification,
    UNCLASSIFIED,
)
from features.points.mapping.current import classify_manual as current_classify
from features.points.project import accounting_parts, project_point_events


AS_OF = date(2026, 8, 22)


def _record(
    on=AS_OF,
    *,
    subjects=None,
    manual_items=None,
    manual_points=0,
    total=None,
    created_at=None,
):
    subjects = dict(subjects or {})
    items = list(manual_items or [])
    subject_sum = sum(int(value or 0) for value in subjects.values())
    if items:
        manual_sum = sum(int(item.get('points') or 0) for item in items)
    else:
        manual_sum = int(manual_points or 0)
    payload = {
        'date': on,
        'subjects': subjects,
        'manual_items': items,
        'manual_points': manual_sum if items else int(manual_points or 0),
        'total_points': total if total is not None else subject_sum + manual_sum,
        'created_at': created_at,
    }
    return payload


def _project(record, classify=current_classify):
    return project_point_events((record,), classify_manual=classify)


class PointEventSubjectTests(unittest.TestCase):
    def test_zero_subject_creates_no_event(self):
        events = _project(_record(subjects={'korean': 0, 'math': 0}))
        self.assertEqual(events, ())

    def test_positive_subject(self):
        events = _project(_record(subjects={'korean': 200}))
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.source_kind, SOURCE_DAILY_SUBJECT)
        self.assertEqual(event.subject_key, 'korean')
        self.assertEqual(event.amount, 200)
        self.assertEqual(event.direction, DIRECTION_EARN)
        self.assertEqual(event.provenance, PROVENANCE_DAILY_COLUMN)
        self.assertIsNone(event.category)

    def test_negative_subject_is_preserved(self):
        events = _project(_record(subjects={'korean': -50}))
        self.assertEqual(events[0].amount, -50)
        self.assertEqual(events[0].direction, DIRECTION_SPEND)

    def test_multiple_subjects(self):
        events = _project(_record(subjects={
            'korean': 200,
            'math': 100,
            'reading': 100,
            'ssen': 0,
        }))
        pairs = [(event.subject_key, event.amount) for event in events]
        self.assertEqual(pairs, [('korean', 200), ('math', 100), ('reading', 100)])


class PointEventManualTests(unittest.TestCase):
    def test_manual_positive_and_negative(self):
        record = _record(manual_items=[
            {'subject': '칭찬', 'reason': '칭찬', 'points': 100},
            {'subject': '프린트', 'reason': '프린트 사용', 'points': -100},
        ])
        events = _project(record)
        self.assertEqual([event.amount for event in events], [100, -100])
        self.assertEqual(events[0].direction, DIRECTION_EARN)
        self.assertEqual(events[1].direction, DIRECTION_SPEND)
        self.assertEqual(events[0].category, CATEGORY_PRAISE)
        self.assertEqual(events[1].category, CATEGORY_ACTIVITY_MATERIAL)
        self.assertEqual(events[1].item_key, 'print')
        self.assertEqual(events[0].provenance, PROVENANCE_MANUAL_JSON)

    def test_multiple_manual_events_same_day(self):
        record = _record(manual_items=[
            {'subject': '칭찬', 'points': 50},
            {'subject': '연필', 'points': -300},
            {'subject': '비즈', 'points': -200},
        ])
        events = _project(record)
        self.assertEqual(len(events), 3)
        self.assertEqual(events[2].item_key, 'beads')

    def test_zero_manual_creates_no_event(self):
        events = _project(_record(manual_items=[{'subject': '칭찬', 'points': 0}]))
        self.assertEqual(events, ())

    def test_unknown_is_unclassified(self):
        events = _project(_record(manual_items=[
            {'subject': '선생님 도움', 'reason': '정리 도움', 'points': 100},
        ]))
        self.assertEqual(events[0].category, CATEGORY_UNCLASSIFIED)

    def test_help_labels_are_not_praise(self):
        for subject in ('선생님 도움', '정리 도움'):
            events = _project(_record(manual_items=[{'subject': subject, 'points': 50}]))
            self.assertEqual(events[0].category, CATEGORY_UNCLASSIFIED, subject)

    def test_conflict_is_unclassified(self):
        events = _project(_record(manual_items=[
            {'subject': '국어교재완료', 'reason': '프린트', 'points': 1000},
        ]))
        self.assertEqual(events[0].category, CATEGORY_UNCLASSIFIED)

    def test_raw_text_is_not_rewritten(self):
        raw_subject = '  국어 교재 완료  '
        raw_reason = '완료(국어)!!'
        events = _project(_record(manual_items=[{
            'subject': raw_subject,
            'reason': raw_reason,
            'points': 2500,
        }]))
        self.assertEqual(events[0].raw_subject, raw_subject)
        self.assertEqual(events[0].raw_reason, raw_reason)
        self.assertEqual(events[0].category, CATEGORY_TEXTBOOK_COMPLETE)
        self.assertEqual(events[0].subject_key, 'korean')

    def test_activity_date_not_created_at(self):
        created = datetime(2026, 9, 1, 12, 0, 0)
        events = _project(_record(
            date(2026, 8, 1),
            subjects={'english': 100},
            created_at=created,
        ))
        self.assertEqual(events[0].activity_date, date(2026, 8, 1))

    def test_manual_sum_fallback(self):
        record = _record(subjects={'math': 100}, manual_items=[], manual_points=40, total=140)
        events = _project(record)
        self.assertEqual(len(events), 2)
        manual = events[1]
        self.assertEqual(manual.source_kind, SOURCE_MANUAL)
        self.assertEqual(manual.provenance, PROVENANCE_MANUAL_SUM)
        self.assertEqual(manual.amount, 40)
        self.assertEqual(manual.category, CATEGORY_UNCLASSIFIED)
        self.assertIsNone(manual.raw_subject)

    def test_textbook_keeps_stored_amount(self):
        events = _project(_record(manual_items=[
            {'subject': '영어교재완료', 'reason': '영어 교재 완료', 'points': 1000},
            {'subject': '쎈교재완료', 'points': 1800},
        ]))
        self.assertEqual(events[0].amount, 1000)
        self.assertEqual(events[0].subject_key, 'english')
        self.assertEqual(events[1].amount, 1800)
        self.assertEqual(events[1].subject_key, 'ssen')

    def test_amount_does_not_decide_category(self):
        for points in (3000, 2000, 1000, -100, 200):
            events = _project(_record(manual_items=[
                {'subject': '기타지급', 'reason': '메모없음', 'points': points},
            ]))
            self.assertEqual(events[0].category, CATEGORY_UNCLASSIFIED)
            self.assertEqual(events[0].amount, points)

    def test_keyword_examples(self):
        print_event = _project(_record(manual_items=[
            {'subject': '프린트 3장', 'points': -100},
        ]))[0]
        self.assertEqual(print_event.category, CATEGORY_ACTIVITY_MATERIAL)
        self.assertEqual(print_event.item_key, 'print')
        beads = _project(_record(manual_items=[
            {'subject': '비즈(대)', 'points': -300},
        ]))[0]
        self.assertEqual(beads.category, CATEGORY_ACTIVITY_MATERIAL)
        self.assertEqual(beads.item_key, 'beads')
        textbook = _project(_record(manual_items=[
            {'subject': '국어 교재 완료', 'points': 3000},
        ]))[0]
        self.assertEqual(textbook.category, CATEGORY_TEXTBOOK_COMPLETE)
        self.assertEqual(textbook.subject_key, 'korean')

    def test_stationery_generic_has_no_item_key(self):
        events = _project(_record(manual_items=[
            {'subject': '학용품 구입', 'points': -400},
            {'subject': '문구류 구입', 'points': -200},
        ]))
        self.assertEqual(events[0].category, CATEGORY_STATIONERY)
        self.assertIsNone(events[0].item_key)
        self.assertEqual(events[1].category, CATEGORY_STATIONERY)
        self.assertIsNone(events[1].item_key)

    def test_preset_key_is_hint_not_amount(self):
        events = _project(_record(manual_items=[{
            'subject': '기타',
            'reason': '',
            'points': 77,
            'presetKey': 'print',
        }]))
        self.assertEqual(events[0].amount, 77)
        self.assertEqual(events[0].category, CATEGORY_ACTIVITY_MATERIAL)
        self.assertEqual(events[0].item_key, 'print')


class PointEventReadingMirrorTests(unittest.TestCase):
    def test_reading_subject_plus_completion_mirror_is_300(self):
        record = _record(
            subjects={'reading': 100},
            manual_items=[{
                'subject': '추천독서 완독',
                'reason': '추천독서 완독 승인',
                'points': 200,
                'source_type': 'recommended_reading',
                'source_event_id': 42,
            }],
        )
        events = _project(record)
        self.assertEqual(sum(event.amount for event in events), 300)
        self.assertEqual(events[0].source_kind, SOURCE_DAILY_SUBJECT)
        self.assertEqual(events[0].amount, 100)
        self.assertFalse(events[0].is_reading_reward_mirror)
        self.assertEqual(events[1].amount, 200)
        self.assertTrue(events[1].is_reading_reward_mirror)
        self.assertEqual(events[1].source_type, 'recommended_reading')
        self.assertEqual(events[1].source_event_id, 42)
        self.assertTrue(accounting_parts(record, events)['balanced'])

    def test_mirror_is_kept_in_manual_sum(self):
        record = _record(
            subjects={'reading': 100},
            manual_items=[{
                'points': 200,
                'source_type': 'challenge_reading',
                'source_event_id': 9,
            }],
        )
        parts = accounting_parts(record, _project(record))
        self.assertEqual(parts['subject_sum'], 100)
        self.assertEqual(parts['manual_sum'], 200)
        self.assertEqual(parts['canonical_total'], 300)


class PointEventAccountingTests(unittest.TestCase):
    def test_balanced_subjects_and_manual(self):
        record = _record(
            subjects={'korean': 200, 'math': 100},
            manual_items=[{'subject': '프린트', 'points': -100}],
        )
        parts = accounting_parts(record, _project(record))
        self.assertEqual(parts['subject_sum'], 300)
        self.assertEqual(parts['manual_sum'], -100)
        self.assertTrue(parts['balanced'])

    def test_mismatch_does_not_invent_residual(self):
        record = _record(subjects={'korean': 200}, manual_items=[], total=999)
        events = _project(record)
        self.assertEqual(sum(event.amount for event in events), 200)
        parts = accounting_parts(record, events)
        self.assertFalse(parts['balanced'])
        self.assertEqual(parts['canonical_total'], 999)


class PointEventClassifierBoundaryTests(unittest.TestCase):
    def test_injected_classifier_changes_category_without_projector_change(self):
        record = _record(manual_items=[{'subject': '특별포인트', 'points': 80}])

        def fake_classify(item):
            if item.get('subject') == '특별포인트':
                return ManualClassification(category=CATEGORY_PRAISE)
            return UNCLASSIFIED

        current_events = project_point_events((record,), classify_manual=current_classify)
        fake_events = project_point_events((record,), classify_manual=fake_classify)
        self.assertEqual(current_events[0].category, CATEGORY_UNCLASSIFIED)
        self.assertEqual(fake_events[0].category, CATEGORY_PRAISE)
        self.assertEqual(current_events[0].amount, fake_events[0].amount)

    def test_project_module_does_not_import_current_mapping(self):
        for name in list(sys.modules):
            if name.startswith('features.points'):
                sys.modules.pop(name, None)
        project_mod = importlib.import_module('features.points.project')
        self.assertNotIn('features.points.mapping.current', sys.modules)
        source = inspect.getsource(project_mod)
        self.assertNotIn('mapping.current', source)
        self.assertNotIn('features.points.mapping', source)


class PointEventFetchRegressionTests(unittest.TestCase):
    """실 fetch 결과만 읽고 ReadingRewardEvent를 합에 더하지 않는지 잠근다."""

    def setUp(self):
        from tests.helpers import bootstrap_test_app
        self.app, self.db = bootstrap_test_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.db.session.remove()
        self.db.drop_all()
        self.db.create_all()
        from app import Child, User
        self.teacher = User(
            username='point_event_teacher',
            name='분석교사',
            role='돌봄선생님',
            email='point-event@example.test',
            password_hash='',
        )
        self.child = Child(name='분석아동', grade=3, viewer_slug='pppppppppppppppppppppppp')
        self.db.session.add_all([self.teacher, self.child])
        self.db.session.commit()

    def tearDown(self):
        self.db.session.remove()
        self.ctx.pop()

    def test_fetch_reading_plus_mirror_stays_300_even_if_reward_event_exists(self):
        import json
        from app import DailyPoints, fetch_child_daily_point_records
        from feature_models import (
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

        book = Book(title='보상도서', normalized_key='reward-book', is_active=True)
        self.db.session.add(book)
        self.db.session.flush()
        reading = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            program_type=PROGRAM_TYPE_RECOMMENDED,
            status=STATUS_COMPLETED,
            started_on=AS_OF,
            completed_on=AS_OF,
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        self.db.session.add(reading)
        self.db.session.flush()
        reward = ReadingRewardEvent(
            child_reading_id=reading.id,
            event_type=EVENT_RECOMMENDED_COMPLETE,
            points=200,
            awarded_on=AS_OF,
            policy_version=POLICY_VERSION_RECOMMENDED_V1,
            created_by_user_id=self.teacher.id,
        )
        self.db.session.add(reward)
        self.db.session.flush()
        history = json.dumps([{
            'id': 1,
            'subject': '추천독서 완독',
            'reason': '추천독서 완독 승인',
            'points': 200,
            'source_type': 'recommended_reading',
            'source_child_reading_id': reading.id,
            'source_event': 'complete',
            'source_event_id': reward.id,
        }], ensure_ascii=False)
        self.db.session.add(DailyPoints(
            child_id=self.child.id,
            date=AS_OF,
            korean_points=0,
            math_points=0,
            ssen_points=0,
            reading_points=100,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=200,
            manual_history=history,
            total_points=300,
            created_by=self.teacher.id,
        ))
        self.db.session.commit()

        records = fetch_child_daily_point_records(self.child.id)
        events = project_point_events(records, classify_manual=current_classify)
        self.assertEqual(sum(event.amount for event in events), 300)
        self.assertEqual(len(events), 2)
        self.assertTrue(any(event.is_reading_reward_mirror for event in events))
        self.assertTrue(accounting_parts(records[0], events)['balanced'])
        self.assertEqual(ReadingRewardEvent.query.count(), 1)


if __name__ == '__main__':
    unittest.main()
