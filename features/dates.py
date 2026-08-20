"""현장 활동일은 KST 달력을 쓴다. 기존 UTC 혼용 코드는 일괄 변경하지 않는다."""
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def kst_today():
    return datetime.now(KST).date()
