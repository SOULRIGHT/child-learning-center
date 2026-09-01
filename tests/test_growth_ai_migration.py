"""Growth AI Alembic migration on temporary SQLite. instance DB 미사용."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext


class GrowthAIMigrationTests(unittest.TestCase):
    def test_upgrade_and_downgrade_on_temp_sqlite(self):
        migration_path = Path(__file__).resolve().parents[1] / (
            'migrations/versions/b8d2e41f6a90_create_growth_ai_tables.py'
        )
        spec = importlib.util.spec_from_file_location('growth_ai_migration', migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory(prefix='clc_growth_ai_mig_') as tmp:
            db_path = Path(tmp) / 'fresh.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text(
                        'CREATE TABLE user (id INTEGER PRIMARY KEY)'
                    ))
                    conn.execute(text(
                        'CREATE TABLE child (id INTEGER PRIMARY KEY)'
                    ))
                    conn.execute(text('INSERT INTO user (id) VALUES (1)'))
                    conn.execute(text('INSERT INTO child (id) VALUES (1)'))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        module.upgrade()
                    tables = inspect(conn).get_table_names()
                    self.assertIn('growth_ai_generation', tables)
                    self.assertIn('growth_ai_feedback', tables)
                    with Operations.context(context):
                        module.downgrade()
                    tables = inspect(conn).get_table_names()
                    self.assertNotIn('growth_ai_generation', tables)
                    self.assertNotIn('growth_ai_feedback', tables)
            finally:
                engine.dispose()
