"""작은 운영 안내 corpus. PRD 전체 ingest / live embeddings 없음."""
from __future__ import annotations

import re

from features.assistant.copy import PAGE_DESCRIPTIONS

HELP_DOCS = (
    {
        'id': 'weekdays-default',
        'title': '센터 기본 학습요일',
        'text': (
            '센터 기본 학습요일이 저장되어 있지 않으면 월~금(기본값)을 사용합니다. '
            '확인만 하면 되고, 반드시 바꿀 필요는 없습니다.'
        ),
    },
    {
        'id': 'subject-weekdays',
        'title': '과목별 예정 학습요일',
        'text': (
            '과목별 요일이 없으면 해당 과목은 센터 기본 요일을 따릅니다. '
            '일부 과목만 따로 둘 수 있습니다.'
        ),
    },
    {
        'id': 'workbook-and-growth',
        'title': '교재 계획과 성장 리포트',
        'text': (
            '교재 계획이 없어도 성장 리포트는 열 수 있습니다. '
            '교재 계획은 관측 기반 진도와 완료예상에 사용합니다. '
            '전 학년·전 과목을 채울 필요는 없습니다.'
        ),
    },
    {
        'id': 'non-study-days',
        'title': '비학습일',
        'text': (
            '법정공휴일과 센터 지정 비학습일입니다. 필수는 아닙니다. '
            '필요할 때 확인하면 됩니다.'
        ),
    },
    {
        'id': 'points-optional',
        'title': '포인트 운영',
        'text': (
            '포인트 기록은 수동 프리셋 없이도 가능합니다. '
            '자주 쓰는 버튼이 필요하면 프리셋을 확인하면 됩니다.'
        ),
    },
    {
        'id': 'reading-optional',
        'title': '독서 운영',
        'text': (
            '등록 도서가 없어도 성장 리포트 사용을 막지 않습니다. '
            '독서 기록 활용을 위한 운영 준비입니다.'
        ),
    },
    {
        'id': 'general-user-settings',
        'title': '일반사용자 설정 권한',
        'text': (
            '일반사용자 계정은 설정 화면을 열 수 없습니다. '
            '아동 기록 조회와 입력은 가능합니다.'
        ),
    },
    {
        'id': 'growth-meaning',
        'title': '성장 리포트',
        'text': PAGE_DESCRIPTIONS['growth.teacher'] + ' 숫자는 확인된 기록만 보여 줍니다.',
    },
    {
        'id': 'setup-hub',
        'title': '센터 운영 설정',
        'text': PAGE_DESCRIPTIONS['setup.hub'],
    },
    {
        'id': 'learning-subjects',
        'title': '학습 과목',
        'text': '학습 기록과 과목별 요일에 쓰는 과목입니다. 활성 과목이 있어야 학습 기록을 남길 수 있습니다.',
    },
)

_TOKEN = re.compile(r'[가-힣A-Za-z0-9]+')
HELP_LIMIT = 3


def search_help(query, *, limit=HELP_LIMIT):
    """어휘 겹침 검색. 문서에 없는 내용을 만들지 않는다."""
    tokens = _tokens(query)
    if not tokens:
        return []
    ranked = []
    for doc in HELP_DOCS:
        hay = _tokens(doc['title'] + ' ' + doc['text'])
        score = len(tokens & hay)
        if '기본' in query and doc['id'] == 'weekdays-default':
            score += 2
        if '교재' in query and doc['id'] == 'workbook-and-growth':
            score += 2
        if '관측' in query and doc['id'] == 'workbook-and-growth':
            score += 2
        if score <= 0:
            continue
        ranked.append((score, doc))
    ranked.sort(key=lambda item: (-item[0], item[1]['id']))
    hits = []
    for score, doc in ranked[:limit]:
        hits.append({
            'id': doc['id'],
            'title': doc['title'],
            'text': doc['text'],
            'kind': 'help',
        })
    return hits


def _tokens(text):
    return {item.casefold() for item in _TOKEN.findall(text or '')}
