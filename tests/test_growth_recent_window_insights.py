"""Recent-window insight significance gates. metric 계산은 바꾸지 않는다."""
from __future__ import annotations

import unittest
from datetime import date

from features.growth.copy import (
    FORBIDDEN_COPY_PHRASES,
    LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST,
    POINTS_PERIOD_INCREASE,
    POINTS_PERIOD_RECENT_WINDOW_BEST,
    PROGRESS_ENTRIES_INCREASE,
    READING_ACTIVITY_INCREASE,
    READING_COMPLETIONS_INCREASE,
    READING_COMPLETIONS_RECENT_WINDOW_BEST,
    READING_DAYS_RECENT_WINDOW_BEST,
    RECENT_WINDOW_SCOPE,
    all_copy_texts,
    fallback_copy,
    headline_for,
    join_subject_labels,
    learning_recent_window_headline,
)
from features.growth.insights import (
    COMPLETION_DELTA_MIN,
    POINTS_PERIOD_DELTA_MIN,
    PROGRESS_ENTRY_DELTA_MIN,
    READING_DAYS_DELTA_MIN,
    RECENT_BEST_COMPLETIONS_MIN_MARGIN,
    RECENT_BEST_LEARNING_PAGES_MIN_MARGIN,
    RECENT_BEST_POINTS_MIN_MARGIN,
    RECENT_BEST_READING_DAYS_MIN_MARGIN,
    generate_insight_candidates,
    top_candidates,
)
from features.growth.service import _insight_payload
from features.growth.windows import current_window, previous_window


AS_OF = date(2026, 12, 15)
CURRENT = {'start': date(2026, 11, 16), 'end': date(2026, 12, 15)}
PREV1 = {'start': date(2026, 10, 17), 'end': date(2026, 11, 15)}
PREV2 = {'start': date(2026, 9, 17), 'end': date(2026, 10, 16)}

BANNED_RECENT_WINDOW = (
    '역대',
    '개인 최고',
    '놀라운',
    '우수',
    '부진',
    '의욕',
    '집중력',
    '최고 기록',
    '습관이 좋아',
    '의지가',
)


def _windows():
    return current_window(AS_OF, 30), previous_window(AS_OF, 30)


def _reading_payload(reading_days=(0, 0), completed=(0, 0)):
    current_window_, previous_window_ = _windows()
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current_window_,
        'previous_window': previous_window_,
        'available_from': {'reading_days': PREV1['start'], 'completed': PREV1['start']},
        'comparable': {
            'reading_days': True,
            'started': True,
            'completed': True,
            'abandoned': False,
            'difficulty_rating': False,
            'fun_rating': False,
            'experience_rating_pair': False,
        },
        'current': {
            'reading_days': reading_days[0],
            'started_count': 0,
            'completed_count': completed[0],
            'abandoned_count': 0,
            'difficulty_rating': {'average': None, 'sample_count': 0},
            'fun_rating': {'average': None, 'sample_count': 0},
            'paired_experience_rating': {
                'sample_count': 0, 'difficulty_average': None, 'fun_average': None,
            },
        },
        'previous': {
            'reading_days': reading_days[1],
            'started_count': 0,
            'completed_count': completed[1],
            'abandoned_count': 0,
            'difficulty_rating': {'average': None, 'sample_count': 0},
            'fun_rating': {'average': None, 'sample_count': 0},
            'paired_experience_rating': {
                'sample_count': 0, 'difficulty_average': None, 'fun_average': None,
            },
        },
    }


def _progress_payload(current_count, previous_count):
    current_window_, previous_window_ = _windows()
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current_window_,
        'previous_window': previous_window_,
        'available_from': {'progress': PREV1['start']},
        'comparable': {'progress': True},
        'current': {'progress_entry_count': current_count, 'progress_entry_count_by_subject': {}},
        'previous': {'progress_entry_count': previous_count, 'progress_entry_count_by_subject': {}},
        'latest_snapshot_by_subject': {},
    }


def _points_payload(current_points, previous_points, *, previous_days=2):
    current_window_, previous_window_ = _windows()
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current_window_,
        'previous_window': previous_window_,
        'available_from': {'points': PREV1['start']},
        'comparable': {'points': True},
        'current': {
            'period_points': current_points,
            'point_activity_days': 2,
            'subject_active_days': {},
            'manual_points_sum': 0,
        },
        'previous': {
            'period_points': previous_points,
            'point_activity_days': previous_days,
            'subject_active_days': {},
            'manual_points_sum': 0,
        },
        'cumulative_as_of': None,
        'current_cumulative': None,
        'child_cumulative_points': 9999,
    }


def _empty_reading():
    return _reading_payload()


def _empty_progress():
    payload = _progress_payload(0, 0)
    payload['comparable'] = {'progress': False}
    return payload


def _empty_points():
    payload = _points_payload(0, 0, previous_days=0)
    payload['comparable'] = {'points': False}
    return payload


def _window_fact(start, end, value, *, title=None):
    return {
        'start': start,
        'end': end,
        'value': value,
        'available': True,
        'comparable': True,
        'textbook_title': title,
    }


def _fact(current, prev1, prev2, *, status='ok', is_best=None, title=None):
    historical = max(prev1, prev2)
    best_window = dict(PREV1) if prev1 >= prev2 else dict(PREV2)
    if status != 'ok':
        return {
            'current': _window_fact(CURRENT['start'], CURRENT['end'], None, title=title),
            'previous_1': _window_fact(PREV1['start'], PREV1['end'], None),
            'previous_2': _window_fact(PREV2['start'], PREV2['end'], None),
            'historical_best': None,
            'historical_best_window': None,
            'margin': None,
            'is_recent_window_best': None,
            'status': status,
        }
    if is_best is None:
        is_best = current > historical
    return {
        'current': _window_fact(CURRENT['start'], CURRENT['end'], current, title=title),
        'previous_1': _window_fact(PREV1['start'], PREV1['end'], prev1, title=title),
        'previous_2': _window_fact(PREV2['start'], PREV2['end'], prev2, title=title),
        'historical_best': historical,
        'historical_best_window': best_window,
        'margin': current - historical,
        'is_recent_window_best': is_best,
        'status': status,
        'source': 'test',
    }


def _bests(*, reading_days=None, completions=None, points=None, learning=None):
    missing = _fact(0, 0, 0, status='insufficient_history')
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'window_count': 3,
        'lookback_days': 90,
        'current_window': dict(CURRENT),
        'previous_1_window': dict(PREV1),
        'previous_2_window': dict(PREV2),
        'reading_days': reading_days if reading_days is not None else missing,
        'reading_completions': completions if completions is not None else missing,
        'points': points if points is not None else missing,
        'learning': learning or {},
    }


def _bundle(*, reading=None, progress=None, points=None, recent=None):
    return {
        'reading': reading if reading is not None else _empty_reading(),
        'progress': progress if progress is not None else _empty_progress(),
        'points': points if points is not None else _empty_points(),
        'recent_window_bests': recent if recent is not None else _bests(),
    }


def _ids(candidates):
    return [item.id for item in candidates]


class RecentWindowThresholdConstantsTests(unittest.TestCase):
    def test_short_term_thresholds_unchanged(self):
        self.assertEqual(READING_DAYS_DELTA_MIN, 2)
        self.assertEqual(COMPLETION_DELTA_MIN, 1)
        self.assertEqual(PROGRESS_ENTRY_DELTA_MIN, 2)
        self.assertEqual(POINTS_PERIOD_DELTA_MIN, 100)

    def test_recent_window_thresholds(self):
        self.assertEqual(RECENT_BEST_READING_DAYS_MIN_MARGIN, 2)
        self.assertEqual(RECENT_BEST_COMPLETIONS_MIN_MARGIN, 2)
        self.assertEqual(RECENT_BEST_POINTS_MIN_MARGIN, 300)
        self.assertEqual(RECENT_BEST_LEARNING_PAGES_MIN_MARGIN, 5)


class RecentWindowSignificanceGateTests(unittest.TestCase):
    def test_reading_margin_boundary(self):
        below = generate_insight_candidates(_bundle(recent=_bests(reading_days=_fact(14, 13, 10))))
        self.assertNotIn(READING_DAYS_RECENT_WINDOW_BEST, _ids(below))
        at = generate_insight_candidates(_bundle(recent=_bests(reading_days=_fact(15, 13, 10))))
        self.assertIn(READING_DAYS_RECENT_WINDOW_BEST, _ids(at))

    def test_completion_margin_boundary(self):
        below = generate_insight_candidates(_bundle(recent=_bests(completions=_fact(4, 3, 2))))
        self.assertNotIn(READING_COMPLETIONS_RECENT_WINDOW_BEST, _ids(below))
        at = generate_insight_candidates(_bundle(recent=_bests(completions=_fact(5, 3, 2))))
        self.assertIn(READING_COMPLETIONS_RECENT_WINDOW_BEST, _ids(at))

    def test_points_margin_boundary(self):
        below = generate_insight_candidates(_bundle(recent=_bests(points=_fact(1800, 1501, 1400))))
        self.assertNotIn(POINTS_PERIOD_RECENT_WINDOW_BEST, _ids(below))
        at = generate_insight_candidates(_bundle(recent=_bests(points=_fact(1800, 1500, 1400))))
        self.assertIn(POINTS_PERIOD_RECENT_WINDOW_BEST, _ids(at))

    def test_learning_margin_and_positive_current(self):
        four = generate_insight_candidates(_bundle(recent=_bests(learning={
            'math': _fact(20, 16, 10, title='수학 3-2'),
        })))
        self.assertNotIn(LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST, _ids(four))
        five = generate_insight_candidates(_bundle(recent=_bests(learning={
            'math': _fact(21, 16, 10, title='수학 3-2'),
        })))
        self.assertIn(LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST, _ids(five))
        nonpositive = generate_insight_candidates(_bundle(recent=_bests(learning={
            'math': _fact(0, -6, -5, title='수학 3-2'),
        })))
        self.assertNotIn(LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST, _ids(nonpositive))
        negative = generate_insight_candidates(_bundle(recent=_bests(learning={
            'math': _fact(-1, -8, -6, title='수학 3-2'),
        })))
        self.assertNotIn(LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST, _ids(negative))

    def test_false_best_insufficient_tie_and_missing_do_not_create(self):
        cases = [
            _fact(10, 12, 8, is_best=False),
            _fact(10, 10, 8, is_best=False),
            _fact(0, 0, 0, status='insufficient_history'),
        ]
        for fact in cases:
            ids = _ids(generate_insight_candidates(_bundle(recent=_bests(reading_days=fact))))
            self.assertNotIn(READING_DAYS_RECENT_WINDOW_BEST, ids)
        book_changed = _fact(20, 10, 8, title='수학 3-2')
        book_changed['status'] = 'book_changed'
        book_changed['is_recent_window_best'] = None
        ids = _ids(generate_insight_candidates(_bundle(recent=_bests(learning={'math': book_changed}))))
        self.assertNotIn(LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST, ids)
        self.assertEqual(_ids(generate_insight_candidates({})), [])
        self.assertEqual(_ids(generate_insight_candidates(_bundle(recent={}))), [])


class RecentWindowLearningAggregateTests(unittest.TestCase):
    def test_one_two_three_subjects_are_single_candidate(self):
        one = generate_insight_candidates(_bundle(recent=_bests(learning={
            'math': _fact(44, 32, 20, title='수학 3-2'),
        })))
        self.assertEqual(_ids(one).count(LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST), 1)
        self.assertEqual(len(one[0].evidence['subjects']), 1)

        two = generate_insight_candidates(_bundle(recent=_bests(learning={
            'math': _fact(44, 32, 20, title='수학 3-2'),
            'korean': _fact(28, 21, 10, title='국어 3-2'),
        })))
        self.assertEqual(_ids(two).count(LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST), 1)
        labels = [row['subject_label'] for row in two[0].evidence['subjects']]
        self.assertEqual(labels, ['국어', '수학'])
        self.assertEqual(two[0].evidence['subjects'][0]['margin'], 7)
        self.assertEqual(two[0].evidence['subjects'][1]['margin'], 12)

        three = generate_insight_candidates(_bundle(recent=_bests(learning={
            'ssen': _fact(39, 31, 20, title='쎈 3-2'),
            'math': _fact(44, 32, 20, title='수학 3-2'),
            'korean': _fact(28, 21, 10, title='국어 3-2'),
        })))
        self.assertEqual(_ids(three).count(LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST), 1)
        self.assertEqual(
            [row['subject_key'] for row in three[0].evidence['subjects']],
            ['korean', 'math', 'ssen'],
        )
        self.assertIn(RECENT_WINDOW_SCOPE, headline_for(three[0]))
        self.assertIn('국어·수학·쎈', headline_for(three[0]))

    def test_only_qualifying_subjects_are_kept(self):
        candidates = generate_insight_candidates(_bundle(recent=_bests(learning={
            'korean': _fact(28, 21, 10, title='국어 3-2'),
            'math': _fact(20, 18, 16, title='수학 3-2'),
            'ssen': _fact(10, 10, 9, title='쎈 3-2'),
        })))
        item = next(row for row in candidates if row.id == LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST)
        self.assertEqual([row['subject_key'] for row in item.evidence['subjects']], ['korean'])
        self.assertEqual(item.evidence['subjects'][0]['current_advance'], 28)
        self.assertEqual(item.evidence['subjects'][0]['historical_best'], 21)
        self.assertEqual(item.evidence['window_count'], 3)


class RecentWindowDedupeTests(unittest.TestCase):
    def test_reading_recent_window_replaces_short_term_increase(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(reading_days=(15, 10)),
            recent=_bests(reading_days=_fact(15, 12, 8)),
        ))
        ids = _ids(candidates)
        self.assertIn(READING_DAYS_RECENT_WINDOW_BEST, ids)
        self.assertNotIn(READING_ACTIVITY_INCREASE, ids)
        picked = top_candidates(candidates, limit=3)
        self.assertEqual([item.id for item in picked].count(READING_DAYS_RECENT_WINDOW_BEST), 1)
        self.assertNotIn(READING_ACTIVITY_INCREASE, _ids(picked))

    def test_reading_short_term_kept_when_recent_window_fails_threshold(self):
        candidates = generate_insight_candidates(_bundle(
            reading=_reading_payload(reading_days=(14, 10)),
            recent=_bests(reading_days=_fact(14, 13, 8)),
        ))
        ids = _ids(candidates)
        self.assertNotIn(READING_DAYS_RECENT_WINDOW_BEST, ids)
        self.assertIn(READING_ACTIVITY_INCREASE, ids)

    def test_completion_and_points_supersession(self):
        passed = generate_insight_candidates(_bundle(
            reading=_reading_payload(completed=(5, 3)),
            points=_points_payload(2100, 1700),
            recent=_bests(completions=_fact(5, 3, 1), points=_fact(2100, 1700, 1600)),
        ))
        ids = _ids(passed)
        self.assertIn(READING_COMPLETIONS_RECENT_WINDOW_BEST, ids)
        self.assertNotIn(READING_COMPLETIONS_INCREASE, ids)
        self.assertIn(POINTS_PERIOD_RECENT_WINDOW_BEST, ids)
        self.assertNotIn(POINTS_PERIOD_INCREASE, ids)

        failed = generate_insight_candidates(_bundle(
            reading=_reading_payload(completed=(4, 3)),
            points=_points_payload(1800, 1650),
            recent=_bests(completions=_fact(4, 3, 1), points=_fact(1800, 1650, 1600)),
        ))
        ids = _ids(failed)
        self.assertNotIn(READING_COMPLETIONS_RECENT_WINDOW_BEST, ids)
        self.assertIn(READING_COMPLETIONS_INCREASE, ids)
        self.assertNotIn(POINTS_PERIOD_RECENT_WINDOW_BEST, ids)
        self.assertIn(POINTS_PERIOD_INCREASE, ids)

    def test_learning_does_not_drop_progress_entry_insight(self):
        candidates = generate_insight_candidates(_bundle(
            progress=_progress_payload(7, 3),
            recent=_bests(learning={'math': _fact(21, 16, 10, title='수학 3-2')}),
        ))
        ids = _ids(candidates)
        self.assertIn(PROGRESS_ENTRIES_INCREASE, ids)
        self.assertIn(LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST, ids)
        picked = top_candidates(candidates, limit=3)
        picked_ids = _ids(picked)
        self.assertIn(PROGRESS_ENTRIES_INCREASE, picked_ids)
        self.assertIn(LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST, picked_ids)

    def test_no_recent_window_leaves_existing_bundle_unchanged(self):
        short = _bundle(
            reading=_reading_payload(reading_days=(8, 5)),
            recent=None,
        )
        short.pop('recent_window_bests')
        with_empty = dict(short)
        with_empty['recent_window_bests'] = _bests()
        self.assertEqual(
            _ids(generate_insight_candidates(short)),
            _ids(generate_insight_candidates(with_empty)),
        )
        self.assertEqual(_ids(generate_insight_candidates(short)), [READING_ACTIVITY_INCREASE])


class RecentWindowCopyAndEvidenceTests(unittest.TestCase):
    def test_copy_has_scope_and_no_banned_phrases(self):
        texts = all_copy_texts()
        joined = '\n'.join(texts)
        for phrase in FORBIDDEN_COPY_PHRASES:
            self.assertNotIn(phrase, joined)
        for phrase in BANNED_RECENT_WINDOW:
            self.assertNotIn(phrase, joined)
        for candidate_id in (
            READING_DAYS_RECENT_WINDOW_BEST,
            READING_COMPLETIONS_RECENT_WINDOW_BEST,
            POINTS_PERIOD_RECENT_WINDOW_BEST,
            LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST,
        ):
            headline = fallback_copy(candidate_id)['headline']
            self.assertIn(RECENT_WINDOW_SCOPE, headline)
        self.assertEqual(join_subject_labels(['국어', '수학']), '국어와 수학')
        self.assertIn('수학 진도가', learning_recent_window_headline(['수학']))
        self.assertIn('국어와 수학', learning_recent_window_headline(['국어', '수학']))

    def test_evidence_shape_and_view_rows(self):
        candidates = generate_insight_candidates(_bundle(recent=_bests(
            reading_days=_fact(15, 12, 8),
            learning={
                'korean': _fact(28, 21, 10, title='국어 3-2'),
                'math': _fact(44, 32, 20, title='수학 3-2'),
            },
        )))
        reading = next(item for item in candidates if item.id == READING_DAYS_RECENT_WINDOW_BEST)
        self.assertEqual(reading.evidence['kind'], 'recent_window_best')
        self.assertEqual(reading.evidence['current'], 15)
        self.assertEqual(reading.evidence['historical_best'], 12)
        self.assertEqual(reading.evidence['margin'], 3)
        self.assertEqual(reading.evidence['window_days'], 30)
        self.assertEqual(reading.evidence['comparison_window_count'], 3)
        self.assertEqual(reading.evidence['current_window']['start'], CURRENT['start'])
        self.assertEqual(reading.evidence['historical_best_window']['start'], PREV1['start'])
        view = _insight_payload(reading)
        self.assertIn('최근 3개 30일', view['headline'])
        self.assertEqual(view['evidence']['kind'], 'recent_window_best')
        self.assertTrue(any(label == '비교 범위' for label, _ in view['evidence_rows']))
        self.assertTrue(any('과거 최고' in label for label, _ in view['evidence_rows']))
        self.assertNotIn('child_id', reading.evidence)

        learning = next(item for item in candidates if item.id == LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST)
        learning_view = _insight_payload(learning)
        self.assertIn('국어와 수학', learning_view['headline'])
        labels = [label for label, _ in learning_view['evidence_rows']]
        self.assertIn('국어', labels)
        self.assertIn('수학', labels)
        self.assertTrue(any('+44쪽' in value for _, value in learning_view['evidence_rows']))
