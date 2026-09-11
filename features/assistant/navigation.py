"""Allowlisted navigation. LLM이 URL을 만들지 않는다."""
from __future__ import annotations

from dataclasses import dataclass

from flask import url_for

from features.assistant.config import can_manage_settings
from features.assistant.copy import (
    NAV_INVALID_CHILD,
    NAV_NEED_CHILD,
    NAV_UNKNOWN,
    SETUP_FORBIDDEN,
)
from features.reading.access import get_child, model_named

CHILD_SEARCH_LIMIT = 8


@dataclass(frozen=True)
class DestinationSpec:
    key: str
    endpoint: str
    child_required: bool
    settings: bool
    label: str
    child_endpoint: str | None = None


# destination key → 실제 Flask endpoint. 존재하지 않는 endpoint를 만들지 않는다.
DESTINATIONS = {
    'child_detail': DestinationSpec('child_detail', 'child_detail', True, False, '아동 상세'),
    'growth': DestinationSpec('growth', 'growth.teacher', True, False, '성장 리포트'),
    'points_input': DestinationSpec('points_input', 'points_input', True, False, '포인트 입력'),
    'points_detail': DestinationSpec('points_detail', 'child_point_analysis', True, False, '포인트 상세'),
    'reading_history': DestinationSpec(
        'reading_history', 'reading.teacher_history', True, False, '독서 기록',
    ),
    'reading_editor': DestinationSpec(
        'reading_editor', 'reading.teacher_editor', True, False, '독서 입력',
    ),
    'progress_history': DestinationSpec(
        'progress_history', 'progress.history', True, False, '학습 진도',
    ),
    'setup_hub': DestinationSpec('setup_hub', 'setup.hub', False, True, '센터 운영 설정'),
    'learning_subjects': DestinationSpec(
        'learning_subjects', 'progress.manage_subjects', False, True, '학습 과목',
    ),
    'study_calendar': DestinationSpec(
        'study_calendar', 'planning.manage_study_calendar', False, True, '센터 학습요일',
    ),
    'subject_weekdays': DestinationSpec(
        'subject_weekdays', 'planning.manage_subject_weekdays', False, True, '과목별 학습요일',
    ),
    'non_study_days': DestinationSpec(
        'non_study_days', 'planning.manage_non_study_days', False, True, '비학습일',
    ),
    'workbook_plans': DestinationSpec(
        'workbook_plans', 'planning.manage_workbook_plans', False, True, '교재 계획',
    ),
    'points_settings': DestinationSpec(
        'points_settings', 'settings_points', False, True, '포인트 설정',
    ),
    'manual_presets': DestinationSpec(
        'manual_presets', 'presets.manage_presets', False, True, '수동 프리셋',
    ),
    'books': DestinationSpec('books', 'books.books_index', False, False, '독서도서'),
    'print_report': DestinationSpec(
        'print_report',
        'settings_print_children',
        False,
        True,
        '출력용 리포트',
        child_endpoint='settings_print_child_report',
    ),
}

ENDPOINT_TO_KEY = {}
for _spec in DESTINATIONS.values():
    ENDPOINT_TO_KEY[_spec.endpoint] = _spec.key
    if _spec.child_endpoint:
        ENDPOINT_TO_KEY[_spec.child_endpoint] = _spec.key

# 사용자 말에서 목적지 추정. 긴 구문을 앞에 둔다.
NAV_PHRASES = (
    (('과목별 학습요일', '과목별 요일', '과목 요일'), 'subject_weekdays'),
    (('센터 기본 학습요일', '기본 학습요일', '학습요일', '공부 요일', '센터 요일'), 'study_calendar'),
    (('학습 과목', '과목 설정'), 'learning_subjects'),
    (('교재 계획', '교재계획'), 'workbook_plans'),
    (('비학습일', '휴일 설정'), 'non_study_days'),
    (('수동 프리셋', '프리셋'), 'manual_presets'),
    (('포인트 설정',), 'points_settings'),
    (('포인트 입력',), 'points_input'),
    (('포인트 상세',), 'points_detail'),
    (('성장 리포트', '성장리포트'), 'growth'),
    (('독서 입력', '독서 편집'), 'reading_editor'),
    (('독서 기록', '독서 이력', '독서기록'), 'reading_history'),
    (('학습 진도', '진도 이력', '진도 기록'), 'progress_history'),
    (('출력용 리포트', '인쇄 리포트', '출력 리포트'), 'print_report'),
    (('센터 운영 설정', '설정 허브', '설정 안내'), 'setup_hub'),
    (('독서도서', '도서 관리', '책 목록'), 'books'),
    (('아동 상세', '아동 정보'), 'child_detail'),
)

EXPLICIT_GO = ('가줘', '열어줘', '열어', '보여줘', '이동해', '이동하자', '가자')

# 요청/화면 affix만 제거한다. nickname 안의 독서/포인트/진도/성장/학습은 지우지 않는다.
_REQUEST_AFFIXES = (
    '성장 리포트', '성장리포트',
    '독서 기록', '독서기록', '독서 이력', '독서이력', '독서 입력', '독서 활동', '독서활동',
    '포인트 입력', '포인트 이력', '포인트 상세', '포인트 평균', '포인트 요약', '포인트 기록',
    '학습 진도', '학습정보', '학습 정보',
    '열어줘', '가줘', '보여줘', '해주세요', '해줘', '열어', '이동해줘', '이동해', '이동',
    '알려주고', '알려줘', '알려 줘',
    '정보 좀', '정보좀',
    '어떻게 돼', '어떻게돼', '요즘 어때',
    '기록 보여줘', '기록 보여',
    '리포트',
    '어때', '얼마나', '비교', '또래',
    '무슨 뜻', '의미', '화면', '페이지',
    '며칠', '몇 권', '화면도', '그리고', '주고',
    '교재 계획', '교재계획', '학습요일', '기본 학습요일',
    '대해서', '에 대한', '에대한',
)
_TRAILING_DOMAIN = (
    '쎈수학', '수학', '국어',
    '포인트', '독서', '학습', '진도', '성장',
    '완독', '수행률', '확인률',
)
_SUBJECT_HINTS = (
    ('쎈수학', 'ssen'),
    ('쎈', 'ssen'),
    ('수학', 'math'),
    ('국어', 'korean'),
)
_GENERIC_REMAINDER = (
    '정보 좀', '정보좀', '정보', '좀',
    '알려줘', '알려 줘', '알려', '줘',
    '어때', '어떻게 돼', '어떻게돼', '어떻게', '돼', '되',
    '기록 보여줘', '기록 보여', '보여줘', '보여',
    '요즘 어때', '요즘', '기록', '현황', '요약',
    '아동', '학생', '요', '대해', '대한',
)


def spec_for(destination):
    if not destination:
        return None
    key = str(destination).strip()
    if key in DESTINATIONS:
        return DESTINATIONS[key]
    mapped = ENDPOINT_TO_KEY.get(key)
    if mapped:
        return DESTINATIONS[mapped]
    return None


def lookup_child(child_id):
    try:
        child_id = int(child_id)
    except (TypeError, ValueError):
        return None
    if child_id <= 0:
        return None
    return get_child(child_id)


def search_children(query):
    """이름 exact/partial 검색. 동명이인은 자동 선택하지 않는다."""
    text = (query or '').strip()
    if not text:
        return []
    Child = model_named('Child')
    exact = (
        Child.query.filter(Child.name == text)
        .order_by(Child.grade, Child.name, Child.id)
        .limit(CHILD_SEARCH_LIMIT)
        .all()
    )
    if exact:
        return exact
    return (
        Child.query.filter(Child.name.contains(text))
        .order_by(Child.grade, Child.name, Child.id)
        .limit(CHILD_SEARCH_LIMIT)
        .all()
    )


def child_public(child):
    if child is None:
        return None
    return {
        'id': child.id,
        'name': child.name,
        'grade': getattr(child, 'grade', None),
    }


def resolve_navigation(destination, params=None, *, role):
    """url_for(known_endpoint, validated_params). 권한 없으면 URL 없음."""
    spec = spec_for(destination)
    if spec is None:
        return {'ok': False, 'error': 'unknown_destination', 'message': NAV_UNKNOWN}
    if spec.settings and not can_manage_settings(role):
        return {'ok': False, 'error': 'forbidden', 'message': SETUP_FORBIDDEN}

    params = params or {}
    child = None
    child_id = params.get('child_id')
    if spec.child_required:
        if child_id in (None, '', False):
            return {
                'ok': False,
                'error': 'missing_child',
                'message': NAV_NEED_CHILD,
                'destination': spec.key,
            }
        child = lookup_child(child_id)
        if child is None:
            return {'ok': False, 'error': 'invalid_child', 'message': NAV_INVALID_CHILD}
        url = url_for(spec.endpoint, child_id=child.id)
    elif spec.child_endpoint and child_id not in (None, '', False):
        child = lookup_child(child_id)
        if child is None:
            return {'ok': False, 'error': 'invalid_child', 'message': NAV_INVALID_CHILD}
        url = url_for(spec.child_endpoint, child_id=child.id)
    else:
        url = url_for(spec.endpoint)

    return {
        'ok': True,
        'destination': spec.key,
        'endpoint': spec.endpoint if not (spec.child_endpoint and child) else spec.child_endpoint,
        'url': url,
        'label': spec.label,
        'child': child_public(child),
    }


def match_destination_from_text(text):
    raw = (text or '').strip()
    if not raw:
        return None
    for phrases, key in NAV_PHRASES:
        for phrase in phrases:
            if phrase in raw:
                return key
    return None


def is_explicit_go(text):
    raw = text or ''
    return any(token in raw for token in EXPLICIT_GO)


def extract_child_query(text):
    return split_child_request(text)['child_query']


def split_child_request(text):
    """raw user text → child entity span + remainder request.

    nickname 내부 단어는 child_query에 남기고, domain은 remainder에서만 본다.
    """
    original = (text or '').strip()
    if not original:
        return {'child_query': '', 'remainder': ''}
    query = original
    for phrase in _REQUEST_AFFIXES:
        query = query.replace(phrase, ' ')
    query = ' '.join(query.split())
    query = _peel_trailing_domain(query)
    query = _strip_edge_particles(query)
    remainder = request_remainder(original, query)
    return {'child_query': query, 'remainder': remainder}


def request_remainder(text, *spans):
    """resolved/extracted child span을 제외한 사용자 의도 문자열."""
    raw = str(text or '')
    ordered = sorted(
        (str(span).strip() for span in spans if span),
        key=len,
        reverse=True,
    )
    for span in ordered:
        idx = raw.find(span)
        if idx >= 0:
            raw = (raw[:idx] + ' ' + raw[idx + len(span):]).strip()
            break
    return ' '.join(raw.split())


def classify_remainder_domain(remainder):
    """entity 바깥 remainder만으로 domain/tool을 정한다. unspecified면 None."""
    raw = (remainder or '').strip()
    if not raw:
        return None
    dest = match_destination_from_text(raw)
    wants_nav = bool(
        dest and (is_explicit_go(raw) or dest == 'growth' or '리포트' in raw)
    )
    facts = _facts_kind_from_remainder(raw)
    if facts:
        return facts
    if wants_nav:
        return {'kind': 'navigate', 'tool': 'navigate', 'destination': dest}
    leftover = raw
    for phrase in _GENERIC_REMAINDER:
        leftover = leftover.replace(phrase, ' ')
    leftover = ''.join(ch for ch in leftover if ch not in '?!.,~')
    leftover = ''.join(leftover.split())
    if not leftover:
        return None
    return None


def _facts_kind_from_remainder(remainder):
    stripped = remainder or ''
    for phrases, _key in NAV_PHRASES:
        for phrase in phrases:
            stripped = stripped.replace(phrase, ' ')
    stripped = ' '.join(stripped.split())
    if not stripped:
        return None
    extra = {}
    for hint, key in _SUBJECT_HINTS:
        if hint in stripped:
            extra['subject_key'] = key
            break
    if '또래' in stripped:
        return {'kind': 'peer', 'tool': 'get_peer_facts', **extra}
    if '포인트' in stripped:
        return {'kind': 'points', 'tool': 'get_points_facts', **extra}
    if '독서' in stripped or '완독' in stripped or '추천도서' in stripped:
        return {'kind': 'reading', 'tool': 'get_reading_facts', **extra}
    if extra or '진도' in stripped or '학습' in stripped or '수행률' in stripped or '확인률' in stripped:
        return {'kind': 'learning', 'tool': 'get_learning_facts', **extra}
    if '성장' in stripped:
        return {'kind': 'growth', 'tool': 'get_growth_facts'}
    return None


def _peel_trailing_domain(text):
    raw = (text or '').strip()
    changed = True
    while changed and raw:
        changed = False
        for token in _TRAILING_DOMAIN:
            if raw == token:
                return ''
            if raw.endswith(token) and len(raw) > len(token):
                prefix = raw[:-len(token)].rstrip(' -')
                if prefix:
                    raw = prefix
                    changed = True
                    break
    return raw


def _strip_edge_particles(text):
    particles = ('으로', '에서', '은', '는', '을', '를', '의')
    cleaned = []
    for token in (text or '').split():
        for particle in particles:
            if token.endswith(particle) and len(token) > len(particle):
                token = token[:-len(particle)]
                break
        if token and token not in {'좀', '아동', '학생'}:
            cleaned.append(token)
    return ' '.join(cleaned)
