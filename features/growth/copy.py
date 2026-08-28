"""InsightCandidate용 규칙 기반 fallback 문장. 사실을 새로 만들지 않는다."""

READING_ACTIVITY_INCREASE = 'READING_ACTIVITY_INCREASE'
READING_ACTIVITY_DECREASE = 'READING_ACTIVITY_DECREASE'
READING_COMPLETIONS_INCREASE = 'READING_COMPLETIONS_INCREASE'
READING_COMPLETIONS_DECREASE = 'READING_COMPLETIONS_DECREASE'
PROGRESS_ENTRIES_INCREASE = 'PROGRESS_ENTRIES_INCREASE'
PROGRESS_ENTRIES_DECREASE = 'PROGRESS_ENTRIES_DECREASE'
POINTS_PERIOD_INCREASE = 'POINTS_PERIOD_INCREASE'
HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN = 'HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN'
READING_DAYS_RECENT_WINDOW_BEST = 'READING_DAYS_RECENT_WINDOW_BEST'
READING_COMPLETIONS_RECENT_WINDOW_BEST = 'READING_COMPLETIONS_RECENT_WINDOW_BEST'
POINTS_PERIOD_RECENT_WINDOW_BEST = 'POINTS_PERIOD_RECENT_WINDOW_BEST'
LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST = 'LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST'
RECENT_WINDOW_SCOPE = '최근 3개 30일 비교구간'

# headline만 쓴다. 숫자는 evidence/UI가 보여 준다.
FALLBACK_COPY = {
    READING_ACTIVITY_INCREASE: {
        'headline': '최근 책을 읽은 날이 이전 기간보다 늘었어요.',
        'detail': '',
    },
    READING_ACTIVITY_DECREASE: {
        'headline': '최근 독서 기록일이 이전 기간보다 줄었어요.',
        'detail': '',
    },
    READING_COMPLETIONS_INCREASE: {
        'headline': '최근 완독한 책이 이전 기간보다 늘었어요.',
        'detail': '',
    },
    READING_COMPLETIONS_DECREASE: {
        'headline': '최근 완독한 책이 이전 기간보다 줄었어요.',
        'detail': '',
    },
    PROGRESS_ENTRIES_INCREASE: {
        'headline': '최근 학습 진도 기록이 이전 기간보다 늘었어요.',
        'detail': '',
    },
    PROGRESS_ENTRIES_DECREASE: {
        'headline': '최근 학습 진도 기록이 이전 기간보다 줄었어요.',
        'detail': '',
    },
    POINTS_PERIOD_INCREASE: {
        'headline': '최근 기간에 받은 포인트가 이전 기간보다 늘었어요.',
        'detail': '',
    },
    HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN: {
        'headline': '더 어렵게 느낀 책을 읽으면서도 재미 평가는 비슷하게 유지됐어요.',
        'detail': '',
    },
    READING_DAYS_RECENT_WINDOW_BEST: {
        'headline': '최근 책을 읽은 날이 최근 3개 30일 비교구간 중 가장 많았어요.',
        'detail': '',
    },
    READING_COMPLETIONS_RECENT_WINDOW_BEST: {
        'headline': '최근 완독한 책이 최근 3개 30일 비교구간 중 가장 많았어요.',
        'detail': '',
    },
    POINTS_PERIOD_RECENT_WINDOW_BEST: {
        'headline': '최근 기간에 받은 포인트가 최근 3개 30일 비교구간 중 가장 높았어요.',
        'detail': '',
    },
    LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST: {
        'headline': '학습 진도가 최근 3개 30일 비교구간 중 가장 크게 진행됐어요.',
        'detail': '',
    },
}

# copy와 이후 LLM 초안에 쓰면 안 되는 해석.
FORBIDDEN_COPY_PHRASES = (
    '실력이 향상',
    '능력이 향상',
    '지능',
    '집중력이 좋아',
    '집중력이 나빠',
    '성격',
    '의지가 부족',
    '책임감',
    '때문에 증가',
    '면제권 때문에',
    '포인트 정책 때문에',
    '선호한다',
    '성숙해',
    '공부를 더 많이',
    '수학 실력이',
    '학습 능력이',
    '어려운 책을 선호',
    '독서 수준이',
    '더 어려운 책을 잘',
    '독서 실력이',
    '흥미가 떨어',
    '독서를 싫어',
    '크게 늘었다',
    '성장했다',
    '실력이',
    '역대',
    '개인 최고',
    '놀라운',
    '우수',
    '부진',
    '의욕',
    'engagement',
    '몰입',
    '선호',
)


def fallback_copy(candidate_id):
    """candidate id → headline/detail. 없는 id는 빈 문장. 사실을 만들지 않는다."""
    row = FALLBACK_COPY.get(candidate_id)
    if row is None:
        return {'headline': '', 'detail': ''}
    return {'headline': row['headline'], 'detail': row.get('detail') or ''}


def _has_batchim(word):
    if not word:
        return False
    code = ord(word[-1]) - 0xAC00
    return 0 <= code <= 11171 and (code % 28) != 0


def join_subject_labels(labels):
    """canonical subject 순서를 유지한 한국어 연결."""
    names = [name for name in labels if name]
    if not names:
        return ''
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        particle = '과' if _has_batchim(names[0]) else '와'
        return f'{names[0]}{particle} {names[1]}'
    return '·'.join(names)


def learning_recent_window_headline(labels):
    names = [name for name in labels if name]
    joined = join_subject_labels(names)
    if not joined:
        return FALLBACK_COPY[LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST]['headline']
    if len(names) >= 3:
        return f'{joined} 모두 {RECENT_WINDOW_SCOPE} 중 가장 큰 진도 증가를 기록했어요.'
    return f'{joined} 진도가 {RECENT_WINDOW_SCOPE} 중 가장 크게 진행됐어요.'


def headline_for(candidate):
    """candidate의 화면 headline. 학습 aggregate만 과목 목록을 넣는다."""
    if candidate is None:
        return ''
    if getattr(candidate, 'id', None) == LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST:
        subjects = (getattr(candidate, 'evidence', None) or {}).get('subjects') or []
        labels = [row.get('subject_label') for row in subjects if row.get('subject_label')]
        if labels:
            return learning_recent_window_headline(labels)
    return fallback_copy(getattr(candidate, 'id', None))['headline']


def all_copy_texts():
    texts = []
    for row in FALLBACK_COPY.values():
        texts.append(row.get('headline') or '')
        texts.append(row.get('detail') or '')
    texts.append(learning_recent_window_headline(['국어']))
    texts.append(learning_recent_window_headline(['국어', '수학']))
    texts.append(learning_recent_window_headline(['국어', '수학', '쎈']))
    return texts
