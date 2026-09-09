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
    return present_cited_evidence_bundle(packet, parsed_output)['items']


def present_cited_evidence_bundle(packet, parsed_output):
    """cited evidence를 모두 유지한 채 UI용 group/compact만 만든다."""
    catalog = _catalog(packet)
    rows = _cited_rows(packet, parsed_output, catalog)
    groups = _group_rows(rows, catalog)
    return {
        'total': len(rows),
        'items': [_public_item(row) for row in rows],
        'groups': groups,
        'chips': ' · '.join(
            f"{group['short_label']} {group['count']}" for group in groups
        ),
    }


def _cited_rows(packet, parsed_output, catalog=None):
    cited = _cited_ids(parsed_output)
    catalog = catalog if catalog is not None else _catalog(packet)
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
        row['evidence_id'] = evidence_id
        rows.append(row)
    return rows


def _public_item(row):
    return {
        'label': row.get('label'),
        'value': row.get('value'),
        'note': row.get('note'),
    }


def _cited_ids(parsed_output):
    found = []
    seen = set()
    output = parsed_output if isinstance(parsed_output, dict) else {}
    items = [
        output.get('priority_insight'),
        output.get('interpretation'),
        output.get('next_check'),
        output.get('summary'),
    ]
    items.extend(output.get('observations') or [])
    items.extend(output.get('next_actions') or [])
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
    if evidence_id.startswith('reading.recommended.activity_days'):
        return _join(period, '추천도서 활동일')
    if evidence_id.startswith('reading.recommended.completions'):
        return _join(period, '추천도서 완독')
    if evidence_id.startswith('reading.activity_days'):
        return _join(period, '독서 활동일')
    if evidence_id.startswith('reading.completions'):
        return _join(period, '완독 수')
    if evidence_id.startswith('rewards.exemption.usage.peer.median'):
        return '동일 학년 면제권 사용 중앙값'
    if evidence_id.startswith('rewards.exemption.usage.peer.n'):
        return '면제권 비교 인원'
    if evidence_id.startswith('rewards.exemption.usage'):
        return _join(period, '면제권 사용')
    if evidence_id.startswith('rewards.manual.event_count'):
        return _join(period, '추가 포인트 횟수')
    if evidence_id.startswith('rewards.manual.points.peer.median'):
        return '동일 학년 추가 포인트 중앙값'
    if evidence_id.startswith('rewards.manual.points.peer.n'):
        return '추가 포인트 비교 인원'
    if evidence_id.startswith('rewards.manual.points'):
        return _join(period, '추가 포인트')
    if evidence_id.startswith('rewards.reading_event.points'):
        return _join(period, '독서 보상 포인트')
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
        return _join(period, '직접 입력 진도 기록')
    if evidence_id.startswith('learning.observed_study_days'):
        return _join(period, '학습 활동일')
    if '.performance.rate.' in evidence_id:
        return _join(period, _join(subject, '학습 수행률'))
    if '.performance.studied_days' in evidence_id:
        return _join(period, _join(subject, '학습일'))
    if '.performance.expected_days' in evidence_id:
        return _join(period, _join(subject, '예정 학습일'))
    if '.performance.confirmation.' in evidence_id:
        return _join(period, _join(subject, '확인률'))
    if '.performance.confirmation_delta_pp' in evidence_id:
        return _join(subject, '확인률 변화')
    if '.performance.delta_pp' in evidence_id:
        return _join(subject, '수행률 변화')
    if '.progress.coverage_ratio' in evidence_id:
        return _join(subject, '관측 기반 진도율')
    if '.progress.observed_page_count' in evidence_id:
        return _join(subject, '관측 페이지')
    if '.progress.assigned_covered_page_count' in evidence_id:
        return _join(subject, '배정 페이지 중 관측')
    if '.progress.assigned_denominator' in evidence_id:
        return _join(subject, '배정 학습페이지')
    if '.progress.latest_observed_end_page' in evidence_id:
        return _join(subject, '참고 위치')
    if '.forecast.earliest_date' in evidence_id:
        return _join(subject, '완료예상 빠른 날짜')
    if '.forecast.latest_date' in evidence_id:
        return _join(subject, '완료예상 늦은 날짜')
    if '.performance_peer.child_value' in evidence_id:
        return _join(subject, '내 학습 수행률')
    if '.performance_peer.peer_median' in evidence_id:
        return _join(subject, '같은 학년·같은 과목 수행률 중앙값')
    if '.performance_peer.difference' in evidence_id:
        return _join(subject, '수행률 또래 차이')
    if '.performance_peer.n' in evidence_id:
        return _join(subject, '수행률 비교 인원')
    if '.coverage_peer.child_value' in evidence_id:
        return _join(subject, '내 관측 기반 진도율')
    if '.coverage_peer.peer_median' in evidence_id:
        return _join(subject, '같은 교재 진도율 중앙값')
    if '.coverage_peer.difference' in evidence_id:
        return _join(subject, '진도율 또래 차이')
    if '.coverage_peer.n' in evidence_id:
        return _join(subject, '진도 비교 인원')
    if evidence_id.startswith('points.peer.child_value'):
        return '내 기간 포인트'
    if evidence_id.startswith('points.peer.peer_median'):
        return '같은 학년 포인트 중앙값'
    if evidence_id.startswith('points.peer.difference'):
        return '포인트 또래 차이'
    if evidence_id.startswith('points.peer.n'):
        return '포인트 비교 인원'
    if evidence_id.startswith('reading.analysis.observation'):
        return '독서 관찰'
    if evidence_id.startswith('reading.analysis.limitation'):
        return '독서 분석 한계'
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
        return _unavailable_text(evidence_id, fact)
    value = fact.get('value')
    if 'exemption.usage' in evidence_id and '.peer.n' not in evidence_id:
        try:
            return f'{int(round(value))}회'
        except (TypeError, ValueError):
            return str(value)
    if 'manual.event_count' in evidence_id:
        try:
            return f'{int(round(value))}회'
        except (TypeError, ValueError):
            return str(value)
    if _is_ratio_id(evidence_id):
        return _percent_value(value)
    if 'delta_pp' in evidence_id:
        return _pp_value(value)
    if '.forecast.earliest_date' in evidence_id or '.forecast.latest_date' in evidence_id:
        return f'{value} 예상' if value else '계산할 수 없음'
    if '.peer.median' in evidence_id and not evidence_id.startswith('rewards.') and 'coverage_peer' not in evidence_id and 'performance_peer' not in evidence_id:
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


_FORECAST_REASON_LABELS = {
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

_PEER_UNAVAILABLE_REASONS = frozenset((
    'no_peers',
    'insufficient_peers',
    'textbook_mismatch',
    'reference_only',
    'child_unavailable',
    'child_confirmation_unavailable',
    'child_confirmation_excluded',
    'excluded_from_stats',
    'none',
))


def _unavailable_text(evidence_id, fact):
    status = fact.get('status') or ''
    if status in _FORECAST_REASON_LABELS:
        return _FORECAST_REASON_LABELS[status]
    if (
        'peer' in evidence_id
        and status in _PEER_UNAVAILABLE_REASONS
    ) or (
        ('performance_peer' in evidence_id or 'coverage_peer' in evidence_id or evidence_id.startswith('points.peer.'))
        and status not in ('insufficient_history',)
        and fact.get('available') is not True
        and '.n' not in evidence_id
    ):
        if status == 'no_plan':
            return '교재 계획 없음'
        return '또래 비교 자료 부족'
    if status == 'insufficient_history':
        return '이전 기간 비교 자료 부족'
    if status == 'unavailable':
        return '계산할 수 없음'
    if status == 'no_plan':
        return '교재 계획 없음'
    return '자료 없음'


def _is_ratio_id(evidence_id):
    return any(token in evidence_id for token in (
        '.performance.rate.',
        '.performance.confirmation.',
        '.progress.coverage_ratio',
        '.performance_peer.child_value',
        '.performance_peer.peer_median',
        '.performance_peer.difference',
        '.coverage_peer.child_value',
        '.coverage_peer.peer_median',
        '.coverage_peer.difference',
    ))


def _percent_value(value):
    try:
        return f'{int(round(float(value) * 100))}%'
    except (TypeError, ValueError):
        return str(value)


def _pp_value(value):
    try:
        number = float(value)
        sign = '+' if number > 0 else ''
        if number.is_integer():
            return f'{sign}{int(number)}%p'
        return f'{sign}{number:g}%p'
    except (TypeError, ValueError):
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


_GROUP_ORDER = (
    'reading',
    'korean',
    'math',
    'ssen',
    'learning_activity',
    'rewards',
    'other',
)

_KNOWN_SUBJECT_GROUPS = {
    'korean': ('korean', '국어 학습', '국어'),
    'math': ('math', '수학 학습', '수학'),
    'ssen': ('ssen', '쎈 학습', '쎈'),
}


def _group_spec(evidence_id, ctx):
    if evidence_id.startswith('reading.'):
        return 'reading', '독서 활동', '독서'
    if evidence_id.startswith('rewards.') or evidence_id.startswith('reading.recommended'):
        if evidence_id.startswith('reading.recommended'):
            return 'reading', '독서 활동', '독서'
        return 'rewards', '보상/활동', '보상'
    if (
        evidence_id.startswith('learning.observed_study_days')
        or evidence_id.startswith('learning.progress_entry_count')
    ):
        return 'learning_activity', '학습 활동', '학습 활동'
    subject_key = ctx.get('subject_key') or _subject_key_from_id(evidence_id)
    known = _KNOWN_SUBJECT_GROUPS.get(subject_key)
    if known:
        return known
    if subject_key:
        name = ctx.get('subject_label') or subject_name(subject_key) or '학습'
        return subject_key, f'{name} 학습', name
    return 'other', '기타', '기타'


def _subject_key_from_id(evidence_id):
    if not evidence_id.startswith('learning.'):
        return None
    parts = evidence_id.split('.')
    if len(parts) < 3:
        return None
    key = parts[1]
    if key in ('progress_entry_count', 'observed_study_days'):
        return None
    return key


def _group_rows(rows, catalog):
    buckets = {}
    extras = []
    for row in rows:
        key, label, short = _group_spec(row['evidence_id'], (catalog.get(row['evidence_id']) or {}).get('_ctx') or {})
        if key not in _GROUP_ORDER and key not in buckets:
            extras.append(key)
        bucket = buckets.setdefault(key, {
            'key': key,
            'label': label,
            'short_label': short,
            'items': [],
        })
        bucket['items'].append(_public_item(row))
        bucket.setdefault('_ids', []).append(row['evidence_id'])
    order = []
    for key in _GROUP_ORDER:
        if key == 'learning_activity':
            for extra in extras:
                if extra not in order and extra in buckets:
                    order.append(extra)
        if key in buckets:
            order.append(key)
    for key in extras:
        if key not in order:
            order.append(key)
    groups = []
    for key in order:
        bucket = buckets[key]
        ids = bucket.pop('_ids')
        items = bucket['items']
        groups.append({
            'key': bucket['key'],
            'label': bucket['label'],
            'short_label': bucket['short_label'],
            'count': len(items),
            'compact': _compact_for(key, ids, catalog),
            'note': _group_note(key, ids),
            'items': items,
        })
    return groups


def _group_note(group_key, ids):
    if group_key == 'learning_activity' and any('observed_study_days' in eid for eid in ids):
        return '포인트가 기록된 학습 활동일 기준이며 출석일이 아닙니다.'
    return None


def _compact_for(group_key, ids, catalog):
    if group_key == 'reading':
        return _compact_reading(ids, catalog)
    if group_key == 'learning_activity':
        return _compact_learning_activity(ids, catalog)
    if group_key == 'rewards':
        return _compact_rewards(ids, catalog)
    if group_key in _KNOWN_SUBJECT_GROUPS or (
        group_key not in ('other', 'reading', 'learning_activity')
        and any(eid.startswith('learning.') for eid in ids)
    ):
        return _compact_subject(ids, catalog)
    if group_key == 'other':
        return _compact_other(ids, catalog)
    return []


def _simple_value(evidence_id, catalog):
    fact = catalog.get(evidence_id)
    if fact is None:
        return None
    if fact.get('available') is not True:
        return _unavailable_text(evidence_id, fact)
    unit = _unit_for(evidence_id)
    if unit and not _is_ratio_id(evidence_id):
        return _with_unit(fact.get('value'), unit)
    return _value_text(evidence_id, fact, fact.get('_ctx') or {}, catalog)


def _compact_pair(label, parts):
    bits = [f'{name} {value}' for name, value in parts if value]
    if not bits:
        return None
    return {'label': label, 'value': ' · '.join(bits)}


def _id_in(ids, exact):
    return exact if exact in ids else None


def _id_has(ids, token):
    for evidence_id in ids:
        if token in evidence_id:
            return evidence_id
    return None


def _compact_reading(ids, catalog):
    rows = []
    current = _compact_pair('최근 30일', (
        ('활동', _simple_value('reading.activity_days.current', catalog) if _id_in(ids, 'reading.activity_days.current') else None),
        ('완독', _simple_value('reading.completions.current', catalog) if _id_in(ids, 'reading.completions.current') else None),
    ))
    previous = _compact_pair('이전 30일', (
        ('활동', _simple_value('reading.activity_days.previous', catalog) if _id_in(ids, 'reading.activity_days.previous') else None),
        ('완독', _simple_value('reading.completions.previous', catalog) if _id_in(ids, 'reading.completions.previous') else None),
    ))
    if current:
        rows.append(current)
    if previous:
        rows.append(previous)
    rec_current = _compact_pair('최근 추천도서', (
        ('활동', _simple_value('reading.recommended.activity_days.current', catalog) if _id_in(ids, 'reading.recommended.activity_days.current') else None),
        ('완독', _simple_value('reading.recommended.completions.current', catalog) if _id_in(ids, 'reading.recommended.completions.current') else None),
    ))
    rec_previous = _compact_pair('이전 추천도서', (
        ('활동', _simple_value('reading.recommended.activity_days.previous', catalog) if _id_in(ids, 'reading.recommended.activity_days.previous') else None),
        ('완독', _simple_value('reading.recommended.completions.previous', catalog) if _id_in(ids, 'reading.recommended.completions.previous') else None),
    ))
    if rec_current:
        rows.append(rec_current)
    if rec_previous:
        rows.append(rec_previous)
    for evidence_id in ids:
        if evidence_id.startswith('reading.analysis.observation'):
            rows.append({'label': '독서 관찰', 'value': _simple_value(evidence_id, catalog)})
    return rows


def _compact_rewards(ids, catalog):
    rows = []
    current = _compact_pair('최근 30일', (
        ('면제권', _display_value('rewards.exemption.usage.current', catalog) if _id_in(ids, 'rewards.exemption.usage.current') else None),
        ('추가 포인트', _display_value('rewards.manual.event_count.current', catalog) if _id_in(ids, 'rewards.manual.event_count.current') else None),
    ))
    previous = _compact_pair('이전 30일', (
        ('면제권', _display_value('rewards.exemption.usage.previous', catalog) if _id_in(ids, 'rewards.exemption.usage.previous') else None),
        ('추가 포인트', _display_value('rewards.manual.event_count.previous', catalog) if _id_in(ids, 'rewards.manual.event_count.previous') else None),
    ))
    if current:
        rows.append(current)
    if previous:
        rows.append(previous)
    return rows


def _display_value(evidence_id, catalog):
    fact = catalog.get(evidence_id)
    if fact is None:
        return None
    return _value_text(evidence_id, fact, fact.get('_ctx') or {}, catalog)


def _compact_learning_activity(ids, catalog):
    rows = []
    current = _id_in(ids, 'learning.observed_study_days.current')
    previous = _id_in(ids, 'learning.observed_study_days.previous')
    if current:
        rows.append({'label': '최근', 'value': _simple_value(current, catalog)})
    if previous:
        rows.append({'label': '이전', 'value': _simple_value(previous, catalog)})
    return rows


def _compact_subject(ids, catalog):
    rows = []
    mapping = (
        ('학습 수행률', '.performance.rate.current'),
        ('관측 기반 진도율', '.progress.coverage_ratio'),
        ('같은 학년·같은 과목 수행률 중앙값', '.performance_peer.peer_median'),
        ('같은 교재 진도율 중앙값', '.coverage_peer.peer_median'),
        ('수행률 비교 인원', '.performance_peer.n'),
        ('진도 비교 인원', '.coverage_peer.n'),
    )
    for label, token in mapping:
        evidence_id = _id_has(ids, token)
        if not evidence_id:
            continue
        rows.append({'label': label, 'value': _simple_value(evidence_id, catalog)})
    forecast = _compact_forecast(ids, catalog)
    if forecast:
        rows.append(forecast)
    return rows


def _compact_forecast(ids, catalog):
    earliest_id = _id_has(ids, '.forecast.earliest_date')
    latest_id = _id_has(ids, '.forecast.latest_date')
    if not earliest_id and not latest_id:
        return None
    earliest_fact = catalog.get(earliest_id) if earliest_id else None
    latest_fact = catalog.get(latest_id) if latest_id else None
    earliest_ok = earliest_fact is not None and earliest_fact.get('available') is True
    latest_ok = latest_fact is not None and latest_fact.get('available') is True
    if earliest_ok and latest_ok:
        earliest = earliest_fact.get('value')
        latest = latest_fact.get('value')
        if earliest == latest:
            return {'label': '완료예상', 'value': f'{earliest} 예상'}
        return {'label': '완료예상', 'value': f'{earliest} ~ {latest} 예상'}
    if earliest_ok:
        return {'label': '완료예상', 'value': f'{earliest_fact.get("value")} 예상'}
    if latest_ok:
        return {'label': '완료예상', 'value': f'{latest_fact.get("value")} 예상'}
    fact = earliest_fact or latest_fact or {}
    return {
        'label': '완료예상',
        'value': _unavailable_text(earliest_id or latest_id, fact),
    }


def _compact_other(ids, catalog):
    rows = []
    current = _id_in(ids, 'points.period.current')
    previous = _id_in(ids, 'points.period.previous')
    if current:
        rows.append({'label': '최근', 'value': _simple_value(current, catalog)})
    if previous:
        rows.append({'label': '이전', 'value': _simple_value(previous, catalog)})
    median = _id_in(ids, 'points.peer.peer_median')
    if median:
        rows.append({'label': '같은 학년 포인트 중앙값', 'value': _simple_value(median, catalog)})
    sample = _id_in(ids, 'points.peer.n')
    if sample:
        rows.append({'label': '포인트 비교 인원', 'value': _simple_value(sample, catalog)})
    return rows
