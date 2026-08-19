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


def configure_test_environment() -> None:
    """app.py import 전에 호출. dotenv가 운영 URL을 덮어쓰지 않도록 빈 값을 먼저 고정한다."""
    os.environ['CLC_TESTING'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # 이미 있는 값도 빈 문자열로 고정 → load_dotenv()가 기존 키를 덮지 않음
    os.environ['DATABASE_URL'] = ''
    os.environ['FIREBASE_CREDENTIALS_JSON'] = ''
    os.environ['SECRET_KEY'] = 'clc-step0-test-secret'


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
        return app, db

    configure_test_environment()

    test_dir = Path(tempfile.mkdtemp(prefix='clc_step0_'))
    _TEST_DB_PATH = test_dir / 'step0.db'
    test_uri = sqlite_uri_for(_TEST_DB_PATH)
    _refuse_remote_database(test_uri)

    db_before = _snapshot_local_db_files()
    threads_before = {t.ident for t in threading.enumerate()}

    from app import app, db  # noqa: WPS433 — env 고정 후에만 import
    import app as app_module  # noqa: WPS433

    db_after = _snapshot_local_db_files()
    threads_after = {t.ident for t in threading.enumerate()}
    new_threads = threads_after - threads_before

    import firebase_admin
    firebase_initialized = bool(firebase_admin._apps)

    configured = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    _refuse_remote_database(configured)

    side_effects = []
    if os.environ.get('DATABASE_URL'):
        side_effects.append(f"DATABASE_URL이 비어 있지 않음: {os.environ.get('DATABASE_URL')!r}")
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

    final_uri = app.config['SQLALCHEMY_DATABASE_URI']
    _refuse_remote_database(final_uri)
    if 'child_center.db' in final_uri:
        raise RuntimeError('테스트가 프로젝트 child_center.db 를 사용하려 합니다. 중단합니다.')
    if Path(final_uri.replace('sqlite:///', '')).resolve() != _TEST_DB_PATH.resolve():
        # sqlite URI 와 실제 파일 경로가 어긋나면 중단
        engine_url = str(db.engine.url)
        _refuse_remote_database(engine_url)
        if 'child_center.db' in engine_url:
            raise RuntimeError(f'엔진이 child_center.db 를 가리킵니다: {engine_url}')

    _BOOTSTRAPPED = True
    return app, db


def import_side_effects():
    return list(_IMPORT_SIDE_EFFECTS or [])
