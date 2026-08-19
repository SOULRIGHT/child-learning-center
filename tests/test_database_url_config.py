"""DATABASE_URL 스킴 판별: SQLite에 Postgres connect_args가 붙지 않는지 확인.

실제 PostgreSQL/Supabase 에는 연결하지 않는다.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

from tests.helpers import PROJECT_ROOT, bootstrap_test_app

bootstrap_test_app()

from app import (  # noqa: E402
    POSTGRESQL_ENGINE_OPTIONS,
    is_postgresql_database_url,
    is_sqlite_database_url,
    sqlalchemy_engine_options_for,
)

EXPECTED_POSTGRES_CONNECT_ARGS = {
    'connect_timeout': 10,
    'keepalives': 1,
    'keepalives_idle': 30,
    'keepalives_interval': 10,
    'keepalives_count': 5,
    'application_name': 'child-learning-center',
}


class DatabaseUrlSchemeTests(unittest.TestCase):
    def test_scheme_helpers(self):
        self.assertTrue(is_postgresql_database_url('postgresql://user:pass@host/db'))
        self.assertTrue(is_postgresql_database_url('postgres://user:pass@host/db'))
        self.assertTrue(is_postgresql_database_url('  POSTGRESQL://user:pass@host/db  '))
        self.assertFalse(is_postgresql_database_url('sqlite:///child_center.db'))
        self.assertFalse(is_postgresql_database_url(''))
        self.assertFalse(is_postgresql_database_url(None))

        self.assertTrue(is_sqlite_database_url('sqlite:///child_center.db'))
        self.assertTrue(is_sqlite_database_url('sqlite:///:memory:'))
        self.assertFalse(is_sqlite_database_url('postgresql://user:pass@host/db'))
        self.assertFalse(is_sqlite_database_url(''))

    def test_explicit_sqlite_url_creates_sqlite_engine(self):
        """sqlite:///child_center.db 옵션으로 sqlite3 엔진 connect가 성공한다."""
        sqlite_url = 'sqlite:///child_center.db'
        self.assertTrue(is_sqlite_database_url(sqlite_url))
        self.assertFalse(is_postgresql_database_url(sqlite_url))

        options = sqlalchemy_engine_options_for(sqlite_url)
        self.assertEqual(options, {})
        self.assertNotIn('keepalives', (options.get('connect_args') or {}))

        tmp = Path(tempfile.mkdtemp(prefix='clc_sqlite_engine_')) / 'child_center.db'
        engine_url = 'sqlite:///' + tmp.resolve().as_posix()
        engine = create_engine(engine_url, **options)
        try:
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text('SELECT 1')).scalar(), 1)
        finally:
            engine.dispose()

    def test_postgresql_engine_options_are_unchanged(self):
        """PostgreSQL URL이면 기존 풀/keepalive 옵션이 그대로 유지된다. 실제 연결은 하지 않는다."""
        pg_url = 'postgresql://user:pass@127.0.0.1:5432/not_connected'
        options = sqlalchemy_engine_options_for(pg_url)
        self.assertIs(options, POSTGRESQL_ENGINE_OPTIONS)
        self.assertEqual(options['pool_size'], 5)
        self.assertEqual(options['max_overflow'], 10)
        self.assertEqual(options['pool_timeout'], 30)
        self.assertEqual(options['pool_recycle'], 300)
        self.assertIs(options['pool_pre_ping'], True)
        self.assertEqual(options['connect_args'], EXPECTED_POSTGRES_CONNECT_ARGS)

        postgres_scheme_url = 'postgres://user:pass@127.0.0.1:5432/not_connected'
        self.assertEqual(
            sqlalchemy_engine_options_for(postgres_scheme_url),
            POSTGRESQL_ENGINE_OPTIONS,
        )

    def test_import_with_explicit_sqlite_database_url(self):
        """별도 프로세스에서 DATABASE_URL=sqlite:///child_center.db 로 import 해도 SQLite 엔진이 뜬다."""
        script = r'''
import os
os.environ["CLC_TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///child_center.db"
os.environ["FIREBASE_CREDENTIALS_JSON"] = ""
os.environ["SECRET_KEY"] = "clc-db-scheme-test"

from sqlalchemy import create_engine, text
from app import IS_POSTGRESQL, app

assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///child_center.db", app.config["SQLALCHEMY_DATABASE_URI"]
assert app.config.get("SESSION_COOKIE_SECURE") is False
assert IS_POSTGRESQL is False
opts = app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {}
assert "keepalives" not in (opts.get("connect_args") or {})
assert "connect_timeout" not in (opts.get("connect_args") or {})

engine = create_engine("sqlite:///:memory:", **opts)
with engine.connect() as conn:
    assert conn.execute(text("SELECT 1")).scalar() == 1
engine.dispose()
print("SQLITE_IMPORT_OK")
'''
        env = os.environ.copy()
        env['CLC_TESTING'] = '1'
        env['DATABASE_URL'] = 'sqlite:///child_center.db'
        env['FIREBASE_CREDENTIALS_JSON'] = ''
        env.pop('SQLALCHEMY_DATABASE_URI', None)

        result = subprocess.run(
            [sys.executable, '-c', script],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f'stdout={result.stdout}\nstderr={result.stderr}',
        )
        self.assertIn('SQLITE_IMPORT_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
