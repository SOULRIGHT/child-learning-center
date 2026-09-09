"""Isolated Growth vNext UI preview. Does not touch production/local child_center.db.

Usage: python scripts/qa/run.py preview
Keep-open browser is separate from seed validation tests.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SENTINEL_REVIEW = 'PREVIEW-STEP6-REVIEW-UNIQUE-PHRASE'
PREVIEW_GRADE = 3


def seed_preview(db, as_of: date) -> dict:
    """Step 3~6 판단용 primary + sparse fixture. smoke _seed()와 분리."""
    from app import Child, User
    from feature_models import (
        ACTOR_TEACHER,
        POLICY_VERSION_GENERAL_V2,
        STATUS_COMPLETED,
        STATUS_IN_PROGRESS,
        Book,
        CenterSystemHolidaySeed,
        ChildReading,
        LearningSubject,
        ReadingDay,
        STUDY_STATUS_EXPLICIT_NOT_STUDIED,
        STUDY_STATUS_STUDIED,
    )
    from features.planning.service import (
        create_workbook_plan,
        set_child_weekdays_override,
        update_center_weekdays,
    )
    from features.progress.service import ensure_default_subjects, set_subject_active
    from features.study.calendar import save_subject_study_weekdays
    from features.study.constants import INPUT_CHANNEL_TEACHER, RECORD_VERIFICATION_OBSERVED
    from features.study.records import create_study_session
    from viewer_slug_utils import generate_viewer_slug

    teacher = User(
        username='preview_teacher',
        name='미리보기교사',
        role='돌봄선생님',
        email='preview-teacher@example.test',
        password_hash='',
    )
    primary = Child(
        name='미리보기아동',
        grade=PREVIEW_GRADE,
        include_in_stats=True,
        viewer_slug=generate_viewer_slug(),
        created_at=datetime(2020, 1, 1),
    )
    db.session.add_all([teacher, primary])
    db.session.commit()

    ensure_default_subjects()
    preview_keys = {'korean', 'math'}
    for row in LearningSubject.query.all():
        if row.key not in preview_keys:
            set_subject_active(row, False)
    update_center_weekdays([0, 1, 2, 3, 4])
    subjects = list(LearningSubject.query.filter_by(is_active=True).order_by(LearningSubject.id.asc()).all())
    if not subjects:
        raise RuntimeError('preview seed has no active LearningSubject.')
    korean = next((row for row in subjects if row.key == 'korean'), None)
    math = next((row for row in subjects if row.key == 'math'), None)
    if korean is None or math is None:
        raise RuntimeError('preview seed needs korean and math subjects.')
    extra_active = [row.key for row in subjects if row.key not in preview_keys]
    if extra_active:
        raise RuntimeError(f'preview seed expected only korean/math active, got {extra_active}')

    for subject in subjects:
        save_subject_study_weekdays(subject.id, [0, 1, 2, 3, 4])
        plan = create_workbook_plan(
            grade=PREVIEW_GRADE,
            learning_subject_id=subject.id,
            textbook_title=f'미리보기 {subject.name} 3-2',
            start_page=1,
            end_page=200,
            start_date=as_of - timedelta(days=90),
            target_completion_date=as_of + timedelta(days=120),
        )
        plan.exclusion_ranges_json = []
        plan.exclusion_ranges_text = ''
    db.session.commit()

    set_child_weekdays_override(primary.id, [0, 1, 2, 3, 4])

    if CenterSystemHolidaySeed.query.filter_by(year=as_of.year).first() is None:
        db.session.add(CenterSystemHolidaySeed(year=as_of.year, seeded_at=datetime.utcnow()))
        db.session.commit()

    peers = []
    for index in range(1, 5):
        peer = Child(
            name=f'미리보기또래{index}',
            grade=PREVIEW_GRADE,
            include_in_stats=True,
            viewer_slug=generate_viewer_slug(),
            created_at=datetime(2020, 1, 1),
        )
        db.session.add(peer)
        peers.append(peer)
        db.session.flush()
        set_child_weekdays_override(peer.id, [0, 1, 2, 3, 4])
    sparse = Child(
        name='미리보기데이터부족',
        grade=6,
        include_in_stats=True,
        viewer_slug=generate_viewer_slug(),
        created_at=datetime(2020, 1, 1),
    )
    db.session.add(sparse)
    db.session.commit()

    _fill_learning(
        db,
        child=primary,
        subjects=subjects,
        focus=(korean, math),
        as_of=as_of,
        teacher_id=teacher.id,
        page_shift=0,
        overlap=True,
    )
    for index, peer in enumerate(peers, start=1):
        _fill_learning(
            db,
            child=peer,
            subjects=subjects,
            focus=(korean, math),
            as_of=as_of,
            teacher_id=teacher.id,
            page_shift=index * 4,
            overlap=False,
        )

    _seed_points(db, primary, teacher.id, as_of, totals=(90, 100, 80))
    peer_totals = ((70, 75, 80), (85, 90, 95), (100, 105, 110), (120, 125, 130))
    for peer, totals in zip(peers, peer_totals):
        _seed_points(db, peer, teacher.id, as_of, totals=totals)

    _seed_reading(db, primary, teacher.id, as_of)
    db.session.commit()

    return {
        'teacher_id': teacher.id,
        'child_id': primary.id,
        'sparse_child_id': sparse.id,
        'peer_ids': [peer.id for peer in peers],
        'subject_id': math.id,
        'subject_key': math.key,
        'korean_key': korean.key,
        'as_of': as_of.isoformat(),
        'viewer_slug': primary.viewer_slug,
        'sentinel_review': SENTINEL_REVIEW,
    }


def run_preview() -> int:
    """Temp SQLite + headed Chromium. Ctrl+C until stop."""
    from tests.helpers import (
        PROJECT_ROOT as HELPERS_ROOT,
        _refuse_remote_database,
        _snapshot_local_db_files,
        sqlite_uri_for,
    )

    qa_dir = Path(__file__).resolve().parent
    if str(qa_dir) not in sys.path:
        sys.path.insert(0, str(qa_dir))
    from run import (  # noqa: WPS433
        QA_SECRET,
        _assert_local_db_unchanged,
        _pick_port,
        _playwright_ready,
        _rmtree,
        _stop_process,
        _wait_http,
    )
    from smoke_step3 import login_load, mint_session_cookie

    if HELPERS_ROOT != PROJECT_ROOT:
        raise RuntimeError('tests.helpers PROJECT_ROOT mismatch.')
    _playwright_ready()
    before = _snapshot_local_db_files()
    temp_dir = Path(tempfile.mkdtemp(prefix='clc_preview_'))
    preview_db = temp_dir / 'preview.db'
    test_uri = sqlite_uri_for(preview_db)
    _refuse_remote_database(test_uri)
    port = _pick_port()
    state_path = temp_dir / 'qa_state.json'
    log_path = temp_dir / 'server.log'
    env = os.environ.copy()
    env['CLC_TESTING'] = '1'
    env['DATABASE_URL'] = test_uri
    env['FIREBASE_CREDENTIALS_JSON'] = ''
    env['SECRET_KEY'] = QA_SECRET
    env['PYTHONIOENCODING'] = 'utf-8'
    env['CLC_QA_PORT'] = str(port)
    env['CLC_QA_STATE_PATH'] = str(state_path)
    env['CLC_QA_SEED'] = 'preview'
    env['READING_AI_ENABLED'] = ''
    env['GENERAL_READING_V2_START_DATE'] = '2026-08-01'
    env.pop('FLASK_ENV', None)
    env.pop('FLASK_DEBUG', None)
    env.pop('CLC_ALLOW_GROWTH_SEED', None)
    env.pop('OPENAI_API_KEY', None)
    env.pop('OPENAI_BASE_URL', None)
    for key in list(env):
        upper = key.upper()
        if upper.startswith('AWS_') or 'BEDROCK' in upper:
            env.pop(key, None)

    print('[preview] isolated SQLite ready')
    print('[preview] local/production DB NOT TOUCHED')
    print(f'PREVIEW DB: {preview_db}')
    print('LOCAL/PRODUCTION DB NOT TOUCHED')

    proc = None
    log_handle = None
    browser = None
    playwright = None
    exit_code = 0
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
            raise RuntimeError(f'preview server failed to start.\n{log_tail}')
        if not state_path.exists():
            raise RuntimeError('preview server started but did not write qa_state.json.')
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if str(state.get('secret_key')) != QA_SECRET:
            raise RuntimeError('QA secret_key mismatch; refusing to mint a session cookie.')
        primary_url = f'{base_url}/children/{int(state["child_id"])}/growth'
        sparse_url = f'{base_url}/children/{int(state["sparse_child_id"])}/growth'
        print(f'[preview] server: {base_url}')
        print('[preview] Growth primary:')
        print(primary_url)
        print('[preview] Growth sparse:')
        print(sparse_url)
        print(f'Growth preview:\n{primary_url}')
        print(f'Sparse preview:\n{sparse_url}')

        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=False, args=['--start-maximized'])
        context = browser.new_context()
        page = context.new_page()
        login_load(page, base_url)
        context.add_cookies([{
            'name': 'session',
            'value': mint_session_cookie(state['secret_key'], int(state['teacher_id'])),
            'url': base_url,
            'httpOnly': True,
            'secure': False,
            'sameSite': 'Lax',
        }])
        page.goto(primary_url, wait_until='domcontentloaded')
        print('Browser opened.')
        print('Press Ctrl+C to stop preview.')
        try:
            while True:
                if proc.poll() is not None:
                    raise RuntimeError('preview server exited unexpectedly.')
                time.sleep(0.5)
        except KeyboardInterrupt:
            print('\n[preview] stopping')
    except Exception as exc:
        print(f'[preview] error: {exc}', file=sys.stderr)
        exit_code = 1
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
        try:
            if playwright is not None:
                playwright.stop()
        except Exception:
            pass
        _stop_process(proc)
        if log_handle is not None:
            log_handle.close()
        _rmtree(temp_dir)
        after = _snapshot_local_db_files()
        try:
            _assert_local_db_unchanged(before, after, 'during preview')
        except Exception as exc:
            print(f'[preview] isolation failure: {exc}', file=sys.stderr)
            exit_code = 1
        if preview_db.exists():
            print(f'[preview] temp DB was not cleaned up: {preview_db}', file=sys.stderr)
            exit_code = 1
    return exit_code


def _weekday_dates(start: date, end: date, weekdays: set[int]):
    cursor = start
    while cursor <= end:
        if cursor.weekday() in weekdays:
            yield cursor
        cursor += timedelta(days=1)


def _fill_learning(db, *, child, subjects, focus, as_of, teacher_id, page_shift, overlap):
    from feature_models import ACTOR_TEACHER, STUDY_STATUS_EXPLICIT_NOT_STUDIED, STUDY_STATUS_STUDIED
    from features.study.calendar import get_subject_study_weekdays
    from features.study.constants import INPUT_CHANNEL_TEACHER, RECORD_VERIFICATION_OBSERVED
    from features.study.records import create_study_session

    window_start = as_of - timedelta(days=59)
    focus_ids = {row.id for row in focus}
    for subject in subjects:
        weekdays = set(get_subject_study_weekdays(subject.id) or [0, 1, 2, 3, 4])
        days = [day for day in _weekday_dates(window_start, as_of, weekdays)]
        studied_n = 0
        for index, day in enumerate(days):
            if subject.id not in focus_ids:
                continue
            # Keep confirmation high: every expected day is explicit.
            if index % 8 == 7:
                create_study_session(
                    child_id=child.id,
                    learning_subject_id=subject.id,
                    study_date=day,
                    study_status=STUDY_STATUS_EXPLICIT_NOT_STUDIED,
                    recorded_by_user_id=teacher_id,
                    record_verification=RECORD_VERIFICATION_OBSERVED,
                    actor_type=ACTOR_TEACHER,
                    input_channel=INPUT_CHANNEL_TEACHER,
                    commit=False,
                )
                continue
            studied_n += 1
            start = 1 + page_shift + (studied_n - 1) * 4
            if overlap and studied_n % 5 == 0 and studied_n > 1:
                start = max(1, start - 1)
            if start > 200:
                create_study_session(
                    child_id=child.id,
                    learning_subject_id=subject.id,
                    study_date=day,
                    study_status=STUDY_STATUS_EXPLICIT_NOT_STUDIED,
                    recorded_by_user_id=teacher_id,
                    record_verification=RECORD_VERIFICATION_OBSERVED,
                    actor_type=ACTOR_TEACHER,
                    input_channel=INPUT_CHANNEL_TEACHER,
                    commit=False,
                )
                continue
            end = min(200, start + 3)
            create_study_session(
                child_id=child.id,
                learning_subject_id=subject.id,
                study_date=day,
                study_status=STUDY_STATUS_STUDIED,
                start_page=start,
                end_page=end,
                recorded_by_user_id=teacher_id,
                record_verification=RECORD_VERIFICATION_OBSERVED,
                actor_type=ACTOR_TEACHER,
                input_channel=INPUT_CHANNEL_TEACHER,
                commit=False,
            )
    db.session.commit()


def _seed_points(db, child, teacher_id, as_of, totals):
    from app import DailyPoints

    for offset, total in zip((2, 9, 16), totals):
        day = as_of - timedelta(days=offset)
        db.session.add(DailyPoints(
            child_id=child.id,
            date=day,
            korean_points=total,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=0,
            manual_history='[]',
            total_points=total,
            created_by=teacher_id,
        ))
    previous = as_of - timedelta(days=40)
    db.session.add(DailyPoints(
        child_id=child.id,
        date=previous,
        korean_points=40,
        math_points=0,
        ssen_points=0,
        reading_points=0,
        piano_points=0,
        english_points=0,
        advanced_math_points=0,
        writing_points=0,
        manual_points=0,
        manual_history='[]',
        total_points=40,
        created_by=teacher_id,
    ))
    db.session.commit()


def _seed_reading(db, child, teacher_id, as_of):
    from feature_models import (
        ACTOR_TEACHER,
        POLICY_VERSION_GENERAL_V2,
        POLICY_VERSION_RECOMMENDED_V1,
        PROGRAM_TYPE_GENERAL,
        PROGRAM_TYPE_RECOMMENDED,
        STATUS_COMPLETED,
        STATUS_IN_PROGRESS,
        Book,
        ChildReading,
        ReadingDay,
    )

    # completed_on must fall inside the current 30-day Growth window.
    # ReadingDay dates stay older than the in-progress 8+8 sample.
    first = _book(db, '미리보기 완독 1')
    first_reading = ChildReading(
        child_id=child.id,
        book_id=first.id,
        started_on=as_of - timedelta(days=26),
        completed_on=as_of - timedelta(days=20),
        ended_on=as_of - timedelta(days=20),
        status=STATUS_COMPLETED,
        program_type=PROGRAM_TYPE_GENERAL,
        policy_version=POLICY_VERSION_GENERAL_V2,
        created_by_user_id=teacher_id,
        actor_type=ACTOR_TEACHER,
    )
    db.session.add(first_reading)
    db.session.flush()
    db.session.add(ReadingDay(
        child_reading_id=first_reading.id,
        date=as_of - timedelta(days=26),
        review_text='첫 권을 끝까지 읽었다.',
        created_by_user_id=teacher_id,
        actor_type=ACTOR_TEACHER,
        policy_version=POLICY_VERSION_GENERAL_V2,
    ))

    second = _book(db, '미리보기 완독 2')
    second_reading = ChildReading(
        child_id=child.id,
        book_id=second.id,
        started_on=as_of - timedelta(days=19),
        completed_on=as_of - timedelta(days=12),
        ended_on=as_of - timedelta(days=12),
        status=STATUS_COMPLETED,
        program_type=PROGRAM_TYPE_RECOMMENDED,
        policy_version=POLICY_VERSION_RECOMMENDED_V1,
        created_by_user_id=teacher_id,
        actor_type=ACTOR_TEACHER,
    )
    db.session.add(second_reading)
    db.session.flush()
    db.session.add(ReadingDay(
        child_reading_id=second_reading.id,
        date=as_of - timedelta(days=19),
        review_text='두 번째 책도 완독했다.',
        created_by_user_id=teacher_id,
        actor_type=ACTOR_TEACHER,
        policy_version=POLICY_VERSION_RECOMMENDED_V1,
    ))

    current_book = _book(db, '미리보기 읽는 중')
    current = ChildReading(
        child_id=child.id,
        book_id=current_book.id,
        started_on=as_of - timedelta(days=16),
        status=STATUS_IN_PROGRESS,
        policy_version=POLICY_VERSION_GENERAL_V2,
        created_by_user_id=teacher_id,
        actor_type=ACTOR_TEACHER,
    )
    db.session.add(current)
    db.session.flush()
    blank_on = as_of - timedelta(days=10)
    for offset in range(16, -1, -1):
        day = as_of - timedelta(days=offset)
        if day == blank_on:
            text = None
        else:
            extra = '짧은 문장. 다음 문장!' if offset % 3 == 0 else '오늘 읽은 장면이 재미있었다'
            text = f'{SENTINEL_REVIEW} {offset} {extra}'
        db.session.add(ReadingDay(
            child_reading_id=current.id,
            date=day,
            review_text=text,
            created_by_user_id=teacher_id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        ))
    db.session.commit()


def _book(db, title):
    from feature_models import Book

    row = Book(title=title, normalized_key=title, is_active=True)
    db.session.add(row)
    db.session.flush()
    return row
