"""Reading 8+8 selector and deterministic analysis facts."""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    POLICY_VERSION_GENERAL_V2,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    Book,
    ChildReading,
    ReadingDay,
)
from features.growth.metrics import reading_metrics  # noqa: E402
from features.reading.analysis import (  # noqa: E402
    TIER_LIMITED,
    TIER_MAJOR,
    TIER_NO_CHANGE,
    apply_allowed_ids,
    build_public_facts,
    character_count,
    select_text_records,
    sentence_count,
    sufficiency_tier,
)


AS_OF = date(2026, 8, 22)


class ReadingAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='reading_analysis_teacher',
            name='분석교사',
            role='돌봄선생님',
            email='reading-analysis@example.test',
            password_hash='',
        )
        self.child = Child(name='분석아동', grade=3, viewer_slug='readanalyzereadanalyzereada')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _book(self, title):
        book = Book(title=title, normalized_key=title, is_active=True)
        db.session.add(book)
        db.session.flush()
        return book

    def _reading(self, book, started_on, status=STATUS_IN_PROGRESS, completed_on=None):
        row = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            started_on=started_on,
            completed_on=completed_on,
            ended_on=completed_on,
            status=status,
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(row)
        db.session.flush()
        return row

    def _day(self, reading, on, text=None):
        day = ReadingDay(
            child_reading_id=reading.id,
            date=on,
            review_text=text,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        )
        db.session.add(day)
        db.session.flush()
        return day

    def test_latest_nonempty_8_plus_previous_8(self):
        book = self._book('연속책')
        reading = self._reading(book, date(2026, 7, 1))
        days = []
        for index in range(20):
            days.append(self._day(
                reading,
                date(2026, 7, 1) + timedelta(days=index),
                text=f'원문 {index:02d} 충분히 긴 감상입니다.',
            ))
        db.session.commit()
        selection = select_text_records(self.child.id, as_of=AS_OF)
        self.assertEqual(len(selection.recent), 8)
        self.assertEqual(len(selection.previous), 8)
        self.assertEqual(selection.recent[0].day_id, days[19].id)
        self.assertEqual(selection.recent[-1].day_id, days[12].id)
        self.assertEqual(selection.previous[0].day_id, days[11].id)
        self.assertEqual(selection.previous[-1].day_id, days[4].id)
        self.assertEqual(selection.all_text_count, 20)

    def test_blank_review_excluded_from_text_samples(self):
        book = self._book('빈감상')
        reading = self._reading(book, date(2026, 8, 1))
        self._day(reading, date(2026, 8, 10), text='   ')
        self._day(reading, date(2026, 8, 11), text=None)
        kept = self._day(reading, date(2026, 8, 12), text='남아요')
        db.session.commit()
        selection = select_text_records(self.child.id, as_of=AS_OF)
        self.assertEqual([row.day_id for row in selection.recent], [kept.id])
        self.assertEqual(selection.previous, ())

    def test_blank_review_still_counts_in_reading_days(self):
        book = self._book('활동일')
        reading = self._reading(book, date(2026, 8, 1))
        self._day(reading, date(2026, 8, 10), text=None)
        self._day(reading, date(2026, 8, 11), text='원문')
        db.session.commit()
        metrics = reading_metrics(self.child.id, as_of=AS_OF, window_days=30)
        self.assertEqual(metrics['current']['reading_days'], 2)
        selection = select_text_records(self.child.id, as_of=AS_OF)
        self.assertEqual(len(selection.recent), 1)

    def test_future_review_excluded_by_as_of(self):
        book = self._book('미래')
        reading = self._reading(book, date(2026, 8, 1))
        kept = self._day(reading, AS_OF, text='오늘 감상')
        self._day(reading, AS_OF + timedelta(days=1), text='미래 감상')
        db.session.commit()
        selection = select_text_records(self.child.id, as_of=AS_OF)
        self.assertEqual([row.day_id for row in selection.recent], [kept.id])

    def test_stable_same_date_ordering(self):
        first_reading = self._reading(
            self._book('같은날1'), date(2026, 8, 20),
            status=STATUS_COMPLETED, completed_on=date(2026, 8, 20),
        )
        second_reading = self._reading(self._book('같은날2'), date(2026, 8, 20))
        first = self._day(first_reading, date(2026, 8, 20), text='먼저')
        second = self._day(second_reading, date(2026, 8, 20), text='나중')
        db.session.commit()
        selection = select_text_records(self.child.id, as_of=AS_OF)
        self.assertGreater(second.id, first.id)
        self.assertEqual(selection.recent[0].day_id, second.id)
        self.assertEqual(selection.recent[1].day_id, first.id)

    def test_character_and_sentence_count(self):
        self.assertEqual(character_count('  ab  '), 2)
        self.assertIsNone(character_count('  '))
        self.assertEqual(sentence_count('안녕'), 1)
        self.assertEqual(sentence_count('하나. 둘! 셋?\n넷'), 4)
        self.assertEqual(sentence_count('...'), 1)
        self.assertIsNone(sentence_count('\n'))

    def test_completed_count_explicit_only(self):
        done = self._book('완독책')
        reading = self._reading(
            done, date(2026, 8, 1), status=STATUS_COMPLETED, completed_on=date(2026, 8, 10),
        )
        self._day(reading, date(2026, 8, 1), text='시작')
        open_book = self._book('진행책')
        open_reading = self._reading(open_book, date(2026, 8, 5))
        self._day(open_reading, date(2026, 8, 5), text='읽는 중')
        db.session.commit()
        facts = build_public_facts(self.child.id, as_of=AS_OF)
        self.assertEqual(facts['completed_count'], 1)

    def test_completion_duration_median_and_missing_not_zero(self):
        empty = build_public_facts(self.child.id, as_of=AS_OF)
        self.assertIsNone(empty['completion_duration_median'])
        self.assertNotEqual(empty['completion_duration_median'], 0)
        first = self._reading(
            self._book('삼일'), date(2026, 8, 1),
            status=STATUS_COMPLETED, completed_on=date(2026, 8, 3),
        )
        self._day(first, date(2026, 8, 1), text='완독 감상')
        second = self._reading(
            self._book('오일'), date(2026, 8, 4),
            status=STATUS_COMPLETED, completed_on=date(2026, 8, 8),
        )
        self._day(second, date(2026, 8, 4), text='둘째 완독')
        db.session.commit()
        facts = build_public_facts(self.child.id, as_of=AS_OF)
        self.assertEqual(facts['completion_duration_median'], 4)

    def test_sufficiency_tiers_and_cap(self):
        self.assertEqual(sufficiency_tier(5, 5), TIER_MAJOR)
        self.assertEqual(sufficiency_tier(3, 3), TIER_LIMITED)
        self.assertEqual(sufficiency_tier(8, 2), TIER_NO_CHANGE)
        self.assertEqual(sufficiency_tier(2, 8), TIER_NO_CHANGE)
        book = self._book('상한')
        reading = self._reading(book, date(2026, 7, 1))
        for index in range(10):
            self._day(reading, date(2026, 7, 1) + timedelta(days=index), text=f'기록 {index}')
        db.session.commit()
        selection = select_text_records(self.child.id, as_of=AS_OF)
        self.assertEqual(len(selection.recent), 8)
        self.assertEqual(len(selection.previous), 2)
        facts = build_public_facts(self.child.id, as_of=AS_OF, selection=selection)
        self.assertEqual(facts['sufficiency'], TIER_NO_CHANGE)
        self.assertNotIn('review_text', str(facts))

    def test_selector_exposes_raw_for_reading_ai_only(self):
        book = self._book('원문접근')
        reading = self._reading(book, date(2026, 8, 1))
        self._day(reading, date(2026, 8, 2), text='SENTINEL_RAW_REVIEW_ZX9')
        db.session.commit()
        selection = select_text_records(self.child.id, as_of=AS_OF)
        self.assertEqual(selection.recent[0].review_text, 'SENTINEL_RAW_REVIEW_ZX9')
        facts = build_public_facts(self.child.id, as_of=AS_OF, selection=selection)
        self.assertNotIn('SENTINEL_RAW_REVIEW_ZX9', str(facts))

    def test_partial_block_recalculates_tier(self):
        book = self._book('차단')
        reading = self._reading(book, date(2026, 8, 1))
        days = [
            self._day(reading, date(2026, 8, 1) + timedelta(days=index), text=f'원문 {index}')
            for index in range(6)
        ]
        db.session.commit()
        selection = select_text_records(self.child.id, as_of=AS_OF)
        self.assertEqual(sufficiency_tier(len(selection.recent), len(selection.previous)), TIER_NO_CHANGE)
        kept = apply_allowed_ids(selection, [days[5].id, days[4].id, days[3].id])
        facts = build_public_facts(self.child.id, as_of=AS_OF, selection=kept)
        self.assertEqual(facts['recent_count'], 3)
        self.assertEqual(facts['previous_count'], 0)
        self.assertEqual(facts['sufficiency'], TIER_NO_CHANGE)

    def _seed_eight_plus_eight(self):
        book = self._book('멤버십')
        reading = self._reading(book, date(2026, 7, 1))
        start = date(2026, 7, 20)
        for index in range(16):
            self._day(reading, start + timedelta(days=index), text=f'원문 {index}')
        db.session.commit()
        selection = select_text_records(self.child.id, as_of=AS_OF)
        self.assertEqual(len(selection.recent), 8)
        self.assertEqual(len(selection.previous), 8)
        return selection

    def test_safety_keeps_recent_membership_and_tier(self):
        selection = self._seed_eight_plus_eight()
        original_recent = [row.day_id for row in selection.recent]
        original_previous = [row.day_id for row in selection.previous]
        blocked = set(original_recent[1:3])
        kept = apply_allowed_ids(
            selection,
            [item for item in original_recent + original_previous if item not in blocked],
        )
        kept_recent = [row.day_id for row in kept.recent]
        kept_previous = [row.day_id for row in kept.previous]
        self.assertEqual(kept_recent, [item for item in original_recent if item not in blocked])
        self.assertEqual(kept_previous, original_previous)
        self.assertEqual(len(kept.recent), 6)
        self.assertEqual(len(kept.previous), 8)
        self.assertTrue(set(kept_recent).isdisjoint(original_previous))
        facts = build_public_facts(self.child.id, as_of=AS_OF, selection=kept)
        self.assertEqual(facts['sufficiency'], TIER_MAJOR)

        limited = apply_allowed_ids(
            selection,
            [item for item in original_recent + original_previous if item not in set(original_recent[1:5])],
        )
        self.assertEqual([row.day_id for row in limited.previous], original_previous)
        self.assertEqual(len(limited.recent), 4)
        self.assertEqual(build_public_facts(self.child.id, as_of=AS_OF, selection=limited)['sufficiency'], TIER_LIMITED)

        no_change = apply_allowed_ids(
            selection,
            [item for item in original_recent + original_previous if item not in set(original_recent[1:7])],
        )
        self.assertEqual([row.day_id for row in no_change.previous], original_previous)
        self.assertEqual(len(no_change.recent), 2)
        self.assertEqual(
            build_public_facts(self.child.id, as_of=AS_OF, selection=no_change)['sufficiency'],
            TIER_NO_CHANGE,
        )

    def test_safety_keeps_previous_membership_and_tier(self):
        selection = self._seed_eight_plus_eight()
        original_recent = [row.day_id for row in selection.recent]
        original_previous = [row.day_id for row in selection.previous]
        blocked = set(original_previous[:3])
        kept = apply_allowed_ids(
            selection,
            [item for item in original_recent + original_previous if item not in blocked],
        )
        self.assertEqual([row.day_id for row in kept.recent], original_recent)
        self.assertEqual(
            [row.day_id for row in kept.previous],
            [item for item in original_previous if item not in blocked],
        )
        self.assertEqual(len(kept.recent), 8)
        self.assertEqual(len(kept.previous), 5)
        self.assertTrue(set(row.day_id for row in kept.previous).isdisjoint(original_recent))
        facts = build_public_facts(self.child.id, as_of=AS_OF, selection=kept)
        self.assertEqual(facts['sufficiency'], TIER_MAJOR)

        no_change = apply_allowed_ids(
            selection,
            [item for item in original_recent + original_previous if item not in set(original_previous[:6])],
        )
        self.assertEqual([row.day_id for row in no_change.recent], original_recent)
        self.assertEqual(len(no_change.previous), 2)
        self.assertEqual(
            build_public_facts(self.child.id, as_of=AS_OF, selection=no_change)['sufficiency'],
            TIER_NO_CHANGE,
        )
