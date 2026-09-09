"""Isolated Flask process for browser QA. Production app.py __main__ is not used.

Parent must set DATABASE_URL to a temp SQLite file before this process starts.
This module refuses remote/local development DBs and never starts backup/Firebase.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.helpers import (  # noqa: E402
    _noop_realtime_backup,
    _refuse_remote_database,
    _snapshot_local_db_files,
    assert_test_engine_isolated,
    configure_test_environment,
    local_development_sqlite_path,
    resolved_engine_sqlite_path,
)


def _qa_db_path_from_url(url: str) -> Path:
    _refuse_remote_database(url)
    if not (url or '').startswith('sqlite:///'):
        raise RuntimeError(f'QA DATABASE_URL must be sqlite, got {url!r}')
    path = Path(url.replace('sqlite:///', '', 1)).resolve()
    local = local_development_sqlite_path()
    if path == local:
        raise RuntimeError(f'QA DATABASE_URL points at local development DB: {path}')
    if 'instance' in path.parts and path.name == 'child_center.db':
        raise RuntimeError(f'QA DATABASE_URL points at instance DB: {path}')
    if local.as_posix() in url.replace('\\', '/'):
        raise RuntimeError('QA DATABASE_URL overlaps local development DB.')
    return path


def _pick_non_study_day(as_of: date, holiday_days: set[date]) -> date:
    last = monthrange(as_of.year, as_of.month)[1]
    for day_n in range(1, last + 1):
        candidate = date(as_of.year, as_of.month, day_n)
        if candidate != as_of and candidate not in holiday_days:
            return candidate
    for day_n in range(1, last + 1):
        candidate = date(as_of.year, as_of.month, day_n)
        if candidate != as_of:
            return candidate
    raise RuntimeError('Could not pick a non-study day in the current month.')


def _weekday_dates(start: date, end: date, weekday: int):
    cursor = start
    while cursor <= end:
        if cursor.weekday() == weekday:
            yield cursor
        cursor += timedelta(days=1)


def _seed_peer_ready_child(db, child, subject, as_of: date, teacher_id: int, *, coverage_end: int, points: int):
    from app import DailyPoints
    from feature_models import ACTOR_TEACHER, STUDY_STATUS_EXPLICIT_NOT_STUDIED, STUDY_STATUS_STUDIED
    from features.study.constants import INPUT_CHANNEL_TEACHER, RECORD_VERIFICATION_OBSERVED
    from features.study.records import create_study_session

    window_start = as_of - timedelta(days=29)
    days = list(_weekday_dates(window_start, as_of, as_of.weekday()))
    if not days:
        raise RuntimeError('QA seed has no expected weekday in the current window.')
    for index, day in enumerate(days):
        if index == 0:
            create_study_session(
                child_id=child.id,
                learning_subject_id=subject.id,
                study_date=day,
                study_status=STUDY_STATUS_STUDIED,
                start_page=1,
                end_page=coverage_end,
                recorded_by_user_id=teacher_id,
                record_verification=RECORD_VERIFICATION_OBSERVED,
                actor_type=ACTOR_TEACHER,
                input_channel=INPUT_CHANNEL_TEACHER,
            )
        else:
            create_study_session(
                child_id=child.id,
                learning_subject_id=subject.id,
                study_date=day,
                study_status=STUDY_STATUS_EXPLICIT_NOT_STUDIED,
                recorded_by_user_id=teacher_id,
                record_verification=RECORD_VERIFICATION_OBSERVED,
                actor_type=ACTOR_TEACHER,
                input_channel=INPUT_CHANNEL_TEACHER,
            )
    db.session.add(DailyPoints(
        child_id=child.id,
        date=as_of,
        korean_points=points,
        math_points=0,
        ssen_points=0,
        reading_points=0,
        piano_points=0,
        english_points=0,
        advanced_math_points=0,
        writing_points=0,
        manual_points=0,
        manual_history='[]',
        total_points=points,
        created_by=teacher_id,
    ))
    db.session.commit()


def _seed(db, as_of: date) -> dict:
    from app import Child, User
    from feature_models import CenterSystemHolidaySeed, LearningSubject
    from features.planning.service import create_workbook_plan, update_center_weekdays
    from features.progress.service import ensure_default_subjects
    from features.study.calendar import save_subject_study_weekdays
    from features.study.holidays import korean_public_holidays

    teacher = User(
        username='qa_teacher',
        name='QA교사',
        role='돌봄선생님',
        email='qa-teacher@example.test',
        password_hash='',
    )
    child = Child(
        name='QA아동',
        grade=3,
        viewer_slug='qaqaqaqaqaqaqaqaqaqaqaqa',
        created_at=datetime(2020, 1, 1),
    )
    db.session.add_all([teacher, child])
    db.session.commit()

    ensure_default_subjects()
    weekday = as_of.weekday()
    other_day = (weekday + 1) % 7
    update_center_weekdays(sorted({weekday, other_day}))

    subjects = list(LearningSubject.query.filter_by(is_active=True).order_by(LearningSubject.id.asc()).all())
    if not subjects:
        raise RuntimeError('QA seed has no active LearningSubject.')
    expected = next((row for row in subjects if row.key == 'math'), subjects[0])
    for subject in subjects:
        days = [weekday] if subject.id == expected.id else [other_day]
        save_subject_study_weekdays(subject.id, days)
        plan = create_workbook_plan(
            grade=3,
            learning_subject_id=subject.id,
            textbook_title=f'QA {subject.name} 교재',
            start_page=1,
            end_page=100,
            start_date=as_of - timedelta(days=30),
            target_completion_date=as_of + timedelta(days=120),
        )
        plan.exclusion_ranges_json = []
        plan.exclusion_ranges_text = ''
    db.session.commit()

    # Prevent GET /settings/non-study-days from seeding holidays that could
    # exclude as_of. Holiday algorithm is out of browser QA scope.
    if CenterSystemHolidaySeed.query.filter_by(year=as_of.year).first() is None:
        db.session.add(CenterSystemHolidaySeed(year=as_of.year, seeded_at=datetime.utcnow()))
        db.session.commit()

    holiday_days = set()
    try:
        holiday_days = set(korean_public_holidays(as_of.year).keys())
    except Exception:
        holiday_days = set()
    non_study_day = _pick_non_study_day(as_of, holiday_days)

    sparse = Child(
        name='QA데이터부족아동',
        grade=3,
        viewer_slug='qasparseqasparseqasparseqa',
        created_at=datetime(2020, 1, 1),
    )
    ready = Child(
        name='QA또래기준아동',
        grade=4,
        viewer_slug='qareadyqareadyqareadyqar',
        created_at=datetime(2020, 1, 1),
    )
    lonely = Child(
        name='QA또래없음아동',
        grade=6,
        viewer_slug='qaloneqaloneqaloneqalone',
        created_at=datetime(2020, 1, 1),
    )
    peers = [
        Child(
            name=f'QA또래{index}',
            grade=4,
            viewer_slug=f'qapeer{index:018d}',
            created_at=datetime(2020, 1, 1),
        )
        for index in range(1, 4)
    ]
    db.session.add_all([sparse, ready, lonely, *peers])
    db.session.commit()

    for subject in subjects:
        plan = create_workbook_plan(
            grade=4,
            learning_subject_id=subject.id,
            textbook_title=f'QA4 {subject.name} 교재',
            start_page=1,
            end_page=100,
            start_date=as_of - timedelta(days=30),
            target_completion_date=as_of + timedelta(days=120),
        )
        plan.exclusion_ranges_json = []
        plan.exclusion_ranges_text = ''
    db.session.commit()

    _seed_peer_ready_child(db, ready, expected, as_of, teacher.id, coverage_end=20, points=125)
    for peer, pages, points in zip(peers, (10, 30, 50), (100, 110, 140)):
        _seed_peer_ready_child(db, peer, expected, as_of, teacher.id, coverage_end=pages, points=points)

    return {
        'teacher_id': teacher.id,
        'child_id': child.id,
        'sparse_child_id': sparse.id,
        'peer_ready_child_id': ready.id,
        'lonely_child_id': lonely.id,
        'subject_id': expected.id,
        'subject_key': expected.key,
        'as_of': as_of.isoformat(),
        'non_study_day': non_study_day.isoformat(),
        'non_study_year': non_study_day.year,
        'non_study_month': non_study_day.month,
        'non_study_label': 'QA-NSD',
    }


def main() -> int:
    raw_url = (os.environ.get('DATABASE_URL') or '').strip()
    qa_db_path = _qa_db_path_from_url(raw_url)
    port = int(os.environ.get('CLC_QA_PORT') or '0')
    if port <= 0 or port == 5000:
        raise RuntimeError(f'CLC_QA_PORT must be a non-5000 TCP port, got {port!r}')
    state_path = Path(os.environ.get('CLC_QA_STATE_PATH') or '').resolve()
    if not state_path:
        raise RuntimeError('CLC_QA_STATE_PATH is required.')

    configure_test_environment(raw_url)
    _refuse_remote_database(os.environ.get('DATABASE_URL') or '')

    db_before = _snapshot_local_db_files()
    threads_before = {t.ident for t in threading.enumerate()}

    from app import app, db  # noqa: WPS433 — DATABASE_URL is already isolated
    import app as app_module  # noqa: WPS433

    db_after = _snapshot_local_db_files()
    new_threads = {t.ident for t in threading.enumerate()} - threads_before
    side_effects = []
    if (os.environ.get('DATABASE_URL') or '') != raw_url:
        side_effects.append('DATABASE_URL changed during import')
    try:
        import firebase_admin
        if firebase_admin._apps:
            side_effects.append('Firebase Admin SDK initialized during import')
    except Exception:
        pass
    if new_threads:
        side_effects.append(f'import created {len(new_threads)} extra thread(s)')
    for path, before in db_before.items():
        after = db_after.get(path)
        if before != after:
            side_effects.append(f'local DB changed during import: {path}')
    if side_effects:
        raise RuntimeError('QA server import isolation failed: ' + ' / '.join(side_effects))

    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = raw_url
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
    app.config['SESSION_COOKIE_SECURE'] = False
    app_module.realtime_backup = _noop_realtime_backup

    with app.app_context():
        db.session.remove()
        db.engine.dispose()
        db.create_all()
        engine_path = assert_test_engine_isolated(db)
        if engine_path != qa_db_path:
            raise RuntimeError(f'QA engine is not the temp DB: {engine_path} vs {qa_db_path}')
        resolved = resolved_engine_sqlite_path(db)
        if resolved != qa_db_path:
            raise RuntimeError(f'QA resolved engine mismatch: {resolved}')
        from features.dates import kst_today
        as_of = kst_today()
        state = _seed(db, as_of)
        state['port'] = port
        state['secret_key'] = app.config['SECRET_KEY']
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')

    print(f'CLC_QA_SERVER_READY port={port}', flush=True)
    app.run(
        host='127.0.0.1',
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'CLC_QA_SERVER_ERROR {exc}', file=sys.stderr, flush=True)
        raise
