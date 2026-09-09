"""Learning metric presentation. 계산/insight 없이 Step D 결과를 화면용으로 조립한다."""
from __future__ import annotations

from features.growth.learning_metrics import MAX_PROGRESS_SNAPSHOT_AGE_DAYS
from features.growth.windows import DEFAULT_WINDOW_DAYS
from features.planning.service import (
    WEEKDAY_SOURCE_CENTER_DEFAULT,
    WEEKDAY_SOURCE_CHILD_OVERRIDE,
)
from features.planning.workload import WORKLOAD_KIND_ESTIMATED, WORKLOAD_KIND_EXACT
from features.study.coverage import learning_progress_summary
from features.study.peer import (
    DISPLAY_LIMITED,
    DISPLAY_NONE,
    DISPLAY_PRIMARY,
    DISPLAY_REFERENCE,
    peer_learning_summary,
)

OBSERVED_STUDY_DAYS_LABEL = '관측 학습일'
OBSERVED_STUDY_DAYS_HINT = '포인트 기록일을 기준으로 한 학습 활동일입니다.'
INSUFFICIENT_LABEL = '비교 자료 부족'
PERIOD_INSUFFICIENT_LABEL = '기간 비교 자료 부족'
PEER_NONE_LABEL = '비교 자료 없음'
PEER_STALE_LABEL = '최근 비교 자료 부족'
PEER_REFERENCE_LABEL = '비교 자료가 적어 주요 비교는 표시하지 않습니다.'
PERFORMANCE_PEER_LABEL = '학습 수행률'
COVERAGE_PEER_LABEL = '관측 기반 진도 또래'
POINTS_PEER_LABEL = '분석기간 총 포인트'
SAME_GRADE_MEDIAN_LABEL = '같은 학년 또래 중앙값'
SAME_BOOK_MEDIAN_LABEL = '같은 교재 또래 중앙값'
NO_SNAPSHOT_LABEL = '진도 기록 없음'
OBSERVED_PROGRESS_LABEL = '관측 기반 진도'
OBSERVED_PROGRESS_HINT = '학습 기록 기준입니다. 교재 시작부터 모든 페이지가 기록되어 있다고 가정하지 않습니다.'
OBSERVED_POSITION_NOTE = '참고 위치'
FORECAST_UNAVAILABLE_LABEL = 'N/A'
FRESHNESS_NOTE = f'최근 {MAX_PROGRESS_SNAPSHOT_AGE_DAYS}일 이내 기록 기준'

FORECAST_REASON_LABELS = {
    'no_plan': '교재 계획 없음',
    'no_studied_sessions': '학습 기록 없음',
    'exclusions_unconfirmed': '제외 페이지 미확정',
    'insufficient_sessions': '학습 횟수 부족',
    'unstable_or_non_positive_pace': '진행 속도 불안정',
    'already_observed_complete': '관측상 배정 페이지 완료',
    'plan_switch_before_completion': '다음 교재 시작 전 완료 예상 불가',
    'insufficient_future_schedule': '남은 예정 학습일 부족',
    'no_future_study_days': '예정 학습일 없음',
}

VS_TARGET_LABELS = {
    'unavailable': '비교 불가',
    'already_observed_complete': '관측상 완료',
    'target_passed_not_observed_complete': '목표일 경과',
    'overlaps_target': '목표일과 겹침',
    'on_or_ahead': '목표일 이내',
    'slight_delay': '목표일보다 약간 늦음',
    'delay_2w_plus': '목표일보다 2주 이상 늦음',
}

WEEKDAY_SOURCE_LABELS = {
    WEEKDAY_SOURCE_CENTER_DEFAULT: '센터 기본 일정 기준',
    WEEKDAY_SOURCE_CHILD_OVERRIDE: '아동별 일정 기준',
}

PLAN_STATUS_ACTIVE = 'active'
PLAN_STATUS_COMPLETE = 'complete'
PLAN_STATUS_BEFORE_START = 'before_plan_start'
PLAN_STATUS_NO_PLAN = 'no_plan'
PLAN_STATUS_NO_SNAPSHOT = 'no_snapshot'
PLAN_STATUS_TARGET_ELAPSED = 'target_elapsed'
PLAN_STATUS_NO_REMAINING_DAYS = 'no_remaining_planned_days'

PEER_STALE_STATUSES = frozenset(('stale_target',))


def build_learning_section(payload, *, child_id=None, as_of=None):
    payload = payload or {}
    windows = {
        'current': payload.get('current_window') or {},
        'previous': payload.get('previous_window') or {},
    }
    subjects = payload.get('subjects') or {}
    observed_by_key = {}
    peer_by_key = {}
    if child_id is not None:
        summary = learning_progress_summary(child_id, as_of=as_of)
        for row in summary.get('subjects') or []:
            observed_by_key[row.get('subject_key')] = row
        window_days = payload.get('window_days') or DEFAULT_WINDOW_DAYS
        learning_peer = peer_learning_summary(child_id, as_of=as_of, window_days=window_days)
        for row in learning_peer.get('subjects') or []:
            peer_by_key[row.get('subject_key')] = row
    return {
        'observed_study_days': _observed_study_days_view(payload.get('observed_study_days') or {}),
        'subjects': [
            _subject_card(
                item,
                windows,
                observed=observed_by_key.get(item.get('subject_key')),
                canonical_peer=peer_by_key.get(item.get('subject_key')),
            )
            for item in subjects.values()
        ],
    }


def _observed_study_days_view(payload):
    current = payload.get('current')
    previous = payload.get('previous')
    return {
        'label': OBSERVED_STUDY_DAYS_LABEL,
        'hint': OBSERVED_STUDY_DAYS_HINT,
        'current': current,
        'previous': previous,
        'current_display': _days_text(current),
        'previous_display': _days_text(previous),
        'summary': _observed_summary(current, previous),
        'attendance': False,
    }


def _observed_summary(current, previous):
    current_text = _days_text(current)
    previous_text = _days_text(previous)
    if current_text is None and previous_text is None:
        return None
    parts = []
    if current_text is not None:
        parts.append(f'최근 {current_text}')
    if previous_text is not None:
        parts.append(f'이전 {previous_text}')
    return ' · '.join(parts)


def _subject_card(payload, windows, observed=None, canonical_peer=None):
    snapshot = payload.get('current_snapshot') or {}
    has_snapshot = snapshot.get('available') is True
    page_advance = _page_advance_view(payload.get('page_advance') or {})
    peer = _peer_view(payload.get('peer') or {}, has_snapshot=has_snapshot)
    plan = _plan_view(payload.get('plan') or {}, has_snapshot=has_snapshot)
    canonical = canonical_peer or {}
    recorded_on = snapshot.get('recorded_on') if has_snapshot else None
    page = snapshot.get('page') if has_snapshot else None
    return {
        'key': payload.get('subject_key'),
        'label': payload.get('subject_name'),
        'has_snapshot': has_snapshot,
        'empty_label': None if has_snapshot else NO_SNAPSHOT_LABEL,
        'textbook_title': snapshot.get('textbook_title') if has_snapshot else None,
        'page': page,
        'page_display': None if page is None else f'현재 { _pages_text(page) }',
        'recorded_on': recorded_on,
        'recorded_on_short': _short_date(recorded_on),
        'recorded_on_label': None if recorded_on is None else f'최근 기록 {_short_date(recorded_on)}',
        'page_advance': page_advance,
        'peer': peer,
        'plan': plan,
        'observed_progress': _observed_progress_view(observed),
        'performance_peer': canonical_peer_view(
            canonical.get('performance'),
            child_label='내 기록',
            median_label=SAME_GRADE_MEDIAN_LABEL,
            format_value=_percent_text,
            block_label=PERFORMANCE_PEER_LABEL,
        ),
        'coverage_peer': canonical_peer_view(
            canonical.get('coverage'),
            child_label='내 기록',
            median_label=SAME_BOOK_MEDIAN_LABEL,
            format_value=_percent_text,
            block_label=COVERAGE_PEER_LABEL,
        ),
        'evidence_rows': _evidence_rows(
            snapshot=snapshot,
            page_advance=payload.get('page_advance') or {},
            peer=payload.get('peer') or {},
            plan=payload.get('plan') or {},
            windows=windows,
            has_snapshot=has_snapshot,
        ),
    }


def _observed_progress_view(payload):
    payload = payload or {}
    progress = payload.get('progress') or {}
    forecast = payload.get('forecast') or {}
    status = payload.get('status') or 'no_plan'
    vs_target = payload.get('vs_target') or forecast.get('vs_target') or 'unavailable'
    ratio = progress.get('coverage_ratio')
    covered = progress.get('assigned_covered_page_count')
    denom = progress.get('assigned_denominator')
    observed_count = progress.get('observed_page_count')
    latest = progress.get('latest_observed_end_page')
    ratio_available = ratio is not None and covered is not None and denom is not None
    if ratio_available:
        percent = int(round(float(ratio) * 100))
        pages_display = f'{int(covered)} / {int(denom)}페이지'
        ratio_display = f'학습 기록 기준 {percent}%'
    elif observed_count is not None:
        pages_display = f'관측 {int(observed_count)}페이지'
        ratio_display = FORECAST_UNAVAILABLE_LABEL
    else:
        pages_display = FORECAST_UNAVAILABLE_LABEL
        ratio_display = FORECAST_UNAVAILABLE_LABEL
    forecast_available = forecast.get('available') is True
    earliest = forecast.get('earliest_date')
    latest_date = forecast.get('latest_date')
    reason = forecast.get('reason') or (status if status != 'exact' else None)
    if forecast_available and earliest is not None and latest_date is not None:
        forecast_display = f'{_iso_date(earliest)} ~ {_iso_date(latest_date)}'
        forecast_reason_label = None
    else:
        forecast_display = FORECAST_UNAVAILABLE_LABEL
        forecast_reason_label = FORECAST_REASON_LABELS.get(reason, '데이터 부족')
    return {
        'label': OBSERVED_PROGRESS_LABEL,
        'hint': OBSERVED_PROGRESS_HINT,
        'status': status,
        'pages_display': pages_display,
        'ratio_display': ratio_display,
        'ratio_available': ratio_available,
        'latest_display': None if latest is None else f'{OBSERVED_POSITION_NOTE} {int(latest)}p',
        'forecast_available': forecast_available,
        'forecast_display': forecast_display,
        'forecast_reason': reason,
        'forecast_reason_label': forecast_reason_label,
        'vs_target': vs_target,
        'vs_target_label': VS_TARGET_LABELS.get(vs_target, VS_TARGET_LABELS['unavailable']),
        'observed_complete': progress.get('observed_complete'),
    }


def _iso_date(value):
    if value is None:
        return None
    return value.isoformat() if hasattr(value, 'isoformat') else str(value)


def _page_advance_view(payload):
    current = payload.get('current') or {}
    previous = payload.get('previous') or {}
    current_available = current.get('available') is True
    trend_comparable = payload.get('comparable') is True
    current_value = current.get('value') if current_available else None
    return {
        'current_available': current_available,
        'current_value': current_value,
        'current_display': _advance_current_display(current_value) if current_available else None,
        'unavailable_label': None if current_available else INSUFFICIENT_LABEL,
        'trend_comparable': trend_comparable,
        'previous_display': (
            _advance_previous_display(previous.get('value'))
            if trend_comparable else None
        ),
        'delta_display': (
            _signed_pages(payload.get('delta'))
            if trend_comparable else None
        ),
        'trend_unavailable_label': (
            PERIOD_INSUFFICIENT_LABEL
            if current_available and not trend_comparable
            else None
        ),
    }


def _advance_current_display(value):
    if value is None:
        return None
    if value == 0:
        return '0p · 변화 없음'
    if value < 0:
        return f'기록상 {_signed_pages(value)}'
    return _signed_pages(value)


def _advance_previous_display(value):
    text = _signed_pages(value)
    if text is None:
        return None
    return f'이전 {text}'


def _peer_view(payload, *, has_snapshot):
    available = payload.get('available') is True
    n = payload.get('peer_n') or 0
    median = payload.get('peer_median')
    gap = payload.get('gap')
    current_page = payload.get('current_page')
    if not has_snapshot:
        return {
            'available': False,
            'n': 0,
            'unavailable_label': None,
            'median_display': None,
            'current_page_display': None,
            'n_display': None,
            'gap_display': None,
        }
    if available:
        return {
            'available': True,
            'n': n,
            'unavailable_label': None,
            'median_display': _pages_text(median),
            'current_page_display': _pages_text(current_page),
            'n_display': f'비교 {int(n)}명',
            'gap_display': None if gap is None else f'중앙값 대비 {_signed_pages(gap)}',
        }
    return {
        'available': False,
        'n': n,
        'unavailable_label': (
            PEER_STALE_LABEL
            if payload.get('status') in PEER_STALE_STATUSES
            else PEER_NONE_LABEL
        ),
        'median_display': None,
        'current_page_display': None,
        'n_display': None,
        'gap_display': None,
    }


def _plan_view(payload, *, has_snapshot):
    status = payload.get('status') or PLAN_STATUS_NO_SNAPSHOT
    estimated = payload.get('workload_kind') == WORKLOAD_KIND_ESTIMATED
    exact = payload.get('workload_kind') == WORKLOAD_KIND_EXACT
    remaining = payload.get('remaining_workload')
    days = payload.get('remaining_planned_study_days')
    required = payload.get('required_per_planned_day')
    target = payload.get('target_completion_date')
    start = payload.get('plan_start_date')
    view = {
        'status': status,
        'headline': None,
        'show_target': False,
        'target_display': None,
        'show_remaining': False,
        'remaining_display': None,
        'remaining_note': None,
        'show_days': False,
        'days_display': None,
        'show_required': False,
        'required_display': None,
        'required_note': None,
        'show_start': False,
        'start_display': None,
        'show_admin_link': False,
        'weekday_source_label': WEEKDAY_SOURCE_LABELS.get(payload.get('weekday_source')),
        'workload_kind': payload.get('workload_kind'),
        'estimated': estimated,
        'exact': exact,
    }
    if not has_snapshot or status == PLAN_STATUS_NO_SNAPSHOT:
        return view
    if status == PLAN_STATUS_NO_PLAN:
        view['headline'] = '등록된 교재 계획 없음'
        view['show_admin_link'] = True
        return view
    if status == PLAN_STATUS_COMPLETE:
        view['headline'] = '목표 분량 완료'
        return view
    if status == PLAN_STATUS_BEFORE_START:
        view['headline'] = (
            f'{_korean_date(start)} 시작 예정' if start is not None else '시작 예정'
        )
        view['show_start'] = start is not None
        view['start_display'] = _korean_date(start)
        view['show_target'] = target is not None
        view['target_display'] = _korean_date(target)
        return view
    if status == PLAN_STATUS_TARGET_ELAPSED:
        view['headline'] = '목표 완료일 경과'
        view['show_remaining'] = remaining is not None
        view['remaining_display'] = _remaining_display(remaining, estimated=estimated)
        view['remaining_note'] = _remaining_note(estimated)
        return view
    if status == PLAN_STATUS_NO_REMAINING_DAYS:
        view['headline'] = '남은 예정 학습일 없음'
        view['show_remaining'] = remaining is not None
        view['remaining_display'] = _remaining_display(remaining, estimated=estimated)
        view['remaining_note'] = _remaining_note(estimated)
        return view
    if status == PLAN_STATUS_ACTIVE:
        view['show_target'] = target is not None
        view['target_display'] = _korean_date(target)
        view['show_remaining'] = remaining is not None
        view['remaining_display'] = _remaining_display(remaining, estimated=estimated)
        view['remaining_note'] = _remaining_note(estimated)
        view['show_days'] = days is not None
        view['days_display'] = _days_text(days)
        view['show_required'] = required is not None
        view['required_display'] = _rate_text(required, approx=estimated)
        view['required_note'] = '(추정)' if estimated and required is not None else None
        return view
    view['headline'] = '학습 계획'
    return view


def _remaining_display(value, *, estimated):
    text = _pages_text(value)
    if text is None:
        return None
    return f'약 {text}' if estimated else text


def _remaining_note(estimated):
    return '(제외 페이지 20% 추정)' if estimated else None


def _evidence_rows(*, snapshot, page_advance, peer, plan, windows, has_snapshot):
    if not has_snapshot:
        return []
    current_adv = page_advance.get('current') or {}
    previous_adv = page_advance.get('previous') or {}
    rows = [
        ('최근 기간', _window_text(windows.get('current'))),
        ('이전 기간', _window_text(windows.get('previous'))),
        ('시작 기록', _snapshot_ref(current_adv.get('baseline'))),
        ('최근 기록', _snapshot_ref(current_adv.get('endpoint') or _snapshot_as_ref(snapshot))),
        ('이전 기간 시작 기록', _snapshot_ref(previous_adv.get('baseline'))),
        ('이전 기간 최근 기록', _snapshot_ref(previous_adv.get('endpoint'))),
    ]
    if has_snapshot:
        rows.append(('기록 현재성', FRESHNESS_NOTE))
    target = plan.get('target_completion_date')
    if target is not None:
        rows.append(('목표 완료일', target.isoformat() if hasattr(target, 'isoformat') else str(target)))
    kind = plan.get('workload_kind')
    if kind == WORKLOAD_KIND_ESTIMATED:
        rows.append(('학습량', '제외 페이지 20% 추정'))
    elif kind == WORKLOAD_KIND_EXACT:
        rows.append(('학습량', '제외 페이지 반영'))
    weekday_label = WEEKDAY_SOURCE_LABELS.get(plan.get('weekday_source'))
    if weekday_label and plan.get('status') not in (PLAN_STATUS_NO_PLAN, PLAN_STATUS_NO_SNAPSHOT):
        rows.append(('학습 일정', weekday_label))
    return [(label, value) for label, value in rows if value]


def _snapshot_as_ref(snapshot):
    if not snapshot:
        return None
    return {
        'recorded_on': snapshot.get('recorded_on'),
        'page': snapshot.get('page'),
    }


def _snapshot_ref(payload):
    if not payload:
        return None
    recorded_on = payload.get('recorded_on')
    page = payload.get('page')
    if recorded_on is None and page is None:
        return None
    date_text = recorded_on.isoformat() if hasattr(recorded_on, 'isoformat') else recorded_on
    if page is None:
        return date_text
    return f'{date_text} · {_pages_text(page)}'


def _window_text(window):
    if not window:
        return None
    start = window.get('start')
    end = window.get('end')
    if start is None or end is None:
        return None
    start_text = start.isoformat() if hasattr(start, 'isoformat') else start
    end_text = end.isoformat() if hasattr(end, 'isoformat') else end
    return f'{start_text} ~ {end_text}'


def canonical_peer_view(payload, *, child_label, median_label, format_value, block_label):
    payload = payload or {}
    tier = payload.get('display_tier') or DISPLAY_NONE
    child_display = format_value(payload.get('child_value'))
    show_median = tier in (DISPLAY_PRIMARY, DISPLAY_LIMITED)
    if show_median:
        status_label = None
    elif tier == DISPLAY_REFERENCE:
        status_label = PEER_REFERENCE_LABEL
    else:
        status_label = PEER_NONE_LABEL
    sample = payload.get('peer_sample_count')
    return {
        'label': block_label,
        'child_label': child_label,
        'median_label': median_label,
        'display_tier': tier,
        'available': payload.get('available') is True,
        'reason': payload.get('reason'),
        'show_median': show_median,
        'child_display': child_display,
        'median_display': format_value(payload.get('peer_median')) if show_median else None,
        'n_display': (
            f'비교 {int(sample)}명' if show_median and sample is not None else None
        ),
        'status_label': status_label,
        'metric': payload.get('metric'),
    }


def _percent_text(value):
    if value is None:
        return None
    return f'{int(round(float(value) * 100))}%'


def _points_text(value):
    if value is None:
        return None
    number = float(value)
    if number.is_integer():
        return f'{int(number)}점'
    return f'{round(number, 1):.1f}점'


def _days_text(value):
    if value is None:
        return None
    return f'{int(value)}일'


def _pages_text(value):
    if value is None:
        return None
    number = float(value)
    if number.is_integer():
        return f'{int(number)}p'
    return f'{round(number, 1):.1f}p'


def _signed_pages(value):
    if value is None:
        return None
    number = float(value)
    sign = '+' if number > 0 else ''
    return f'{sign}{_pages_text(value)}'


def _rate_text(value, *, approx=False):
    if value is None:
        return None
    body = f'{round(float(value), 1):.1f}p / 학습일'
    return f'약 {body}' if approx else body


def _short_date(value):
    if value is None:
        return None
    return f'{value.month}/{value.day}'


def _korean_date(value):
    if value is None:
        return None
    return f'{value.month}월 {value.day}일'
