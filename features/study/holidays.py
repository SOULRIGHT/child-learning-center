"""한국 법정·대체공휴일 목록. CenterNonStudyDay seed에만 쓰고 resolver는 DB만 읽는다."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.exc import IntegrityError

from extensions import db
from feature_models import CenterNonStudyDay, CenterSystemHolidaySeed
from features.study.calendar import StudyCalendarError
from features.study.constants import NON_STUDY_SOURCE_SYSTEM_HOLIDAY

_LABEL_MAX = 80


def korean_public_holidays(year):
    """year의 한국 법정공휴일+대체공휴일. {date: label}."""
    year = int(year)
    try:
        import holidays as holidays_lib
    except ImportError as exc:
        raise StudyCalendarError(
            '공휴일 라이브러리가 설치되어 있지 않습니다.',
            code='holiday_library_missing',
        ) from exc
    try:
        calendar = holidays_lib.country_holidays('KR', years=year, language='ko')
    except TypeError:
        calendar = holidays_lib.country_holidays('KR', years=year)
    result = {}
    for day, name in calendar.items():
        if not isinstance(day, date) or isinstance(day, datetime):
            continue
        if day.year != year:
            continue
        label = str(name).strip() or '법정공휴일'
        result[day] = label[:_LABEL_MAX]
    return result


def year_system_holidays_initialized(year):
    """해당 연도 기본 공휴일이 최초 제공됐는지. exclusion row 개수로 추론하지 않는다."""
    return (
        CenterSystemHolidaySeed.query
        .filter_by(year=int(year))
        .first()
        is not None
    )


def _occupied_days(year):
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    return {
        row.day
        for row in (
            CenterNonStudyDay.query
            .filter(CenterNonStudyDay.day >= start)
            .filter(CenterNonStudyDay.day <= end)
            .all()
        )
    }


def _insert_missing_system_holidays(year):
    """라이브러리 공휴일 중 DB에 없는 날짜만 추가한다. commit하지 않는다."""
    occupied = _occupied_days(year)
    created = 0
    now = datetime.utcnow()
    for day, label in sorted(korean_public_holidays(year).items()):
        if day in occupied:
            continue
        db.session.add(CenterNonStudyDay(
            day=day,
            source=NON_STUDY_SOURCE_SYSTEM_HOLIDAY,
            label=label,
            created_at=now,
            updated_at=now,
        ))
        occupied.add(day)
        created += 1
    return created


def _mark_year_initialized(year):
    if year_system_holidays_initialized(year):
        return
    db.session.add(CenterSystemHolidaySeed(year=int(year), seeded_at=datetime.utcnow()))


def ensure_system_holidays(year):
    """해당 연도 기본 공휴일을 최초 1회만 제공한다.

    이미 초기화된 연도는 exclusion row가 없어도 다시 넣지 않는다.
    같은 날짜에 센터 비학습일이 있으면 그 날짜는 skip한다.
    """
    year = int(year)
    if year_system_holidays_initialized(year):
        return 0
    created = _insert_missing_system_holidays(year)
    _mark_year_initialized(year)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return 0
    return created


def restore_system_holidays(year):
    """운영자가 명시한 기본 공휴일 복원. 학습일로 복구한 날짜도 다시 비학습일이 된다.

    이미 있는 센터 지정 날짜는 덮어쓰지 않는다.
    """
    year = int(year)
    created = _insert_missing_system_holidays(year)
    _mark_year_initialized(year)
    db.session.commit()
    return created
