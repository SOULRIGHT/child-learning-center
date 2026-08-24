"""Growth 화면용 view model. 새 분석 규칙을 만들지 않고 Step 1/2 결과를 조립한다."""
from __future__ import annotations

from features.growth.copy import fallback_copy
from features.growth.insights import generate_insight_candidates, top_candidates
from features.growth.metrics import metrics_bundle
from features.growth.windows import resolve_as_of
from feature_models import PROGRAM_TYPE_CHALLENGE, PROGRAM_TYPE_GENERAL, PROGRAM_TYPE_RECOMMENDED
from features.subjects import PROGRESS_SUBJECT_KEYS, subject_name

INSIGHT_LIMIT = 3

CATEGORY_LABELS = {
    'reading_activity': '독서 활동',
    'reading_completions': '완독',
    'progress_entries': '학습 진도',
    'points_period': '포인트',
    'reading_experience': '독서 경험',
}

METRIC_LABELS = {
    'reading_days': ('독서 기록일', '일'),
    'completed_count': ('완독', '권'),
    'progress_entry_count': ('학습 진도 기록', '건'),
    'period_points': ('기간 포인트', '점'),
    'paired_experience_rating': ('체감 난이도·재미', ''),
}

SOURCE_LABELS = {
    'reading_day.date': '독서 기록일',
    'child_reading.completed_on': '완독일',
    'learning_progress_entry.recorded_on': '학습 진도 기록일',
    'daily_points.date': '포인트 기록일',
    'child_reading.paired_experience_rating': '같은 책의 난이도·재미 평가',
}

PROGRAM_LABELS = {
    PROGRAM_TYPE_GENERAL: '일반',
    PROGRAM_TYPE_RECOMMENDED: '추천',
    PROGRAM_TYPE_CHALLENGE: '도전',
}


def _format_number(value):
    if value is None:
        return None
    if isinstance(value, float) and not value.is_integer():
        return f'{value:.1f}'
    return str(int(round(value)))


def _with_unit(value, unit):
    text = _format_number(value)
    if text is None:
        return None
    return f'{text}{unit}' if unit else text


def _signed(value, unit):
    if value is None:
        return None
    sign = '+' if value > 0 else ''
    return f'{sign}{_with_unit(value, unit)}'


def _window_text(window):
    if not window:
        return None
    start = window.get('start')
    end = window.get('end')
    if start is None or end is None:
        return None
    return f'{start.isoformat()} ~ {end.isoformat()}'


def _coverage_comparable(bundle):
    reading = (bundle.get('reading') or {}).get('comparable') or {}
    progress = (bundle.get('progress') or {}).get('comparable') or {}
    points = (bundle.get('points') or {}).get('comparable') or {}
    return any((
        reading.get('reading_days'),
        reading.get('completed'),
        reading.get('experience_rating_pair'),
        progress.get('progress'),
        points.get('points'),
    ))


def _empty_reason(bundle, insights):
    if insights:
        return None
    if _coverage_comparable(bundle):
        return 'no_change'
    return 'insufficient'


def _count_insight_payload(candidate):
    evidence = candidate.evidence or {}
    label, unit = METRIC_LABELS.get(candidate.metric_key, (candidate.metric_key, ''))
    current = evidence.get('current')
    previous = evidence.get('previous')
    delta = evidence.get('delta')
    return {
        'id': candidate.id,
        'category': candidate.category,
        'category_label': CATEGORY_LABELS.get(candidate.category, candidate.category),
        'direction': candidate.direction,
        'headline': fallback_copy(candidate.id).get('headline') or '',
        'comparison_line': (
            f'이전 {_with_unit(previous, unit)} → 최근 {_with_unit(current, unit)}'
            if current is not None and previous is not None
            else ''
        ),
        'delta_line': _signed(delta, unit) or '',
        'evidence_rows': _evidence_rows(candidate, label, unit),
    }


def _paired_insight_payload(candidate):
    evidence = candidate.evidence or {}
    current = evidence.get('current') or {}
    previous = evidence.get('previous') or {}
    delta = evidence.get('delta') or {}
    n_current = evidence.get('n_current')
    n_previous = evidence.get('n_previous')
    return {
        'id': candidate.id,
        'category': candidate.category,
        'category_label': CATEGORY_LABELS.get(candidate.category, candidate.category),
        'direction': candidate.direction,
        'headline': fallback_copy(candidate.id).get('headline') or '',
        'comparison_line': (
            f"난이도 {_format_number(previous.get('difficulty_average'))} → "
            f"{_format_number(current.get('difficulty_average'))} / "
            f"재미 {_format_number(previous.get('fun_average'))} → "
            f"{_format_number(current.get('fun_average'))}"
        ),
        'delta_line': (
            f"난이도 {_signed(delta.get('difficulty'), '')} / "
            f"재미 {_signed(delta.get('fun'), '')}"
        ),
        'evidence_rows': _evidence_rows(
            candidate, '체감 난이도·재미', '',
            extra=(
                ('이전 표본', None if n_previous is None else f'n={int(n_previous)}'),
                ('최근 표본', None if n_current is None else f'n={int(n_current)}'),
            ),
        ),
    }


def _evidence_rows(candidate, metric_label, unit, extra=()):
    evidence = candidate.evidence or {}
    rows = [
        ('분석 기간', None),
        ('이전', _window_text(evidence.get('previous_window'))),
        ('최근', _window_text(evidence.get('current_window'))),
        (metric_label, None),
    ]
    if candidate.metric_key == 'paired_experience_rating':
        current = evidence.get('current') or {}
        previous = evidence.get('previous') or {}
        delta = evidence.get('delta') or {}
        rows.extend((
            (
                '체감 난이도',
                f"{_format_number(previous.get('difficulty_average'))} → "
                f"{_format_number(current.get('difficulty_average'))} "
                f"({_signed(delta.get('difficulty'), '')})",
            ),
            (
                '재미',
                f"{_format_number(previous.get('fun_average'))} → "
                f"{_format_number(current.get('fun_average'))} "
                f"({_signed(delta.get('fun'), '')})",
            ),
        ))
    else:
        rows.append((
            metric_label,
            f"{_with_unit(evidence.get('previous'), unit)} → "
            f"{_with_unit(evidence.get('current'), unit)} "
            f"({_signed(evidence.get('delta'), unit)})",
        ))
    source = SOURCE_LABELS.get(evidence.get('source'), None)
    if source:
        rows.append(('자료', source))
    n_current = evidence.get('n_current')
    n_previous = evidence.get('n_previous')
    if candidate.metric_key != 'paired_experience_rating' and n_current is not None and n_previous is not None:
        if n_current != evidence.get('current') or n_previous != evidence.get('previous'):
            rows.append(('표본', f'이전 n={int(n_previous)} / 최근 n={int(n_current)}'))
    for label, value in extra:
        if value:
            rows.append((label, value))
    return [(label, value) for label, value in rows if value]


def _insight_payload(candidate):
    if candidate.metric_key == 'paired_experience_rating':
        return _paired_insight_payload(candidate)
    return _count_insight_payload(candidate)


def _rating_display(stats):
    stats = stats or {}
    count = stats.get('sample_count') or 0
    if count <= 0 or stats.get('average') is None:
        return {'text': '기록 없음', 'average': None, 'sample_count': 0}
    return {
        'text': f"{_format_number(stats.get('average'))} (n={int(count)})",
        'average': stats.get('average'),
        'sample_count': int(count),
    }


def _reading_section(payload):
    current = payload.get('current') or {}
    previous = payload.get('previous') or {}
    programs = []
    current_by = current.get('completed_by_program') or {}
    previous_by = previous.get('completed_by_program') or {}
    for key, label in PROGRAM_LABELS.items():
        programs.append({
            'key': key,
            'label': label,
            'current': int(current_by.get(key) or 0),
            'previous': int(previous_by.get(key) or 0),
        })
    return {
        'reading_days_current': current.get('reading_days'),
        'reading_days_previous': previous.get('reading_days'),
        'completed_count_current': current.get('completed_count'),
        'completed_count_previous': previous.get('completed_count'),
        'programs': programs,
        'difficulty': _rating_display(current.get('difficulty_rating')),
        'fun': _rating_display(current.get('fun_rating')),
    }


def _progress_section(payload):
    current = payload.get('current') or {}
    previous = payload.get('previous') or {}
    current_by = current.get('progress_entry_count_by_subject') or {}
    previous_by = previous.get('progress_entry_count_by_subject') or {}
    subjects = []
    snapshots = []
    latest = payload.get('latest_snapshot_by_subject') or {}
    for key in PROGRESS_SUBJECT_KEYS:
        subjects.append({
            'key': key,
            'label': subject_name(key),
            'current': int(current_by.get(key) or 0),
            'previous': int(previous_by.get(key) or 0),
        })
        snap = latest.get(key)
        if not snap:
            snapshots.append({
                'key': key,
                'label': subject_name(key),
                'textbook_title': None,
                'page': None,
                'recorded_on': None,
            })
            continue
        snapshots.append({
            'key': key,
            'label': subject_name(key),
            'textbook_title': snap.get('textbook_title'),
            'page': snap.get('page'),
            'recorded_on': snap.get('recorded_on'),
        })
    return {
        'entry_count_current': current.get('progress_entry_count'),
        'entry_count_previous': previous.get('progress_entry_count'),
        'by_subject': subjects,
        'latest_snapshots': snapshots,
    }


def _points_section(payload):
    current = payload.get('current') or {}
    previous = payload.get('previous') or {}
    cumulative = payload.get('cumulative_as_of')
    return {
        'period_points_current': current.get('period_points'),
        'period_points_previous': previous.get('period_points'),
        'activity_days_current': current.get('point_activity_days'),
        'activity_days_previous': previous.get('point_activity_days'),
        'manual_points_sum_current': current.get('manual_points_sum'),
        'cumulative_as_of': cumulative,
        'cumulative_unavailable': cumulative is None,
    }


def build_growth_view_model(child, *, as_of=None, is_viewer_mode=False):
    """metrics → candidates → top 3 → fallback copy → 화면용 dict."""
    as_of = resolve_as_of(as_of)
    bundle = metrics_bundle(child.id, as_of=as_of)
    candidates = generate_insight_candidates(bundle)
    top = top_candidates(candidates, limit=INSIGHT_LIMIT)
    insights = [_insight_payload(item) for item in top]
    reading = bundle.get('reading') or {}
    progress = bundle.get('progress') or {}
    points = bundle.get('points') or {}
    return {
        'child': child,
        'is_viewer_mode': bool(is_viewer_mode),
        'as_of': as_of,
        'window_days': reading.get('window_days') or 30,
        'current_window': reading.get('current_window'),
        'previous_window': reading.get('previous_window'),
        'insights': insights,
        'empty_reason': _empty_reason(bundle, insights),
        'reading': _reading_section(reading),
        'progress': _progress_section(progress),
        'points': _points_section(points),
        'bundle': bundle,
    }
