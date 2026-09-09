"""현재 센터 운영 정책 자연어. 아동 판정 규칙이 아니다.

이 모듈은 미래 교체 경계다.

장기적으로:
관리자 초기설정/관리자 페이지
→ 센터 운영 정책을 자연어 textarea로 자세히 작성
→ DB 저장 (본문은 자유형, 적용 시점/버전 메타데이터를 둘 수 있음)
→ get_current_center_policy_text()만 바꿔 해당 센터 Growth AI context로 전달

지금은 DB/UI가 없다. 정형화된 0/100/200 form을 제품 전제조건으로 두지 않는다.
센터마다 운영 방식이 전혀 다를 수 있고 숫자 기반 정책이 아닐 수 있다.

정책은 관측된 포인트가 어떤 운영에서 만들어졌는지를 이해하기 위한 해석 배경이다.
아동 능력/성취/난이도/집중력/노력/동기를 점수 한 값으로 평가하는 규칙이 아니다.
"""
from __future__ import annotations

MAX_CENTER_POLICY_TEXT_LEN = 4000

# 현재 알고 있는 사실만. 없는 규칙을 추측해 보완하지 않는다.
CURRENT_CENTER_POLICY_TEXT = (
    '일반 학습에서는 그날 정해진 학습을 모두 맞으면 200점, '
    '하나라도 틀리면 100점, 학습하지 않으면 0점으로 기록한다.\n'
    '\n'
    '쎈 학습은 일반 학습과 점수 체계가 다르며, 모두 맞은 경우에도 100점이다. '
    '현재 설명에 없는 쎈의 다른 경우에 대한 규칙은 추측하지 않는다.\n'
    '\n'
    '독서는 정해진 독서 활동을 모두 하고 독서기록장까지 작성해야 100점으로 기록하며, '
    '그 조건을 모두 충족하지 않으면 0점이다.'
)


def get_current_center_policy_text():
    """AI/Evidence Packet에 넣을 센터 정책 문자열. 없으면 None.

    현재는 코드 상수. 이후 이 함수 본문만 DB/센터 설정 조회로 교체한다.
    아동 이름/메모/개인정보와 결합하지 않는다.
    """
    return normalize_center_policy_text(CURRENT_CENTER_POLICY_TEXT)


def normalize_center_policy_text(value):
    """빈 값/공백만이면 None. 과도한 길이는 AI 입력 한도에서 자른다."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > MAX_CENTER_POLICY_TEXT_LEN:
        return text[:MAX_CENTER_POLICY_TEXT_LEN]
    return text
