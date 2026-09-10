"""교사 대상 짧은 조교 문구. 유아틱/장문 essay 금지."""

GREETING = '무엇을 도와드릴까요?'
HELP_SCOPE = '지금은 화면 이동과 센터 설정 안내를 도와드릴 수 있어요.'
SETUP_CONTINUE = '센터 설정을 순서대로 확인할 수 있어요.'
SETUP_FORBIDDEN = '이 설정은 현재 계정에서 열 수 없습니다.'
NAV_UNKNOWN = '그 화면은 열 수 있는 목록에 없습니다.'
NAV_NEED_CHILD = '이동하려면 아동을 먼저 지정해 주세요.'
NAV_INVALID_CHILD = '해당 아동을 찾을 수 없습니다.'
NAV_NEED_CHOICE = '같은 이름의 아동이 여러 명입니다. 아래에서 선택해 주세요.'
NAV_NO_MATCH = '이름에 해당하는 아동을 찾지 못했습니다.'
NAV_NEED_NAME = '어느 아동의 화면을 열까요? 이름을 알려 주세요.'
PAGE_GENERIC = '현재 화면의 내용을 확인하고, 필요한 설정이나 아동 화면으로 이동할 수 있어요.'
ONBOARDING_UNAVAILABLE = '지금은 센터 설정 안내를 불러오지 못했습니다.'
ONBOARDING_DONE = '필요한 센터 설정은 확인된 상태입니다. 설정 화면에서 한 번 더 살펴볼 수 있어요.'
PROVIDER_ERROR = '조교 응답을 가져오지 못했습니다. 기존 화면은 그대로 사용할 수 있어요.'
DISABLED = '조교를 사용할 수 없습니다.'
FALLBACK = '화면 이동이나 센터 설정 안내가 필요하면 말씀해 주세요. 학습·포인트 숫자 질문은 아직 연결되지 않았습니다.'
OPENING_GROWTH = '성장 리포트로 이동할게요.'
OPENING_READING = '독서 기록으로 이동할게요.'
OPENING_GENERIC = '해당 화면으로 이동할게요.'

QUICK_CONTINUE_SETUP = '센터 설정 이어서 하기'
QUICK_EXPLAIN_PAGE = '현재 화면 설명'
QUICK_OPEN_GROWTH = '아동 성장 리포트 열기'
QUICK_OPEN_READING = '독서 기록 열기'

PAGE_DESCRIPTIONS = {
    'dashboard': '센터의 오늘 현황을 한눈에 보는 화면입니다.',
    'children_list': '등록된 아동 목록을 확인하고 각 아동 화면으로 이동할 수 있습니다.',
    'child_detail': '선택한 아동의 기본 정보와 최근 기록을 확인하는 화면입니다.',
    'growth.teacher': '아동의 학습·포인트·독서 기록을 함께 확인하는 화면입니다.',
    'setup.hub': '센터 운영 설정 상태를 확인하고 각 설정 화면으로 이동할 수 있습니다.',
    'settings': '센터 운영과 관련된 설정 모음 화면입니다.',
    'points_list': '포인트 기록을 확인하고 입력 화면으로 이동할 수 있습니다.',
    'points_input': '선택한 아동의 하루 포인트를 기록하는 화면입니다.',
    'points_history': '선택한 아동의 포인트 변경 이력을 확인하는 화면입니다.',
    'reading.teacher_editor': '선택한 아동의 독서 기록을 입력하는 화면입니다.',
    'reading.teacher_history': '선택한 아동의 독서 이력을 확인하는 화면입니다.',
    'progress.history': '선택한 아동의 학습 진도 이력을 확인하는 화면입니다.',
    'progress.manage_subjects': '학습 기록에 쓰는 과목을 확인하는 화면입니다.',
    'planning.manage_study_calendar': '센터에서 기본적으로 공부하는 요일을 확인하는 화면입니다.',
    'planning.manage_subject_weekdays': '과목별 예정 학습요일을 확인하는 화면입니다.',
    'planning.manage_non_study_days': '법정공휴일과 센터 지정 비학습일을 확인하는 화면입니다.',
    'planning.manage_workbook_plans': '관측 기반 진도와 완료예상에 쓰는 교재 계획을 확인하는 화면입니다.',
    'settings_points': '포인트 운영 설정을 확인하는 화면입니다.',
    'presets.manage_presets': '자주 쓰는 수동 포인트 버튼을 확인하는 화면입니다.',
    'books.books_index': '독서 기록에 쓰는 도서를 관리하는 화면입니다.',
    'settings_print_children': '출력용 개인 리포트를 열 아동을 고르는 화면입니다.',
    'settings_print_child_report': '선택한 아동의 출력용 개인 리포트 화면입니다.',
}

PAGE_TITLES = {
    'dashboard': '대시보드',
    'children_list': '아동 관리',
    'child_detail': '아동 상세',
    'growth.teacher': '성장 리포트',
    'setup.hub': '센터 운영 설정',
    'settings': '설정',
    'points_input': '포인트 입력',
    'points_history': '포인트 이력',
    'reading.teacher_editor': '독서 기록',
    'reading.teacher_history': '독서 이력',
    'progress.history': '학습 진도',
}


def page_description(endpoint):
    if not endpoint:
        return PAGE_GENERIC
    return PAGE_DESCRIPTIONS.get(endpoint, PAGE_GENERIC)


def page_title(endpoint):
    if not endpoint:
        return ''
    return PAGE_TITLES.get(endpoint, '')


def opening_text(destination_key):
    if destination_key == 'growth':
        return OPENING_GROWTH
    if destination_key == 'reading_history':
        return OPENING_READING
    return OPENING_GENERIC
