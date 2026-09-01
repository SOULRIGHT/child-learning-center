"""Deterministic friendly evidence rows. LLM이 만들지 않는다. raw evidence_id는 UI에 넣지 않는다."""
from __future__ import annotations

from features.growth.ai.validator import _unit_for
from features.subjects import subject_name

_UNIT_LABEL = {
    'day': '일',
    'book': '권',
    'point': '점',
    'page': '페이지',
    'count': '건',
    'person': '명',
}

_PERIOD = {
    'current': '최근',
    'previous': '이전',
    'delta': '변화',
    'previous_1': '직전 구간',
    'previous_2': '그 이전 구간',
}


def present_cited_evidence(packet, parsed_output):
    cited = _cited_ids(parsed_output)
    catalog = _catalog(packet)
    rows = []
    seen = set()
    for evidence_id in cited:
        fact = catalog.get(evidence_id)
        if fact is None:
            continue
        row = _format_row(evidence_id, fact, catalog)
        key = (row['label'], row['value'])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def _cited_ids(parsed_output):
    found = []
    seen = set()
    output = parsed_output if isinstance(parsed_output, dict) else {}
    items = [output.get('summary')]
    items.extend(output.get('observations') or [])
    items.extend(output.get('suggestions') or [])
    for item in items:
        if not isinstance(item, dict):
            continue
        for evidence_id in item.get('evidence_ids') or []:
            if isinstance(evidence_id, str) and evidence_id and evidence_id not in seen:
                seen.add(evidence_id)
                found.append(evidence_id)
    return found


def _catalog(packet):
    catalog = {}
    scope = (packet or {}).get('scope') or {}

    def walk(node, ctx):
        if isinstance(node, dict):
            next_ctx = dict(ctx)
            if isinstance(node.get('subject_label'), str) and node.get('subject_label'):
                next_ctx['subject_label'] = node['subject_label']
            if isinstance(node.get('subject_key'), str) and node.get('subject_key'):
                next_ctx['subject_key'] = node['subject_key']
            if isinstance(node.get('textbook_title'), str) and node.get('textbook_title'):
                next_ctx['textbook_title'] = node['textbook_title']
            if node.get('workload_kind') in ('exact', 'estimated'):
                next_ctx['workload_kind'] = node['workload_kind']
            if isinstance(node.get('window'), dict):
                next_ctx['window'] = node['window']
            if node.get('attendance') is False:
                next_ctx['not_attendance'] = True
            evidence_id = node.get('evidence_id')
            if isinstance(evidence_id, str) and evidence_id and evidence_id not in catalog:
                fact = dict(node)
                fact['_ctx'] = next_ctx
                catalog[evidence_id] = fact
            for value in node.values():
                walk(value, next_ctx)
        elif isinstance(node, list):
            for item in node:
                walk(item, ctx)

    walk(packet if isinstance(packet, dict) else {}, {'scope': scope})
    return catalog


def _format_row(evidence_id, fact, catalog):
    ctx = fact.get('_ctx') or {}
    label = _label(evidence_id, ctx)
    value = _value_text(evidence_id, fact, ctx, catalog)
    notes = []
    window = fact.get('window') or ctx.get('window')
    window_text = _window_text(window) or _scope_window_text(evidence_id, ctx.get('scope') or {})
    if window_text:
        notes.append(window_text)
    textbook = fact.get('textbook_title') or ctx.get('textbook_title')
    if textbook:
        notes.append(textbook)
    if ctx.get('workload_kind') == 'estimated' and _is_plan_numeric(evidence_id):
        notes.append('추정값')
    if 'observed_study_days' in evidence_id or ctx.get('not_attendance'):
        notes.append('출석일이 아니라 포인트가 기록된 날입니다')
    return {
        'label': label,
        'value': value,
        'note': ' · '.join(notes) if notes else None,
    }


def _label(evidence_id, ctx):
    subject = ctx.get('subject_label') or subject_name(ctx.get('subject_key')) or _subject_from_id(evidence_id)
    period = _period_word(evidence_id)
    if evidence_id.startswith('reading.activity_days'):
        return _join(period, '독서 활동일')
    if evidence_id.startswith('reading.completions'):
        return _join(period, '완독')
    if evidence_id.startswith('reading.rwb.activity_days'):
        return _join(_rwb_period(evidence_id), '최근 구간 독서 활동일')
    if evidence_id.startswith('reading.rwb.completions'):
        return _join(_rwb_period(evidence_id), '최근 구간 완독')
    if evidence_id.startswith('reading.experience.difficulty'):
        return _join(period, '체감 난이도')
    if evidence_id.startswith('reading.experience.fun'):
        return _join(period, '체감 재미')
    if evidence_id.startswith('reading.experience.n'):
        return _join(period, '평가 표본 수')
    if evidence_id.startswith('points.period') or evidence_id.startswith('points.rwb.period'):
        return _join(period or _rwb_period(evidence_id), '기간 포인트')
    if evidence_id == 'points.cumulative_as_of':
        return '현재 기준 누적 포인트'
    if evidence_id.startswith('learning.progress_entry_count'):
        return _join(period, '학습 진도 기록')
    if evidence_id.startswith('learning.observed_study_days'):
        return _join(period, '학습 활동일')
    if '.snapshot.current_page' in evidence_id:
        return _join(subject, '현재 페이지')
    if '.snapshot.recorded_on' in evidence_id:
        return _join(subject, '최근 진도 기록일')
    if '.page_advance.current' in evidence_id or '.page_advance.previous' in evidence_id:
        return _join(period, _join(subject, '진도 증가'))
    if '.page_advance.delta' in evidence_id:
        return _join(subject, '진도 증가 변화')
    if '.peer.median' in evidence_id:
        return _join(subject, '동일 학년·동일 교재 비교')
    if '.peer.n' in evidence_id:
        return _join(subject, '비교 인원')
    if '.peer.gap' in evidence_id:
        return _join(subject, '비교 차이')
    if '.peer.current_page' in evidence_id:
        return _join(subject, '비교용 현재 페이지')
    if '.plan.required_per_day' in evidence_id:
        return _join(subject, '학습 계획')
    if '.plan.remaining_workload' in evidence_id:
        return _join(subject, '남은 학습량')
    if '.plan.remaining_planned_days' in evidence_id:
        return _join(subject, '남은 학습일')
    if '.plan.workload_kind' in evidence_id:
        return _join(subject, '학습량 기준')
    if '.plan.target_completion_date' in evidence_id:
        return _join(subject, '목표 완료일')
    if '.rwb.page_advance' in evidence_id:
        return _join(_rwb_period(evidence_id), _join(subject, '최근 구간 진도'))
    return _join(subject, '성장 자료')


def _value_text(evidence_id, fact, ctx, catalog):
    if fact.get('available') is not True:
        return '자료 없음'
    value = fact.get('value')
    if '.peer.median' in evidence_id:
        median_text = _with_unit(value, 'page')
        n_fact = catalog.get(evidence_id.rsplit('.', 1)[0] + '.n') or {}
        if n_fact.get('available') is True:
            return f'중앙값 {median_text} / 비교 인원 {_with_unit(n_fact.get("value"), "person")}'
        return f'중앙값 {median_text}'
    if '.plan.required_per_day' in evidence_id:
        prefix = '학습일당 약 ' if ctx.get('workload_kind') == 'estimated' else '학습일당 '
        return prefix + _with_unit(value, 'page')
    if '.plan.workload_kind' in evidence_id:
        return '추정' if value == 'estimated' else '확정'
    unit = _unit_for(evidence_id)
    if unit:
        return _with_unit(value, unit)
    if isinstance(value, bool):
        return '예' if value else '아니오'
    return str(value)


def _with_unit(value, unit):
    label = _UNIT_LABEL.get(unit, '')
    if isinstance(value, float) and not value.is_integer():
        number = f'{value:g}'
    else:
        try:
            number = str(int(round(value)))
        except (TypeError, ValueError):
            return str(value)
    return f'{number}{label}' if label else number


def _window_text(window):
    if not isinstance(window, dict):
        return None
    start = window.get('start')
    end = window.get('end')
    if start and end:
        return f'{start} ~ {end}'
    return None


def _scope_window_text(evidence_id, scope):
    if '.current' in evidence_id or evidence_id.endswith('.current_page'):
        return _window_text(scope.get('current_window'))
    if '.previous' in evidence_id and 'previous_1' not in evidence_id and 'previous_2' not in evidence_id:
        return _window_text(scope.get('previous_window'))
    return None


def _period_word(evidence_id):
    for key, label in _PERIOD.items():
        if evidence_id.endswith('.' + key) or f'.{key}' in evidence_id.split('.rwb')[-1]:
            if key in ('previous_1', 'previous_2'):
                continue
            if evidence_id.endswith('.' + key):
                return label
    return None


def _rwb_period(evidence_id):
    if evidence_id.endswith('.current') or '.current' in evidence_id.rsplit('.', 1)[0]:
        if evidence_id.endswith('.current'):
            return '최근 구간'
    if evidence_id.endswith('.previous_1'):
        return '직전 구간'
    if evidence_id.endswith('.previous_2'):
        return '그 이전 구간'
    if evidence_id.endswith('.historical_best'):
        return '최근 3구간 최고'
    if evidence_id.endswith('.margin'):
        return '최고 기록과 차이'
    return None


def _subject_from_id(evidence_id):
    if not evidence_id.startswith('learning.'):
        return None
    parts = evidence_id.split('.')
    if len(parts) < 3:
        return None
    key = parts[1]
    if key in ('progress_entry_count', 'observed_study_days'):
        return None
    return subject_name(key) or None


def _is_plan_numeric(evidence_id):
    return any(token in evidence_id for token in (
        '.plan.remaining_workload',
        '.plan.required_per_day',
        '.plan.remaining_planned_days',
    ))


def _join(*parts):
    return ' '.join(part for part in parts if part)
