"""Step 0 테스트 부트스트랩.

app.py 를 import 하기 전에 반드시 호출한다.
운영 DATABASE_URL / Supabase / 테스트 Render PG 에 연결하지 않는다.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass

_BOOTSTRAPPED = False
_TEST_DB_PATH = None
_IMPORT_SIDE_EFFECTS = None


def local_development_sqlite_path() -> Path:
    return (PROJECT_ROOT / 'instance' / 'child_center.db').resolve()


def test_sqlite_path():
    return None if _TEST_DB_PATH is None else _TEST_DB_PATH.resolve()


def resolved_engine_sqlite_path(db) -> Path | None:
    raw = getattr(getattr(db, 'engine', None), 'url', None)
    database = getattr(raw, 'database', None) if raw is not None else None
    if not database:
        return None
    return Path(database).resolve()


def assert_test_engine_isolated(db) -> Path:
    """테스트 엔진이 instance/child_center.db 가 아닌지 강제한다."""
    path = resolved_engine_sqlite_path(db)
    local = local_development_sqlite_path()
    if path is None:
        raise RuntimeError('테스트 엔진 SQLite path를 확인할 수 없습니다.')
    if path == local:
        raise RuntimeError(f'테스트 엔진이 local development DB를 가리킵니다: {path}')
    if 'instance' in path.parts and path.name == 'child_center.db' and path.parent.name == 'instance':
        raise RuntimeError(f'테스트 엔진이 instance/child_center.db 계열입니다: {path}')
    intended = test_sqlite_path()
    if intended is not None and path != intended:
        raise RuntimeError(f'테스트 엔진이 의도한 temp DB가 아닙니다: {path} vs {intended}')
    return path


def _refuse_remote_database(url: str) -> None:
    lowered = (url or '').lower()
    if 'postgres' in lowered or 'supabase' in lowered or 'render.com' in lowered:
        raise RuntimeError(
            f'Step 0 테스트가 원격 DB URL을 사용하려 합니다. 중단합니다: {url!r}'
        )


def _local_db_candidates():
    return [
        PROJECT_ROOT / 'child_center.db',
        PROJECT_ROOT / 'instance' / 'child_center.db',
    ]


def _snapshot_local_db_files():
    snapshot = {}
    for path in _local_db_candidates():
        if path.exists():
            stat = path.stat()
            snapshot[str(path)] = (stat.st_mtime_ns, stat.st_size)
        else:
            snapshot[str(path)] = None
    return snapshot


def configure_test_environment(database_url: str) -> None:
    """app.py import 전에 호출. DATABASE_URL을 temp SQLite로 먼저 고정한다.

    빈 문자열로 두면 app.py 가 sqlite:///child_center.db 로 fallback 하고
    Flask-SQLAlchemy 가 instance/child_center.db 에 엔진을 붙일 수 있다.
    CLC_TESTING=1 은 import side-effect 방지일 뿐 DB path isolation 이 아니다.
    """
    os.environ['CLC_TESTING'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['DATABASE_URL'] = database_url
    os.environ['FIREBASE_CREDENTIALS_JSON'] = ''
    os.environ['SECRET_KEY'] = 'clc-step0-test-secret'
    os.environ['GENERAL_READING_V2_START_DATE'] = '2026-08-01'
    os.environ['VIEWER_CHILD_WRITE_TTL_MINUTES'] = '15'
    os.environ.pop('CLC_ALLOW_GROWTH_SEED', None)


def sqlite_uri_for(path: Path) -> str:
    return 'sqlite:///' + path.resolve().as_posix()


def _noop_realtime_backup(*args, **kwargs):
    """테스트가 워크스페이스 backups/ 에 파일을 쓰지 않도록 한다. 프로덕션 코드는 변경하지 않는다."""
    return True


def bootstrap_test_app():
    """테스트용 SQLite로 Flask app/db를 준비한다. 여러 번 호출해도 한 번만 import 한다."""
    global _BOOTSTRAPPED, _TEST_DB_PATH, _IMPORT_SIDE_EFFECTS
    if _BOOTSTRAPPED:
        from app import app, db
        with app.app_context():
            assert_test_engine_isolated(db)
        return app, db

    test_dir = Path(tempfile.mkdtemp(prefix='clc_step0_'))
    _TEST_DB_PATH = test_dir / 'step0.db'
    test_uri = sqlite_uri_for(_TEST_DB_PATH)
    _refuse_remote_database(test_uri)
    if local_development_sqlite_path().as_posix() in test_uri.replace('\\', '/'):
        raise RuntimeError('테스트 URI가 local development DB와 겹칩니다.')

    configure_test_environment(test_uri)

    db_before = _snapshot_local_db_files()
    threads_before = {t.ident for t in threading.enumerate()}

    from app import app, db  # noqa: WPS433 — temp DATABASE_URL 고정 후에만 import
    import app as app_module  # noqa: WPS433

    db_after = _snapshot_local_db_files()
    threads_after = {t.ident for t in threading.enumerate()}
    new_threads = threads_after - threads_before

    import firebase_admin
    firebase_initialized = bool(firebase_admin._apps)

    configured = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    _refuse_remote_database(configured)

    side_effects = []
    env_url = os.environ.get('DATABASE_URL') or ''
    if env_url != test_uri:
        side_effects.append(f'DATABASE_URL이 test URI가 아님: {env_url!r}')
    if firebase_initialized:
        side_effects.append('Firebase Admin SDK가 import 중 초기화됨')
    if new_threads:
        side_effects.append(f'import 중 새 스레드가 생성됨: {len(new_threads)}개')
    for path, before in db_before.items():
        after = db_after.get(path)
        if before is None and after is not None:
            side_effects.append(f'로컬 DB 파일이 import 중 생성됨: {path}')
        elif before is not None and after is not None and before != after:
            side_effects.append(f'로컬 DB 파일이 import 중 변경됨: {path}')

    _IMPORT_SIDE_EFFECTS = side_effects
    if side_effects:
        raise RuntimeError(
            'app.py import 중 외부 부작용이 감지되어 Step 0 테스트를 중단합니다. '
            + ' / '.join(side_effects)
        )

    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = test_uri
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
    app_module.realtime_backup = _noop_realtime_backup

    with app.app_context():
        db.session.remove()
        db.engine.dispose()
        db.create_all()
        assert_test_engine_isolated(db)

    final_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    _refuse_remote_database(final_uri)
    if Path(final_uri.replace('sqlite:///', '')).resolve() != _TEST_DB_PATH.resolve():
        raise RuntimeError(f'테스트 config URI가 temp DB가 아닙니다: {final_uri}')

    _BOOTSTRAPPED = True
    return app, db


def import_side_effects():
    return list(_IMPORT_SIDE_EFFECTS or [])
