"""Point composition v1. Evidence/AI에 연결하지 않는다."""
from __future__ import annotations

import inspect
import unittest
from datetime import date

from features.growth.point_composition import (
    point_composition_from_events,
    summarize_point_events,
)
from features.growth.windows import current_window, previous_window
from features.points.events import (
    CATEGORY_ACTIVITY_MATERIAL,
    CATEGORY_EXTRA_LEARNING,
    CATEGORY_HELP_CONTRIBUTION,
    CATEGORY_PRAISE,
    CATEGORY_STATIONERY,
    CATEGORY_TEXTBOOK_COMPLETE,
    CATEGORY_UNCLASSIFIED,
    PROVENANCE_DAILY_COLUMN,
    PROVENANCE_MANUAL_JSON,
    PointEvent,
    SOURCE_DAILY_SUBJECT,
    SOURCE_MANUAL,
)


AS_OF = date(2026, 8, 22)
CURRENT_START = date(2026, 7, 24)
PREV_END = date(2026, 7, 23)


def _subject(on, key, amount):
    return PointEvent(
        activity_date=on,
        source_kind=SOURCE_DAILY_SUBJECT,
        amount=amount,
        provenance=PROVENANCE_DAILY_COLUMN,
        subject_key=key,
    )


def _manual(
    on,
    amount,
    *,
    category=CATEGORY_UNCLASSIFIED,
    subject_key=None,
    item_key=None,
    source_type=None,
    source_event_id=None,
    raw_subject='원문과목',
    raw_reason='원문사유',
):
    return PointEvent(
        activity_date=on,
        source_kind=SOURCE_MANUAL,
        amount=amount,
        provenance=PROVENANCE_MANUAL_JSON,
        subject_key=subject_key,
        category=category,
        item_key=item_key,
        raw_subject=raw_subject,
        raw_reason=raw_reason,
        source_type=source_type,
        source_event_id=source_event_id,
    )


def _window_sum(events):
    return summarize_point_events(events, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))


def _assert_no_raw(test, payload):
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            test.assertNotIn('raw_subject', item)
            test.assertNotIn('raw_reason', item)
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)


class PointCompositionPureTests(unittest.TestCase):
    def test_subject_korean_math_net_300(self):
        summary = _window_sum((
            _subject(AS_OF, 'korean', 200),
            _subject(AS_OF, 'math', 100),
        ))
        self.assertEqual(summary['net_points'], 300)
        self.assertEqual(summary['total_earn_points'], 300)
        self.assertEqual(summary['total_spend_points'], 0)
        self.assertEqual(summary['subjects']['korean'], {'points': 200, 'active_days': 1})
        self.assertEqual(summary['subjects']['math'], {'points': 100, 'active_days': 1})
        self.assertNotIn('ssen', summary['subjects'])

    def test_textbook_and_print_composition(self):
        summary = _window_sum((
            _manual(AS_OF, 3000, category=CATEGORY_TEXTBOOK_COMPLETE, subject_key='korean'),
            _manual(AS_OF, -200, category=CATEGORY_ACTIVITY_MATERIAL, item_key='print'),
        ))
        self.assertEqual(summary['net_points'], 2800)
        self.assertEqual(summary['total_earn_points'], 3000)
        self.assertEqual(summary['total_spend_points'], -200)
        self.assertEqual(summary['textbook']['points'], 3000)
        self.assertEqual(summary['textbook']['count'], 1)
        self.assertEqual(summary['textbook']['by_subject']['korean'], {'points': 3000, 'count': 1})
        self.assertEqual(summary['material']['points'], -200)
        self.assertEqual(summary['material']['count'], 1)
        self.assertEqual(summary['material']['by_item']['print'], {'points': -200, 'count': 1})
        self.assertEqual(summary['manual']['earn_points'], 3000)
        self.assertEqual(summary['manual']['spend_points'], -200)

    def test_reading_plus_mirror_net_300_excludes_mirror_from_manual(self):
        summary = _window_sum((
            _subject(AS_OF, 'reading', 100),
            _manual(
                AS_OF,
                200,
                category=CATEGORY_UNCLASSIFIED,
                source_type='recommended_reading',
                source_event_id=42,
            ),
        ))
        self.assertEqual(summary['net_points'], 300)
        self.assertEqual(summary['total_earn_points'], 300)
        self.assertEqual(summary['subjects']['reading']['points'], 100)
        self.assertEqual(summary['manual']['earn_points'], 0)
        self.assertEqual(summary['manual']['earn_count'], 0)
        self.assertEqual(summary['unclassified']['earn_points'], 0)
        self.assertEqual(summary['praise']['count'], 0)

    def test_praise_two_events(self):
        summary = _window_sum((
            _manual(AS_OF, 100, category=CATEGORY_PRAISE),
            _manual(date(2026, 8, 21), 50, category=CATEGORY_PRAISE),
        ))
        self.assertEqual(summary['praise']['count'], 2)
        self.assertEqual(summary['praise']['points'], 150)
        self.assertEqual(summary['manual']['earn_count'], 2)

    def test_unclassified_earn_and_spend(self):
        summary = _window_sum((
            _manual(AS_OF, 500, category=CATEGORY_UNCLASSIFIED),
            _manual(AS_OF, -100, category=CATEGORY_UNCLASSIFIED),
        ))
        self.assertEqual(summary['unclassified']['earn_points'], 500)
        self.assertEqual(summary['unclassified']['earn_count'], 1)
        self.assertEqual(summary['unclassified']['spend_points'], -100)
        self.assertEqual(summary['unclassified']['spend_count'], 1)
        self.assertEqual(summary['net_points'], 400)

    def test_textbook_by_subject_math_and_ssen(self):
        summary = _window_sum((
            _manual(AS_OF, 3000, category=CATEGORY_TEXTBOOK_COMPLETE, subject_key='math'),
            _manual(AS_OF, 2000, category=CATEGORY_TEXTBOOK_COMPLETE, subject_key='ssen'),
            _manual(AS_OF, 1000, category=CATEGORY_TEXTBOOK_COMPLETE, subject_key=None),
        ))
        self.assertEqual(summary['textbook']['points'], 6000)
        self.assertEqual(summary['textbook']['count'], 3)
        self.assertEqual(summary['textbook']['by_subject']['math'], {'points': 3000, 'count': 1})
        self.assertEqual(summary['textbook']['by_subject']['ssen'], {'points': 2000, 'count': 1})
        self.assertNotIn('english', summary['textbook']['by_subject'])
        self.assertNotIn(None, summary['textbook']['by_subject'])

    def test_stationery_without_item_key_stays_generic(self):
        summary = _window_sum((
            _manual(AS_OF, -400, category=CATEGORY_STATIONERY, item_key=None),
            _manual(AS_OF, -300, category=CATEGORY_STATIONERY, item_key='pencil'),
        ))
        self.assertEqual(summary['stationery']['points'], -700)
        self.assertEqual(summary['stationery']['count'], 2)
        self.assertEqual(summary['stationery']['by_item'], {'pencil': {'points': -300, 'count': 1}})
        self.assertNotIn(None, summary['stationery']['by_item'])

    def test_empty_window_is_zero(self):
        summary = summarize_point_events((), start_date=CURRENT_START, end_date=AS_OF)
        self.assertEqual(summary['net_points'], 0)
        self.assertEqual(summary['total_earn_points'], 0)
        self.assertEqual(summary['total_spend_points'], 0)
        self.assertEqual(summary['subjects'], {})
        self.assertEqual(summary['manual']['earn_count'], 0)
        self.assertEqual(summary['textbook']['count'], 0)
        self.assertEqual(summary['praise']['count'], 0)
        self.assertEqual(summary['help']['count'], 0)
        self.assertEqual(summary['extra_learning']['count'], 0)
        self.assertEqual(summary['extra_learning']['by_subject'], {})

    def test_current_previous_date_boundaries(self):
        events = (
            _subject(PREV_END, 'korean', 100),
            _subject(CURRENT_START, 'korean', 200),
            _subject(AS_OF, 'math', 50),
            _subject(date(2026, 8, 23), 'english', 999),
        )
        payload = point_composition_from_events(events, as_of=AS_OF, window_days=30)
        self.assertEqual(payload['current_window'], current_window(AS_OF, 30))
        self.assertEqual(payload['previous_window'], previous_window(AS_OF, 30))
        self.assertEqual(payload['previous']['net_points'], 100)
        self.assertEqual(payload['previous']['subjects']['korean']['points'], 100)
        self.assertEqual(payload['current']['net_points'], 250)
        self.assertEqual(payload['current']['subjects']['korean']['points'], 200)
        self.assertEqual(payload['current']['subjects']['math']['points'], 50)
        self.assertNotIn('english', payload['current']['subjects'])
        self.assertNotIn('english', payload['previous']['subjects'])

    def test_output_has_no_raw_text_fields(self):
        summary = _window_sum((
            _manual(AS_OF, 80, category=CATEGORY_PRAISE, raw_subject='비밀이름', raw_reason='개인메모'),
        ))
        _assert_no_raw(self, summary)
        self.assertNotIn('비밀이름', str(summary))
        self.assertNotIn('개인메모', str(summary))

    def test_created_at_is_not_used(self):
        event = _subject(AS_OF, 'piano', 100)
        summary = summarize_point_events((event,), start_date=AS_OF, end_date=AS_OF)
        self.assertEqual(summary['subjects']['piano']['points'], 100)
        self.assertFalse(hasattr(event, 'created_at'))

    def test_category_sum_is_not_net(self):
        summary = _window_sum((
            _subject(AS_OF, 'korean', 200),
            _manual(AS_OF, 3000, category=CATEGORY_TEXTBOOK_COMPLETE, subject_key='korean'),
            _manual(
                AS_OF, 200, category=CATEGORY_UNCLASSIFIED,
                source_type='recommended_reading', source_event_id=1,
            ),
        ))
        category_like = (
            summary['textbook']['points']
            + summary['praise']['points']
            + summary['help']['points']
            + summary['extra_learning']['points']
            + summary['material']['points']
            + summary['stationery']['points']
            + summary['unclassified']['earn_points']
            + summary['unclassified']['spend_points']
        )
        self.assertEqual(summary['net_points'], 3400)
        self.assertEqual(category_like, 3000)
        self.assertNotEqual(category_like, summary['net_points'])

    def test_help_and_extra_learning_composition(self):
        summary = _window_sum((
            _subject(AS_OF, 'korean', 200),
            _manual(AS_OF, 100, category=CATEGORY_HELP_CONTRIBUTION),
            _manual(AS_OF, 700, category=CATEGORY_HELP_CONTRIBUTION),
            _manual(AS_OF, 200, category=CATEGORY_EXTRA_LEARNING, subject_key='math'),
            _manual(AS_OF, 1000, category=CATEGORY_EXTRA_LEARNING, subject_key=None),
        ))
        self.assertEqual(summary['net_points'], 2200)
        self.assertEqual(summary['total_earn_points'], 2200)
        self.assertEqual(summary['total_spend_points'], 0)
        self.assertEqual(summary['subjects']['korean']['points'], 200)
        self.assertEqual(summary['manual']['earn_points'], 2000)
        self.assertEqual(summary['manual']['earn_count'], 4)
        self.assertEqual(summary['help']['points'], 800)
        self.assertEqual(summary['help']['count'], 2)
        self.assertEqual(summary['extra_learning']['points'], 1200)
        self.assertEqual(summary['extra_learning']['count'], 2)
        self.assertEqual(summary['extra_learning']['by_subject']['math'], {'points': 200, 'count': 1})
        self.assertNotIn(None, summary['extra_learning']['by_subject'])
        self.assertEqual(summary['unclassified']['earn_count'], 0)
        self.assertEqual(summary['praise']['count'], 0)

    def test_english_piano_are_regular_subjects(self):
        summary = _window_sum((
            _subject(AS_OF, 'english', 100),
            _subject(date(2026, 8, 20), 'english', 100),
            _subject(AS_OF, 'piano', 100),
        ))
        self.assertEqual(summary['subjects']['english'], {'points': 200, 'active_days': 2})
        self.assertEqual(summary['subjects']['piano'], {'points': 100, 'active_days': 1})

    def test_module_does_not_import_current_mapping(self):
        import features.growth.point_composition as module
        source = inspect.getsource(module)
        self.assertNotIn('mapping.current', source)
        self.assertNotIn('classify_manual', source)
        self.assertNotIn('from feature_models', source)
        self.assertNotIn('import feature_models', source)
        self.assertNotIn('features.points.semantic', source)


class PointCompositionCanonicalTests(unittest.TestCase):
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
            username='composition_teacher',
            name='구성교사',
            role='돌봄선생님',
            email='composition@example.test',
            password_hash='',
        )
        self.child = Child(name='구성아동', grade=3, viewer_slug='qqqqqqqqqqqqqqqqqqqqqqqq')
        self.db.session.add_all([self.teacher, self.child])
        self.db.session.commit()

    def tearDown(self):
        self.db.session.remove()
        self.ctx.pop()

    def _daily(self, on, *, korean=0, math=0, reading=0, manual=0, history='[]', total=None):
        from app import DailyPoints
        row = DailyPoints(
            child_id=self.child.id,
            date=on,
            korean_points=korean,
            math_points=math,
            ssen_points=0,
            reading_points=reading,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=manual,
            manual_history=history,
            total_points=total if total is not None else korean + math + reading + manual,
            created_by=self.teacher.id,
        )
        self.db.session.add(row)
        self.db.session.flush()
        return row

    def test_period_total_matches_composition_net_current_and_previous(self):
        from features.growth.metrics import point_composition_metrics, points_metrics
        self._daily(PREV_END, korean=100)
        self._daily(AS_OF, korean=200, math=50)
        self.db.session.commit()
        points = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        composition = point_composition_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(points['current']['period_points'], composition['current']['net_points'])
        self.assertEqual(points['previous']['period_points'], composition['previous']['net_points'])
        self.assertEqual(composition['current']['net_points'], 250)
        self.assertEqual(composition['previous']['net_points'], 100)

    def test_reading_mirror_and_reward_event_stay_300(self):
        import json
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
        from features.growth.metrics import (
            metrics_bundle,
            point_composition_metrics,
            points_metrics,
        )
        from features.growth.evidence_packet import build_teacher_evidence_packet

        book = Book(title='구성도서', normalized_key='composition-book', is_active=True)
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
            'source_event_id': reward.id,
        }], ensure_ascii=False)
        self._daily(AS_OF, reading=100, manual=200, history=history, total=300)
        self.db.session.commit()

        points = points_metrics(self.child.id, as_of=AS_OF, window_days=30)
        composition = point_composition_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(points['current']['period_points'], 300)
        self.assertEqual(composition['current']['net_points'], 300)
        self.assertEqual(composition['current']['total_earn_points'], 300)
        self.assertEqual(composition['current']['manual']['earn_points'], 0)
        self.assertNotEqual(composition['current']['net_points'], 500)
        self.assertEqual(ReadingRewardEvent.query.count(), 1)

        bundle = metrics_bundle(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(bundle['point_composition']['current']['net_points'], 300)
        packet = build_teacher_evidence_packet(bundle, grade=3)
        blob = str(packet)
        self.assertNotIn('point_composition', blob)
        self.assertNotIn('raw_subject', blob)
        self.assertNotIn('추천독서 완독 승인', blob)
        _assert_no_raw(self, bundle['point_composition'])


if __name__ == '__main__':
    unittest.main()
