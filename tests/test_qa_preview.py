"""Growth vNext UI preview seed. Does not keep a browser open."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from tests.helpers import (
    bootstrap_test_app,
    local_development_sqlite_path,
    resolved_engine_sqlite_path,
    _snapshot_local_db_files,
)

QA_DIR = Path(__file__).resolve().parents[1] / 'scripts' / 'qa'
if str(QA_DIR) not in sys.path:
    sys.path.insert(0, str(QA_DIR))

from preview import SENTINEL_REVIEW, seed_preview  # noqa: E402

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    PROGRAM_TYPE_GENERAL,
    PROGRAM_TYPE_RECOMMENDED,
    STATUS_COMPLETED,
    ChildReading,
    LearningSubject,
)
from features.dates import kst_today  # noqa: E402
from features.growth.metrics import reading_metrics  # noqa: E402
from features.growth.windows import current_window  # noqa: E402
from features.planning.timeline import resolve_canonical_workbook_plan  # noqa: E402
from features.reading.analysis import TIER_MAJOR, build_public_facts, select_text_records  # noqa: E402
from features.study.coverage import completion_forecast  # noqa: E402


class PreviewSeedTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.assertNotEqual(resolved_engine_sqlite_path(db), local_development_sqlite_path())
        self.client = app.test_client()
        self.db_before = _snapshot_local_db_files()
        os.environ['READING_AI_ENABLED'] = ''

    def tearDown(self):
        os.environ.pop('READING_AI_ENABLED', None)
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_preview_seed_renders_growth_numbers_without_raw_review(self):
        as_of = kst_today()
        state = seed_preview(db, as_of)
        self.assertEqual(_snapshot_local_db_files(), self.db_before)
        self.assertNotEqual(resolved_engine_sqlite_path(db), local_development_sqlite_path())

        child_id = int(state['child_id'])
        sparse_id = int(state['sparse_child_id'])
        teacher = User.query.get(int(state['teacher_id']))
        self.assertIsNotNone(teacher)
        self.assertEqual(Child.query.get(child_id).grade, 3)
        self.assertEqual(len(state['peer_ids']), 4)

        selection = select_text_records(child_id, as_of=as_of)
        self.assertEqual(len(selection.recent), 8)
        self.assertEqual(len(selection.previous), 8)
        facts = build_public_facts(child_id, as_of=as_of, selection=selection)
        self.assertEqual(facts['sufficiency'], TIER_MAJOR)
        self.assertEqual(facts['completion_duration_median'], 7.5)
        self.assertNotIn(SENTINEL_REVIEW, str(facts))

        window = current_window(as_of)
        readings = ChildReading.query.filter_by(child_id=child_id, status=STATUS_COMPLETED).all()
        self.assertEqual(len(readings), 2)
        for row in readings:
            self.assertGreaterEqual(row.completed_on, window['start'])
            self.assertLessEqual(row.completed_on, window['end'])
            self.assertLessEqual(row.started_on, row.completed_on)
        metrics = reading_metrics(child_id, as_of=as_of)
        current_reading = metrics['current']
        self.assertGreater(current_reading['reading_days'], 0)
        self.assertEqual(current_reading['completed_count'], 2)
        by_program = current_reading['completed_by_program']
        self.assertEqual(by_program[PROGRAM_TYPE_GENERAL], 1)
        self.assertEqual(by_program[PROGRAM_TYPE_RECOMMENDED], 1)
        self.assertEqual(sum(by_program.values()), 2)

        ssen = LearningSubject.query.filter_by(key='ssen').first()
        if ssen is not None:
            self.assertFalse(ssen.is_active)

        math = LearningSubject.query.filter_by(key=state['subject_key']).first()
        plan = resolve_canonical_workbook_plan(Child.query.get(child_id), math.id, as_of)
        forecast = completion_forecast(child_id, plan, as_of=as_of)
        self.assertTrue(forecast['available'], forecast.get('reason'))
        self.assertIsNotNone(forecast['earliest_date'])
        self.assertIsNotNone(forecast['latest_date'])

        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(teacher.id)
            sess['_fresh'] = True
        response = self.client.get(f'/children/{child_id}/growth')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        math_key = state['subject_key']
        korean_key = state['korean_key']
        self.assertIn(f'data-testid="observed-progress-{math_key}"', html)
        self.assertIn(f'data-testid="observed-progress-{korean_key}"', html)
        self.assertNotIn('data-learning-subject="ssen"', html)
        self.assertIn(f'data-testid="canonical-peer-performance-{math_key}"', html)
        self.assertIn(f'data-display-tier="primary"', html)
        self.assertIn(f'data-testid="canonical-peer-coverage-{math_key}"', html)
        self.assertIn('data-testid="canonical-peer-points"', html)
        self.assertIn('같은 학년 또래 중앙값', html)
        self.assertIn('같은 교재 또래 중앙값', html)
        self.assertIn('비교 4명', html)
        self.assertIn('data-sufficiency="major"', html)
        self.assertIn('최근 8건 · 이전 8건', html)
        self.assertIn('최근 2권', html)
        self.assertNotIn(SENTINEL_REVIEW, html)
        self.assertIn('data-testid="observed-forecast-range"', html)
        self.assertNotIn('data-ai-state="current"', html)
        self.assertIn('role="progressbar"', html)
        self.assertIn('data-testid="growth-summary"', html)
        self.assertIn('id="growth-ai-title"', html)

        sparse = self.client.get(f'/children/{sparse_id}/growth')
        self.assertEqual(sparse.status_code, 200)
        sparse_html = sparse.get_data(as_text=True)
        self.assertIn('교재 계획 없음', sparse_html)
        self.assertIn('data-testid="observed-forecast-unavailable"', sparse_html)
        self.assertNotIn(SENTINEL_REVIEW, sparse_html)
        self.assertEqual(_snapshot_local_db_files(), self.db_before)
