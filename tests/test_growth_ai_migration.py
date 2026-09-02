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

    def test_attempt_table_upgrade_and_downgrade(self):
        root = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
        gen = _load(root / 'b8d2e41f6a90_create_growth_ai_tables.py', 'growth_ai_gen')
        attempt = _load(root / 'c3a8f17b2d01_create_growth_ai_attempt.py', 'growth_ai_attempt')
        with tempfile.TemporaryDirectory(prefix='clc_growth_ai_attempt_mig_') as tmp:
            db_path = Path(tmp) / 'fresh.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text('CREATE TABLE user (id INTEGER PRIMARY KEY)'))
                    conn.execute(text('CREATE TABLE child (id INTEGER PRIMARY KEY)'))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        gen.upgrade()
                        attempt.upgrade()
                    tables = inspect(conn).get_table_names()
                    self.assertIn('growth_ai_attempt', tables)
                    columns = {col['name'] for col in inspect(conn).get_columns('growth_ai_attempt')}
                    self.assertIn('generated_output', columns)
                    self.assertIn('validator_codes', columns)
                    self.assertIn('safety_categories', columns)
                    self.assertIn('total_tokens', columns)
                    with Operations.context(context):
                        attempt.downgrade()
                    self.assertNotIn('growth_ai_attempt', inspect(conn).get_table_names())
            finally:
                engine.dispose()

    def test_safety_categories_added_when_attempt_table_already_exists(self):
        root = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
        patch = _load(
            root / 'd9e1b24c7a03_add_growth_ai_attempt_safety_categories.py',
            'growth_ai_attempt_patch',
        )
        with tempfile.TemporaryDirectory(prefix='clc_growth_ai_attempt_col_') as tmp:
            db_path = Path(tmp) / 'existing.db'
            engine = create_engine('sqlite:///' + db_path.resolve().as_posix())
            try:
                with engine.begin() as conn:
                    conn.execute(text(
                        'CREATE TABLE growth_ai_generation (id INTEGER PRIMARY KEY)'
                    ))
                    conn.execute(text(
                        """
                        CREATE TABLE growth_ai_attempt (
                            id INTEGER PRIMARY KEY,
                            generation_id INTEGER NOT NULL,
                            attempt_number INTEGER NOT NULL,
                            started_at DATETIME NOT NULL,
                            status VARCHAR(32) NOT NULL,
                            failure_code VARCHAR(64)
                        )
                        """
                    ))
                    context = MigrationContext.configure(conn)
                    with Operations.context(context):
                        patch.upgrade()
                    columns = {col['name'] for col in inspect(conn).get_columns('growth_ai_attempt')}
                    self.assertIn('safety_categories', columns)
                    with Operations.context(context):
                        patch.upgrade()
                    columns = {col['name'] for col in inspect(conn).get_columns('growth_ai_attempt')}
                    self.assertIn('safety_categories', columns)
            finally:
                engine.dispose()


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
