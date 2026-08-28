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
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import current_app, has_app_context

from extensions import db
from feature_models import (
    ACTOR_TEACHER,
    POLICY_VERSION_CHALLENGE_V1,
    POLICY_VERSION_GENERAL_V2,
    POLICY_VERSION_RECOMMENDED_V1,
    PROGRAM_TYPE_CHALLENGE,
    PROGRAM_TYPE_GENERAL,
    PROGRAM_TYPE_RECOMMENDED,
    REWARD_MODE_EXEMPTION,
    STATUS_ABANDONED,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    Book,
    ChildReading,
    ExemptionTicket,
    ExemptionTicketSource,
    ExemptionUsage,
    LearningProgressEntry,
    LearningSubject,
    ReadingDay,
    ReadingRewardEvent,
    normalize_book_title,
)
from features.dates import is_production_runtime, kst_today
from features.growth.windows import current_window, previous_window
from features.progress.service import ensure_default_subjects
from features.reading.policy import allowed_reading_points
from scripts.seed.growth_seed_fixtures import (
    OLD_PLACEHOLDER_TITLES,
    all_book_specs,
    book_titles,
    compose_review,
    specs_for_band,
    stable_int,
)


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
    'S21': {'name': '시드-완독10', 'grade': 6, 'label': '장기 독서 history 약 28권'},
    'S22': {'name': '시드-첫추천완독', 'grade': 3, 'label': '첫 추천 완독'},
}

EXPECTED = {
    'S1': {
        'include': ['READING_DAYS_RECENT_WINDOW_BEST'],
        'exclude': ['READING_ACTIVITY_DECREASE', 'READING_ACTIVITY_INCREASE'],
    },
    'S2': {'include': ['READING_ACTIVITY_DECREASE'], 'exclude': ['READING_ACTIVITY_INCREASE']},
    'S3': {'exclude': ['READING_ACTIVITY_INCREASE', 'READING_ACTIVITY_DECREASE', 'READING_DAYS_RECENT_WINDOW_BEST']},
    'S4': {
        'include': ['READING_COMPLETIONS_RECENT_WINDOW_BEST'],
        'exclude': ['READING_COMPLETIONS_INCREASE'],
    },
    'S5': {'include': ['PROGRESS_ENTRIES_INCREASE']},
    'S6': {'include': ['PROGRESS_ENTRIES_DECREASE']},
    'S7': {
        'include': ['POINTS_PERIOD_RECENT_WINDOW_BEST'],
        'exclude': ['POINTS_PERIOD_INCREASE'],
    },
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
            'READING_DAYS_RECENT_WINDOW_BEST',
            'READING_COMPLETIONS_RECENT_WINDOW_BEST',
            'POINTS_PERIOD_RECENT_WINDOW_BEST',
            'LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST',
        ],
    },
    'S17': {
        'include': [
            'READING_DAYS_RECENT_WINDOW_BEST',
            'READING_COMPLETIONS_RECENT_WINDOW_BEST',
            'PROGRESS_ENTRIES_INCREASE',
        ],
        'exclude': [
            'READING_ACTIVITY_INCREASE',
            'READING_COMPLETIONS_INCREASE',
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
            'READING_DAYS_RECENT_WINDOW_BEST',
            'READING_COMPLETIONS_RECENT_WINDOW_BEST',
            'POINTS_PERIOD_RECENT_WINDOW_BEST',
            'LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST',
        ],
    },
}


def scenario_names():
    return [item['name'] for item in SCENARIO_CATALOG.values()]


def _grade_band(grade):
    return '2-3' if int(grade or 0) <= 3 else '4-6'


def _coerce_program(grade, program):
    """1학년은 추천 eligibility를 만들지 않는다. 도전은 5~6만."""
    grade = int(grade or 0)
    program = program or PROGRAM_TYPE_GENERAL
    if grade <= 1:
        return PROGRAM_TYPE_GENERAL
    if program == PROGRAM_TYPE_CHALLENGE and grade < 5:
        return PROGRAM_TYPE_GENERAL
    return program


def _habit_program(child_key, grade, index):
    grade = int(grade or 0)
    share = CHILD_PROGRAM_SHARE.get(child_key, 20)
    if grade <= 1 or share <= 0:
        return PROGRAM_TYPE_GENERAL
    roll = stable_int(f'{child_key}:prog:{index}', 100)
    if roll >= share:
        return PROGRAM_TYPE_GENERAL
    if grade >= 5 and stable_int(f'{child_key}:ch:{index}', 10) < 3:
        return PROGRAM_TYPE_CHALLENGE
    return PROGRAM_TYPE_RECOMMENDED


def _project_local_sqlite_path():
    return (Path(__file__).resolve().parents[2] / 'instance' / 'child_center.db').resolve()


def _resolved_engine_sqlite_path():
    raw = getattr(getattr(db, 'engine', None), 'url', None)
    database = getattr(raw, 'database', None) if raw is not None else None
    if not database:
        return None
    return Path(database).resolve()


class GrowthSeedDenied(RuntimeError):
    """Web/CLI가 안전하게 거절할 때 쓰는 공개 메시지. DB URI를 담지 않는다."""

    def __init__(self, reason):
        self.reason = reason
        messages = {
            'production': 'Growth 테스트 데이터는 운영 환경에서 실행할 수 없습니다.',
            'postgres': 'Growth 테스트 데이터는 PostgreSQL에서 실행할 수 없습니다.',
            'not_sqlite': 'Growth 테스트 데이터는 로컬 개발 SQLite에서만 실행할 수 있습니다.',
            'not_local': 'Growth 테스트 데이터는 로컬 개발 SQLite에서만 실행할 수 있습니다.',
        }
        self.public_message = messages.get(reason, 'Growth 테스트 데이터를 실행할 수 없습니다.')
        super().__init__(self.public_message)


def _config_or_env_uri():
    if has_app_context():
        uri = current_app.config.get('SQLALCHEMY_DATABASE_URI') or ''
        if uri:
            return uri
    return os.environ.get('DATABASE_URL') or ''


def growth_seed_web_denial_reason():
    """Web Growth seed 거부 사유. None이면 이 Flask 엔진에서 실행 가능하다.

    허용:
    - production이 아니고
    - PostgreSQL이 아니고
    - SQLite이며
    - resolved engine path가 project/instance/child_center.db
      또는 CLC_TESTING=1 의 격리된 temp SQLite
    """
    flask_env = (os.environ.get('FLASK_ENV') or '').strip().lower()
    if flask_env == 'production':
        return 'production'
    uri = _config_or_env_uri().strip().lower()
    if uri.startswith('postgresql://') or uri.startswith('postgres://'):
        return 'postgres'
    if is_production_runtime():
        return 'production'
    path = _resolved_engine_sqlite_path() if has_app_context() else None
    if path is None:
        return 'not_sqlite'
    local = _project_local_sqlite_path()
    if path == local:
        return None
    testing = os.environ.get('CLC_TESTING') == '1'
    if testing and not (path.name == 'child_center.db' and path.parent.name == 'instance'):
        return None
    return 'not_local'


def growth_seed_web_available():
    return growth_seed_web_denial_reason() is None


def run_explicit_growth_seed(anchor_date=None, replace_existing=True):
    """개발자가 명시한 Web/UI 실행. helper guard는 약화하지 않는다.

    instance/child_center.db 는 기존처럼 CLC_ALLOW_GROWTH_SEED 가 필요하다.
    이 함수는 대상 검증 후에만 프로세스 동안 잠시 허용하고, 끝나면 되돌린다.
    """
    reason = growth_seed_web_denial_reason()
    if reason:
        raise GrowthSeedDenied(reason)
    previous = os.environ.get(ALLOW_ENV)
    os.environ[ALLOW_ENV] = '1'
    try:
        return seed_growth_scenarios(anchor_date=anchor_date, replace_existing=replace_existing)
    finally:
        if previous is None:
            os.environ.pop(ALLOW_ENV, None)
        else:
            os.environ[ALLOW_ENV] = previous


def assert_growth_seed_target_allowed(uri=None):
    """production / 승인 없는 로컬 운영 DB를 거부한다.

    config URI만 보지 않는다. Flask instance-relative sqlite:///child_center.db
    는 엔진이 instance/child_center.db 를 가리킬 수 있다.
    CLC_ALLOW_GROWTH_SEED=1 은 로컬 개발 DB에 대한 명시적 승인이지
    테스트 isolation 이 아니다.
    """
    if is_production_runtime():
        raise RuntimeError('Growth development seed는 production에서 실행할 수 없습니다.')
    if uri is None and has_app_context():
        uri = current_app.config.get('SQLALCHEMY_DATABASE_URI') or ''
    if uri is None:
        uri = os.environ.get('DATABASE_URL') or ''
    normalized = str(uri).replace('\\', '/')
    allowed = os.environ.get(ALLOW_ENV) == '1'
    if 'child_center.db' in normalized and not allowed:
        raise RuntimeError(
            'instance/child_center.db 에는 '
            f'{ALLOW_ENV}=1 없이 Growth seed를 실행하지 않습니다.'
        )
    if not allowed and has_app_context():
        engine_path = _resolved_engine_sqlite_path()
        local = _project_local_sqlite_path()
        if engine_path is not None and (
            engine_path == local
            or (engine_path.name == 'child_center.db' and engine_path.parent.name == 'instance')
        ):
            raise RuntimeError(
                'Growth seed 엔진이 local development DB를 가리킵니다. '
                f'{ALLOW_ENV}=1 없이 실행하지 않습니다: {engine_path}'
            )


def _slug(key):
    return hashlib.md5(f'growth-seed-{key}'.encode('utf-8')).hexdigest()[:24]


# gap after an included day: 0=다음날도 활동, 1~3=결석/주말 공백
_ACTIVITY_GAPS = {
    'dense': (0, 0, 1, 0, 0, 0, 1, 0, 2, 0, 0, 1, 0, 0),
    'mid': (0, 1, 0, 0, 2, 0, 1, 0, 0, 1, 0, 3, 0, 0),
    'airy': (1, 0, 2, 0, 1, 0, 3, 0, 1, 2, 0, 1, 0),
}

# CSV 참고: 국어 100/200, 수학 100/200, 쎈 0/100. random 금지. Child마다 다른 시퀀스.
_POINT_PATTERNS = {
    'KOR_HEAVY': {
        'korean': (200, 200, 200, 100, 200, 200, 100),
        'math': (100, 100, 200, 100, 100, 100, 200),
        'ssen': (100, 100, 0, 100, 100, 100, 0),
    },
    'MATH_HEAVY': {
        'korean': (100, 200, 100, 100, 200, 100, 100),
        'math': (200, 200, 100, 200, 200, 100, 200),
        'ssen': (100, 0, 100, 100, 0, 100, 100),
    },
    'SSEN_HIGH': {
        'korean': (200, 100, 200, 100, 200, 100, 200),
        'math': (100, 200, 100, 200, 100, 100, 200),
        'ssen': (100, 100, 100, 100, 100, 100, 0),
    },
    'SSEN_LOW': {
        'korean': (200, 100, 200, 100, 100, 200, 100),
        'math': (100, 100, 200, 100, 200, 100, 100),
        'ssen': (100, 0, 0, 0, 100, 0, 0),
    },
    'BALANCED': {
        'korean': (100, 200, 100, 200, 100, 200, 100),
        'math': (200, 100, 200, 100, 200, 100, 200),
        'ssen': (100, 100, 0, 100, 100, 0, 100),
    },
    'MILD': {
        'korean': (100, 100, 200, 100, 100, 100, 100),
        'math': (100, 100, 100, 200, 100, 100, 100),
        'ssen': (100, 0, 100, 0, 100, 0, 100),
    },
    'HOT': {
        'korean': (200, 200, 200, 200, 100, 200, 200),
        'math': (200, 100, 200, 200, 100, 200, 200),
        'ssen': (100, 100, 100, 100, 100, 100, 0),
    },
    'LOW': {
        'korean': (100, 100, 0, 100, 100, 0, 100),
        'math': (100, 0, 100, 100, 0, 100, 0),
        'ssen': (0, 100, 0, 0, 100, 0, 0),
    },
    'A': None, 'B': None, 'C': None,
}
_POINT_PATTERNS['A'] = _POINT_PATTERNS['KOR_HEAVY']
_POINT_PATTERNS['B'] = _POINT_PATTERNS['MATH_HEAVY']
_POINT_PATTERNS['C'] = _POINT_PATTERNS['SSEN_LOW']

DURATION_GENERAL = (2, 3, 4, 3, 2, 3, 5, 3, 4, 2, 3)
DURATION_REC = (3, 4, 5, 2, 4, 3, 5, 4)
DURATION_REC_THICK = (4, 6, 5, 8, 4, 7, 5)
DURATION_CHALLENGE = (6, 8, 5, 10, 7, 12, 5)

# manuals: (kind, points) placed on an activity date
CHILD_PROFILES = {
    'S1': {'voice': 'VOICE_A', 'pattern': 'KOR_HEAVY', 'hist': 70, 'prev': 20, 'cur': 20, 'gap': 'dense', 'back': 150,
           'hist_n': 7, 'english': False, 'piano': False, 'manuals': ()},
    'S2': {'voice': 'VOICE_B', 'pattern': 'MATH_HEAVY', 'hist': 35, 'prev': 18, 'cur': 16, 'gap': 'mid', 'back': 120,
           'hist_n': 3, 'english': False, 'piano': True, 'manuals': (('학용품 구입', -300, 'hist'),)},
    'S3': {'voice': 'VOICE_TERSE', 'pattern': 'BALANCED', 'hist': 30, 'prev': 16, 'cur': 16, 'gap': 'dense', 'back': 110,
           'hist_n': 2, 'english': False, 'piano': False, 'manuals': ()},
    'S4': {'voice': 'VOICE_C', 'pattern': 'MATH_HEAVY', 'hist': 22, 'prev': 16, 'cur': 16, 'gap': 'mid', 'back': 100,
           'hist_n': 5, 'english': True, 'piano': False, 'manuals': ()},
    'S5': {'voice': 'VOICE_A', 'pattern': 'KOR_HEAVY', 'hist': 50, 'prev': 18, 'cur': 18, 'gap': 'dense', 'back': 140,
           'hist_n': 5, 'english': False, 'piano': False, 'manuals': (('선생님 도움', 300, 'cur'),)},
    'S6': {'voice': 'VOICE_TERSE', 'pattern': 'SSEN_LOW', 'hist': 38, 'prev': 17, 'cur': 16, 'gap': 'airy', 'back': 120,
           'hist_n': 2, 'english': False, 'piano': True, 'manuals': ()},
    'S7': {'voice': 'VOICE_D', 'pattern': 'MILD', 'hist': 18, 'prev': 12, 'cur': 22, 'gap': 'mid', 'back': 90,
           'hist_n': 3, 'english': True, 'piano': False, 'manuals': (('선생님 도움', 300, 'cur'),), 'cur_pattern': 'HOT'},
    'S8': {'voice': 'VOICE_TERSE', 'pattern': 'MATH_HEAVY', 'hist': 14, 'prev': 0, 'cur': 14, 'gap': 'dense', 'back': 80,
           'hist_n': 2, 'english': False, 'piano': False, 'manuals': ()},
    'S9': {'voice': 'VOICE_D', 'pattern': 'SSEN_HIGH', 'hist': 24, 'prev': 16, 'cur': 16, 'gap': 'dense', 'back': 100,
           'hist_n': 6, 'english': False, 'piano': True, 'manuals': ()},
    'S10': {'voice': 'VOICE_E', 'pattern': 'SSEN_LOW', 'hist': 12, 'prev': 12, 'cur': 12, 'gap': 'mid', 'back': 80,
           'hist_n': 2, 'english': False, 'piano': False, 'manuals': (('학용품 구입', -500, 'hist'),)},
    'S11': {'voice': 'VOICE_C', 'pattern': 'SSEN_LOW', 'hist': 16, 'prev': 14, 'cur': 14, 'gap': 'airy', 'back': 90,
           'hist_n': 2, 'english': False, 'piano': False, 'manuals': ()},
    'S12': {'voice': 'VOICE_VERBOSE', 'pattern': 'KOR_HEAVY', 'hist': 32, 'prev': 16, 'cur': 16, 'gap': 'dense', 'back': 110,
            'hist_n': 4, 'english': False, 'piano': False, 'manuals': (('정리 도움', 300, 'hist'),)},
    'S13': {'voice': 'VOICE_RARE', 'pattern': 'LOW', 'hist': 0, 'prev': 0, 'cur': 2, 'gap': 'airy', 'back': 20,
            'hist_n': 0, 'english': False, 'piano': False, 'manuals': ()},
    'S14': {'voice': 'VOICE_D', 'pattern': 'MATH_HEAVY', 'hist': 28, 'prev': 16, 'cur': 18, 'gap': 'mid', 'back': 110,
            'hist_n': 6, 'english': True, 'piano': False, 'manuals': (('영어교재완료', 1000, 'hist'),)},
    'S15': {'voice': 'VOICE_TERSE', 'pattern': 'KOR_HEAVY', 'hist': 0, 'prev': 0, 'cur': 10, 'gap': 'dense', 'back': 20,
            'hist_n': 0, 'english': False, 'piano': False, 'manuals': ()},
    'S16': {'voice': 'VOICE_E', 'pattern': 'MILD', 'hist': 22, 'prev': 14, 'cur': 14, 'gap': 'dense', 'back': 90,
            'hist_n': 12, 'english': True, 'piano': True, 'manuals': (('쎈교재완료', 3000, 'hist'),)},
    'S17': {'voice': 'VOICE_B', 'pattern': 'MATH_HEAVY', 'hist': 36, 'prev': 16, 'cur': 18, 'gap': 'mid', 'back': 120,
            'hist_n': 5, 'english': False, 'piano': False, 'manuals': ()},
    'S18': {'voice': 'VOICE_TERSE', 'pattern': 'BALANCED', 'hist': 20, 'prev': 14, 'cur': 14, 'gap': 'dense', 'back': 90,
            'hist_n': 4, 'english': False, 'piano': False, 'manuals': ()},
    'S19': {'voice': 'VOICE_C', 'pattern': 'SSEN_LOW', 'hist': 18, 'prev': 12, 'cur': 12, 'gap': 'airy', 'back': 80,
            'hist_n': 3, 'english': False, 'piano': False, 'manuals': (('문구류 구입', -300, 'cur'),)},
    'S20': {'voice': 'VOICE_RARE', 'pattern': 'LOW', 'hist': 0, 'prev': 4, 'cur': 4, 'gap': 'airy', 'back': 30,
            'hist_n': 0, 'english': False, 'piano': False, 'manuals': ()},
    'S21': {'voice': 'VOICE_VERBOSE', 'pattern': 'MILD', 'hist': 70, 'prev': 16, 'cur': 16, 'gap': 'mid', 'back': 160,
            'hist_n': 20, 'english': True, 'piano': False, 'manuals': (('국어교재완료', 2000, 'hist'),)},
    'S22': {'voice': 'VOICE_B', 'pattern': 'KOR_HEAVY', 'hist': 0, 'prev': 0, 'cur': 10, 'gap': 'dense', 'back': 20,
            'hist_n': 0, 'english': False, 'piano': False, 'manuals': ()},
}

# Child-level 추천/도전 참여 습관 (%). 아동마다 다르고, 1학년은 0.
# 전체 aggregate가 약 25~35%가 되도록 맞춘다. 아동별 정확히 30%가 아니다.
CHILD_PROGRAM_SHARE = {
    'S1': 24, 'S2': 32, 'S3': 0, 'S4': 42, 'S5': 26, 'S6': 14,
    'S7': 28, 'S8': 6, 'S9': 38, 'S10': 18, 'S11': 32, 'S12': 16,
    'S13': 0, 'S14': 44, 'S15': 0, 'S16': 50, 'S17': 28, 'S18': 8,
    'S19': 22, 'S20': 0, 'S21': 22, 'S22': 100,
}
# 5~6학년 면제권 사용 계획. 발급 자체는 production service가 자격/쿨다운을 판정한다.
EXEMPTION_PLANS = {
    'S7': {'use': 1, 'hold': False, 'expire': False},
    'S9': {'use': 2, 'hold': False, 'expire': False},
    'S10': {'use': 0, 'hold': True, 'expire': True},
    'S14': {'use': 1, 'hold': True, 'expire': False},
    'S16': {'use': 2, 'hold': False, 'expire': True},
    'S21': {'use': 2, 'hold': True, 'expire': False},
}

# 진도 snapshot: 매일 입력이 아니라 주 1~2회. page는 학습일 누적.
# 포인트 하반기 2026-07-01~, 학습 2학기 2026-09-01~. canonical test anchor 2026-12-15.
CANONICAL_ANCHOR = date(2026, 12, 15)
HALF_YEAR_START = date(2026, 7, 1)
TERM2_START = date(2026, 9, 1)
STUDY_PACE = {'korean': 1, 'math': 2, 'ssen': 2}
ZERO_PROGRESS = frozenset({'S13', 'S20'})
ATTENDANCE_PROFILES = {
    'S1': 'VERY_STEADY', 'S2': 'NORMAL', 'S3': 'NORMAL', 'S4': 'STEADY',
    'S5': 'STEADY', 'S6': 'NORMAL', 'S7': 'STEADY', 'S8': 'IRREGULAR',
    'S9': 'VERY_STEADY', 'S10': 'IRREGULAR', 'S11': 'NORMAL', 'S12': 'VERY_STEADY',
    'S13': 'SPARSE', 'S14': 'STEADY', 'S15': 'SPARSE', 'S16': 'STEADY',
    'S17': 'STEADY', 'S18': 'NORMAL', 'S19': 'IRREGULAR', 'S20': 'SPARSE',
    'S21': 'VERY_STEADY', 'S22': 'SPARSE',
}
STUDY_PROFILES = {
    'S1': 'STEADY', 'S2': 'NORMAL', 'S3': 'NORMAL', 'S4': 'NORMAL',
    'S5': 'STEADY', 'S6': 'NORMAL', 'S7': 'FOCUSED', 'S8': 'IRREGULAR',
    'S9': 'STEADY', 'S10': 'IRREGULAR', 'S11': 'NORMAL', 'S12': 'STEADY',
    'S13': 'SPARSE', 'S14': 'NORMAL', 'S15': 'SPARSE', 'S16': 'FOCUSED',
    'S17': 'NORMAL', 'S18': 'NORMAL', 'S19': 'IRREGULAR', 'S20': 'SPARSE',
    'S21': 'STEADY', 'S22': 'SPARSE',
}
STUDY_OUTLIERS = frozenset({'S7', 'S8', 'S10'})
# 2학기 최신 page. STEADY/NORMAL 같은 학년은 약 10p, outlier만 20~30p 뒤.
TERM2_TARGETS = {
    'S1': {'korean': 78, 'math': 132, 'ssen': 124},
    'S2': {'korean': 76, 'math': 128, 'ssen': 122},
    'S3': {'korean': 70, 'math': 122, 'ssen': 116},
    'S4': {'korean': 79, 'math': 132, 'ssen': 124},
    'S5': {'korean': 74, 'math': 126, 'ssen': 120},
    'S6': {'korean': 73, 'math': 124, 'ssen': 118},
    'S7': {'korean': 58, 'math': 104, 'ssen': 88},
    'S8': {'korean': 52, 'math': 104, 'ssen': 98},
    'S9': {'korean': 75, 'math': 132, 'ssen': 124},
    'S10': {'korean': 50, 'math': 102, 'ssen': 96},
    'S11': {'korean': 75, 'math': 128, 'ssen': 120},
    'S12': {'korean': 80, 'math': 134, 'ssen': 126},
    'S13': {'korean': 12, 'math': 20, 'ssen': 18},
    'S14': {'korean': 72, 'math': 126, 'ssen': 120},
    'S15': {'korean': 28, 'math': 56, 'ssen': 52},
    'S16': {'korean': 62, 'math': 126, 'ssen': 100},
    'S17': {'korean': 77, 'math': 130, 'ssen': 123},
    'S18': {'korean': 70, 'math': 122, 'ssen': 116},
    'S19': {'korean': 64, 'math': 118, 'ssen': 110},
    'S20': {'korean': 10, 'math': 16, 'ssen': 14},
    'S21': {'korean': 77, 'math': 130, 'ssen': 122},
    'S22': {'korean': 32, 'math': 64, 'ssen': 58},
}
_MONTH_DAY_RANGES = {
    'VERY_STEADY': (18, 22),
    'STEADY': (15, 20),
    'NORMAL': (11, 17),
    'IRREGULAR': (5, 10),
    'SPARSE': (1, 4),
}
_SNAPSHOT_GAPS = {
    'STEADY': (5, 6, 7, 5, 8, 6, 4, 7, 11, 6, 5, 8),
    'NORMAL': (6, 8, 7, 5, 9, 12, 7, 6, 8, 13),
    'IRREGULAR': (9, 14, 18, 8, 16, 21, 11, 15),
    'SPARSE': (22, 30, 28),
    'FOCUSED': (5, 7, 6, 10, 8, 13, 6, 9),
}
_SNAPSHOT_CAPS = {
    'STEADY': 22,
    'NORMAL': 16,
    'IRREGULAR': 8,
    'SPARSE': 3,
    'FOCUSED': 18,
}
_SNAPSHOT_LAGS = {
    'STEADY': (0, 1, 2, 3, 0, 1),
    'NORMAL': (1, 2, 4, 6, 3),
    'IRREGULAR': (7, 9, 12, 14, 8),
    'SPARSE': (10, 15, 18),
    'FOCUSED': (1, 3, 5, 0),
}
# 창 안 progress_entry_count contract. 숫자는 과목 row 합.
_WINDOW_PROGRESS = {
    'S3': {'prev': (2, 2), 'cur': (2, 2)},
    'S5': {'prev': (3,), 'cur': (3, 2, 2)},
    'S6': {'prev': (3, 2, 2), 'cur': (3,)},
    'S17': {'prev': (3,), 'cur': (3, 2, 2)},
    'S18': {'prev': (2, 2), 'cur': (2, 2)},
}


def _irregular_dates(window, count, gap_key):
    """출석처럼 불규칙한 활동일. 첫날은 window.start (coverage comparable)."""
    if count <= 0:
        return []
    gaps = _ACTIVITY_GAPS[gap_key]
    start, end = window['start'], window['end']
    dates = [start]
    cursor = start + timedelta(days=1 + gaps[0])
    gi = 1
    while cursor <= end and len(dates) < count:
        if cursor.weekday() == 6:
            cursor += timedelta(days=1)
            continue
        dates.append(cursor)
        cursor += timedelta(days=1 + gaps[gi % len(gaps)])
        gi += 1
    filler = start + timedelta(days=1)
    while len(dates) < count and filler <= end:
        if filler not in dates and filler.weekday() < 5:
            dates.append(filler)
        filler += timedelta(days=1)
    return sorted(dates)[:count]


def _extended_dates(end, days_back, count, gap_key):
    start = end - timedelta(days=days_back)
    return _irregular_dates({'start': start, 'end': end}, count, gap_key)


def _weekdays(start, end):
    dates = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def _is_event_day(key, on):
    if key == 'S18':
        return False
    return stable_int(f'{key}:evt:{on.isoformat()}', 14) == 0


def _choose_days(days, count, key, month_key):
    days = list(days)
    if count <= 0:
        return []
    if count >= len(days):
        return days
    remaining = list(days)
    for index in range(len(days) - count):
        remaining.pop(stable_int(f'{key}:{month_key}:drop:{index}', len(remaining)))
    return remaining


def _attendance_days(key, start, end, current=None):
    """평일 출석 흔적. snapshot이 아니라 DailyPoints 활동일."""
    profile = ATTENDANCE_PROFILES[key]
    lo, hi = _MONTH_DAY_RANGES[profile]
    grade = SCENARIO_CATALOG[key]['grade']
    selected = []
    by_month = {}
    for on in _weekdays(start, end):
        by_month.setdefault((on.year, on.month), []).append(on)
    for (year, month), days in by_month.items():
        target_full = lo + stable_int(f'{key}:{year}-{month}', hi - lo + 1)
        if grade <= 2:
            target_full += 4
        elif grade == 3:
            target_full += 2
        elif grade == 5:
            target_full = max(1, target_full - 2)
        elif grade >= 6:
            if key in ('S16', 'S21'):
                cut = 1
            else:
                cut = 5
            target_full = max(1, target_full - cut)
        rate = min(1.0, target_full / 22)
        scaled = max(1, int(round(len(days) * rate)))
        scaled = min(len(days), scaled)
        selected.extend(_choose_days(days, scaled, key, f'{year}-{month}'))
    dates = sorted(set(selected))
    if key == 'S7' and current is not None:
        have = set(dates)
        current_n = sum(1 for on in dates if current['start'] <= on <= current['end'])
        for on in _weekdays(current['start'], current['end']):
            if current_n >= 20:
                break
            if on not in have:
                dates.append(on)
                have.add(on)
                current_n += 1
        dates = sorted(dates)
    return dates


def _reading_point_for(on, *, has_reading, is_complete_day, salt):
    if not has_reading:
        return 0
    allowed = allowed_reading_points(on)
    if is_complete_day and 200 in allowed and salt % 7 == 0:
        return 200
    if 100 in allowed:
        return 100
    return 0


def _cycle(seq, index):
    return seq[index % len(seq)]


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


def _ensure_book(title, *, author=None, recommended=False, challenge=False, grade_band=None):
    key = normalize_book_title(title)
    book = Book.query.filter_by(normalized_key=key, grade_band=grade_band).first()
    if book is None:
        book = Book(
            title=title,
            author=author,
            normalized_key=key,
            is_active=True,
            is_recommended=recommended,
            is_challenge_eligible=challenge,
            grade_band=grade_band,
        )
        db.session.add(book)
        db.session.flush()
        return book
    book.title = title
    if author:
        book.author = author
    book.is_recommended = recommended
    book.is_challenge_eligible = challenge
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
    reward_mode = None
    if int(child.grade or 0) in (5, 6) and program in (
        PROGRAM_TYPE_RECOMMENDED, PROGRAM_TYPE_CHALLENGE,
    ):
        reward_mode = REWARD_MODE_EXEMPTION
    row = ChildReading(
        child_id=child.id,
        book_id=book.id,
        started_on=started_on,
        completed_on=completed_on,
        ended_on=ended_on,
        status=status,
        program_type=program,
        policy_version=policy,
        reward_mode=reward_mode,
        difficulty_rating=difficulty,
        fun_rating=fun,
        created_by_user_id=actor_id,
        actor_type=ACTOR_TEACHER,
    )
    db.session.add(row)
    db.session.flush()
    return row


def _days(reading, dates, actor_id, *, child=None, book=None, voice_key='VOICE_C',
          child_key='S1', allow_reviews=True):
    title = book.title if book is not None else ''
    challenge = bool(book and book.is_challenge_eligible)
    total = len(dates)
    for index, on in enumerate(dates):
        text = None
        if allow_reviews:
            text = compose_review(
                voice_key, title, challenge=challenge,
                index=index, total=total, child_key=child_key,
            )
        db.session.add(ReadingDay(
            child_reading_id=reading.id,
            date=on,
            created_by_user_id=actor_id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
            review_text=text,
        ))


def _points(
    child,
    on,
    actor_id,
    *,
    korean=0,
    math=0,
    ssen=0,
    reading=0,
    piano=0,
    english=0,
    advanced_math=0,
    writing=0,
    manual_entries=None,
):
    from app import DailyPoints, PointsHistory
    entries = list(manual_entries or [])
    manual = sum(int(item.get('points') or 0) for item in entries)
    total = korean + math + ssen + reading + piano + english + advanced_math + writing + manual
    db.session.add(DailyPoints(
        child_id=child.id,
        date=on,
        korean_points=korean,
        math_points=math,
        ssen_points=ssen,
        reading_points=reading,
        piano_points=piano,
        english_points=english,
        advanced_math_points=advanced_math,
        writing_points=writing,
        manual_points=manual,
        manual_history=json.dumps(entries, ensure_ascii=False) if entries else '[]',
        total_points=total,
        created_by=actor_id,
    ))
    db.session.add(PointsHistory(
        child_id=child.id,
        date=on,
        old_korean_points=0,
        old_math_points=0,
        old_ssen_points=0,
        old_reading_points=0,
        old_piano_points=0,
        old_english_points=0,
        old_advanced_math_points=0,
        old_writing_points=0,
        old_total_points=0,
        new_korean_points=korean,
        new_math_points=math,
        new_ssen_points=ssen,
        new_reading_points=reading,
        new_piano_points=piano,
        new_english_points=english,
        new_advanced_math_points=advanced_math,
        new_writing_points=writing,
        new_total_points=total,
        change_type='create',
        changed_by=actor_id,
        # seed-only: activity date 14:30 so /points/history 30-day window can show
        # current-window rows. Production create path uses datetime.utcnow() at save.
        changed_at=datetime(on.year, on.month, on.day, 14, 30, 0),
        change_reason='시드 데이터 신규 입력',
    ))
    return total


def _progress(child, subject, on, actor_id, *, title, page):
    entry = LearningProgressEntry(
        child_id=child.id,
        learning_subject_id=subject.id,
        recorded_on=on,
        textbook_title=title,
        page=max(1, int(page)),
        created_by_user_id=actor_id,
    )
    db.session.add(entry)
    return entry


def _textbook_title(grade, subject_key, on):
    if on < TERM2_START:
        raise RuntimeError(f'2학기 ProgressEntry는 {TERM2_START} 이후만 허용합니다: {on}')
    grade = max(1, int(grade or 1))
    if subject_key == 'korean':
        return f'우등생 국어 {grade}-2'
    if subject_key == 'math':
        return f'우등생 수학 {grade}-2'
    return f'쎈연산 {grade}-2'


def _study_advance(key, profile, on, index, subject):
    if profile == 'SPARSE' and index % 4 != 0:
        return 0
    if profile == 'IRREGULAR' and index % 3 == 2:
        return 0
    if _is_event_day(key, on):
        return 0
    if profile == 'FOCUSED' and index % 2 == 1:
        if key == 'S7' and subject == 'ssen':
            return 0
        if key == 'S16' and subject == 'korean':
            return 0
    pace = STUDY_PACE[subject]
    jitter = stable_int(f'{key}:pace:{on.isoformat()}:{subject}', 12)
    if subject == 'korean' and jitter == 0:
        return 2
    if subject in ('math', 'ssen') and jitter == 1:
        return 1
    if subject in ('math', 'ssen') and jitter == 2:
        return 3
    return pace


def _walk_snapshot_dates(activity, profile, child_key):
    """활동일 위에서 뒤로 걷는다. 요일 고정 없이 4~9일 간격이 많게."""
    activity = sorted(set(activity))
    if not activity:
        return []
    gaps = _SNAPSHOT_GAPS[profile]
    cap = _SNAPSHOT_CAPS[profile]
    lags = _SNAPSHOT_LAGS[profile]
    lag = lags[stable_int(child_key + ':lag', len(lags))]
    target_last = activity[-1] - timedelta(days=lag)
    last = next((on for on in reversed(activity) if on <= target_last), activity[0])
    dates = []
    cursor = last
    gi = 0
    while len(dates) < cap:
        snap = next((on for on in reversed(activity) if on <= cursor), None)
        if snap is None:
            break
        if snap not in dates:
            dates.append(snap)
        nxt = snap - timedelta(days=gaps[gi % len(gaps)])
        gi += 1
        if nxt >= snap:
            break
        cursor = nxt
        if cursor < activity[0]:
            if activity[0] not in dates and len(dates) < cap:
                dates.append(activity[0])
            break
    return sorted(dates)


def _pick_n_dates(activity, count):
    activity = sorted(set(activity))
    if not activity or count <= 0:
        return []
    if count >= len(activity):
        return list(activity)
    picked = []
    seen = set()
    span = len(activity) - 1
    for index in range(count):
        if count == 1:
            pos = min(span, max(0, len(activity) // 3))
        else:
            pos = int(round(index * span / (count - 1)))
        chosen = None
        for delta in range(len(activity)):
            for candidate in (pos + delta, pos - delta):
                if 0 <= candidate < len(activity) and activity[candidate] not in seen:
                    chosen = activity[candidate]
                    break
            if chosen is not None:
                break
        if chosen is not None:
            picked.append(chosen)
            seen.add(chosen)
    return sorted(picked)


def _subjects_for_count(count, subjects):
    order = ('korean', 'math', 'ssen')
    return [subjects[key] for key in order[:max(1, min(3, count))]]


def _subjects_for_snapshot(key, profile, on, subjects):
    skip = stable_int(f'{key}:subj:{on.isoformat()}', 6)
    names = ['korean', 'math', 'ssen']
    if skip == 0:
        names = ['korean', 'math']
    elif skip == 1 and profile != 'FOCUSED':
        names = ['math', 'ssen']
    return [subjects[name] for name in names]


def _seed_child_progress(key, child, activity, subjects, actor_id, previous, current):
    """주 1~2회 snapshot. 학습일은 DailyPoints 위에만 두고 DB에는 snapshot만 남긴다."""
    profile = STUDY_PROFILES[key]
    activity = sorted(on for on in set(activity) if on >= TERM2_START)
    if not activity or key in ZERO_PROGRESS:
        return
    hist = [on for on in activity if on < previous['start']]
    prev_d = [on for on in activity if previous['start'] <= on <= previous['end']]
    cur_d = [on for on in activity if current['start'] <= on <= current['end']]
    spec = _WINDOW_PROGRESS.get(key)
    subjects_by_date = {}
    if spec:
        snapshot = _walk_snapshot_dates(hist, profile, key)
        prev_pool = [on for on in prev_d if on <= previous['end'] - timedelta(days=2)] or prev_d
        cur_pool = [on for on in cur_d if on >= current['start'] + timedelta(days=2)] or cur_d
        prev_snaps = _pick_n_dates(prev_pool, len(spec['prev']))
        cur_snaps = _pick_n_dates(cur_pool, len(spec['cur']))
        if len(prev_snaps) != len(spec['prev']) or len(cur_snaps) != len(spec['cur']):
            raise RuntimeError(f'{key} progress window snapshots could not be placed')
        first_window = min(prev_snaps + cur_snaps)
        snapshot = [on for on in snapshot if (first_window - on).days >= 4]
        snapshot.extend(prev_snaps)
        snapshot.extend(cur_snaps)
        for on, count in zip(prev_snaps, spec['prev']):
            subjects_by_date[on] = _subjects_for_count(count, subjects)
        for on, count in zip(cur_snaps, spec['cur']):
            subjects_by_date[on] = _subjects_for_count(count, subjects)
    else:
        snapshot = _walk_snapshot_dates(activity, profile, key)
    snapshot = sorted({on for on in snapshot if on in set(activity) and on >= TERM2_START})
    if not snapshot:
        return
    reconfirm_on = None
    if profile == 'STEADY' and len(snapshot) >= 2:
        reconfirm_on = snapshot[1]
    targets = TERM2_TARGETS[key]
    start_pages = {}
    for subject_key in STUDY_PACE:
        total = 0
        for index, on in enumerate(activity):
            total += _study_advance(key, profile, on, index, subject_key)
        start_pages[subject_key] = max(1, targets[subject_key] - total)
    running = dict(start_pages)
    last_by_subject = {}
    snapshot_set = set(snapshot)
    for index, on in enumerate(activity):
        for subject_key in STUDY_PACE:
            running[subject_key] += _study_advance(key, profile, on, index, subject_key)
        if on in snapshot_set:
            chosen = subjects_by_date.get(on)
            if chosen is None:
                chosen = _subjects_for_snapshot(key, profile, on, subjects)
            for subject in chosen:
                page = min(running[subject.key], targets[subject.key])
                previous_entry = last_by_subject.get(subject.key)
                if (
                    reconfirm_on is not None
                    and on == reconfirm_on
                    and subject.key == 'korean'
                    and previous_entry is not None
                ):
                    page = previous_entry.page
                entry = _progress(
                    child, subject, on, actor_id,
                    title=_textbook_title(child.grade, subject.key, on),
                    page=page,
                )
                last_by_subject[subject.key] = entry
    for subject_key, target in targets.items():
        entry = last_by_subject.get(subject_key)
        if entry is not None and entry.page < target:
            entry.page = target


def _manual(on, subject, points, reason):
    return [{
        'id': 1,
        'subject': subject,
        'points': points,
        'reason': reason,
        'created_by': '시드교사',
        'created_at': f'{on.isoformat()} 14:30:00',
    }]


def _activity_subject_value(value, *, child, child_key, index, subject, pattern):
    """학년 평균 우하향은 수행률로 만든다. total/cumulative를 직접 쓰지 않는다."""
    if not value:
        return 0
    grade = int(child.grade or 0)
    salt = stable_int(f'{child_key}:{subject}:{index}', 100)
    if pattern == 'HOT':
        miss, reduce = 12, 24
    elif child_key == 'S16':
        miss, reduce = 36, 60
    elif grade <= 2:
        miss, reduce = 6, 12
    elif grade == 3:
        miss, reduce = 16, 28
    elif grade == 4:
        miss, reduce = 30, 50
    elif grade == 5:
        miss, reduce = 40, 68
    else:
        miss, reduce = 66, 92
    if salt < miss:
        return 0
    if salt < reduce:
        return min(value, 100)
    return value


def _fill_activity_points(
    child,
    dates,
    actor_id,
    *,
    pattern,
    reading_dates,
    complete_dates=None,
    manuals_by_date=None,
    english=False,
    piano=False,
    reading_points_override=None,
    child_key='S1',
):
    reading_set = set(reading_dates or ())
    complete_set = set(complete_dates or ())
    manuals_by_date = manuals_by_date or {}
    seq = _POINT_PATTERNS[pattern]
    eng_mod = 6 + (stable_int(child_key + ':eng') % 4)
    piano_mod = 7 + (stable_int(child_key + ':piano') % 3)
    for index, on in enumerate(dates):
        korean = _activity_subject_value(
            _cycle(seq['korean'], index),
            child=child, child_key=child_key, index=index, subject='korean', pattern=pattern,
        )
        math = _activity_subject_value(
            _cycle(seq['math'], index),
            child=child, child_key=child_key, index=index, subject='math', pattern=pattern,
        )
        ssen = _activity_subject_value(
            _cycle(seq['ssen'], index),
            child=child, child_key=child_key, index=index, subject='ssen', pattern=pattern,
        )
        if child.grade <= 2 and index % 5 == 4:
            ssen = 0
        if child.grade >= 6 and index % 3 == 2 and pattern not in ('HOT', 'SSEN_HIGH'):
            ssen = 0
        if _is_event_day(child_key, on):
            korean = 0
            math = 0
            ssen = 0
        reading = (
            reading_points_override
            if reading_points_override is not None and on in reading_set
            else _reading_point_for(
                on,
                has_reading=on in reading_set,
                is_complete_day=on in complete_set,
                salt=index + stable_int(child_key, 20),
            )
        )
        if (
            reading_points_override is None
            and reading
            and int(child.grade or 0) >= 5
            and on not in complete_set
            and (index + stable_int(child_key, 11)) % 3 == 0
        ):
            reading = 0
        english_pts = 100 if english and index % eng_mod == 0 and child.grade >= 4 else 0
        piano_pts = 100 if piano and index % piano_mod == 1 and child.grade >= 3 else 0
        _points(
            child, on, actor_id,
            korean=korean, math=math, ssen=ssen, reading=reading,
            english=english_pts, piano=piano_pts,
            manual_entries=manuals_by_date.get(on),
        )


def _next_spec(child_key, grade, program, used, index):
    program = _coerce_program(grade, program)
    band = _grade_band(grade)
    if program == PROGRAM_TYPE_CHALLENGE:
        pool = specs_for_band('4-6', recommended=False, challenge=True)
        kind = 'ch'
    elif program == PROGRAM_TYPE_RECOMMENDED:
        pool = specs_for_band(band, recommended=True, challenge=False)
        kind = 'rec'
    else:
        pool = specs_for_band(band, recommended=False, challenge=False)
        kind = 'gen'
    unused = [spec for spec in pool if spec['key'] not in used]
    if not unused:
        return None
    offset = stable_int(f'{child_key}:{kind}:off', len(unused))
    stride = 1 + stable_int(f'{child_key}:{kind}:str', max(1, len(unused) - 1))
    spec = unused[(offset + index * stride) % len(unused)]
    used.add(spec['key'])
    return spec


def _place_completed(
    child, dates, specs, actor_id, books, *, child_key, voice_key,
    allow_reviews=True, start_at=0, used=None,
):
    """dates에서 순차로 책을 배치. 동시에 여러 권을 겹치지 않는다."""
    cursor = start_at
    reading_dates = []
    complete_dates = []
    rows = []
    used = used if used is not None else set()
    for local_index, spec in enumerate(specs):
        duration = spec['duration']
        chunk = dates[cursor:cursor + duration]
        if len(chunk) < duration:
            break
        program = _coerce_program(child.grade, spec.get('program', PROGRAM_TYPE_GENERAL))
        book_spec = spec.get('book_spec') or _next_spec(
            child_key, child.grade, program, used, local_index + cursor,
        )
        if book_spec is None:
            break
        book = books[book_spec['key']]
        difficulty, fun = spec.get('ratings') or (None, None)
        started, completed = chunk[0], chunk[-1]
        row = _reading(
            child, book, started_on=started, completed_on=completed,
            status=STATUS_COMPLETED, actor_id=actor_id, program=program,
            difficulty=difficulty, fun=fun,
        )
        _days(
            row, chunk, actor_id,
            child=child, book=book, voice_key=voice_key,
            child_key=child_key, allow_reviews=allow_reviews,
        )
        reading_dates.extend(chunk)
        complete_dates.append(completed)
        rows.append(row)
        cursor += duration
    return rows, reading_dates, complete_dates, cursor, used


def _place_in_progress(
    child, dates, actor_id, books, *, child_key, voice_key, start_at=0,
    duration=3, allow_reviews=True, used=None, program=PROGRAM_TYPE_GENERAL,
):
    chunk = dates[start_at:start_at + duration]
    if not chunk:
        return None, [], start_at, used or set()
    used = used if used is not None else set()
    program = _coerce_program(child.grade, program)
    book_spec = _next_spec(child_key, child.grade, program, used, start_at + 50)
    if book_spec is None:
        return None, [], start_at, used
    book = books[book_spec['key']]
    row = _reading(
        child, book, started_on=chunk[0], status=STATUS_IN_PROGRESS,
        actor_id=actor_id, program=program,
    )
    _days(
        row, chunk, actor_id, child=child, book=book,
        voice_key=voice_key, child_key=child_key, allow_reviews=allow_reviews,
    )
    return row, list(chunk), start_at + len(chunk), used


def remove_growth_seed_children():
    """시드- catalog 이름 아동과 그 원장만 지운다. 다른 아동은 건드리지 않는다."""
    from app import Child, DailyPoints, LearningRecord, PointsHistory
    names = scenario_names()
    children = Child.query.filter(Child.name.in_(names)).all()
    ids = [child.id for child in children]
    if ids:
        ticket_ids = [
            row.id for row in ExemptionTicket.query.filter(ExemptionTicket.child_id.in_(ids)).all()
        ]
        if ticket_ids:
            ExemptionUsage.query.filter(
                ExemptionUsage.exemption_ticket_id.in_(ticket_ids),
            ).delete(synchronize_session=False)
            ExemptionTicketSource.query.filter(
                ExemptionTicketSource.exemption_ticket_id.in_(ticket_ids),
            ).delete(synchronize_session=False)
            ExemptionTicket.query.filter(ExemptionTicket.id.in_(ticket_ids)).delete(
                synchronize_session=False,
            )
        readings = ChildReading.query.filter(ChildReading.child_id.in_(ids)).all()
        reading_ids = [row.id for row in readings]
        if reading_ids:
            ReadingRewardEvent.query.filter(
                ReadingRewardEvent.child_reading_id.in_(reading_ids),
            ).delete(synchronize_session=False)
            ReadingDay.query.filter(ReadingDay.child_reading_id.in_(reading_ids)).delete(synchronize_session=False)
            ChildReading.query.filter(ChildReading.id.in_(reading_ids)).delete(synchronize_session=False)
        LearningProgressEntry.query.filter(LearningProgressEntry.child_id.in_(ids)).delete(synchronize_session=False)
        PointsHistory.query.filter(PointsHistory.child_id.in_(ids)).delete(synchronize_session=False)
        DailyPoints.query.filter(DailyPoints.child_id.in_(ids)).delete(synchronize_session=False)
        LearningRecord.query.filter(LearningRecord.child_id.in_(ids)).delete(synchronize_session=False)
        Child.query.filter(Child.id.in_(ids)).delete(synchronize_session=False)
    seed_book_titles = list(book_titles()) + list(OLD_PLACEHOLDER_TITLES)
    Book.query.filter(Book.title.in_(seed_book_titles)).delete(synchronize_session=False)
    db.session.commit()
    db.session.expunge_all()
    return len(ids) if ids else 0


def _sync_cumulative(children):
    from app import DailyPoints
    for child in children:
        total = db.session.query(db.func.coalesce(db.func.sum(DailyPoints.total_points), 0)).filter_by(
            child_id=child.id,
        ).scalar()
        child.cumulative_points = int(total or 0)


def _seed_exemptions(created, actor_id, as_of):
    """5~6 recommended/challenge 완독 자격을 production service로 ticket/usage 원장에 남긴다."""
    from app import User
    from features.exemption.service import (
        ExemptionError,
        expire_stale_tickets,
        issue_exemption_ticket,
        next_ready_entitlement_group,
        use_exemption_ticket,
    )

    user = User.query.get(actor_id)
    ssen_assigned = False
    for key in ('S7', 'S9', 'S10', 'S14', 'S16', 'S21'):
        child = created[key]
        plan = EXEMPTION_PLANS[key]
        used_count = 0
        dates = sorted({
            row.completed_on
            for row in ChildReading.query.filter_by(
                child_id=child.id,
                status=STATUS_COMPLETED,
            ).filter(
                ChildReading.program_type.in_((PROGRAM_TYPE_RECOMMENDED, PROGRAM_TYPE_CHALLENGE)),
                ChildReading.completed_on.isnot(None),
            ).all()
            if row.completed_on is not None
        })
        for issue_on in dates:
            group = next_ready_entitlement_group(child.id)
            if group is None or group.get('qualified_on') is None:
                continue
            if group['qualified_on'] > issue_on:
                continue
            try:
                ticket = issue_exemption_ticket(child.id, user, today=issue_on)
            except ExemptionError:
                continue
            valid_at_as_of = ticket.expires_on >= as_of
            if used_count < plan['use']:
                delay = (3, 6, 9, 4, 11, 2, 8)[stable_int(f'{key}:delay:{used_count}', 7)]
                used_on = issue_on + timedelta(days=int(delay))
                if used_on > ticket.expires_on:
                    used_on = ticket.expires_on
                if used_on < ticket.issued_on:
                    used_on = ticket.issued_on
                if (key == 'S16' and used_count == 0) or (
                    not ssen_assigned and key == 'S21' and used_count == 0
                ):
                    subject = 'ssen'
                    ssen_assigned = True
                else:
                    subject = 'math'
                try:
                    use_exemption_ticket(
                        ticket.id, subject, user, used_on=used_on, today=used_on,
                    )
                    used_count += 1
                except ExemptionError:
                    pass
            elif plan['hold'] and valid_at_as_of:
                break
            else:
                expire_stale_tickets(child.id, ticket.expires_on + timedelta(days=1))
                db.session.commit()
        held = ExemptionTicket.query.filter_by(child_id=child.id, status='active').first()
        if held is not None and held.expires_on < as_of:
            expire_stale_tickets(child.id, as_of)
            db.session.commit()


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
    missing = {'korean', 'math', 'ssen'} - set(subjects)
    if missing:
        raise RuntimeError(f'학습 과목이 없습니다: {sorted(missing)}')

    books = {}
    for spec in all_book_specs():
        books[spec['key']] = _ensure_book(
            spec['title'],
            author=spec['author'],
            recommended=spec['recommended'],
            challenge=spec['challenge'],
            grade_band=spec['grade_band'],
        )
    created = {}

    def horizon(key):
        profile = CHILD_PROFILES[key]
        if key == 'S13':
            weekdays = _weekdays(current['start'], current['end'])
            cur_d = [weekdays[min(2, len(weekdays) - 1)], weekdays[min(5, len(weekdays) - 1)]]
            cur_d = sorted(set(on for on in cur_d if on <= current['end']))
            return profile, [], [], cur_d
        all_d = _attendance_days(key, HALF_YEAR_START, anchor, current=current)
        if key == 'S8':
            all_d = [on for on in all_d if not (previous['start'] <= on <= previous['end'])]
        if key == 'S18':
            hist = [on for on in all_d if on < previous['start']]
            prev_d = _weekdays(previous['start'], previous['end'])[:14]
            cur_d = _weekdays(current['start'], current['end'])[:14]
            return profile, hist, prev_d, cur_d
            have = set(all_d)
            needed = 8 if key == 'S15' else 6
            current_n = sum(1 for on in all_d if current['start'] <= on <= current['end'])
            for on in _weekdays(current['start'], current['end']):
                if current_n >= needed:
                    break
                if on not in have:
                    all_d.append(on)
                    have.add(on)
                    current_n += 1
            all_d = sorted(set(all_d))
        hist = [on for on in all_d if on < previous['start']]
        prev_d = [on for on in all_d if previous['start'] <= on <= previous['end']]
        cur_d = [on for on in all_d if current['start'] <= on <= current['end']]
        return profile, hist, prev_d, cur_d

    def seed_points(key, child, dates, reading_dates, complete_dates, **kwargs):
        profile = CHILD_PROFILES[key]
        _fill_activity_points(
            child, dates, actor_id,
            pattern=kwargs.get('pattern', profile['pattern']),
            reading_dates=reading_dates,
            complete_dates=complete_dates,
            manuals_by_date=kwargs.get('manuals_by_date'),
            english=profile['english'],
            piano=profile['piano'],
            reading_points_override=kwargs.get('reading_points_override'),
            child_key=key,
        )

    def completed(key, child, dates, durations, *, ratings=None, programs=None,
                  allow_reviews=True, used=None, start_at=0):
        profile = CHILD_PROFILES[key]
        specs = []
        for index, duration in enumerate(durations):
            spec = {'duration': duration}
            if ratings and index < len(ratings):
                spec['ratings'] = ratings[index]
            if programs and index < len(programs):
                spec['program'] = _coerce_program(child.grade, programs[index])
            else:
                spec['program'] = _habit_program(key, child.grade, len(used or ()) + index)
            specs.append(spec)
        return _place_completed(
            child, dates, specs, actor_id, books,
            child_key=key, voice_key=profile['voice'],
            allow_reviews=allow_reviews, start_at=start_at, used=used,
        )

    def history_books(key, child, hist_d, n, used, programs=None):
        if n <= 0 or not hist_d:
            return [], [], used
        seq = DURATION_GENERAL
        if child.grade >= 5:
            seq = DURATION_GENERAL + DURATION_REC[:3]
        durations = [seq[(stable_int(key + ':hd') + i) % len(seq)] for i in range(n)]
        _, r, c, _, used = completed(key, child, hist_d, tuple(durations), programs=programs, used=used)
        return r, c, used

    def manuals_for(key, hist_d, prev_d, cur_d):
        out = {}
        for subject, points, where in CHILD_PROFILES[key]['manuals']:
            pool = {'hist': hist_d, 'prev': prev_d, 'cur': cur_d}[where]
            if not pool:
                continue
            idx = min(len(pool) - 1, 4 if points < 0 else max(0, len(pool) // 2))
            on = pool[idx]
            out[on] = _manual(on, subject, points, subject)
        return out

    def points_split(key, child, hist_d, prev_d, cur_d, reading, complete, manuals, **kwargs):
        rset, cset = set(reading), set(complete)
        cur_pattern = kwargs.pop('cur_pattern', None) or CHILD_PROFILES[key].get('cur_pattern')
        if hist_d:
            seed_points(
                key, child, hist_d,
                [d for d in hist_d if d in rset], [d for d in hist_d if d in cset],
                manuals_by_date={d: manuals[d] for d in hist_d if d in manuals},
                **kwargs,
            )
        if prev_d:
            seed_points(
                key, child, prev_d,
                [d for d in prev_d if d in rset], [d for d in prev_d if d in cset],
                manuals_by_date={d: manuals[d] for d in prev_d if d in manuals},
                **kwargs,
            )
        if cur_d:
            extra = dict(kwargs)
            if cur_pattern:
                extra['pattern'] = cur_pattern
            seed_points(
                key, child, cur_d,
                [d for d in cur_d if d in rset], [d for d in cur_d if d in cset],
                manuals_by_date={d: manuals[d] for d in cur_d if d in manuals},
                **extra,
            )

    # S1 reading 8 -> 14, history + many activity days
    child = _child('S1', created)
    _, hist_d, prev_d, cur_d = horizon('S1')
    used = set()
    rh, ch, used = history_books('S1', child, hist_d, 7, used)
    _, r1, c1, _, used = completed('S1', child, prev_d, (3, 3, 2), used=used)
    _, r2, c2, _, used = completed('S1', child, cur_d, (3, 3, 4, 4), used=used)
    points_split('S1', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S1', hist_d, prev_d, cur_d))

    # S2 reading 14 -> 8
    child = _child('S2', created)
    _, hist_d, prev_d, cur_d = horizon('S2')
    used = set()
    rh, ch, used = history_books('S2', child, hist_d, 3, used)
    _, r1, c1, _, used = completed('S2', child, prev_d, (3, 4, 3, 4), used=used)
    _, r2, c2, _, used = completed('S2', child, cur_d, (3, 3, 2), used=used)
    points_split('S2', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S2', hist_d, prev_d, cur_d))

    # S3 reading 10 -> 10, progress 4 -> 4
    child = _child('S3', created)
    _, hist_d, prev_d, cur_d = horizon('S3')
    used = set()
    rh, ch, used = history_books('S3', child, hist_d, 2, used)
    _, r1, c1, _, used = completed('S3', child, prev_d, (3, 3, 4), used=used)
    _, r2, c2, _, used = completed('S3', child, cur_d, (3, 4, 3), used=used)
    points_split('S3', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S3', hist_d, prev_d, cur_d))

    # S4 completions 2 -> 4, reading days similar
    child = _child('S4', created)
    _, hist_d, prev_d, cur_d = horizon('S4')
    used = set()
    rh, ch, used = history_books('S4', child, hist_d, 5, used)
    _, r1, c1, _, used = completed('S4', child, prev_d, (5, 5), used=used)
    _, r2, c2, _, used = completed('S4', child, cur_d, (2, 3, 2, 3), used=used)
    points_split('S4', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S4', hist_d, prev_d, cur_d))

    # S5 progress 3 -> 7
    child = _child('S5', created)
    _, hist_d, prev_d, cur_d = horizon('S5')
    used = set()
    rh, ch, used = history_books('S5', child, hist_d, 5, used)
    _, r1, c1, _, used = completed('S5', child, prev_d, (3, 3, 4), used=used)
    _, r2, c2, _, used = completed('S5', child, cur_d, (3, 3, 4), used=used)
    points_split('S5', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S5', hist_d, prev_d, cur_d))

    # S6 progress 7 -> 3
    child = _child('S6', created)
    _, hist_d, prev_d, cur_d = horizon('S6')
    used = set()
    rh, ch, used = history_books('S6', child, hist_d, 2, used)
    _, r1, c1, _, used = completed('S6', child, prev_d, (3, 3, 4), used=used)
    _, r2, c2, _, used = completed('S6', child, cur_d, (4, 3, 3), used=used)
    points_split('S6', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S6', hist_d, prev_d, cur_d))

    # S7 points increase
    child = _child('S7', created)
    _, hist_d, prev_d, cur_d = horizon('S7')
    used = set()
    rh, ch, used = history_books('S7', child, hist_d, 3, used)
    _, r1, c1, _, used = completed('S7', child, prev_d, (3, 3), used=used)
    _, r2, c2, _, used = completed('S7', child, cur_d, (3, 4), used=used)
    points_split(
        'S7', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2,
        manuals_for('S7', hist_d, prev_d, cur_d),
    )

    # S8 previous window 0
    child = _child('S8', created)
    _, hist_d, prev_d, cur_d = horizon('S8')
    used = set()
    rh, ch, used = history_books('S8', child, hist_d, 2, used)
    _, r2, c2, _, used = completed('S8', child, cur_d, (3, 3), used=used)
    points_split('S8', child, hist_d, [], cur_d, rh + r2, ch + c2, manuals_for('S8', hist_d, [], cur_d))

    # S9 paired positive 3+3, extra unrated history
    child = _child('S9', created)
    _, hist_d, prev_d, cur_d = horizon('S9')
    used = set()
    _, rh_pair, ch_pair, cursor, used = completed(
        'S9', child, hist_d, (3, 4, 3), ratings=[(3, 4), (2, 5), (3, 4)], used=used,
    )
    rh_rest, ch_rest, used = history_books('S9', child, hist_d[cursor:], 3, used)
    rh, ch = rh_pair + rh_rest, ch_pair + ch_rest
    _, r1, c1, _, used = completed(
        'S9', child, prev_d, (1, 4, 3), ratings=[(2, 4), (3, 4), (3, 5)], used=used,
    )
    _, r2, c2, _, used = completed(
        'S9', child, cur_d, (3, 3, 4), ratings=[(4, 4), (4, 4), (3, 5)], used=used,
    )
    points_split('S9', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S9', hist_d, prev_d, cur_d))

    # S10 paired fun drop
    child = _child('S10', created)
    _, hist_d, prev_d, cur_d = horizon('S10')
    used = set()
    rh, ch, used = history_books('S10', child, hist_d, 2, used)
    _, r1, c1, _, used = completed(
        'S10', child, prev_d, (3, 4, 3), ratings=[(2, 5), (3, 5), (3, 4)], used=used,
    )
    _, r2, c2, _, used = completed(
        'S10', child, cur_d, (3, 3, 4), ratings=[(4, 2), (4, 2), (4, 3)], used=used,
    )
    points_split('S10', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S10', hist_d, prev_d, cur_d))

    # S11 paired n=2
    child = _child('S11', created)
    _, hist_d, prev_d, cur_d = horizon('S11')
    used = set()
    rh, ch, used = history_books('S11', child, hist_d, 2, used)
    _, r1, c1, _, used = completed('S11', child, prev_d, (3, 4), ratings=[(3, 4), (2, 5)], used=used)
    _, r2, c2, _, used = completed('S11', child, cur_d, (3, 4), ratings=[(4, 4), (5, 3)], used=used)
    points_split('S11', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S11', hist_d, prev_d, cur_d))

    # S12 unpaired only
    child = _child('S12', created)
    _, hist_d, prev_d, cur_d = horizon('S12')
    used = set()
    rh, ch, used = history_books('S12', child, hist_d, 4, used)
    _, r1, c1, _, used = completed(
        'S12', child, prev_d, (3, 3, 3), ratings=[(3, None), (4, None), (2, None)], used=used,
    )
    _, r2, c2, _, used = completed(
        'S12', child, cur_d, (3, 4, 3), ratings=[(None, 5), (None, 4), (None, 4)], used=used,
    )
    points_split('S12', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S12', hist_d, prev_d, cur_d))

    # S13 sparse recent-only
    child = _child('S13', created)
    profile, _, _, sparse = horizon('S13')
    used = set()
    _, r1, c1, _, used = completed(
        'S13', child, sparse[:1], (1,), allow_reviews=False, used=used,
    )
    _, r2, _, used = _place_in_progress(
        child, sparse, actor_id, books, child_key='S13', voice_key=profile['voice'],
        start_at=1, duration=1, allow_reviews=False, used=used,
    )
    seed_points('S13', child, sparse, r1 + r2, c1)

    # S14 general/recommended/challenge + abandoned
    child = _child('S14', created)
    _, hist_d, prev_d, cur_d = horizon('S14')
    used = set()
    rh, ch, used = history_books('S14', child, hist_d, 6, used)
    _, r1, c1, _, used = completed('S14', child, prev_d, (3, 4), used=used)
    _, r2, c2, cursor, used = completed(
        'S14', child, cur_d, (3, 4, 7),
        programs=[PROGRAM_TYPE_GENERAL, PROGRAM_TYPE_RECOMMENDED, PROGRAM_TYPE_CHALLENGE],
        ratings=[(3, 4), (4, 4), (5, 3)], used=used,
    )
    abandoned_chunk = cur_d[cursor:cursor + 2]
    if abandoned_chunk:
        book_spec = _next_spec('S14', child.grade, PROGRAM_TYPE_GENERAL, used, 90)
        if book_spec is not None:
            abandoned = _reading(
                child, books[book_spec['key']], started_on=abandoned_chunk[0],
                ended_on=abandoned_chunk[-1], status=STATUS_ABANDONED, actor_id=actor_id,
            )
            _days(
                abandoned, abandoned_chunk, actor_id, child=child, book=books[book_spec['key']],
                voice_key=CHILD_PROFILES['S14']['voice'], child_key='S14',
            )
            r2 = r2 + abandoned_chunk
    points_split('S14', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S14', hist_d, prev_d, cur_d))

    # S15 first completion in current
    child = _child('S15', created)
    _, hist_d, prev_d, cur_d = horizon('S15')
    used = set()
    _, r2, c2, _, used = completed('S15', child, cur_d, (3,), ratings=[(None, None)], used=used)
    points_split('S15', child, hist_d, prev_d, cur_d, r2, c2, manuals_for('S15', hist_d, prev_d, cur_d))

    # S16 grade 6 outlier + 쎈교재완료
    child = _child('S16', created)
    _, hist_d, prev_d, cur_d = horizon('S16')
    used = set()
    mix = [PROGRAM_TYPE_GENERAL] * 8 + [PROGRAM_TYPE_RECOMMENDED] * 3 + [PROGRAM_TYPE_CHALLENGE]
    rh, ch, used = history_books('S16', child, hist_d, 12, used, programs=mix)
    _, r1, c1, _, used = completed('S16', child, prev_d, (3, 4), used=used)
    _, r2, c2, _, used = completed('S16', child, cur_d, (3, 4, 3), used=used)
    points_split('S16', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S16', hist_d, prev_d, cur_d))

    # S17 reading + completions + progress increase
    child = _child('S17', created)
    _, hist_d, prev_d, cur_d = horizon('S17')
    used = set()
    rh, ch, used = history_books('S17', child, hist_d, 5, used)
    _, r1, c1, _, used = completed('S17', child, prev_d, (2, 3), used=used)
    _, r2, c2, _, used = completed('S17', child, cur_d, (3, 3, 4, 4), used=used)
    points_split('S17', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S17', hist_d, prev_d, cur_d))

    # S18 candidate 0
    child = _child('S18', created)
    _, hist_d, prev_d, cur_d = horizon('S18')
    used = set()
    rh, ch, used = history_books('S18', child, hist_d, 4, used)
    _, r1, c1, _, used = completed('S18', child, prev_d, (3, 3), used=used)
    _, r2, c2, _, used = completed('S18', child, cur_d, (3, 3), used=used)
    points_split(
        'S18', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2,
        manuals_for('S18', hist_d, prev_d, cur_d),
        reading_points_override=100,
    )

    # S19 mid rank
    child = _child('S19', created)
    _, hist_d, prev_d, cur_d = horizon('S19')
    used = set()
    rh, ch, used = history_books('S19', child, hist_d, 3, used)
    _, r1, c1, _, used = completed('S19', child, prev_d, (3, 2), used=used)
    _, r2, c2, _, used = completed('S19', child, cur_d, (3, 3), used=used)
    points_split('S19', child, hist_d, prev_d, cur_d, rh + r1 + r2, ch + c1 + c2, manuals_for('S19', hist_d, prev_d, cur_d))

    # S20 low rank
    child = _child('S20', created)
    _, hist_d, prev_d, cur_d = horizon('S20')
    points_split('S20', child, hist_d, prev_d, cur_d, [], [], manuals_for('S20', hist_d, prev_d, cur_d))

    # S21 long reading history ~28권
    child = _child('S21', created)
    _, hist_d, prev_d, cur_d = horizon('S21')
    used = set()
    long_d = hist_d + prev_d + cur_d
    durations21 = (
        3, 2, 4, 3, 5, 3, 2, 4, 3, 3,
        4, 2, 3, 5, 3, 3, 8, 3, 4, 2,
        3, 3, 4, 3, 2, 4, 3, 3,
    )
    programs21 = [PROGRAM_TYPE_GENERAL] * 28
    programs21[2] = PROGRAM_TYPE_RECOMMENDED
    programs21[4] = PROGRAM_TYPE_RECOMMENDED
    programs21[11] = PROGRAM_TYPE_RECOMMENDED
    programs21[16] = PROGRAM_TYPE_CHALLENGE
    programs21[19] = PROGRAM_TYPE_RECOMMENDED
    programs21[22] = PROGRAM_TYPE_RECOMMENDED
    programs21[25] = PROGRAM_TYPE_CHALLENGE
    specs21 = [{'duration': d, 'program': programs21[i]} for i, d in enumerate(durations21)]
    long_title = next(spec for spec in all_book_specs() if '이상한 제목' in spec['title'])
    specs21[-1]['book_spec'] = long_title
    used.add(long_title['key'])
    _, r21, c21, _, used = _place_completed(
        child, long_d, specs21, actor_id, books,
        child_key='S21', voice_key=CHILD_PROFILES['S21']['voice'], used=used,
    )
    manuals = manuals_for('S21', hist_d, prev_d, cur_d)
    seed_points('S21', child, long_d, r21, c21, manuals_by_date=manuals)

    # S22 first recommended completion
    child = _child('S22', created)
    _, hist_d, prev_d, cur_d = horizon('S22')
    used = set()
    _, r2, c2, _, used = completed(
        'S22', child, cur_d, (4,), programs=[PROGRAM_TYPE_RECOMMENDED], used=used,
    )
    points_split('S22', child, hist_d, prev_d, cur_d, r2, c2, manuals_for('S22', hist_d, prev_d, cur_d))

    db.session.flush()
    from app import DailyPoints
    for key, child in created.items():
        dates = [
            row.date
            for row in DailyPoints.query.filter_by(child_id=child.id).order_by(DailyPoints.date).all()
        ]
        _seed_child_progress(key, child, dates, subjects, actor_id, previous, current)

    _sync_cumulative(created.values())
    db.session.commit()
    _seed_exemptions(created, actor_id, anchor)
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
        print(f"  {key} {child['name']} (id={child['id']}, {child['grade']}학년) - {spec['label']}")


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
