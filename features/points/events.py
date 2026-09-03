"""분석용 PointEvent. DailyPoints 원장을 바꾸지 않는 읽기 projection 계약."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

SOURCE_DAILY_SUBJECT = 'daily_subject'
SOURCE_MANUAL = 'manual'

PROVENANCE_DAILY_COLUMN = 'daily_column'
PROVENANCE_MANUAL_JSON = 'manual_json'
PROVENANCE_MANUAL_SUM = 'manual_sum'

DIRECTION_EARN = 'EARN'
DIRECTION_SPEND = 'SPEND'

CATEGORY_TEXTBOOK_COMPLETE = 'TEXTBOOK_COMPLETE'
CATEGORY_PRAISE = 'PRAISE'
CATEGORY_ACTIVITY_MATERIAL = 'ACTIVITY_MATERIAL'
CATEGORY_STATIONERY = 'STATIONERY'
CATEGORY_HELP_CONTRIBUTION = 'HELP_CONTRIBUTION'
CATEGORY_EXTRA_LEARNING = 'EXTRA_LEARNING'
CATEGORY_UNCLASSIFIED = 'UNCLASSIFIED'

READING_REWARD_MIRROR_SOURCE_TYPES = frozenset((
    'recommended_reading',
    'challenge_reading',
))


def direction_for(amount):
    """amount > 0 → EARN, amount < 0 → SPEND. 0은 이벤트가 아니므로 None."""
    value = int(amount or 0)
    if value > 0:
        return DIRECTION_EARN
    if value < 0:
        return DIRECTION_SPEND
    return None


@dataclass(frozen=True)
class ManualClassification:
    category: str
    subject_key: str | None = None
    item_key: str | None = None


UNCLASSIFIED = ManualClassification(category=CATEGORY_UNCLASSIFIED)


@dataclass(frozen=True)
class PointEvent:
    activity_date: date
    source_kind: str
    amount: int
    provenance: str
    subject_key: str | None = None
    category: str | None = None
    item_key: str | None = None
    raw_subject: str | None = None
    raw_reason: str | None = None
    source_type: str | None = None
    source_event_id: int | None = None

    @property
    def direction(self):
        return direction_for(self.amount)

    @property
    def is_reading_reward_mirror(self):
        """DailyPoints manual_history에 복사된 독서 보상인지.

        미러여도 amount는 실제 일일 총점의 일부이므로 이벤트를 버리지 않는다.
        총액에 ReadingRewardEvent를 다시 더하면 안 된다.
        """
        if self.source_kind != SOURCE_MANUAL:
            return False
        if self.source_type in READING_REWARD_MIRROR_SOURCE_TYPES:
            return True
        return self.source_event_id is not None
