"""Growth Step 3: teacher view-model assembly. LLM/rank/NFC 없음."""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    POLICY_VERSION_GENERAL_V2,
    STATUS_COMPLETED,
    Book,
    ChildReading,
    LearningProgressEntry,
    ReadingDay,
)
from features.growth.copy import (
    HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN,
    READING_ACTIVITY_INCREASE,
)
from features.growth.insights import generate_insight_candidates, top_candidates
from features.growth.service import INSIGHT_LIMIT, build_growth_view_model
from features.progress.service import ensure_default_subjects
from feature_models import LearningSubject  # noqa: E402


AS_OF = date(2026, 12, 15)
PREV_START = date(2026, 10, 17)
CURRENT_START = date(2026, 11, 16)


class GrowthServiceTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        ensure_default_subjects()
        self.teacher = User(
            username='growth_svc_teacher',
            name='성장교사',
            role='돌봄선생님',
            email='growth-svc@example.test',
            password_hash='',
        )
        self.child = Child(name='성장아동', grade=3, viewer_slug='gggggggggggggggggggggggg')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        self.subjects = {row.key: row for row in LearningSubject.query.all()}

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _book(self, title):
        book = Book(title=title, normalized_key=title, is_active=True, grade_band='2-3')
        db.session.add(book)
        db.session.flush()
        return book

    def _reading_days(self, dates):
        book = self._book('성장책')
        reading = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            started_on=dates[0],
            status='in_progress',
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        for on in dates:
            db.session.add(ReadingDay(
                child_reading_id=reading.id,
                date=on,
                created_by_user_id=self.teacher.id,
                actor_type=ACTOR_TEACHER,
                policy_version=POLICY_VERSION_GENERAL_V2,
            ))
        db.session.commit()
        return reading

    def _completed(self, title, completed_on, *, difficulty=None, fun=None, started_on=None):
        book = self._book(title)
        started = started_on or (completed_on - timedelta(days=2))
        reading = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            started_on=started,
            completed_on=completed_on,
            status=STATUS_COMPLETED,
            policy_version=POLICY_VERSION_GENERAL_V2,
            difficulty_rating=difficulty,
            fun_rating=fun,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        db.session.add(ReadingDay(
            child_reading_id=reading.id,
            date=completed_on,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        ))
        db.session.commit()
        return reading

    def _progress(self, subject_key, recorded_on, page, title):
        db.session.add(LearningProgressEntry(
            child_id=self.child.id,
            learning_subject_id=self.subjects[subject_key].id,
            recorded_on=recorded_on,
            textbook_title=title,
            page=page,
            created_by_user_id=self.teacher.id,
        ))
        db.session.commit()

    def _points(self, on, total, *, korean=0, manual=0):
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
            manual_points=manual,
            manual_history='[]',
            total_points=total,
            created_by=self.teacher.id,
        ))
        db.session.commit()

    def test_assembles_metrics_candidates_and_copy(self):
        previous = [PREV_START + timedelta(days=offset) for offset in range(6)]
        current = [CURRENT_START + timedelta(days=offset) for offset in range(11)]
        self._reading_days(previous + current)
        view = build_growth_view_model(self.child, as_of=AS_OF)
        self.assertEqual(view['as_of'], AS_OF)
        self.assertEqual(view['current_window']['start'], CURRENT_START)
        self.assertEqual(len(view['insights']), 1)
        self.assertEqual(view['insights'][0]['id'], READING_ACTIVITY_INCREASE)
        self.assertIn('늘었어요', view['insights'][0]['headline'])
        self.assertEqual(view['insights'][0]['comparison_line'], '이전 6일 → 최근 11일')
        self.assertEqual(view['empty_reason'], None)
        self.assertNotIn('bundle', view['insights'][0])
        reading_kpi = next(item for item in view['kpis'] if item['key'] == 'reading_days')
        self.assertTrue(reading_kpi['comparable'])
        self.assertTrue(reading_kpi['comparison_available'])
        self.assertEqual(reading_kpi['current'], 11)
        self.assertEqual(reading_kpi['previous'], 6)
        self.assertEqual(reading_kpi['delta'], 5)
        self.assertEqual(reading_kpi['comparison_display'], '6일 → 11일')
        self.assertEqual(view['charts']['activity']['current'][0], 11)
        self.assertEqual(view['charts']['activity']['previous'][0], 6)
        self.assertEqual(view['insights'][0]['evidence']['current'], 11)
        self.assertEqual(view['insights'][0]['evidence']['previous'], 6)
        self.assertEqual(view['insights'][0]['evidence']['delta'], 5)

    def test_incomparable_kpi_keeps_current_without_previous_delta_or_tone(self):
        self._reading_days([CURRENT_START])
        view = build_growth_view_model(self.child, as_of=AS_OF)
        reading_kpi = next(item for item in view['kpis'] if item['key'] == 'reading_days')

        self.assertEqual(reading_kpi['current'], 1)
        self.assertEqual(reading_kpi['current_display'], '1일')
        self.assertFalse(reading_kpi['comparable'])
        self.assertFalse(reading_kpi['comparison_available'])
        self.assertIsNone(reading_kpi['previous'])
        self.assertIsNone(reading_kpi['delta'])
        self.assertIsNone(reading_kpi['delta_display'])
        self.assertIsNone(reading_kpi['tone'])
        self.assertIsNone(view['charts']['activity'])
        self.assertEqual(view['charts']['activity_bars'], [])
        self.assertIsNone(view['charts']['points'])

    def test_comparable_true_zero_is_flat_not_unknown(self):
        self._points(PREV_START, 0)
        view = build_growth_view_model(self.child, as_of=AS_OF)
        points_kpi = next(item for item in view['kpis'] if item['key'] == 'period_points')

        self.assertTrue(points_kpi['comparable'])
        self.assertTrue(points_kpi['comparison_available'])
        self.assertEqual(points_kpi['current'], 0)
        self.assertEqual(points_kpi['previous'], 0)
        self.assertEqual(points_kpi['delta'], 0)
        self.assertEqual(points_kpi['tone'], 'flat')
        self.assertEqual(points_kpi['comparison_display'], '0점 → 0점')
        self.assertEqual(points_kpi['change_display'], '변화 없음')
        self.assertEqual(view['charts']['points']['values'], [0, 0])

    def test_activity_chart_only_includes_comparable_metric_families(self):
        self._reading_days([PREV_START, CURRENT_START])
        self._progress('korean', PREV_START, 10, '국어')
        self._progress('korean', CURRENT_START, 20, '국어')
        view = build_growth_view_model(self.child, as_of=AS_OF)

        self.assertEqual(
            view['charts']['activity']['labels'],
            ['독서 기록일', '학습 진도 기록'],
        )
        self.assertEqual(view['charts']['activity']['previous'], [1, 1])
        self.assertEqual(view['charts']['activity']['current'], [1, 1])
        self.assertNotIn('완독', view['charts']['activity']['labels'])

    def test_incomparable_points_keep_current_and_do_not_create_chart(self):
        self._points(CURRENT_START, 1200, korean=1200)
        view = build_growth_view_model(self.child, as_of=AS_OF)
        points_kpi = next(item for item in view['kpis'] if item['key'] == 'period_points')

        self.assertEqual(points_kpi['current'], 1200)
        self.assertEqual(points_kpi['current_display'], '1,200점')
        self.assertFalse(points_kpi['comparable'])
        self.assertIsNone(points_kpi['previous'])
        self.assertIsNone(points_kpi['delta'])
        self.assertIsNone(points_kpi['tone'])
        self.assertEqual(view['points']['period_points_current_display'], '1,200점')
        self.assertIsNone(view['points']['period_points_previous_display'])
        self.assertIsNone(view['points']['period_points_delta_display'])
        self.assertIsNone(view['charts']['points'])

    def test_top_candidates_limit_is_three(self):
        self.assertEqual(INSIGHT_LIMIT, 3)
        previous = [PREV_START + timedelta(days=offset) for offset in range(6)]
        current = [CURRENT_START + timedelta(days=offset) for offset in range(11)]
        self._reading_days(previous + current)
        for index in range(4):
            self._completed(f'완독{index}', PREV_START + timedelta(days=index))
        for index in range(8):
            self._completed(f'최근완독{index}', CURRENT_START + timedelta(days=index))
        for index in range(3):
            self._progress('korean', PREV_START + timedelta(days=index), 10 + index, '국어')
        for index in range(6):
            self._progress('korean', CURRENT_START + timedelta(days=index), 40 + index, '국어')
        self._points(PREV_START, 50, korean=50)
        self._points(CURRENT_START, 200, korean=200)
        view = build_growth_view_model(self.child, as_of=AS_OF)
        candidates = generate_insight_candidates(view['bundle'])
        self.assertGreaterEqual(len(candidates), 4)
        self.assertEqual(len(view['insights']), 3)
        self.assertEqual(
            [item['id'] for item in view['insights']],
            [item.id for item in top_candidates(candidates, limit=3)],
        )

    def test_empty_insufficient_when_not_comparable(self):
        view = build_growth_view_model(self.child, as_of=AS_OF)
        self.assertEqual(view['insights'], [])
        self.assertEqual(view['empty_reason'], 'insufficient')

    def test_empty_no_change_when_comparable_but_flat(self):
        days = [PREV_START + timedelta(days=offset) for offset in range(6)]
        days += [CURRENT_START + timedelta(days=offset) for offset in range(6)]
        self._reading_days(days)
        view = build_growth_view_model(self.child, as_of=AS_OF)
        self.assertEqual(view['insights'], [])
        self.assertEqual(view['empty_reason'], 'no_change')

    def test_cumulative_as_of_none_is_not_zero(self):
        view = build_growth_view_model(self.child, as_of=date(2025, 1, 1))
        self.assertIsNone(view['points']['cumulative_as_of'])
        self.assertTrue(view['points']['cumulative_unavailable'])
        self.assertNotEqual(view['points']['cumulative_as_of'], 0)

    def test_latest_snapshot_outside_current_window_still_shown(self):
        self._progress('korean', date(2026, 10, 1), 51, '우등생 국어 3-2')
        view = build_growth_view_model(self.child, as_of=AS_OF)
        korean = next(item for item in view['progress']['latest_snapshots'] if item['key'] == 'korean')
        self.assertEqual(korean['page'], 51)
        self.assertEqual(korean['recorded_on'], date(2026, 10, 1))
        self.assertEqual(korean['textbook_title'], '우등생 국어 3-2')
        self.assertLess(korean['recorded_on'], view['current_window']['start'])

    def test_future_rows_after_as_of_are_ignored(self):
        self._reading_days([PREV_START, CURRENT_START, date(2026, 12, 20)])
        self._progress('math', date(2026, 12, 20), 99, '미래수학')
        self._progress('math', date(2026, 10, 1), 88, '우등생 수학 3-2')
        self._points(date(2026, 12, 20), 500)
        view = build_growth_view_model(self.child, as_of=AS_OF)
        self.assertEqual(view['reading']['reading_days_current'], 1)
        math = next(item for item in view['progress']['latest_snapshots'] if item['key'] == 'math')
        self.assertEqual(math['page'], 88)
        self.assertEqual(math['recorded_on'], date(2026, 10, 1))
        self.assertEqual(view['points']['period_points_current'], 0)

    def test_paired_insight_is_assembled(self):
        for index, (diff, fun) in enumerate(((3, 4), (3, 4), (3, 4))):
            self._completed(
                f'이전평가{index}',
                PREV_START + timedelta(days=index),
                difficulty=diff,
                fun=fun,
            )
        for index, (diff, fun) in enumerate(((4, 4), (4, 4), (4, 4))):
            self._completed(
                f'최근평가{index}',
                CURRENT_START + timedelta(days=index),
                difficulty=diff,
                fun=fun,
            )
        view = build_growth_view_model(self.child, as_of=AS_OF)
        ids = [item['id'] for item in view['insights']]
        self.assertIn(HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN, ids)
        paired = next(item for item in view['insights'] if item['id'] == HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN)
        self.assertIn('어렵게', paired['headline'])
        self.assertTrue(any('난이도' in row[0] for row in paired['evidence_rows']))
        self.assertEqual(paired['evidence']['kind'], 'paired')
