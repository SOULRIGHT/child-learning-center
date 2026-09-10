"""센터 운영 설정 상태를 기존 config row로만 읽는다.

완료 boolean / setup progress table / 퍼센트 점수를 만들지 않는다.
GET에서 DB write 하지 않는다.
"""
from __future__ import annotations

from datetime import date

from feature_models import (
    Book,
    CenterNonStudyDay,
    CenterSubjectStudyWeekdays,
    LearningWorkbookPlan,
)
from features.dates import kst_today
from features.planning.service import get_center_calendar_row
from features.planning.weekdays import DEFAULT_STUDY_WEEKDAYS, format_weekdays
from features.presets.service import list_active_presets
from features.progress.service import list_active_subjects

STATUS_SAVED = 'saved'
STATUS_USING_DEFAULT = 'using_default'
STATUS_PARTIAL = 'partial'
STATUS_MISSING = 'missing'
STATUS_OPTIONAL = 'optional'
STATUS_AVAILABLE = 'available'

DEST_LEARNING_SUBJECTS = 'progress.manage_subjects'
DEST_CENTER_WEEKDAYS = 'planning.manage_study_calendar'
DEST_SUBJECT_WEEKDAYS = 'planning.manage_subject_weekdays'
DEST_NON_STUDY_DAYS = 'planning.manage_non_study_days'
DEST_WORKBOOK_PLANS = 'planning.manage_workbook_plans'
DEST_POINTS = 'settings_points'
DEST_PRESETS = 'presets.manage_presets'
DEST_BOOKS = 'books.books_index'

NEXT_RULES = (
    ('learning_subjects', frozenset({STATUS_MISSING})),
    ('center_study_weekdays', frozenset({STATUS_USING_DEFAULT})),
    ('subject_weekdays', frozenset({STATUS_MISSING, STATUS_PARTIAL})),
    ('workbook_plans', frozenset({STATUS_MISSING})),
    ('points', frozenset({STATUS_OPTIONAL})),
    ('reading', frozenset({STATUS_OPTIONAL})),
)

ACTION_CONFIRM = '확인하기'
ACTION_CONFIGURE = '설정하기'
ACTION_BY_STATUS = {
    STATUS_SAVED: ACTION_CONFIRM,
    STATUS_USING_DEFAULT: ACTION_CONFIRM,
    STATUS_AVAILABLE: ACTION_CONFIRM,
    STATUS_OPTIONAL: ACTION_CONFIRM,
    STATUS_PARTIAL: ACTION_CONFIGURE,
    STATUS_MISSING: ACTION_CONFIGURE,
}


def build_center_setup_status(*, today=None):
    """Read-only projection. Flask/request/session에 의존하지 않는다."""
    as_of = today or kst_today()
    sections = [
        _learning_subjects_item(),
        _center_weekdays_item(),
        _subject_weekdays_item(),
        _non_study_days_item(as_of),
        _workbook_plans_item(),
        _points_item(),
        _reading_item(),
    ]
    by_key = {item['key']: item for item in sections}
    return {
        'sections': sections,
        'next': _next_recommended(by_key),
    }


def _item(*, key, status, label, summary, detail, destination, counts, extra_actions=None):
    return {
        'key': key,
        'status': status,
        'label': label,
        'summary': summary,
        'detail': detail,
        'destination': destination,
        'action_label': ACTION_BY_STATUS[status],
        'counts': counts,
        'extra_actions': list(extra_actions or ()),
    }


def _learning_subjects_item():
    subjects = list_active_subjects()
    count = len(subjects)
    if count:
        status = STATUS_SAVED
        summary = f'활성 과목 {count}개'
        detail = '학습 기록과 과목별 요일에 쓰는 과목입니다.'
    else:
        status = STATUS_MISSING
        summary = '활성 과목 없음'
        detail = '학습 기록에 쓸 과목을 확인해 주세요.'
    return _item(
        key='learning_subjects',
        status=status,
        label='학습 과목',
        summary=summary,
        detail=detail,
        destination=DEST_LEARNING_SUBJECTS,
        counts={'active': count},
    )


def _center_weekdays_item():
    row = get_center_calendar_row()
    if row is None:
        return _item(
            key='center_study_weekdays',
            status=STATUS_USING_DEFAULT,
            label='센터 기본 학습요일',
            summary='기본값(월~금) 사용 중',
            detail='기본값(월~금) 사용 중 · 확인 권장',
            destination=DEST_CENTER_WEEKDAYS,
            counts={'saved': 0},
        )
    label = format_weekdays(row.study_weekdays or list(DEFAULT_STUDY_WEEKDAYS))
    return _item(
        key='center_study_weekdays',
        status=STATUS_SAVED,
        label='센터 기본 학습요일',
        summary=f'저장됨 · {label}',
        detail='센터에서 기본적으로 공부하는 요일입니다.',
        destination=DEST_CENTER_WEEKDAYS,
        counts={'saved': 1},
    )


def _subject_weekdays_item():
    subjects = list_active_subjects()
    total = len(subjects)
    ids = [row.id for row in subjects]
    configured = 0
    if ids:
        configured = (
            CenterSubjectStudyWeekdays.query
            .filter(CenterSubjectStudyWeekdays.learning_subject_id.in_(ids))
            .count()
        )
    if total == 0 or configured == 0:
        status = STATUS_MISSING
        summary = f'활성 과목 {total}개 중 명시 설정 0개'
        detail = '미설정 과목은 센터 기본 요일을 사용합니다.'
    elif configured < total:
        status = STATUS_PARTIAL
        summary = f'활성 과목 {total}개 중 명시 설정 {configured}개'
        detail = '일부 과목만 별도 요일이 있습니다. 나머지는 센터 기본 요일입니다.'
    else:
        status = STATUS_SAVED
        summary = f'활성 과목 {total}개 모두 명시 설정'
        detail = '과목별 예정 학습요일이 저장되어 있습니다.'
    return _item(
        key='subject_weekdays',
        status=status,
        label='과목별 예정 학습요일',
        summary=summary,
        detail=detail,
        destination=DEST_SUBJECT_WEEKDAYS,
        counts={'configured': configured, 'total': total},
    )


def _non_study_days_item(as_of):
    year = as_of.year
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    count = (
        CenterNonStudyDay.query
        .filter(CenterNonStudyDay.day >= start)
        .filter(CenterNonStudyDay.day <= end)
        .count()
    )
    if count:
        summary = f'{year}년 등록 {count}건'
        detail = '법정공휴일과 센터 지정 비학습일입니다. 필수는 아닙니다.'
    else:
        summary = f'{year}년 등록 0건'
        detail = '필수는 아닙니다. 공휴일 기본값이나 센터 휴일을 필요할 때 확인하면 됩니다.'
    return _item(
        key='non_study_days',
        status=STATUS_OPTIONAL,
        label='비학습일',
        summary=summary,
        detail=detail,
        destination=DEST_NON_STUDY_DAYS,
        counts={'year': year, 'count': count},
    )


def _workbook_plans_item():
    count = LearningWorkbookPlan.query.count()
    if count:
        status = STATUS_AVAILABLE
        summary = f'교재 계획 {count}건'
        detail = '관측 기반 진도와 완료예상에 사용합니다. 전 학년·전 과목을 채울 필요는 없습니다.'
    else:
        status = STATUS_MISSING
        summary = '교재 계획 없음'
        detail = '관측 기반 진도/완료예상에 필요한 설정입니다. 성장 리포트 자체는 열 수 있습니다.'
    return _item(
        key='workbook_plans',
        status=status,
        label='교재 계획',
        summary=summary,
        detail=detail,
        destination=DEST_WORKBOOK_PLANS,
        counts={'count': count},
    )


def _points_item():
    presets = list_active_presets()
    count = len(presets)
    if count:
        status = STATUS_AVAILABLE
        summary = f'수동 프리셋 {count}개'
        detail = '포인트 기록은 프리셋 없이도 가능합니다.'
    else:
        status = STATUS_OPTIONAL
        summary = '수동 프리셋 없음'
        detail = '필수는 아닙니다. 자주 쓰는 수동 포인트 버튼을 만들 수 있습니다.'
    return _item(
        key='points',
        status=status,
        label='포인트 운영',
        summary=summary,
        detail=detail,
        destination=DEST_POINTS,
        counts={'preset_count': count},
        extra_actions=(
            {
                'key': 'presets',
                'label': '수동 프리셋',
                'destination': DEST_PRESETS,
            },
        ),
    )


def _reading_item():
    active = Book.query.filter_by(is_active=True).count()
    recommended = Book.query.filter_by(is_active=True, is_recommended=True).count()
    if active:
        status = STATUS_AVAILABLE
        summary = f'등록 도서 {active}권'
        detail = '독서 기록에 사용합니다. 성장 리포트 사용을 막지 않습니다.'
    else:
        status = STATUS_OPTIONAL
        summary = '등록된 도서 없음'
        detail = '독서 기록 활용을 위한 운영 준비입니다. 필수는 아닙니다.'
    return _item(
        key='reading',
        status=status,
        label='독서 운영',
        summary=summary,
        detail=detail,
        destination=DEST_BOOKS,
        counts={'active': active, 'recommended': recommended},
    )


def _next_recommended(by_key):
    for key, statuses in NEXT_RULES:
        item = by_key.get(key)
        if item is None:
            continue
        if item['status'] in statuses:
            return {
                'key': item['key'],
                'status': item['status'],
                'label': item['label'],
                'detail': item['detail'],
                'destination': item['destination'],
                'action_label': item['action_label'],
            }
    return None
