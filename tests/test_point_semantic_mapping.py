"""Stored semantic mapping v1. LLM/Evidence/UI에 연결하지 않는다."""
from __future__ import annotations

import importlib
import inspect
import unittest
from datetime import date
from pathlib import Path

from features.points.events import (
    CATEGORY_EXTRA_LEARNING,
    CATEGORY_HELP_CONTRIBUTION,
    CATEGORY_PRAISE,
    CATEGORY_STATIONERY,
    CATEGORY_UNCLASSIFIED,
)
from features.points.mapping.current import classify_manual as current_classify
from features.points.project import accounting_parts, project_point_events
from features.points.semantic import (
    SOURCE_SEMANTIC_LLM,
    classification_from_stored,
    get_semantic_mapping,
    unmapped_manual_label_counts,
    upsert_semantic_mapping,
)
from features.points.text import compact_lookup
from feature_models import PointSemanticMapping


AS_OF = date(2026, 8, 22)


def _record(manual_items, *, subjects=None, total=None):
    subjects = dict(subjects or {})
    items = list(manual_items or [])
    subject_sum = sum(int(value or 0) for value in subjects.values())
    manual_sum = sum(int(item.get('points') or 0) for item in items)
    return {
        'date': AS_OF,
        'subjects': subjects,
        'manual_items': items,
        'manual_points': manual_sum,
        'total_points': total if total is not None else subject_sum + manual_sum,
    }


def _runtime_project(record):
    from features.points import project_current_center_events
    return project_current_center_events((record,))


class PointSemanticBoundaryTests(unittest.TestCase):
    def test_compact_lookup_unifies_study_more_labels(self):
        self.assertEqual(compact_lookup('공부 더 함'), compact_lookup('공부더함'))
        self.assertEqual(compact_lookup('공부 더 함'), '공부더함')

    def test_current_mapping_does_not_touch_db(self):
        source = inspect.getsource(importlib.import_module('features.points.mapping.current'))
        self.assertNotIn('feature_models', source)
        self.assertNotIn('semantic', source)
        self.assertNotIn('PointSemanticMapping', source)

    def test_table_has_no_pii_columns(self):
        names = {column.name for column in PointSemanticMapping.__table__.columns}
        self.assertEqual(
            names,
            {
                'id', 'normalized_label', 'category', 'subject_key',
                'item_key', 'source', 'created_at', 'updated_at',
            },
        )
        forbidden = {
            'created_by', 'child_id', 'user_id', 'raw_reason', 'reason',
            'raw_subject', 'child_name', 'email',
        }
        self.assertTrue(names.isdisjoint(forbidden))


class PointSemanticMappingTests(unittest.TestCase):
    def setUp(self):
        from tests.helpers import bootstrap_test_app
        self.app, self.db = bootstrap_test_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.db.session.remove()
        self.db.drop_all()
        self.db.create_all()

    def tearDown(self):
        self.db.session.remove()
        self.ctx.pop()

    def test_deterministic_wins_over_semantic(self):
        upsert_semantic_mapping('칭찬', CATEGORY_STATIONERY, source=SOURCE_SEMANTIC_LLM)
        self.db.session.commit()
        events = _runtime_project(_record([{'subject': '칭찬', 'points': 100}]))
        self.assertEqual(events[0].category, CATEGORY_PRAISE)
        self.assertEqual(events[0].amount, 100)

    def test_semantic_applies_when_deterministic_unclassified(self):
        upsert_semantic_mapping('공부 더 함', CATEGORY_EXTRA_LEARNING)
        self.db.session.commit()
        events = _runtime_project(_record([{'subject': '공부 더 함', 'points': 300}]))
        self.assertEqual(events[0].category, CATEGORY_EXTRA_LEARNING)
        self.assertEqual(events[0].amount, 300)

    def test_missing_semantic_mapping_stays_unclassified(self):
        events = _runtime_project(_record([{'subject': '새로운표현', 'points': 80}]))
        self.assertEqual(events[0].category, CATEGORY_UNCLASSIFIED)
        self.assertEqual(events[0].amount, 80)

    def test_help_mapping_applies(self):
        upsert_semantic_mapping('교실 정리', CATEGORY_HELP_CONTRIBUTION)
        self.db.session.commit()
        events = _runtime_project(_record([{'subject': '교실 정리', 'points': 100}]))
        self.assertEqual(events[0].category, CATEGORY_HELP_CONTRIBUTION)

    def test_subject_key_mapping_applies(self):
        upsert_semantic_mapping(
            '수학 더 풀기',
            CATEGORY_EXTRA_LEARNING,
            subject_key='math',
        )
        self.db.session.commit()
        events = _runtime_project(_record([{'subject': '수학 더 풀기', 'points': 200}]))
        self.assertEqual(events[0].category, CATEGORY_EXTRA_LEARNING)
        self.assertEqual(events[0].subject_key, 'math')

    def test_invalid_stored_category_falls_back(self):
        row = PointSemanticMapping(
            normalized_label=compact_lookup('이상한분류'),
            category='NOT_A_REAL_CATEGORY',
            source=SOURCE_SEMANTIC_LLM,
        )
        self.db.session.add(row)
        self.db.session.commit()
        stored = get_semantic_mapping('이상한분류')
        self.assertEqual(stored.category, 'NOT_A_REAL_CATEGORY')
        classified = classification_from_stored(stored)
        self.assertEqual(classified.category, CATEGORY_UNCLASSIFIED)
        events = _runtime_project(_record([{'subject': '이상한분류', 'points': 50}]))
        self.assertEqual(events[0].category, CATEGORY_UNCLASSIFIED)
        self.assertEqual(events[0].amount, 50)

    def test_upsert_same_normalized_label_does_not_duplicate(self):
        upsert_semantic_mapping('공부 더 함', CATEGORY_UNCLASSIFIED)
        upsert_semantic_mapping('공부더함', CATEGORY_EXTRA_LEARNING, subject_key='math')
        self.db.session.commit()
        self.assertEqual(PointSemanticMapping.query.count(), 1)
        stored = get_semantic_mapping('공부 더 함')
        self.assertEqual(stored.category, CATEGORY_EXTRA_LEARNING)
        self.assertEqual(stored.subject_key, 'math')
        self.assertEqual(stored.normalized_label, '공부더함')

    def test_semantic_does_not_change_amount_or_net(self):
        record = _record(
            [{'subject': '공부 더 함', 'points': 300}],
            subjects={'korean': 200},
        )
        before = project_point_events((record,), classify_manual=current_classify)
        self.assertEqual(before[1].category, CATEGORY_UNCLASSIFIED)
        self.assertEqual(sum(event.amount for event in before), 500)
        self.assertTrue(accounting_parts(record, before)['balanced'])

        upsert_semantic_mapping('공부 더 함', CATEGORY_EXTRA_LEARNING)
        self.db.session.commit()
        after = _runtime_project(record)
        self.assertEqual(after[1].category, CATEGORY_EXTRA_LEARNING)
        self.assertEqual(after[1].amount, before[1].amount)
        self.assertEqual(after[1].activity_date, before[1].activity_date)
        self.assertEqual(after[1].source_kind, before[1].source_kind)
        self.assertEqual(sum(event.amount for event in after), sum(event.amount for event in before))
        self.assertTrue(accounting_parts(record, after)['balanced'])

    def test_unmapped_label_helper_skips_known_and_deterministic(self):
        upsert_semantic_mapping('이미매핑', CATEGORY_HELP_CONTRIBUTION)
        self.db.session.commit()
        records = (
            _record([
                {'subject': '칭찬', 'points': 100},
                {'subject': '이미매핑', 'points': 50},
                {'subject': '공부 더 함', 'points': 300},
                {'subject': '공부더함', 'points': 200},
                {'subject': '새로운표현', 'points': 10},
            ]),
        )
        rows = unmapped_manual_label_counts(records)
        labels = {row['label']: row['count'] for row in rows}
        self.assertNotIn('칭찬', labels)
        self.assertNotIn('이미매핑', labels)
        self.assertEqual(labels['공부더함'], 2)
        self.assertEqual(labels['새로운표현'], 1)

    def test_migration_creates_table_on_fresh_sqlite(self):
        import importlib.util
        import tempfile
        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine, inspect, text

        migration_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/e6b4d19a8c22_create_point_semantic_mapping.py'
        )
        spec = importlib.util.spec_from_file_location('point_semantic_mapping_migration', migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory(prefix='clc_semantic_mig_') as tmp:
            db_path = Path(tmp) / 'fresh.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    tables = inspect(conn).get_table_names()
                    columns = {
                        col['name'] for col in inspect(conn).get_columns('point_semantic_mapping')
                    }
                    conn.execute(text(
                        "INSERT INTO point_semantic_mapping "
                        "(normalized_label, category, source) "
                        "VALUES ('공부더함', 'EXTRA_LEARNING', 'semantic_llm')"
                    ))
            finally:
                engine.dispose()

        self.assertIn('point_semantic_mapping', tables)
        self.assertTrue(
            {
                'id', 'normalized_label', 'category', 'subject_key',
                'item_key', 'source', 'created_at', 'updated_at',
            }.issubset(columns)
        )
        self.assertNotIn('created_by', columns)
        self.assertNotIn('child_id', columns)


if __name__ == '__main__':
    unittest.main()
