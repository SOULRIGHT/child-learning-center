"""Growth 개발/검증용 deterministic scenario seed.

목적: 기능·UI·edge case·demo 화면을 사람이 예측 가능하게 검증한다.
목적이 아닌 것: 실제 사용자 분포 추정, threshold calibration,
정책 효과 증명, 센터 통계 대체.

기존 seed_basic / seed_quick_30 / seed_name / seed_production 은 그대로 둔다.
이 모듈은 시드- 이름 아동만 추가/교체한다.

threshold는 provisional initial rule 이다. 이 seed로 임계값을 검증했다고 말하지 않는다.

instance/child_center.db 와 production 은 기본 거부.
테스트/임시 DB에서만 기본 실행한다.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from datetime import date, timedelta

from flask import current_app, has_app_context

from extensions import db
from feature_models import (
    ACTOR_TEACHER,
    GRADE_BAND_2_3,
    GRADE_BAND_4_6,
    POLICY_VERSION_CHALLENGE_V1,
    POLICY_VERSION_GENERAL_V2,
    POLICY_VERSION_RECOMMENDED_V1,
    PROGRAM_TYPE_CHALLENGE,
    PROGRAM_TYPE_GENERAL,
    PROGRAM_TYPE_RECOMMENDED,
    STATUS_ABANDONED,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    Book,
    ChildReading,
    LearningProgressEntry,
    LearningSubject,
    ReadingDay,
    normalize_book_title,
)
from features.dates import is_production_runtime, kst_today
from features.growth.windows import current_window, previous_window
from features.progress.service import ensure_default_subjects


NAME_PREFIX = '시드-'
ALLOW_ENV = 'CLC_ALLOW_GROWTH_SEED'

# 개발자가 어떤 아동을 열지 알기 위한 catalog. DB에 저장하지 않는다.
SCENARIO_CATALOG = {
    'S1': {'name': '시드-독서증가', 'grade': 2, 'label': '독서 활동 증가'},
    'S2': {'name': '시드-독서감소', 'grade': 3, 'label': '독서 활동 감소'},
    'S3': {'name': '시드-변화없음', 'grade': 1, 'label': '독서 변화 거의 없음'},
    'S4': {'name': '시드-완독증가', 'grade': 4, 'label': '완독 증가'},
    'S5': {'name': '시드-진도증가', 'grade': 2, 'label': '학습 진도 기록 증가'},
    'S6': {'name': '시드-진도감소', 'grade': 3, 'label': '학습 진도 기록 감소'},
    'S7': {'name': '시드-포인트증가', 'grade': 5, 'label': '기간 포인트 증가'},
    'S8': {'name': '시드-이전포인트없음', 'grade': 4, 'label': 'previous point activity 0'},
    'S9': {'name': '시드-난이도재미유지', 'grade': 5, 'label': 'paired 난이도↑ 재미 유지'},
    'S10': {'name': '시드-재미하락', 'grade': 6, 'label': '난이도↑ 재미 크게 하락'},
    'S11': {'name': '시드-평가부족', 'grade': 4, 'label': 'paired n=2'},
    'S12': {'name': '시드-평가분리', 'grade': 3, 'label': 'unpaired rating'},
    'S13': {'name': '시드-신규희소', 'grade': 1, 'label': 'recent-only, coverage 부족'},
    'S14': {'name': '시드-추천도전', 'grade': 5, 'label': '일반/추천/도전 완독'},
    'S15': {'name': '시드-첫기록', 'grade': 2, 'label': '첫 독서/첫 완독'},
    'S16': {'name': '시드-포인트상위', 'grade': 6, 'label': '누적 상위'},
    'S17': {'name': '시드-복합증가', 'grade': 3, 'label': '독서+완독+진도 증가'},
    'S18': {'name': '시드-후보없음', 'grade': 2, 'label': 'candidate 0개'},
    'S19': {'name': '시드-포인트중위', 'grade': 4, 'label': '누적 중위'},
    'S20': {'name': '시드-포인트하위', 'grade': 1, 'label': '누적 하위'},
    'S21': {'name': '시드-완독10', 'grade': 6, 'label': '완독 10권'},
    'S22': {'name': '시드-첫추천완독', 'grade': 3, 'label': '첫 추천 완독'},
}

EXPECTED = {
    'S1': {'include': ['READING_ACTIVITY_INCREASE'], 'exclude': ['READING_ACTIVITY_DECREASE']},
    'S2': {'include': ['READING_ACTIVITY_DECREASE'], 'exclude': ['READING_ACTIVITY_INCREASE']},
    'S3': {'exclude': ['READING_ACTIVITY_INCREASE', 'READING_ACTIVITY_DECREASE']},
    'S4': {'include': ['READING_COMPLETIONS_INCREASE']},
    'S5': {'include': ['PROGRESS_ENTRIES_INCREASE']},
    'S6': {'include': ['PROGRESS_ENTRIES_DECREASE']},
    'S7': {'include': ['POINTS_PERIOD_INCREASE']},
    'S8': {'exclude': ['POINTS_PERIOD_INCREASE']},
    'S9': {'include': ['HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN']},
    'S10': {'exclude': ['HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN']},
    'S11': {'exclude': ['HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN']},
    'S12': {'exclude': ['HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN'], 'paired_n': 0},
    'S13': {
        'exclude': [
            'READING_ACTIVITY_INCREASE',
            'READING_ACTIVITY_DECREASE',
            'POINTS_PERIOD_INCREASE',
            'PROGRESS_ENTRIES_INCREASE',
            'HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN',
        ],
    },
    'S17': {
        'include': [
            'READING_ACTIVITY_INCREASE',
            'READING_COMPLETIONS_INCREASE',
            'PROGRESS_ENTRIES_INCREASE',
        ],
    },
    'S18': {
        'exclude': [
            'READING_ACTIVITY_INCREASE',
            'READING_ACTIVITY_DECREASE',
            'READING_COMPLETIONS_INCREASE',
            'READING_COMPLETIONS_DECREASE',
            'PROGRESS_ENTRIES_INCREASE',
            'PROGRESS_ENTRIES_DECREASE',
            'POINTS_PERIOD_INCREASE',
            'HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN',
        ],
    },
}


def scenario_names():
    return [item['name'] for item in SCENARIO_CATALOG.values()]


def assert_growth_seed_target_allowed(uri=None):
    """production / 승인 없는 로컬 운영 DB를 거부한다."""
    if is_production_runtime():
        raise RuntimeError('Growth development seed는 production에서 실행할 수 없습니다.')
    if uri is None and has_app_context():
        uri = current_app.config.get('SQLALCHEMY_DATABASE_URI') or ''
    if uri is None:
        uri = os.environ.get('DATABASE_URL') or ''
    normalized = str(uri).replace('\\', '/')
    if 'child_center.db' in normalized and os.environ.get(ALLOW_ENV) != '1':
        raise RuntimeError(
            'instance/child_center.db 에는 '
            f'{ALLOW_ENV}=1 없이 Growth seed를 실행하지 않습니다.'
        )


def _slug(key):
    return hashlib.md5(f'growth-seed-{key}'.encode('utf-8')).hexdigest()[:24]


def _pick_dates(window, count):
    start, end = window['start'], window['end']
    if count <= 0:
        return []
    span = (end - start).days
    if count == 1:
        return [start]
    chosen = []
    seen = set()
    for index in range(count):
        offset = round(index * span / (count - 1))
        day = start + timedelta(days=offset)
        if day not in seen:
            chosen.append(day)
            seen.add(day)
    cursor = start
    while len(chosen) < count and cursor <= end:
        if cursor not in seen:
            chosen.append(cursor)
            seen.add(cursor)
        cursor += timedelta(days=1)
    return chosen[:count]


def _actor_user_id(created_by_user_id):
    from app import User
    if created_by_user_id is not None:
        return created_by_user_id
    existing = User.query.filter_by(username='growth_seed_teacher').first()
    if existing is not None:
        return existing.id
    first = User.query.first()
    if first is not None:
        return first.id
    user = User(username='growth_seed_teacher', name='시드교사', role='돌봄선생님', password_hash='')
    db.session.add(user)
    db.session.flush()
    return user.id


def _ensure_book(title, *, recommended=False, challenge=False, grade_band=None):
    key = normalize_book_title(title)
    book = Book.query.filter_by(normalized_key=key).first()
    if book is None:
        book = Book(
            title=title,
            normalized_key=key,
            is_active=True,
            is_recommended=recommended,
            is_challenge_eligible=challenge,
            grade_band=grade_band,
        )
        db.session.add(book)
        db.session.flush()
        return book
    book.is_recommended = recommended
    book.is_challenge_eligible = challenge
    if grade_band is not None:
        book.grade_band = grade_band
    book.is_active = True
    return book


def _child(key, created):
    spec = SCENARIO_CATALOG[key]
    from app import Child
    child = Child(
        name=spec['name'],
        grade=spec['grade'],
        include_in_stats=True,
        viewer_slug=_slug(key),
        cumulative_points=0,
    )
    db.session.add(child)
    db.session.flush()
    created[key] = child
    return child


def _reading(child, book, *, started_on, status, actor_id, completed_on=None, ended_on=None,
             program=PROGRAM_TYPE_GENERAL, difficulty=None, fun=None):
    policy = POLICY_VERSION_GENERAL_V2
    if program == PROGRAM_TYPE_RECOMMENDED:
        policy = POLICY_VERSION_RECOMMENDED_V1
    elif program == PROGRAM_TYPE_CHALLENGE:
        policy = POLICY_VERSION_CHALLENGE_V1
    row = ChildReading(
        child_id=child.id,
        book_id=book.id,
        started_on=started_on,
        completed_on=completed_on,
        ended_on=ended_on,
        status=status,
        program_type=program,
        policy_version=policy,
        difficulty_rating=difficulty,
        fun_rating=fun,
        created_by_user_id=actor_id,
        actor_type=ACTOR_TEACHER,
    )
    db.session.add(row)
    db.session.flush()
    return row


def _days(reading, dates, actor_id):
    for on in dates:
        db.session.add(ReadingDay(
            child_reading_id=reading.id,
            date=on,
            created_by_user_id=actor_id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        ))


def _points(child, on, actor_id, *, korean=0, math=0, ssen=0, reading=0, manual=0):
    from app import DailyPoints
    total = korean + math + ssen + reading + manual
    db.session.add(DailyPoints(
        child_id=child.id,
        date=on,
        korean_points=korean,
        math_points=math,
        ssen_points=ssen,
        reading_points=reading,
        piano_points=0,
        english_points=0,
        advanced_math_points=0,
        writing_points=0,
        manual_points=manual,
        manual_history='[]',
        total_points=total,
        created_by=actor_id,
    ))
    return total


def _progress(child, subject, on, actor_id, *, title='시드교재', page=10):
    db.session.add(LearningProgressEntry(
        child_id=child.id,
        learning_subject_id=subject.id,
        recorded_on=on,
        textbook_title=title,
        page=page,
        created_by_user_id=actor_id,
    ))


def _flat_points(child, windows, actor_id, daily):
    for window in windows:
        for on in _pick_dates(window, 4):
            _points(child, on, actor_id, korean=daily)


def remove_growth_seed_children():
    """시드- catalog 이름 아동과 그 원장만 지운다. 다른 아동은 건드리지 않는다."""
    from app import Child, DailyPoints, LearningRecord
    names = scenario_names()
    children = Child.query.filter(Child.name.in_(names)).all()
    ids = [child.id for child in children]
    if not ids:
        return 0
    readings = ChildReading.query.filter(ChildReading.child_id.in_(ids)).all()
    reading_ids = [row.id for row in readings]
    if reading_ids:
        ReadingDay.query.filter(ReadingDay.child_reading_id.in_(reading_ids)).delete(synchronize_session=False)
        ChildReading.query.filter(ChildReading.id.in_(reading_ids)).delete(synchronize_session=False)
    LearningProgressEntry.query.filter(LearningProgressEntry.child_id.in_(ids)).delete(synchronize_session=False)
    DailyPoints.query.filter(DailyPoints.child_id.in_(ids)).delete(synchronize_session=False)
    LearningRecord.query.filter(LearningRecord.child_id.in_(ids)).delete(synchronize_session=False)
    Child.query.filter(Child.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    db.session.expunge_all()
    return len(ids)


def _sync_cumulative(children):
    from app import DailyPoints
    for child in children:
        total = db.session.query(db.func.coalesce(db.func.sum(DailyPoints.total_points), 0)).filter_by(
            child_id=child.id,
        ).scalar()
        child.cumulative_points = int(total or 0)


def seed_growth_scenarios(anchor_date=None, created_by_user_id=None, replace_existing=False):
    """anchor_date 기준 current/previous 30일에 scenario 아동을 심는다."""
    assert_growth_seed_target_allowed()
    from app import Child
    existing = Child.query.filter(Child.name.in_(scenario_names())).count()
    if existing and not replace_existing:
        raise RuntimeError(
            '시드- 아동이 이미 있습니다. replace_existing=True 로만 다시 심습니다.'
        )
    if existing and replace_existing:
        remove_growth_seed_children()

    anchor = anchor_date or kst_today()
    if isinstance(anchor, str):
        anchor = date.fromisoformat(anchor)
    current = current_window(anchor, 30)
    previous = previous_window(anchor, 30)
    actor_id = _actor_user_id(created_by_user_id)
    ensure_default_subjects()
    subjects = {row.key: row for row in LearningSubject.query.all()}
    korean = subjects['korean']
    math = subjects['math']
    ssen = subjects['ssen']

    books = {
        f'g{index}': _ensure_book(f'시드일반{index:02d}')
        for index in range(1, 36)
    }
    books['rec23'] = _ensure_book('시드추천23', recommended=True, grade_band=GRADE_BAND_2_3)
    books['rec46'] = _ensure_book('시드추천46', recommended=True, grade_band=GRADE_BAND_4_6)
    books['ch'] = _ensure_book('시드도전책', challenge=True)
    created = {}

    def reading_days_both(child, book_key, previous_count, current_count):
        prev_dates = _pick_dates(previous, previous_count)
        cur_dates = _pick_dates(current, current_count)
        started = prev_dates[0] if prev_dates else cur_dates[0]
        reading = _reading(
            child, books[book_key], started_on=started, status=STATUS_IN_PROGRESS, actor_id=actor_id,
        )
        _days(reading, prev_dates + cur_dates, actor_id)
        return reading

    def complete_n(child, window, count, *, ratings=None, programs=None, book_start=1):
        dates = _pick_dates(window, max(count, 1))
        rows = []
        for index in range(count):
            on = dates[index % len(dates)]
            started = on - timedelta(days=1) if on > window['start'] else on
            program = PROGRAM_TYPE_GENERAL
            if programs and index < len(programs):
                program = programs[index]
            difficulty = fun = None
            if ratings and index < len(ratings):
                difficulty, fun = ratings[index]
            book = books[f'g{book_start + index}']
            if program == PROGRAM_TYPE_RECOMMENDED:
                book = books['rec46'] if child.grade >= 4 else books['rec23']
            elif program == PROGRAM_TYPE_CHALLENGE:
                book = books['ch']
            row = _reading(
                child, book, started_on=started, completed_on=on, status=STATUS_COMPLETED,
                actor_id=actor_id, program=program, difficulty=difficulty, fun=fun,
            )
            _days(row, [started, on] if started != on else [on], actor_id)
            rows.append(row)
        return rows

    # S1 reading 5 -> 10
    child = _child('S1', created)
    reading_days_both(child, 'g1', 5, 10)

    # S2 reading 10 -> 5
    child = _child('S2', created)
    reading_days_both(child, 'g1', 10, 5)

    # S3 reading 6 -> 6
    child = _child('S3', created)
    reading_days_both(child, 'g1', 6, 6)
    _flat_points(child, [previous, current], actor_id, 100)
    for on in _pick_dates(previous, 4) + _pick_dates(current, 4):
        _progress(child, korean, on, actor_id, page=10)

    # S4 completions 2 -> 4
    child = _child('S4', created)
    complete_n(child, previous, 2, book_start=1)
    complete_n(child, current, 4, book_start=3)

    # S5 progress 3 -> 7
    child = _child('S5', created)
    for on in _pick_dates(previous, 3):
        _progress(child, korean, on, actor_id, page=8)
    for index, on in enumerate(_pick_dates(current, 7)):
        subject = (korean, math, ssen)[index % 3]
        _progress(child, subject, on, actor_id, page=12 + index)

    # S6 progress 7 -> 3
    child = _child('S6', created)
    for on in _pick_dates(previous, 7):
        _progress(child, math, on, actor_id, page=20)
    for on in _pick_dates(current, 3):
        _progress(child, math, on, actor_id, page=30)

    # S7 points increase, both windows have activity
    child = _child('S7', created)
    for on in _pick_dates(previous, 4):
        _points(child, on, actor_id, korean=100)
    for on in _pick_dates(current, 4):
        _points(child, on, actor_id, korean=200, math=100)

    # S8 coverage before previous, no previous-window rows, current has points
    child = _child('S8', created)
    _points(child, previous['start'] - timedelta(days=7), actor_id, korean=100)
    for on in _pick_dates(current, 3):
        _points(child, on, actor_id, korean=200)

    # S9 paired positive
    child = _child('S9', created)
    complete_n(
        child, previous, 3, book_start=1,
        ratings=[(2, 4), (3, 4), (3, 5)],
    )
    complete_n(
        child, current, 3, book_start=4,
        ratings=[(4, 4), (4, 4), (3, 5)],
    )

    # S10 paired fun drop
    child = _child('S10', created)
    complete_n(
        child, previous, 3, book_start=1,
        ratings=[(2, 5), (3, 5), (3, 4)],
    )
    complete_n(
        child, current, 3, book_start=4,
        ratings=[(4, 2), (4, 2), (4, 3)],
    )

    # S11 paired n=2
    child = _child('S11', created)
    complete_n(child, previous, 2, book_start=1, ratings=[(3, 4), (2, 5)])
    complete_n(child, current, 2, book_start=3, ratings=[(4, 4), (5, 3)])

    # S12 unpaired only
    child = _child('S12', created)
    complete_n(child, previous, 3, book_start=1, ratings=[(3, None), (4, None), (2, None)])
    complete_n(child, current, 3, book_start=4, ratings=[(None, 5), (None, 4), (None, 4)])

    # S13 recent only
    child = _child('S13', created)
    dates = _pick_dates(current, 3)[-2:]
    reading = _reading(child, books['g1'], started_on=dates[0], status=STATUS_IN_PROGRESS, actor_id=actor_id)
    _days(reading, dates, actor_id)
    _points(child, current['end'], actor_id, korean=100)

    # S14 program mix
    child = _child('S14', created)
    complete_n(
        child, current, 3, book_start=1,
        programs=[PROGRAM_TYPE_GENERAL, PROGRAM_TYPE_RECOMMENDED, PROGRAM_TYPE_CHALLENGE],
        ratings=[(3, 4), (4, 4), (5, 3)],
    )
    _reading(
        child, books['g10'], started_on=current['start'], ended_on=current['start'] + timedelta(days=2),
        status=STATUS_ABANDONED, actor_id=actor_id,
    )

    # S15 first reading + first completion in current
    child = _child('S15', created)
    complete_n(child, current, 1, book_start=1, ratings=[(None, None)])

    # S16 high rank
    child = _child('S16', created)
    for on in _pick_dates(previous, 8) + _pick_dates(current, 8):
        _points(child, on, actor_id, korean=200, math=200, ssen=100)

    # S17 overlap increases
    child = _child('S17', created)
    reading_days_both(child, 'g1', 5, 10)
    complete_n(child, previous, 1, book_start=3)
    complete_n(child, current, 3, book_start=4)
    for on in _pick_dates(previous, 3):
        _progress(child, korean, on, actor_id)
    for on in _pick_dates(current, 7):
        _progress(child, math, on, actor_id, page=15)

    # S18 zero candidates
    child = _child('S18', created)
    reading_days_both(child, 'g1', 6, 6)
    complete_n(child, previous, 2, book_start=3)
    complete_n(child, current, 2, book_start=5)
    for on in _pick_dates(previous, 4) + _pick_dates(current, 4):
        _progress(child, ssen, on, actor_id, page=18)
    _flat_points(child, [previous, current], actor_id, 100)

    # S19 mid rank
    child = _child('S19', created)
    for on in _pick_dates(previous, 5) + _pick_dates(current, 5):
        _points(child, on, actor_id, korean=100, math=100)

    # S20 low rank
    child = _child('S20', created)
    _points(child, previous['start'], actor_id, korean=100)
    _points(child, current['start'], actor_id, korean=100)

    # S21 ten completions
    child = _child('S21', created)
    complete_n(child, previous, 6, book_start=1)
    complete_n(child, current, 4, book_start=7)

    # S22 first recommended completion
    child = _child('S22', created)
    complete_n(child, current, 1, book_start=1, programs=[PROGRAM_TYPE_RECOMMENDED])

    _sync_cumulative(created.values())
    db.session.commit()

    return {
        'anchor_date': anchor,
        'current_window': current,
        'previous_window': previous,
        'children': {
            key: {'id': child.id, 'name': child.name, 'grade': child.grade}
            for key, child in created.items()
        },
        'expected': EXPECTED,
        'catalog': SCENARIO_CATALOG,
    }


def print_seed_manifest(result):
    print(f"Growth seed anchor={result['anchor_date']}")
    print(f"current {result['current_window']['start']}..{result['current_window']['end']}")
    print(f"previous {result['previous_window']['start']}..{result['previous_window']['end']}")
    print('이 데이터는 개발/검증용 scenario 이다. 실제 운영 분포가 아니다.')
    for key, spec in SCENARIO_CATALOG.items():
        child = result['children'][key]
        print(f"  {key} {child['name']} (id={child['id']}, {child['grade']}학년) — {spec['label']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description='Growth development scenario seed')
    parser.add_argument('--anchor', default=None, help='YYYY-MM-DD. 기본은 kst_today()')
    parser.add_argument('--replace', action='store_true', help='기존 시드- 아동만 지우고 다시 심는다')
    args = parser.parse_args(argv)
    from app import app
    with app.app_context():
        assert_growth_seed_target_allowed()
        result = seed_growth_scenarios(anchor_date=args.anchor, replace_existing=args.replace)
        print_seed_manifest(result)


if __name__ == '__main__':
    main()
