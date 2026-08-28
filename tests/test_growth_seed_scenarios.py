"""Growth Step 2.5: deterministic development seed contracts. UI/route 없음."""
from __future__ import annotations

import os
import unittest
from collections import defaultdict
from datetime import date
import json
import statistics

from tests.helpers import (
    assert_test_engine_isolated,
    bootstrap_test_app,
    local_development_sqlite_path,
    test_sqlite_path,
)

app, db = bootstrap_test_app()

from app import Child, DailyPoints, PointsHistory, fetch_child_daily_point_records  # noqa: E402
from feature_models import (  # noqa: E402
    Book,
    ChildReading,
    ExemptionTicket,
    ExemptionTicketSource,
    ExemptionUsage,
    LearningProgressEntry,
    LearningSubject,
    ReadingDay,
    ReadingRewardEvent,
)
from features.exemption.policy import (  # noqa: E402
    REWARD_MODE_EXEMPTION,
    next_issue_on,
)
from features.reading.rewards import (  # noqa: E402
    EVENT_CHALLENGE_COMPLETE,
    EVENT_CHALLENGE_START,
    EVENT_RECOMMENDED_COMPLETE,
    EVENT_RECOMMENDED_START,
    incentive_reward_points,
)
from features.growth.copy import (  # noqa: E402
    HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN,
    POINTS_PERIOD_INCREASE,
)
from features.growth.insights import generate_insight_candidates  # noqa: E402
from features.growth.metrics import metrics_bundle  # noqa: E402
from scripts.seed.seed_growth_scenarios import (  # noqa: E402
    ALLOW_ENV,
    CANONICAL_ANCHOR,
    CHILD_PROFILES,
    EXPECTED,
    HALF_YEAR_START,
    SCENARIO_CATALOG,
    STUDY_OUTLIERS,
    STUDY_PACE,
    STUDY_PROFILES,
    TERM2_START,
    ZERO_PROGRESS,
    assert_growth_seed_target_allowed,
    seed_growth_scenarios,
)
from scripts.seed.growth_seed_fixtures import (  # noqa: E402
    CHALLENGE_TITLES,
    GENERAL_23,
    GENERAL_46,
    INTENTIONAL_TYPOS,
    RECOMMENDED_23,
    RECOMMENDED_46,
    book_titles,
    review_habit_for_voice,
)


AS_OF = date(2026, 12, 15)


class GrowthSeedSafetyTests(unittest.TestCase):
    def test_refuses_local_operating_db_without_allow_env(self):
        previous = os.environ.pop(ALLOW_ENV, None)
        try:
            with self.assertRaises(RuntimeError):
                assert_growth_seed_target_allowed('sqlite:///instance/child_center.db')
        finally:
            if previous is not None:
                os.environ[ALLOW_ENV] = previous

    def test_refuses_production_runtime(self):
        previous = os.environ.get('FLASK_ENV')
        os.environ['FLASK_ENV'] = 'production'
        try:
            with self.assertRaises(RuntimeError):
                assert_growth_seed_target_allowed('sqlite:////tmp/step.db')
        finally:
            if previous is None:
                os.environ.pop('FLASK_ENV', None)
            else:
                os.environ['FLASK_ENV'] = previous

    def test_seed_engine_is_isolated_from_local_development_db(self):
        with app.app_context():
            path = assert_test_engine_isolated(db)
            local = local_development_sqlite_path()
            intended = test_sqlite_path()
            self.assertTrue(path.is_absolute())
            self.assertNotEqual(path, local)
            self.assertEqual(path, intended)
            self.assertNotEqual(path.name, 'child_center.db')
            os.environ.pop(ALLOW_ENV, None)
            assert_growth_seed_target_allowed()


class GrowthSeedContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = app.app_context()
        cls.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        cls.engine_path = assert_test_engine_isolated(db)
        cls.result = seed_growth_scenarios(anchor_date=AS_OF, replace_existing=True)
        cls.children = {
            key: Child.query.get(info['id'])
            for key, info in cls.result['children'].items()
        }

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        cls.ctx.pop()

    def _bundle(self, key):
        return metrics_bundle(self.children[key].id, as_of=AS_OF, window_days=30)

    def _ids(self, key):
        return [item.id for item in generate_insight_candidates(self._bundle(key))]

    def test_catalog_size_and_models_created(self):
        self.assertEqual(len(SCENARIO_CATALOG), 22)
        self.assertEqual(Child.query.count(), 22)
        self.assertGreater(Book.query.count(), 5)
        self.assertGreater(ChildReading.query.count(), 20)
        self.assertGreater(ReadingDay.query.count(), 20)
        self.assertGreater(LearningProgressEntry.query.count(), 10)
        self.assertGreater(DailyPoints.query.count(), 20)
        grades = {child.grade for child in self.children.values()}
        self.assertGreaterEqual(len(grades), 5)

    def test_seed_is_deterministic(self):
        first = {
            key: self._ids(key)
            for key in ('S1', 'S8', 'S9', 'S10', 'S13', 'S17', 'S18')
        }
        again = seed_growth_scenarios(anchor_date=AS_OF, replace_existing=True)
        self.assertEqual(again['anchor_date'], AS_OF)
        second = {
            key: [item.id for item in generate_insight_candidates(
                metrics_bundle(again['children'][key]['id'], as_of=AS_OF, window_days=30)
            )]
            for key in first
        }
        self.assertEqual(first, second)
        GrowthSeedContractTests.children = {
            key: Child.query.get(info['id'])
            for key, info in again['children'].items()
        }

    def test_s1_reading_increase(self):
        ids = self._ids('S1')
        self.assertIn('READING_DAYS_RECENT_WINDOW_BEST', ids)
        self.assertNotIn('READING_ACTIVITY_INCREASE', ids)
        self.assertNotIn('READING_ACTIVITY_DECREASE', ids)

    def test_s3_no_reading_activity_insight(self):
        ids = self._ids('S3')
        self.assertNotIn('READING_ACTIVITY_INCREASE', ids)
        self.assertNotIn('READING_ACTIVITY_DECREASE', ids)

    def test_s8_no_points_increase(self):
        bundle = self._bundle('S8')
        self.assertTrue(bundle['points']['comparable']['points'])
        self.assertEqual(bundle['points']['previous']['point_activity_days'], 0)
        self.assertGreater(bundle['points']['current']['period_points'], 0)
        self.assertNotIn(POINTS_PERIOD_INCREASE, self._ids('S8'))

    def test_s9_paired_cross_insight(self):
        self.assertIn(HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN, self._ids('S9'))

    def test_s10_no_paired_cross_insight(self):
        self.assertNotIn(HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN, self._ids('S10'))

    def test_s12_paired_n_is_zero(self):
        reading = self._bundle('S12')['reading']
        self.assertEqual(reading['current']['paired_experience_rating']['sample_count'], 0)
        self.assertEqual(reading['previous']['paired_experience_rating']['sample_count'], 0)
        self.assertGreater(reading['previous']['difficulty_rating']['sample_count'], 0)
        self.assertGreater(reading['current']['fun_rating']['sample_count'], 0)
        self.assertNotIn(HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN, self._ids('S12'))

    def test_s13_insufficient_coverage_has_no_forced_growth(self):
        ids = self._ids('S13')
        for candidate_id in EXPECTED['S13']['exclude']:
            self.assertNotIn(candidate_id, ids)

    def test_expected_include_exclude_contracts(self):
        for key, spec in EXPECTED.items():
            ids = self._ids(key)
            for candidate_id in spec.get('include', []):
                self.assertIn(candidate_id, ids, msg=f'{key} missing {candidate_id}: {ids}')
            for candidate_id in spec.get('exclude', []):
                self.assertNotIn(candidate_id, ids, msg=f'{key} unexpected {candidate_id}: {ids}')

    def test_candidate_count_coverage(self):
        counts = {key: len(self._ids(key)) for key in SCENARIO_CATALOG}
        self.assertTrue(any(value == 0 for value in counts.values()), counts)
        self.assertTrue(any(value == 1 for value in counts.values()), counts)
        self.assertTrue(any(value == 2 for value in counts.values()), counts)
        self.assertTrue(any(value >= 3 for value in counts.values()), counts)

    def _canonical_sum(self, key):
        child = self.children[key]
        records = fetch_child_daily_point_records(child.id)
        return sum(row['total_points'] for row in records)

    def test_cumulative_matches_canonical_daily_points(self):
        for key in ('S7', 'S8', 'S16', 'S19', 'S20', 'S21'):
            child = self.children[key]
            canonical = self._canonical_sum(key)
            ledger = db.session.query(db.func.coalesce(db.func.sum(DailyPoints.total_points), 0)).filter_by(
                child_id=child.id,
            ).scalar()
            self.assertEqual(int(child.cumulative_points or 0), canonical, key)
            self.assertEqual(int(ledger or 0), canonical, key)

    def test_points_history_matches_daily_points_for_s7(self):
        child = self.children['S7']
        daily_rows = DailyPoints.query.filter_by(child_id=child.id).all()
        history = PointsHistory.query.filter_by(child_id=child.id).all()
        self.assertEqual(len(history), len(daily_rows))
        self.assertGreaterEqual(len(daily_rows), 20)
        self.assertTrue(all(row.change_type == 'create' for row in history))
        by_date = {row.date: row for row in daily_rows}
        for item in history:
            daily = by_date[item.date]
            self.assertEqual(item.new_total_points, daily.total_points)
            self.assertEqual(item.new_korean_points, daily.korean_points)
            self.assertEqual(item.new_math_points, daily.math_points)
            self.assertEqual(item.new_ssen_points, daily.ssen_points)
            self.assertEqual(item.new_reading_points, daily.reading_points)
        self.assertEqual(
            sum(row.new_total_points for row in history),
            self._canonical_sum('S7'),
        )

    def test_s16_s19_s20_cumulative_order(self):
        high = int(self.children['S16'].cumulative_points or 0)
        mid = int(self.children['S19'].cumulative_points or 0)
        low = int(self.children['S20'].cumulative_points or 0)
        self.assertGreater(high, mid)
        self.assertGreater(mid, low)

    def test_reading_day_reviews_are_mixed(self):
        total = ReadingDay.query.count()
        with_review = ReadingDay.query.filter(
            ReadingDay.review_text.isnot(None),
            ReadingDay.review_text != '',
        ).count()
        without_review = total - with_review
        self.assertGreater(with_review, 0)
        self.assertGreater(without_review, 0)

    def test_s13_stays_sparse(self):
        child = self.children['S13']
        days = ReadingDay.query.join(ChildReading).filter(ChildReading.child_id == child.id).all()
        self.assertTrue(all(not day.review_text for day in days))
        point_dates = {row.date for row in DailyPoints.query.filter_by(child_id=child.id).all()}
        reading_dates = {day.date for day in days}
        self.assertTrue(reading_dates <= point_dates)
        self.assertEqual(len(point_dates), len(reading_dates))
        self.assertLessEqual(len(days), 2)

    def test_book_titles_come_from_catalog(self):
        titles = {book.title for book in Book.query.all()}
        catalog = book_titles()
        self.assertTrue(titles)
        self.assertTrue(titles <= catalog)
        self.assertEqual(len(RECOMMENDED_23), 100)
        self.assertEqual(len(RECOMMENDED_46), 17)
        self.assertEqual(len(GENERAL_23), 25)
        self.assertEqual(len(GENERAL_46), 25)
        self.assertEqual(len(CHALLENGE_TITLES), 15)
        rec23 = Book.query.filter_by(is_recommended=True, grade_band='2-3').count()
        rec46 = Book.query.filter_by(is_recommended=True, grade_band='4-6').count()
        general = Book.query.filter_by(is_recommended=False, is_challenge_eligible=False).count()
        challenge = Book.query.filter_by(is_challenge_eligible=True).count()
        self.assertEqual(rec23, 100)
        self.assertEqual(rec46, 17)
        self.assertEqual(general, 50)
        self.assertEqual(challenge, 15)
        self.assertIn('달빛 우체국의 마지막 편지', titles)
        self.assertIn('모래시계 왕국의 마지막 기록', titles)
        self.assertIn('어린 왕자', titles)
        self.assertIn('로빈슨 크루소', titles)
        long_title = '아주 길고 조금 이상한 제목의 모험 이야기, 잃어버린 오후와 세 개의 문'
        self.assertIn(long_title, titles)
        authors = {book.author for book in Book.query.all() if book.author}
        self.assertGreaterEqual(len(authors), 8)
        same_title_bands = Book.query.filter_by(title='어린 왕자').all()
        self.assertGreaterEqual(len({row.grade_band for row in same_title_bands}), 2)

    def test_s7_manual_history_is_consistent(self):
        child = self.children['S7']
        rows = DailyPoints.query.filter_by(child_id=child.id).all()
        with_manual = [row for row in rows if (row.manual_points or 0) > 0]
        self.assertEqual(len(with_manual), 1)
        import json
        items = json.loads(with_manual[0].manual_history)
        self.assertEqual(sum(item['points'] for item in items), with_manual[0].manual_points)
        self.assertEqual(with_manual[0].total_points, self._subject_sum(with_manual[0]))

    def _subject_sum(self, row):
        return (
            (row.korean_points or 0)
            + (row.math_points or 0)
            + (row.ssen_points or 0)
            + (row.reading_points or 0)
            + (row.piano_points or 0)
            + (row.english_points or 0)
            + (row.advanced_math_points or 0)
            + (row.writing_points or 0)
            + (row.manual_points or 0)
        )

    def test_rich_scenarios_have_enough_point_days(self):
        for key in ('S1', 'S2', 'S4', 'S5', 'S6', 'S7', 'S9', 'S17'):
            n = DailyPoints.query.filter_by(child_id=self.children[key].id).count()
            self.assertGreaterEqual(n, 20, key)

    def test_reading_dates_are_subset_of_point_dates(self):
        for key, child in self.children.items():
            point_dates = {
                row.date for row in DailyPoints.query.filter_by(child_id=child.id).all()
            }
            reading_dates = {
                day.date
                for day in ReadingDay.query.join(ChildReading).filter(ChildReading.child_id == child.id).all()
            }
            self.assertTrue(reading_dates <= point_dates, key)

    def test_completed_books_mostly_last_2_to_5_activity_days(self):
        lengths = []
        for row in ChildReading.query.filter_by(status='completed').all():
            n = ReadingDay.query.filter_by(child_reading_id=row.id).count()
            lengths.append(n)
        self.assertGreater(len(lengths), 10)
        typical = sum(1 for n in lengths if 2 <= n <= 5)
        self.assertGreaterEqual(typical / len(lengths), 0.7)
        self.assertTrue(any(n >= 6 for n in lengths))

    def test_daily_points_total_matches_subject_sum(self):
        for row in DailyPoints.query.all():
            self.assertEqual(row.total_points, self._subject_sum(row), row.date)

    def test_points_history_count_matches_daily_points(self):
        for key, child in self.children.items():
            daily = DailyPoints.query.filter_by(child_id=child.id).all()
            history = PointsHistory.query.filter_by(child_id=child.id).all()
            self.assertEqual(len(history), len(daily), key)
            by_date = {row.date: row for row in daily}
            for item in history:
                daily_row = by_date[item.date]
                self.assertEqual(item.new_total_points, daily_row.total_points, key)
                self.assertEqual(item.change_type, 'create', key)

    def test_manual_points_are_rare(self):
        total = DailyPoints.query.count()
        with_manual = DailyPoints.query.filter(DailyPoints.manual_points != 0).count()
        self.assertGreater(total, 50)
        self.assertLess(with_manual, total * 0.05)

    def test_core_subjects_have_nonzero_activity(self):
        child = self.children['S1']
        rows = DailyPoints.query.filter_by(child_id=child.id).all()
        self.assertTrue(any((row.korean_points or 0) > 0 for row in rows))
        self.assertTrue(any((row.math_points or 0) > 0 for row in rows))
        self.assertTrue(any((row.ssen_points or 0) > 0 for row in rows))

    def test_long_history_has_many_completed_books(self):
        child = self.children['S21']
        completed = ChildReading.query.filter_by(child_id=child.id, status='completed').count()
        self.assertGreaterEqual(completed, 25)
        self.assertLessEqual(completed, 30)
        point_dates = {row.date for row in DailyPoints.query.filter_by(child_id=child.id).all()}
        reading_dates = {
            day.date
            for day in ReadingDay.query.join(ChildReading).filter(ChildReading.child_id == child.id).all()
        }
        self.assertTrue(reading_dates <= point_dates)
        self.assertGreaterEqual(len(point_dates), 25)

    def test_review_lifecycle_has_null_short_and_completion_text(self):
        completed = ChildReading.query.filter_by(status='completed').all()
        found_null = found_short = found_long = False
        for row in completed:
            days = (
                ReadingDay.query.filter_by(child_reading_id=row.id)
                .order_by(ReadingDay.date.asc())
                .all()
            )
            if len(days) < 3:
                continue
            texts = [(day.review_text or '').strip() for day in days]
            if any(not text for text in texts[:-1]):
                found_null = True
            if any(0 < len(text) <= 40 for text in texts[:-1]):
                found_short = True
            if texts[-1] and len(texts[-1]) >= 12:
                found_long = True
        self.assertTrue(found_null)
        self.assertTrue(found_short)
        self.assertTrue(found_long)

    def test_representative_recent_child_book_count(self):
        counts = []
        for key in ('S1', 'S2', 'S4', 'S5', 'S6', 'S7', 'S9', 'S17'):
            n = ChildReading.query.filter_by(
                child_id=self.children[key].id, status='completed',
            ).count()
            counts.append(n)
            self.assertGreaterEqual(n, 5, key)
        self.assertGreaterEqual(max(counts) - min(counts), 3)

    def test_grade_band_matches_child_grade(self):
        for row in ChildReading.query.all():
            child = Child.query.get(row.child_id)
            book = Book.query.get(row.book_id)
            if child.grade <= 3:
                self.assertEqual(book.grade_band, '2-3', child.name)
            else:
                self.assertEqual(book.grade_band, '4-6', child.name)

    def test_challenge_readings_only_for_grade_5_and_6(self):
        for row in ChildReading.query.filter_by(program_type='challenge').all():
            child = Child.query.get(row.child_id)
            self.assertIn(child.grade, (5, 6), child.name)
            book = Book.query.get(row.book_id)
            self.assertTrue(book.is_challenge_eligible)
            self.assertFalse(book.is_recommended)

    def test_same_band_children_do_not_share_identical_book_sets(self):
        pairs = (('S1', 'S5'), ('S2', 'S12'), ('S9', 'S14'))
        for left, right in pairs:
            titles_left = {
                Book.query.get(row.book_id).title
                for row in ChildReading.query.filter_by(child_id=self.children[left].id).all()
            }
            titles_right = {
                Book.query.get(row.book_id).title
                for row in ChildReading.query.filter_by(child_id=self.children[right].id).all()
            }
            self.assertTrue(titles_left)
            self.assertTrue(titles_right)
            self.assertNotEqual(titles_left, titles_right, f'{left}/{right}')

    def test_review_realism_contracts(self):
        texts = [
            (day.review_text or '').strip()
            for day in ReadingDay.query.all()
        ]
        self.assertTrue(any(not text for text in texts))
        self.assertTrue(any(text and text.count('.') <= 1 for text in texts))
        self.assertTrue(any(text.count('.') >= 2 for text in texts))
        joined = '\n'.join(text for text in texts if text)
        self.assertTrue(any(marker in joined for marker in INTENTIONAL_TYPOS))
        by_book = {}
        for row in ChildReading.query.filter_by(status='completed').all():
            days = ReadingDay.query.filter_by(child_reading_id=row.id).all()
            completion = next((day.review_text for day in days if day.date == row.completed_on), None)
            if completion:
                by_book.setdefault(row.book_id, []).append((row.child_id, completion))
        differed = False
        for pairs in by_book.values():
            children = {item[0] for item in pairs}
            reviews = {item[1] for item in pairs}
            if len(children) >= 2 and len(reviews) >= 2:
                differed = True
                break
        self.assertTrue(differed)

    def test_point_diversity_demo_contract(self):
        values = [int(child.cumulative_points or 0) for child in self.children.values()]
        self.assertGreaterEqual(max(values), 40000)
        self.assertLessEqual(min(values), 5000)
        days = [
            DailyPoints.query.filter_by(child_id=child.id).count()
            for child in self.children.values()
        ]
        self.assertGreaterEqual(max(days) - min(days), 40)
        low = [int(self.children[key].cumulative_points or 0) for key, child in self.children.items() if child.grade in (2, 3)]
        high = [int(self.children[key].cumulative_points or 0) for key, child in self.children.items() if child.grade in (5, 6)]
        self.assertGreater(statistics.median(low), statistics.median(high))
        self.assertTrue(min(low) < max(high))
        self.assertTrue(max(low) > min(high))

    def test_manual_events_include_negative_and_completion(self):
        rows = DailyPoints.query.filter(DailyPoints.manual_points != 0).all()
        self.assertTrue(rows)
        payloads = [json.loads(row.manual_history) for row in rows]
        subjects = {item['subject'] for entries in payloads for item in entries}
        self.assertTrue(any(row.manual_points < 0 for row in rows))
        self.assertTrue(any(row.manual_points >= 1000 for row in rows))
        self.assertTrue(subjects & {'학용품 구입', '문구류 구입'})
        self.assertTrue(subjects & {'쎈교재완료', '국어교재완료', '영어교재완료'})

    def test_manual_history_sum_matches_manual_points(self):
        for row in DailyPoints.query.filter(DailyPoints.manual_points != 0).all():
            items = json.loads(row.manual_history or '[]')
            self.assertEqual(sum(item['points'] for item in items), row.manual_points)

    def _progress_rows(self, key=None):
        query = LearningProgressEntry.query
        if key is not None:
            query = query.filter_by(child_id=self.children[key].id)
        return query.order_by(LearningProgressEntry.recorded_on, LearningProgressEntry.id).all()

    def _subject_map(self):
        return {row.id: row.key for row in LearningSubject.query.all()}

    def _latest_term2_page(self, key, subject_key):
        subject = LearningSubject.query.filter_by(key=subject_key).one()
        rows = [
            row for row in self._progress_rows(key)
            if row.learning_subject_id == subject.id and row.recorded_on >= TERM2_START
        ]
        if not rows:
            return None
        return max(rows, key=lambda row: (row.recorded_on, row.id)).page

    def _snapshot_gaps(self, key):
        dates = sorted({row.recorded_on for row in self._progress_rows(key)})
        return [(later - earlier).days for earlier, later in zip(dates, dates[1:])]

    def test_progress_dates_are_subset_of_point_dates(self):
        for key, child in self.children.items():
            point_dates = {row.date for row in DailyPoints.query.filter_by(child_id=child.id).all()}
            progress_dates = {row.recorded_on for row in self._progress_rows(key)}
            self.assertTrue(progress_dates <= point_dates, key)

    def test_progress_pages_are_non_decreasing_per_title(self):
        subjects = self._subject_map()
        grouped = defaultdict(list)
        for row in self._progress_rows():
            grouped[(row.child_id, subjects[row.learning_subject_id], row.textbook_title)].append(row)
        for key, rows in grouped.items():
            pages = [row.page for row in rows]
            self.assertEqual(pages, sorted(pages), key)

    def test_progress_snapshot_gaps_are_weekly_not_daily(self):
        steady_gaps = []
        all_gaps = []
        long_irregular = False
        mid_gaps = []
        for key in SCENARIO_CATALOG:
            gaps = self._snapshot_gaps(key)
            all_gaps.extend(gaps)
            if STUDY_PROFILES[key] == 'STEADY' and gaps:
                steady_gaps.extend(gaps)
            if STUDY_PROFILES[key] == 'IRREGULAR' and gaps and max(gaps) >= 14:
                long_irregular = True
            mid_gaps.extend(gap for gap in gaps if 10 <= gap <= 14)
        self.assertTrue(steady_gaps)
        typical = sum(1 for gap in steady_gaps if 4 <= gap <= 9)
        self.assertGreaterEqual(typical / len(steady_gaps), 0.55, steady_gaps)
        self.assertTrue(mid_gaps, all_gaps)
        self.assertTrue(long_irregular)
        self.assertGreaterEqual(max(all_gaps), 14)

    def test_same_grade_steady_normal_pages_cluster(self):
        by_grade = defaultdict(list)
        for key, child in self.children.items():
            if STUDY_PROFILES[key] not in ('STEADY', 'NORMAL'):
                continue
            page = self._latest_term2_page(key, 'math')
            if page is None:
                continue
            by_grade[child.grade].append((key, page))
        clustered = False
        for grade, items in by_grade.items():
            if len(items) < 2:
                continue
            pages = [page for _, page in items]
            self.assertGreater(max(pages) - min(pages), 0, items)
            self.assertLessEqual(max(pages) - min(pages), 12, items)
            clustered = True
        self.assertTrue(clustered)

    def test_same_grade_has_progress_outliers(self):
        found = []
        for grade in {child.grade for child in self.children.values()}:
            cluster = []
            outliers = []
            for key, child in self.children.items():
                if child.grade != grade:
                    continue
                page = self._latest_term2_page(key, 'math')
                if page is None:
                    continue
                if STUDY_PROFILES[key] in ('STEADY', 'NORMAL'):
                    cluster.append((key, page))
                if key in STUDY_OUTLIERS:
                    outliers.append((key, page))
            if len(cluster) < 2 or not outliers:
                continue
            cluster_max = max(page for _, page in cluster)
            for key, page in outliers:
                gap = cluster_max - page
                if 18 <= gap <= 35:
                    found.append((grade, key, cluster_max, page, gap))
        self.assertGreaterEqual(len(found), 2, found)
        self.assertLess(len(found), 8, found)

    def test_not_all_same_grade_children_share_one_page(self):
        by_grade = defaultdict(set)
        for key, child in self.children.items():
            page = self._latest_term2_page(key, 'math')
            if page is not None:
                by_grade[child.grade].add(page)
        populated = {grade: pages for grade, pages in by_grade.items() if len(pages) >= 2 or len(pages) == 1}
        self.assertTrue(any(len(pages) >= 2 for pages in populated.values()), populated)

    def test_study_pace_is_visible_across_snapshots_not_per_row(self):
        rates = {'korean': [], 'math': [], 'ssen': []}
        snapshot_deltas = {'korean': [], 'math': [], 'ssen': []}
        subjects = {row.key: row.id for row in LearningSubject.query.all()}
        for key in ('S1', 'S9', 'S12', 'S21'):
            child = self.children[key]
            activity = sorted({row.date for row in DailyPoints.query.filter_by(child_id=child.id).all()})
            for subject_key in STUDY_PACE:
                rows = [
                    row for row in self._progress_rows(key)
                    if row.learning_subject_id == subjects[subject_key]
                    and row.recorded_on >= TERM2_START
                ]
                for earlier, later in zip(rows, rows[1:]):
                    study_days = [on for on in activity if earlier.recorded_on < on <= later.recorded_on]
                    if not study_days:
                        continue
                    delta = later.page - earlier.page
                    snapshot_deltas[subject_key].append(delta)
                    rates[subject_key].append(delta / len(study_days))
        self.assertTrue(any(delta > STUDY_PACE['math'] for delta in snapshot_deltas['math']))
        self.assertTrue(any(delta == 0 for delta in snapshot_deltas['math'] + snapshot_deltas['korean']))
        self.assertAlmostEqual(statistics.median(rates['korean']), 1.0, delta=0.55)
        self.assertAlmostEqual(statistics.median(rates['math']), 2.0, delta=0.7)
        self.assertAlmostEqual(statistics.median(rates['ssen']), 2.0, delta=0.7)

    def test_s5_s6_s17_progress_entry_counts(self):
        for key, previous, current in (('S5', 3, 7), ('S6', 7, 3), ('S17', 3, 7)):
            progress = self._bundle(key)['progress']
            self.assertEqual(progress['previous']['progress_entry_count'], previous, key)
            self.assertEqual(progress['current']['progress_entry_count'], current, key)

    def test_progress_exists_beyond_s5_s6_s17(self):
        other = [
            key for key in SCENARIO_CATALOG
            if key not in ('S5', 'S6', 'S17') and self._progress_rows(key)
        ]
        self.assertGreaterEqual(len(other), 10, other)
        self.assertEqual(len(self._progress_rows('S13')), 0)
        self.assertEqual(len(self._progress_rows('S20')), 0)

    def test_progress_titles_use_real_textbooks(self):
        titles = {row.textbook_title for row in self._progress_rows()}
        self.assertTrue(any(title.startswith('우등생 국어 ') for title in titles))
        self.assertTrue(any(title.startswith('우등생 수학 ') for title in titles))
        self.assertTrue(any(title.startswith('쎈연산 ') for title in titles))
        self.assertFalse(any('시드교재' in title for title in titles))
        self.assertFalse(any('쎈 수학' in title for title in titles))
        self.assertTrue(all(title.endswith('-2') for title in titles))

    def test_term2_progress_starts_in_september(self):
        self.assertEqual(
            LearningProgressEntry.query.filter(LearningProgressEntry.recorded_on < TERM2_START).count(),
            0,
        )
        rows = self._progress_rows()
        self.assertTrue(rows)
        self.assertGreaterEqual(min(row.recorded_on for row in rows), TERM2_START)
        self.assertLessEqual(max(row.recorded_on for row in rows), AS_OF)

    def test_progress_titles_match_child_grade(self):
        for key, child in self.children.items():
            for row in self._progress_rows(key):
                self.assertTrue(
                    row.textbook_title.endswith(f'{child.grade}-2'),
                    f'{key} {row.textbook_title}',
                )

    def test_half_year_daily_points_range(self):
        dates = [row.date for row in DailyPoints.query.all()]
        self.assertTrue(dates)
        self.assertGreaterEqual(min(dates), HALF_YEAR_START)
        self.assertLessEqual(max(dates), AS_OF)

    def test_steady_normal_have_progress_history(self):
        for key in SCENARIO_CATALOG:
            if STUDY_PROFILES[key] in ('STEADY', 'NORMAL', 'FOCUSED'):
                self.assertGreater(len(self._progress_rows(key)), 0, key)

    def test_zero_progress_only_explicit_sparse_new(self):
        zeros = {
            key for key in SCENARIO_CATALOG
            if not self._progress_rows(key)
        }
        self.assertEqual(zeros, set(ZERO_PROGRESS))
        self.assertLessEqual(len(zeros), 2)

    def test_canonical_anchor_windows(self):
        self.assertEqual(AS_OF, CANONICAL_ANCHOR)
        self.assertEqual(self.result['anchor_date'], CANONICAL_ANCHOR)
        self.assertEqual(self.result['current_window']['start'], date(2026, 11, 16))
        self.assertEqual(self.result['current_window']['end'], date(2026, 12, 15))
        self.assertEqual(self.result['previous_window']['start'], date(2026, 10, 17))
        self.assertEqual(self.result['previous_window']['end'], date(2026, 11, 15))

    def test_snapshot_days_are_weekly_not_daily(self):
        for key in ('S1', 'S5', 'S9', 'S12', 'S21'):
            days = sorted({row.recorded_on for row in self._progress_rows(key)})
            self.assertGreaterEqual(len(days), 12, key)
            self.assertLessEqual(len(days), 26, key)
            span_weeks = max(1, (days[-1] - days[0]).days / 7)
            per_week = len(days) / span_weeks
            self.assertGreaterEqual(per_week, 0.7, key)
            self.assertLessEqual(per_week, 2.6, key)

    def _chart_grade_mean(self, grades):
        children = [
            child for child in Child.query.filter_by(include_in_stats=True).all()
            if child.grade in grades
        ]
        ids = [child.id for child in children]
        if not ids:
            return 0.0
        rows = DailyPoints.query.filter(DailyPoints.child_id.in_(ids)).all()
        if not rows:
            return 0.0
        return sum(row.total_points for row in rows) / len(rows)

    def _sentence_count(self, text):
        return len([part for part in (text or '').replace('!', '.').replace('?', '.').split('.') if part.strip()])

    def test_program_share_in_realistic_band(self):
        rows = ChildReading.query.all()
        self.assertGreater(len(rows), 20)
        rec = sum(1 for row in rows if row.program_type == 'recommended')
        challenge = sum(1 for row in rows if row.program_type == 'challenge')
        share = 100.0 * (rec + challenge) / len(rows)
        self.assertGreaterEqual(share, 25.0, share)
        self.assertLessEqual(share, 35.0, share)

    def test_grade56_program_readings_use_exemption_mode(self):
        rows = [
            row for row in ChildReading.query.all()
            if Child.query.get(row.child_id).grade in (5, 6)
            and row.program_type in ('recommended', 'challenge')
        ]
        self.assertTrue(rows)
        self.assertTrue(all(row.reward_mode == REWARD_MODE_EXEMPTION for row in rows))

    def test_exemption_readings_have_no_extra_point_rewards(self):
        rows = [
            row for row in ChildReading.query.all()
            if row.reward_mode == REWARD_MODE_EXEMPTION
        ]
        self.assertTrue(rows)
        ids = [row.id for row in rows]
        self.assertEqual(
            ReadingRewardEvent.query.filter(ReadingRewardEvent.child_reading_id.in_(ids)).count(),
            0,
        )
        for row in rows:
            child = Child.query.get(row.child_id)
            for event_type in (
                EVENT_RECOMMENDED_START, EVENT_RECOMMENDED_COMPLETE,
                EVENT_CHALLENGE_START, EVENT_CHALLENGE_COMPLETE,
            ):
                points = incentive_reward_points(
                    row.program_type, child.grade, event_type, row.reward_mode,
                )
                self.assertIsNone(points, f'{child.name} {row.program_type} {event_type}')

    def test_exemption_ticket_ledger_and_policy(self):
        tickets = ExemptionTicket.query.all()
        self.assertTrue(tickets)
        for ticket in tickets:
            sources = ExemptionTicketSource.query.filter_by(exemption_ticket_id=ticket.id).all()
            self.assertTrue(sources, ticket.id)
            for source in sources:
                reading = ChildReading.query.get(source.child_reading_id)
                self.assertEqual(reading.child_id, ticket.child_id)
                self.assertEqual(reading.reward_mode, REWARD_MODE_EXEMPTION)
            usage = ExemptionUsage.query.filter_by(exemption_ticket_id=ticket.id).first()
            if ticket.status == 'used':
                self.assertIsNotNone(usage)
                self.assertGreaterEqual(usage.used_on, ticket.issued_on)
                self.assertLessEqual(usage.used_on, ticket.expires_on)
            elif ticket.status in ('active', 'expired'):
                self.assertIsNone(usage)
        by_child = defaultdict(list)
        for ticket in tickets:
            by_child[ticket.child_id].append(ticket)
        for child_id, rows in by_child.items():
            active = [row for row in rows if row.status == 'active']
            self.assertLessEqual(len(active), 1, child_id)
            ordered = sorted(rows, key=lambda row: (row.issued_on, row.id))
            for left, right in zip(ordered, ordered[1:]):
                self.assertGreaterEqual(right.issued_on, next_issue_on(left.issued_on))

    def test_exemption_usage_subject_mix(self):
        usages = ExemptionUsage.query.all()
        self.assertTrue(usages)
        math_n = sum(1 for row in usages if row.subject_key == 'math')
        ssen_n = sum(1 for row in usages if row.subject_key == 'ssen')
        self.assertGreaterEqual(ssen_n, 1)
        self.assertEqual(math_n + ssen_n, len(usages))
        self.assertGreater(math_n, ssen_n)
        self.assertGreaterEqual(math_n / len(usages), 0.7)
        self.assertTrue(all(row.subject_key in ('math', 'ssen') for row in usages))

    def test_grade_chart_mean_low_grades_exceed_high_grades(self):
        low = self._chart_grade_mean((1, 2))
        high = self._chart_grade_mean((4, 5, 6))
        grade2 = self._chart_grade_mean((2,))
        grade6 = self._chart_grade_mean((6,))
        self.assertGreater(low, high)
        self.assertGreater(grade2, grade6)

    def test_grade_point_distribution_overlaps(self):
        low = [int(child.cumulative_points or 0) for child in self.children.values() if child.grade in (1, 2, 3)]
        high = [int(child.cumulative_points or 0) for child in self.children.values() if child.grade in (4, 5, 6)]
        self.assertTrue(min(low) < max(high))
        self.assertTrue(max(low) > min(high))

    def test_no_accidental_reread_per_child(self):
        for child in self.children.values():
            book_ids = [
                row.book_id for row in ChildReading.query.filter_by(child_id=child.id).all()
            ]
            self.assertEqual(len(book_ids), len(set(book_ids)), child.name)

    def test_same_band_catalog_has_no_unintended_duplicates(self):
        seen = {}
        for book in Book.query.all():
            key = (book.normalized_key, book.grade_band)
            self.assertNotIn(key, seen, key)
            seen[key] = book.id

    def test_review_voice_and_length_diversity(self):
        habits = [
            review_habit_for_voice(CHILD_PROFILES[key]['voice'])
            for key in SCENARIO_CATALOG
        ]
        self.assertGreaterEqual(habits.count('CAREFUL'), 2)
        self.assertGreaterEqual(habits.count('TERSE'), 6)
        self.assertGreaterEqual(habits.count('NORMAL'), 12)
        lengths = []
        for row in ChildReading.query.filter_by(status='completed').all():
            day = ReadingDay.query.filter_by(
                child_reading_id=row.id, date=row.completed_on,
            ).first()
            if day is None or not (day.review_text or '').strip():
                continue
            lengths.append(self._sentence_count(day.review_text))
        self.assertTrue(any(n <= 2 for n in lengths), lengths)
        self.assertTrue(any(2 <= n <= 3 for n in lengths), lengths)
        self.assertTrue(any(n >= 4 for n in lengths), lengths)

    def test_grade1_has_no_recommended_or_challenge(self):
        for row in ChildReading.query.all():
            child = Child.query.get(row.child_id)
            if child.grade <= 1:
                self.assertEqual(row.program_type, 'general', child.name)

    def test_provenance_totals_match_subjects_and_history(self):
        for child in self.children.values():
            for row in DailyPoints.query.filter_by(child_id=child.id).all():
                subject = (
                    (row.korean_points or 0)
                    + (row.math_points or 0)
                    + (row.ssen_points or 0)
                    + (row.reading_points or 0)
                    + (row.piano_points or 0)
                    + (row.english_points or 0)
                    + (row.advanced_math_points or 0)
                    + (row.writing_points or 0)
                    + (row.manual_points or 0)
                )
                self.assertEqual(row.total_points, subject, child.name)
            ledger = db.session.query(db.func.coalesce(db.func.sum(DailyPoints.total_points), 0)).filter_by(
                child_id=child.id,
            ).scalar()
            self.assertEqual(int(child.cumulative_points or 0), int(ledger or 0), child.name)
            self.assertEqual(
                PointsHistory.query.filter_by(child_id=child.id).count(),
                DailyPoints.query.filter_by(child_id=child.id).count(),
                child.name,
            )


if __name__ == '__main__':
    unittest.main()
