"""면제권 정책 v1 상수. 센터별 UI 설정은 최종 일반화 단계에서 검토한다."""
from datetime import timedelta

from features.subjects import EXEMPTION_SUBJECT_KEYS, exemption_subject_choices, subject_name

EXEMPTION_POLICY_VERSION = 'v1'

EXEMPTION_MAX_ACTIVE = 1
EXEMPTION_VALID_DAYS = 14
EXEMPTION_ISSUE_COOLDOWN_DAYS = 14

EXEMPTION_FIRST_RECOMMENDED_COUNT = 1
EXEMPTION_NEXT_RECOMMENDED_COUNT = 2

EXEMPTION_ELIGIBLE_GRADES = (5, 6)
DEFAULT_EXEMPTION_SUBJECT_KEYS = EXEMPTION_SUBJECT_KEYS
DEFAULT_EXEMPTION_SUBJECTS = tuple(exemption_subject_choices())


def resolve_exemption_subject(raw):
    key = '' if raw is None else str(raw).strip().lower()
    if key not in EXEMPTION_SUBJECT_KEYS:
        return None
    return {'key': key, 'name': subject_name(key)}


REWARD_MODE_POINTS = 'points'
REWARD_MODE_EXEMPTION = 'exemption'
REWARD_MODES = (REWARD_MODE_POINTS, REWARD_MODE_EXEMPTION)


def ticket_expires_on(issued_on):
    """발급일 포함 14일: issued_on ~ issued_on+13."""
    return issued_on + timedelta(days=EXEMPTION_VALID_DAYS - 1)


def next_issue_on(issued_on):
    """다음 발급 가능일: issued_on + 14일."""
    return issued_on + timedelta(days=EXEMPTION_ISSUE_COOLDOWN_DAYS)


def parse_grade(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def grade_supports_reward_choice(grade):
    return parse_grade(grade) in EXEMPTION_ELIGIBLE_GRADES
