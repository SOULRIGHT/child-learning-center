"""Teacher-facing Growth AI copy. 내부 코드/provider 이름을 노출하지 않는다."""

MSG_DISABLED = (
    'AI 성장 해석 기능을 현재 사용할 수 없습니다.\n'
    '잠시 후 다시 이용하거나 관리자에게 문의해주세요.'
)
MSG_IDLE_BODY = (
    '독서·학습·포인트 데이터를 바탕으로\n'
    '최근 성장 흐름을 AI가 함께 살펴봐요.\n\n'
    '생성된 해석은 사실 확인과 안전성 검사를 거친 뒤 표시됩니다.'
)
MSG_IDLE_HINT_REF = 'AI 해석은 교사의 관찰을 돕는 참고자료입니다.'
MSG_IDLE_HINT_QUOTA = '새로운 AI 해석은 계정당 하루 최대 30회 생성할 수 있어요.'
MSG_LOADING_HEADER = 'AI 성장 해석을 준비하고 있어요'
MSG_LOADING_WAIT = '잠시만 기다려주세요!'
MSG_LOADING_BODY = (
    '성장 데이터를 정리하고\n'
    'AI 해석과 검증을 차례대로 진행하고 있어요.'
)
MSG_LOADING_STEPS = (
    '성장 데이터 정리',
    'AI가 기록의 흐름 해석',
    '사실이 맞는지 확인',
    '안전하게 보여드릴 수 있는지 확인',
)
MSG_LOADING_CYCLE = (
    '성장 데이터를 차근차근 정리하고 있어요...',
    'AI가 기록의 흐름을 살펴보고 있어요...',
    '해석에 잘못된 사실이 없는지 확인하고 있어요...',
    '안전하게 보여드릴 수 있는 내용인지 확인하고 있어요...',
)
MSG_LOADING_ETA = '보통 5~10초 정도 걸려요.'
MSG_LOADING_WAITING = '성장 해석을 꼼꼼하게 마무리하고 있어요...'
MSG_LOADING_WAITING_HINT = '거의 다 준비됐어요. 잠시만 기다려주세요.'
MSG_READY = 'AI 성장 해석이 준비됐어요!'
MSG_STALE = (
    '성장 데이터가 업데이트됐어요.\n'
    '최신 데이터를 기준으로 AI 해석을 다시 만들 수 있습니다.'
)
MSG_STALE_DURING = (
    '분석 중 성장 데이터가 업데이트됐어요.\n'
    '최신 데이터로 다시 분석해주세요.'
)
MSG_QUOTA = (
    '오늘 AI 성장 해석 생성 횟수를 모두 사용했어요.\n'
    '내일 다시 이용해주세요.'
)
MSG_ERROR = (
    '이번에는 AI 성장 해석을 준비하지 못했어요.\n'
    '잠시 후 다시 시도해주세요.'
)
MSG_TIMEOUT = (
    'AI 해석 준비 시간이 조금 길어졌어요.\n'
    '다시 시도해주세요.'
)
MSG_IN_PROGRESS = (
    '이미 같은 해석을 준비하고 있어요.\n'
    '잠시만 기다려주세요.'
)
BTN_GENERATE = 'AI 성장 해석 만들기'
BTN_RETRY = '다시 시도'
BTN_REFRESH = '새로 분석하기'
BTN_REFRESH_AGAIN = '다시 분석하기'
CARD_TITLE = 'AI 성장 해석'
PRIORITY_TITLE = '가장 먼저 볼 변화'
INTERPRETATION_TITLE = '이 변화의 의미'
OBS_TITLE = '관찰한 점'
SUG_TITLE = '지금 해볼 일'
NEXT_CHECK_TITLE = '다음에 확인할 점'
EVIDENCE_TITLE = '분석 근거'
EVIDENCE_VIEW = '분석 근거 보기'
EVIDENCE_EXPAND_ALL = '모든 근거 펼쳐보기'
EVIDENCE_ITEMS = '개별 근거 모두 보기'
EVIDENCE_LINKED = '이 해석에 연결된 근거'
FEEDBACK_PROMPT = '이 해석이 도움이 되었나요?'
FEEDBACK_NEGATIVE_PROMPT = '어떤 점이 이상했나요?'
FEEDBACK_PLACEHOLDER = '사실과 다른 부분, 이해하기 어려운 표현 등을 알려주세요.'
FEEDBACK_SUBMIT = '의견 보내기'
