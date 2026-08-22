"""InsightCandidate용 규칙 기반 fallback 문장. 사실을 새로 만들지 않는다."""

READING_ACTIVITY_INCREASE = 'READING_ACTIVITY_INCREASE'
READING_ACTIVITY_DECREASE = 'READING_ACTIVITY_DECREASE'
READING_COMPLETIONS_INCREASE = 'READING_COMPLETIONS_INCREASE'
READING_COMPLETIONS_DECREASE = 'READING_COMPLETIONS_DECREASE'
PROGRESS_ENTRIES_INCREASE = 'PROGRESS_ENTRIES_INCREASE'
PROGRESS_ENTRIES_DECREASE = 'PROGRESS_ENTRIES_DECREASE'
POINTS_PERIOD_INCREASE = 'POINTS_PERIOD_INCREASE'
HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN = 'HIGHER_PERCEIVED_DIFFICULTY_WITH_STABLE_FUN'

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


def all_copy_texts():
    texts = []
    for row in FALLBACK_COPY.values():
        texts.append(row.get('headline') or '')
        texts.append(row.get('detail') or '')
    return texts
