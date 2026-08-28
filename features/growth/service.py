"""Growth 화면용 view model. 새 분석 규칙을 만들지 않고 Step 1/2 결과를 조립한다."""
from __future__ import annotations

from features.growth.copy import fallback_copy
from features.growth.insights import generate_insight_candidates, top_candidates
from features.growth.learning_view import build_learning_section
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


def _numeric_delta(current, previous):
    if current is None or previous is None:
        return None
    return current - previous


def _format_grouped(value):
    if value is None:
        return None
    if isinstance(value, float) and not value.is_integer():
        return f'{value:,.1f}'
    return f'{int(round(value)):,}'


def _tone_for(delta):
    if delta is None:
        return 'neutral'
    if delta > 0:
        return 'up'
    if delta < 0:
        return 'down'
    return 'flat'


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
        'comparison_short': (
            f'{_with_unit(previous, unit)} → {_with_unit(current, unit)}'
            if current is not None and previous is not None
            else ''
        ),
        'delta_line': _signed(delta, unit) or '',
        'evidence_rows': _evidence_rows(candidate, label, unit),
        'evidence': _count_evidence_view(candidate, label, unit),
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
        'comparison_short': (
            f"난이도 {_format_number(previous.get('difficulty_average'))} → "
            f"{_format_number(current.get('difficulty_average'))}"
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
        'evidence': _paired_evidence_view(candidate),
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


def _count_evidence_view(candidate, metric_label, unit):
    evidence = candidate.evidence or {}
    previous = evidence.get('previous')
    current = evidence.get('current')
    delta = evidence.get('delta')
    return {
        'kind': 'count',
        'metric_label': metric_label,
        'source_label': SOURCE_LABELS.get(evidence.get('source')),
        'previous_window': _window_text(evidence.get('previous_window')),
        'current_window': _window_text(evidence.get('current_window')),
        'previous': previous,
        'current': current,
        'delta': delta,
        'previous_display': _with_unit(previous, unit),
        'current_display': _with_unit(current, unit),
        'delta_display': _signed(delta, unit),
        'unit': unit,
    }


def _paired_evidence_view(candidate):
    evidence = candidate.evidence or {}
    return {
        'kind': 'paired',
        'metric_label': '체감 난이도·재미',
        'source_label': SOURCE_LABELS.get(evidence.get('source')),
        'previous_window': _window_text(evidence.get('previous_window')),
        'current_window': _window_text(evidence.get('current_window')),
        'previous': evidence.get('previous'),
        'current': evidence.get('current'),
        'delta': evidence.get('delta'),
        'n_previous': evidence.get('n_previous'),
        'n_current': evidence.get('n_current'),
    }


def _insight_payload(candidate):
    if candidate.metric_key == 'paired_experience_rating':
        return _paired_insight_payload(candidate)
    return _count_insight_payload(candidate)


def _rating_display(stats):
    stats = stats or {}
    count = stats.get('sample_count') or 0
    if count <= 0 or stats.get('average') is None:
        return {
            'text': '기록 없음',
            'average': None,
            'sample_count': 0,
            'out_of_five': None,
        }
    average = stats.get('average')
    return {
        'text': f"{_format_number(average)} (n={int(count)})",
        'average': average,
        'sample_count': int(count),
        'out_of_five': f'{_format_number(average)} / 5',
    }


def _reading_section(payload):
    current = payload.get('current') or {}
    previous = payload.get('previous') or {}
    comparable = payload.get('comparable') or {}
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
        'reading_days_comparable': comparable.get('reading_days') is True,
        'completed_count_current': current.get('completed_count'),
        'completed_count_previous': previous.get('completed_count'),
        'completed_comparable': comparable.get('completed') is True,
        'programs': programs,
        'difficulty': _rating_display(current.get('difficulty_rating')),
        'fun': _rating_display(current.get('fun_rating')),
    }


def _progress_section(payload):
    current = payload.get('current') or {}
    previous = payload.get('previous') or {}
    comparable = payload.get('comparable') or {}
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
        'comparable': comparable.get('progress') is True,
        'by_subject': subjects,
        'latest_snapshots': snapshots,
    }


def _points_section(payload):
    current = payload.get('current') or {}
    previous = payload.get('previous') or {}
    comparable = (payload.get('comparable') or {}).get('points') is True
    cumulative = payload.get('cumulative_as_of')
    period_current = current.get('period_points')
    period_previous = previous.get('period_points')
    period_delta = (
        _numeric_delta(period_current, period_previous)
        if comparable else None
    )
    return {
        'period_points_current': period_current,
        'period_points_previous': period_previous,
        'period_points_comparable': comparable,
        'period_points_delta': period_delta,
        'period_points_current_display': (
            None if period_current is None else f'{_format_grouped(period_current)}점'
        ),
        'period_points_previous_display': (
            None if not comparable or period_previous is None
            else f'{_format_grouped(period_previous)}점'
        ),
        'period_points_delta_display': (
            None if period_delta is None else (
                f'+{_format_grouped(period_delta)}점' if period_delta > 0
                else f'{_format_grouped(period_delta)}점'
            )
        ),
        'activity_days_current': current.get('point_activity_days'),
        'activity_days_previous': previous.get('point_activity_days'),
        'manual_points_sum_current': current.get('manual_points_sum'),
        'manual_points_sum_current_display': (
            None if current.get('manual_points_sum') is None
            else f"{_format_grouped(current.get('manual_points_sum'))}점"
        ),
        'cumulative_as_of': cumulative,
        'cumulative_unavailable': cumulative is None,
        'cumulative_display': (
            None if cumulative is None else f'{_format_grouped(cumulative)}점'
        ),
    }


def _kpi_item(key, label, current, previous, unit, *, comparable, grouped=False):
    comparison_available = (
        comparable is True and current is not None and previous is not None
    )
    visible_previous = previous if comparison_available else None
    delta = (
        _numeric_delta(current, previous)
        if comparison_available else None
    )
    if grouped:
        current_display = None if current is None else f'{_format_grouped(current)}{unit}'
        previous_display = (
            None if visible_previous is None
            else f'{_format_grouped(visible_previous)}{unit}'
        )
        if delta is None:
            delta_display = None
        elif delta > 0:
            delta_display = f'+{_format_grouped(delta)}{unit}'
        else:
            delta_display = f'{_format_grouped(delta)}{unit}'
    else:
        current_display = _with_unit(current, unit)
        previous_display = _with_unit(visible_previous, unit)
        delta_display = _signed(delta, unit) if delta is not None else None
    return {
        'key': key,
        'label': label,
        'current': current,
        'previous': visible_previous,
        'delta': delta,
        'unit': unit,
        'comparable': comparable is True,
        'comparison_available': comparison_available,
        'current_display': current_display,
        'previous_display': previous_display,
        'comparison_display': (
            f'{previous_display} → {current_display}'
            if comparison_available else None
        ),
        'delta_display': delta_display,
        'change_display': '변화 없음' if delta == 0 else delta_display,
        'tone': _tone_for(delta) if comparison_available else None,
    }


def _kpi_strip(reading, progress, points):
    return [
        _kpi_item(
            'reading_days', '최근 독서 기록일',
            reading.get('reading_days_current'),
            reading.get('reading_days_previous'),
            '일',
            comparable=reading.get('reading_days_comparable'),
        ),
        _kpi_item(
            'completed_count', '최근 완독 권수',
            reading.get('completed_count_current'),
            reading.get('completed_count_previous'),
            '권',
            comparable=reading.get('completed_comparable'),
        ),
        _kpi_item(
            'progress_entries', '최근 학습 진도 기록',
            progress.get('entry_count_current'),
            progress.get('entry_count_previous'),
            '건',
            comparable=progress.get('comparable'),
        ),
        _kpi_item(
            'period_points', '최근 기간 포인트',
            points.get('period_points_current'),
            points.get('period_points_previous'),
            '점',
            comparable=points.get('period_points_comparable'),
            grouped=True,
        ),
    ]


def _pair_bar(label, previous, current, unit):
    if previous is None or current is None:
        return None
    peak = max(previous, current)
    return {
        'label': label,
        'unit': unit,
        'previous': previous,
        'current': current,
        'previous_display': _with_unit(previous, unit),
        'current_display': _with_unit(current, unit),
        'previous_pct': 0 if peak == 0 else (previous / peak * 100),
        'current_pct': 0 if peak == 0 else (current / peak * 100),
        'delta': _numeric_delta(current, previous),
        'delta_display': _signed(_numeric_delta(current, previous), unit),
    }


def _charts(reading, progress, points):
    activity_bars = []
    activity_labels = []
    activity_previous = []
    activity_current = []
    pairs = (
        (
            '독서 기록일', '일',
            reading.get('reading_days_previous'),
            reading.get('reading_days_current'),
            reading.get('reading_days_comparable'),
        ),
        (
            '완독', '권',
            reading.get('completed_count_previous'),
            reading.get('completed_count_current'),
            reading.get('completed_comparable'),
        ),
        (
            '학습 진도 기록', '건',
            progress.get('entry_count_previous'),
            progress.get('entry_count_current'),
            progress.get('comparable'),
        ),
    )
    for label, unit, previous, current, comparable in pairs:
        if comparable is not True:
            continue
        bar = _pair_bar(label, previous, current, unit)
        if bar is None:
            continue
        activity_bars.append(bar)
        activity_labels.append(label)
        activity_previous.append(previous)
        activity_current.append(current)
    period_previous = points.get('period_points_previous')
    period_current = points.get('period_points_current')
    points_chart = None
    if (
        points.get('period_points_comparable') is True
        and period_previous is not None
        and period_current is not None
    ):
        points_chart = {
            'labels': ['이전 기간', '최근 기간'],
            'values': [period_previous, period_current],
        }
    return {
        'activity_bars': activity_bars,
        'activity': {
            'labels': activity_labels,
            'previous': activity_previous,
            'current': activity_current,
        } if activity_labels else None,
        'points': points_chart,
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
    learning = bundle.get('learning') or {}
    reading_view = _reading_section(reading)
    progress_view = _progress_section(progress)
    points_view = _points_section(points)
    learning_view = build_learning_section(learning)
    return {
        'child': child,
        'is_viewer_mode': bool(is_viewer_mode),
        'as_of': as_of,
        'window_days': reading.get('window_days') or 30,
        'current_window': reading.get('current_window'),
        'previous_window': reading.get('previous_window'),
        'insights': insights,
        'empty_reason': _empty_reason(bundle, insights),
        'reading': reading_view,
        'progress': progress_view,
        'points': points_view,
        'learning': learning_view,
        'kpis': _kpi_strip(reading_view, progress_view, points_view),
        'charts': _charts(reading_view, progress_view, points_view),
        'bundle': bundle,
    }
