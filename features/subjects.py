"""현재 센터용 임시 과목 registry.

DailyPoints 고정 컬럼이 현재 운영 과목의 정본이다.
DB Subject master / 설정 UI / DailyPoints 동적화는 만들지 않는다.

TODO: Unified dynamic Subject architecture
- 기존 DailyPoints 고정 과목 제거/호환 이관
- 하나의 Subject PK 기반 master 도입
- points / progress / exemption 모두 같은 Subject FK 사용
- 센터별 UI에서 과목 추가/비활성/정렬/기능별 사용 여부 관리
- 기존 역사 데이터 보존 migration 필요
이번 Step에서는 구현하지 않는다.
"""

# DailyPoints 모델에 실제로 존재하는 과목 컬럼만 등록한다. manual_points는 과목이 아니다.
CURRENT_SUBJECTS = {
    'korean': {
        'name': '국어',
        'daily_points_field': 'korean_points',
        'sort_order': 10,
    },
    'math': {
        'name': '수학',
        'daily_points_field': 'math_points',
        'sort_order': 20,
    },
    'ssen': {
        'name': '쎈',
        'daily_points_field': 'ssen_points',
        'sort_order': 30,
    },
    'reading': {
        'name': '독서',
        'daily_points_field': 'reading_points',
    },
    'piano': {
        'name': '피아노',
        'daily_points_field': 'piano_points',
    },
    'english': {
        'name': '영어',
        'daily_points_field': 'english_points',
    },
    'advanced_math': {
        'name': '고학년수학',
        'daily_points_field': 'advanced_math_points',
    },
    'writing': {
        'name': '쓰기',
        'daily_points_field': 'writing_points',
    },
}

PROGRESS_SUBJECT_KEYS = ('korean', 'math', 'ssen')
EXEMPTION_SUBJECT_KEYS = ('korean', 'math', 'ssen', 'reading')


def subject_name(key):
    item = CURRENT_SUBJECTS.get(key)
    return item['name'] if item else None


def progress_default_subjects():
    return tuple(
        {
            'key': key,
            'name': CURRENT_SUBJECTS[key]['name'],
            'sort_order': CURRENT_SUBJECTS[key]['sort_order'],
        }
        for key in PROGRESS_SUBJECT_KEYS
    )


def exemption_subject_choices():
    return [
        {'key': key, 'name': CURRENT_SUBJECTS[key]['name']}
        for key in EXEMPTION_SUBJECT_KEYS
    ]
