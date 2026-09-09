"""Reading analysis result Alembic migration on temporary SQLite."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext


class ReadingAnalysisMigrationTests(unittest.TestCase):
    def test_upgrade_and_downgrade_on_temp_sqlite(self):
        migration_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/c4d8e29f6b10_create_reading_analysis_result.py'
        )
        spec = importlib.util.spec_from_file_location('reading_ai_migration', migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory(prefix='clc_reading_ai_mig_') as tmp:
            db_path = Path(tmp) / 'fresh.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text('CREATE TABLE user (id INTEGER PRIMARY KEY)'))
                    conn.execute(text('CREATE TABLE child (id INTEGER PRIMARY KEY)'))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    tables = inspect(conn).get_table_names()
                    self.assertIn('reading_analysis_result', tables)
                    columns = {col['name'] for col in inspect(conn).get_columns('reading_analysis_result')}
                    self.assertIn('fingerprint', columns)
                    self.assertIn('parsed_output', columns)
                    self.assertIn('facts_snapshot', columns)
                    self.assertNotIn('review_text', columns)
                    self.assertNotIn('prompt', columns)
                    with Operations.context(context):
                        module.downgrade()
                    tables = inspect(conn).get_table_names()
                    self.assertNotIn('reading_analysis_result', tables)
            finally:
                engine.dispose()
