"""Browser QA orchestrator. Does not run the unittest suite.

Usage: python scripts/qa/run.py step3|step4|step5|step6|preview
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.helpers import (  # noqa: E402
    PROJECT_ROOT as HELPERS_ROOT,
    _refuse_remote_database,
    _snapshot_local_db_files,
    sqlite_uri_for,
)

QA_SECRET = 'clc-step0-test-secret'
USAGE = 'Usage: python scripts/qa/run.py step3|step4|step5|step6|preview'


def _pick_port() -> int:
    for _ in range(20):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        port = int(sock.getsockname()[1])
        sock.close()
        if port != 5000:
            return port
    raise RuntimeError('Could not allocate a non-5000 QA port.')


def _wait_http(url: str, timeout_s: float = 45.0) -> None:
    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 500:
                    return
                last_error = f'HTTP {resp.status}'
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.25)
    raise RuntimeError(f'QA server did not become ready at {url}: {last_error}')


def _stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
        return
    except subprocess.TimeoutExpired:
        pass
    proc.kill()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        pass


def _rmtree(path: Path) -> None:
    for _ in range(6):
        try:
            if path.exists():
                shutil.rmtree(path)
            return
        except OSError:
            time.sleep(0.4)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _assert_local_db_unchanged(before: dict, after: dict, when: str) -> None:
    if before != after:
        raise RuntimeError(f'local development DB changed {when}: {before!r} -> {after!r}')


def _print_report(suite: str, results: list[tuple[str, str]], error: str | None, ok: bool) -> int:
    title = {
        'step3': 'STEP 3 BROWSER QA',
        'step4': 'STEP 4 BROWSER QA',
        'step5': 'STEP 5 BROWSER QA',
        'step6': 'STEP 6 BROWSER QA',
    }.get(suite, f'{suite.upper()} BROWSER QA')
    print(title)
    for name, status in results:
        print(f'{name}: {status}')
    passed = sum(1 for _, status in results if status == 'PASS')
    failed = sum(1 for _, status in results if status == 'FAIL')
    print(f'{passed} passed')
    print(f'{failed} failed')
    if error:
        print(error)
    if not ok or failed:
        print('FAIL')
        return 1
    print('PASS')
    return 0


def _playwright_ready() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            'Playwright is not installed.\n'
            'Install (do not run this from qa.ps1 automatically):\n'
            '  python -m pip install -r requirements-dev.txt\n'
            '  python -m playwright install chromium'
        ) from exc
    from pathlib import Path as P

    with sync_playwright() as playwright:
        executable = P(playwright.chromium.executable_path)
        if not executable.exists():
            raise SystemExit(
                'Playwright Chromium is not installed.\n'
                'Install (do not run this from qa.ps1 automatically):\n'
                '  python -m playwright install chromium'
            )


def _run_browser(suite: str, base_url: str, state: dict, artifacts_dir: Path) -> list[tuple[str, str]]:
    from playwright.sync_api import sync_playwright

    qa_dir = Path(__file__).resolve().parent
    if str(qa_dir) not in sys.path:
        sys.path.insert(0, str(qa_dir))
    from smoke_step3 import (  # noqa: WPS433
        StepFailure,
        login_load,
        mint_session_cookie,
    )
    if suite == 'step3':
        from smoke_step3 import run_authenticated_steps  # noqa: WPS433
    elif suite == 'step4':
        from smoke_step4 import run_authenticated_steps  # noqa: WPS433
    elif suite == 'step5':
        from smoke_step5 import run_authenticated_steps  # noqa: WPS433
    elif suite == 'step6':
        from smoke_step6 import run_authenticated_steps  # noqa: WPS433
    else:
        raise RuntimeError(f'Unsupported QA suite: {suite}')

    results: list[tuple[str, str]] = []
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = artifacts_dir / f'{suite}-failed.png'
    trace_path = artifacts_dir / f'{suite}-trace.zip'
    discard = artifacts_dir / f'.{suite}-trace-discard.zip'
    cookie = mint_session_cookie(state['secret_key'], int(state['teacher_id']))
    failed = False
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        context.tracing.start(screenshots=True, snapshots=True)
        page = context.new_page()
        try:
            login_load(page, base_url)
            results.append(('login_load', 'PASS'))
            context.add_cookies([{
                'name': 'session',
                'value': cookie,
                'url': base_url,
                'httpOnly': True,
                'secure': False,
                'sameSite': 'Lax',
            }])
            results.extend(run_authenticated_steps(page, base_url=base_url, state=state))
        except Exception as exc:
            failed = True
            step = getattr(exc, 'step', None) or 'browser'
            message = getattr(exc, 'message', None) or str(exc)
            if not any(name == step for name, _ in results):
                results.append((step, 'FAIL'))
            saved_screenshot = False
            try:
                page.screenshot(path=str(screenshot_path), full_page=True)
                saved_screenshot = screenshot_path.exists()
            except Exception:
                saved_screenshot = False
            extra = [f'failed step: {step}', message]
            if saved_screenshot:
                extra.append(f'screenshot: {screenshot_path}')
            extra.append(f'trace: {trace_path}')
            raise StepFailure(step, '\n'.join(extra), results=results) from exc
        finally:
            try:
                if failed:
                    context.tracing.stop(path=str(trace_path))
                else:
                    context.tracing.stop(path=str(discard))
                    if discard.exists():
                        discard.unlink()
            except Exception:
                pass
            if not failed:
                if screenshot_path.exists():
                    screenshot_path.unlink()
                if trace_path.exists():
                    trace_path.unlink()
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
    return results


def run_suite(suite: str) -> int:
    if suite not in ('step3', 'step4', 'step5', 'step6'):
        print(USAGE)
        return 2
    if HELPERS_ROOT != PROJECT_ROOT:
        raise RuntimeError('tests.helpers PROJECT_ROOT mismatch.')
    _playwright_ready()
    before = _snapshot_local_db_files()
    temp_dir = Path(tempfile.mkdtemp(prefix='clc_qa_'))
    qa_db = temp_dir / 'qa.db'
    test_uri = sqlite_uri_for(qa_db)
    _refuse_remote_database(test_uri)
    port = _pick_port()
    state_path = temp_dir / 'qa_state.json'
    log_path = temp_dir / 'server.log'
    artifacts_dir = PROJECT_ROOT / 'qa-results'
    env = os.environ.copy()
    env['CLC_TESTING'] = '1'
    env['DATABASE_URL'] = test_uri
    env['FIREBASE_CREDENTIALS_JSON'] = ''
    env['SECRET_KEY'] = QA_SECRET
    env['PYTHONIOENCODING'] = 'utf-8'
    env['CLC_QA_PORT'] = str(port)
    env['CLC_QA_STATE_PATH'] = str(state_path)
    env.pop('FLASK_ENV', None)
    env.pop('FLASK_DEBUG', None)
    env.pop('CLC_ALLOW_GROWTH_SEED', None)

    proc = None
    log_handle = None
    exit_code = 1
    results: list[tuple[str, str]] = []
    error_text = None
    try:
        log_handle = open(log_path, 'w', encoding='utf-8')
        creationflags = 0
        if sys.platform == 'win32':
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / 'scripts' / 'qa' / 'server.py')],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        base_url = f'http://127.0.0.1:{port}'
        try:
            _wait_http(f'{base_url}/login')
        except Exception:
            log_tail = log_path.read_text(encoding='utf-8', errors='replace')[-4000:]
            raise RuntimeError(f'QA server failed to start.\n{log_tail}')
        if not state_path.exists():
            raise RuntimeError('QA server started but did not write qa_state.json.')
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if str(state.get('secret_key')) != QA_SECRET:
            raise RuntimeError('QA secret_key mismatch; refusing to mint a session cookie.')
        results = _run_browser(suite, base_url, state, artifacts_dir)
        exit_code = 0
    except Exception as exc:
        error_text = str(exc)
        carried = getattr(exc, 'results', None)
        if carried:
            results = list(carried)
        step = getattr(exc, 'step', None)
        if step and not any(name == step for name, _ in results):
            results.append((step, 'FAIL'))
        exit_code = 1
    finally:
        _stop_process(proc)
        if log_handle is not None:
            log_handle.close()
        _rmtree(temp_dir)
        after = _snapshot_local_db_files()
        try:
            _assert_local_db_unchanged(before, after, 'during QA run')
        except Exception as exc:
            error_text = f'{error_text}\n{exc}' if error_text else str(exc)
            exit_code = 1
        if qa_db.exists():
            extra = f'QA temp DB was not cleaned up: {qa_db}'
            error_text = f'{error_text}\n{extra}' if error_text else extra
            exit_code = 1
    return _print_report(suite, results, error_text, exit_code == 0)


def run_step3() -> int:
    return run_suite('step3')


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ('step3', 'step4', 'step5', 'step6', 'preview'):
        print(USAGE)
        return 2
    if argv[1] == 'preview':
        qa_dir = Path(__file__).resolve().parent
        if str(qa_dir) not in sys.path:
            sys.path.insert(0, str(qa_dir))
        from preview import run_preview  # noqa: WPS433
        return run_preview()
    return run_suite(argv[1])


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
