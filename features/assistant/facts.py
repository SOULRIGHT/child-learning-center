"""Growth canonical facts를 assistant tool용으로 얇게 투영한다.

Evidence Packet 전체 dump / raw review / ORM 객체를 반환하지 않는다.
metrics를 다시 계산하지 않고 기존 packet builder를 읽는다.
"""
from __future__ import annotations

from features.assistant.navigation import lookup_child
from features.dates import parse_activity_date_text
from features.growth.ai.runtime import build_current_packet
from features.growth.ai.presenter import _catalog as _presentation_catalog
from features.growth.ai.presenter import _format_row as _present_fact_row
from features.subjects import subject_name

MAX_FACTS = 24
BLOCKED_EVIDENCE_PREFIXES = (
    'reading.analysis.observation',
    'reading.analysis.limitation',
)
BLOCKED_KEYS = frozenset({
    'review_text', 'review', 'raw_output', 'packet', 'observations',
})
TOPIC_PREFIXES = {
    'learning': ('learning.',),
    'points': ('points.',),
    'reading': ('reading.',),
    'peer': ('peer',),
    'growth': (),
}

_LABELS = {
    'learning.math.performance.studied_days.current': '수학 학습일(최근)',
    'learning.korean.performance.studied_days.current': '국어 학습일(최근)',
    'learning.ssen.performance.studied_days.current': '쎈수학 학습일(최근)',
    'learning.math.progress.latest_observed_end_page': '수학 관측 끝 페이지',
    'learning.korean.progress.latest_observed_end_page': '국어 관측 끝 페이지',
    'points.period_total.current': '기간 포인트(최근)',
    'points.cumulative_as_of': '누적 포인트',
    'reading.activity_days.current': '최근 독서 활동일',
    'reading.completed_count': '완독 수',
}
_ASSISTANT_LABELS = {
    'points.period_total.current': '최근 기간 포인트',
    'points.period_total.previous': '이전 기간 포인트',
    'points.period_total.delta': '포인트 변화',
    'points.cumulative_as_of': '현재 누적 포인트',
    'points.peer.child_value': '최근 기간 포인트',
    'points.peer.peer_median': '같은 학년 중앙값',
    'points.peer.n': '비교 인원',
    'points.peer.difference': '중앙값과 차이',
    'reading.activity_days.current': '최근 기간 독서 활동',
    'reading.activity_days.previous': '이전 기간 독서 활동',
    'reading.activity_days.delta': '독서 활동 변화',
    'reading.completions.current': '최근 기간 완독',
    'reading.completions.previous': '이전 기간 완독',
    'reading.completions.delta': '완독 변화',
    'reading.recommended.activity_days.current': '최근 기간 추천도서 활동',
    'reading.recommended.activity_days.previous': '이전 기간 추천도서 활동',
    'reading.recommended.activity_days.delta': '추천도서 활동 변화',
    'reading.recommended.completions.current': '최근 기간 추천도서 완독',
    'reading.recommended.completions.previous': '이전 기간 추천도서 완독',
    'reading.recommended.completions.delta': '추천도서 완독 변화',
    'reading.analysis.recent_count': '최근 기간 독서 기록',
    'reading.analysis.previous_count': '이전 기간 독서 기록',
    'reading.analysis.text_record_count': '텍스트가 있는 독서 기록',
    'reading.analysis.completed_count': '완독 기록',
    'reading.analysis.completion_duration_median': '완독 기간 중앙값',
    'reading.analysis.character_count.recent_median': '최근 기록 글자 수 중앙값',
    'reading.analysis.character_count.previous_median': '이전 기록 글자 수 중앙값',
    'reading.analysis.character_count.recent_sample_count': '최근 글자 수 비교 기록',
    'reading.analysis.character_count.previous_sample_count': '이전 글자 수 비교 기록',
    'reading.analysis.sentence_count.recent_median': '최근 기록 문장 수 중앙값',
    'reading.analysis.sentence_count.previous_median': '이전 기록 문장 수 중앙값',
    'reading.analysis.sentence_count.recent_sample_count': '최근 문장 수 비교 기록',
    'reading.analysis.sentence_count.previous_sample_count': '이전 문장 수 비교 기록',
}
_ASSISTANT_UNITS = {
    'reading.analysis.recent_count': '건',
    'reading.analysis.previous_count': '건',
    'reading.analysis.text_record_count': '건',
    'reading.analysis.completed_count': '권',
    'reading.analysis.completion_duration_median': '일',
    'reading.analysis.character_count.recent_median': '자',
    'reading.analysis.character_count.previous_median': '자',
    'reading.analysis.character_count.recent_sample_count': '건',
    'reading.analysis.character_count.previous_sample_count': '건',
    'reading.analysis.sentence_count.recent_median': '문장',
    'reading.analysis.sentence_count.previous_median': '문장',
    'reading.analysis.sentence_count.recent_sample_count': '건',
    'reading.analysis.sentence_count.previous_sample_count': '건',
}


_FOCUS_CUES = (
    '변화', '수행률', '확인률', '완독', '평균', '이전 기간', '최근 포인트',
    '비교 인원', '활동일', '최근 기간', '이전 포인트',
)
_FOCUS_KEYS = (
    ('추천도서', ('recommended', '추천도서')),
    ('완독', ('completion', '완독', 'completions')),
    ('변화', ('delta', '변화')),
    ('수행률', ('rate', '수행')),
    ('확인률', ('confirm', '확인률', '확인')),
    ('활동일', ('active_days', 'activity_days', '활동일')),
    ('이전 기간', ('previous', '이전')),
    ('최근 기간', ('current', '최근')),
    ('최근 포인트', ('current', 'points', '최근', '포인트')),
    ('이전 포인트', ('previous', 'points', '이전', '포인트')),
    ('비교 인원', ('peer.n', '.n', '비교 인원', '인원')),
    ('포인트', ('points', '포인트')),
    ('이전', ('previous', '이전')),
    ('최근', ('current', '최근')),
    ('비교', ('peer', '비교')),
    ('인원', ('.n', '인원')),
)


def infer_metric_focus(text):
    raw = (text or '').strip()
    if not raw or not any(cue in raw for cue in _FOCUS_CUES):
        return None
    if any(token in raw for token in ('정보 좀', '학습정보', '다 보여', '전체 요약')):
        return None
    return raw[:80]


def facts_matching_focus(facts, focus):
    if not focus:
        return list(facts or ())
    keys = [(cue, aliases) for cue, aliases in _FOCUS_KEYS if cue in (focus or '')]
    if not keys:
        return list(facts or ())
    scored = []
    for fact in facts or ():
        score = _focus_score(fact, keys)
        if score:
            scored.append((score, fact))
    if not scored:
        return []
    best = max(score for score, _row in scored)
    chosen = [fact for score, fact in scored if score == best]
    if not any(cue == '변화' for cue, _aliases in keys):
        return chosen
    stems = []
    for fact in chosen:
        evidence_id = str(fact.get('evidence_id') or '')
        for suffix in ('.current', '.previous', '.delta', '.delta_pp'):
            if evidence_id.endswith(suffix):
                stems.append(evidence_id[:-len(suffix)])
                break
    if not stems:
        return chosen
    family = [
        fact for fact in facts or ()
        if any(str(fact.get('evidence_id') or '').startswith(stem) for stem in stems)
    ]
    return family or chosen


def growth_facts_for_child(child_id, *, as_of=None, topic='growth', subject_key=None, focus=None):
    child = lookup_child(child_id)
    if child is None:
        return {'ok': False, 'error': 'invalid_child'}
    parsed = _parse_as_of(as_of)
    packet = build_current_packet(child, as_of=parsed)
    facts = compact_facts(packet, topic=topic, subject_key=subject_key, focus=focus)
    result = {
        'ok': True,
        'child': {
            'id': child.id,
            'name': child.name,
            'grade': getattr(child, 'grade', None),
        },
        'as_of': packet.get('as_of'),
        'facts': facts,
    }
    if focus:
        result['focus'] = str(focus)[:80]
        all_facts = compact_facts(packet, topic=topic, subject_key=subject_key)
        if all_facts and not facts:
            result['focus_unmatched'] = True
    return result


def compact_facts(packet, *, topic='growth', subject_key=None, focus=None):
    rows = []
    presentation_catalog = _presentation_catalog(packet)
    for node in _walk(packet.get('supporting_facts') or {}):
        evidence_id = node.get('evidence_id')
        if not isinstance(evidence_id, str) or not evidence_id:
            continue
        if any(evidence_id.startswith(prefix) for prefix in BLOCKED_EVIDENCE_PREFIXES):
            continue
        if not _topic_match(evidence_id, topic, subject_key):
            continue
        available = node.get('available') is True
        value = node.get('value') if available else None
        if _looks_like_review(value):
            continue
        presentation = _presentation(
            evidence_id,
            node,
            presentation_catalog,
            available=available,
        )
        row = {
            'evidence_id': evidence_id,
            'label': presentation['label'],
            'available': available,
            'value': _public_value(value) if available else None,
            'status': None if available else (node.get('status') or 'unavailable'),
        }
        if available:
            row['display_value'] = presentation['value']
        else:
            row['unavailable_reason'] = presentation['value']
        if presentation.get('note'):
            row['note'] = presentation['note']
        if node.get('unit'):
            row['unit'] = str(node.get('unit'))[:20]
        period = _period(evidence_id)
        if period:
            row['period'] = period
        rows.append(row)
        if len(rows) >= MAX_FACTS:
            break
    if focus:
        return facts_matching_focus(rows, focus)
    return rows


def _topic_match(evidence_id, topic, subject_key):
    topic = (topic or 'growth').strip()
    if topic == 'peer':
        if 'peer' not in evidence_id:
            return False
        if subject_key:
            return evidence_id.startswith(f'learning.{subject_key}.')
        return True
    if topic != 'growth':
        prefixes = TOPIC_PREFIXES.get(topic)
        if prefixes and not any(evidence_id.startswith(prefix) for prefix in prefixes):
            return False
    if subject_key and evidence_id.startswith('learning.'):
        return evidence_id.startswith(f'learning.{subject_key}.')
    return True


def _walk(node):
    if isinstance(node, dict):
        if 'evidence_id' in node:
            yield node
        for key, value in node.items():
            if key in BLOCKED_KEYS:
                continue
            yield from _walk(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)


def _looks_like_review(value):
    if not isinstance(value, str):
        return False
    if len(value) > 160:
        return True
    lowered = value.casefold()
    return '감상' in lowered or 'review' in lowered


def _public_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, str):
            return value[:120]
        return value
    if isinstance(value, (list, tuple)):
        return [_public_value(item) for item in value[:8]]
    if isinstance(value, dict):
        return {
            str(key): _public_value(item)
            for key, item in list(value.items())[:8]
            if key not in BLOCKED_KEYS
        }
    return str(value)[:80]


def _label(evidence_id):
    if evidence_id in _LABELS:
        return _LABELS[evidence_id]
    parts = [part for part in evidence_id.split('.') if part]
    return ' '.join(parts[-3:]) if parts else evidence_id


def _presentation(evidence_id, node, catalog, *, available):
    try:
        presented = _present_fact_row(evidence_id, catalog[evidence_id], catalog)
    except (KeyError, TypeError, ValueError):
        presented = {
            'label': _label(evidence_id),
            'value': _public_value(node.get('value')) if available else '자료 없음',
            'note': None,
        }
    label = _assistant_label(evidence_id, presented.get('label'))
    value = presented.get('value')
    if available and _is_delta(evidence_id):
        value = _directional_delta(node.get('value'), value)
    elif available and evidence_id in _ASSISTANT_UNITS:
        value = _with_display_unit(node.get('value'), _ASSISTANT_UNITS[evidence_id])
    return {
        'label': str(label)[:80],
        'value': str(value if value not in (None, '') else ('자료 없음' if not available else ''))[:120],
        'note': str(presented.get('note') or '')[:160] or None,
    }


def _is_delta(evidence_id):
    return evidence_id.endswith('.delta') or evidence_id.endswith('.delta_pp')


def _assistant_label(evidence_id, fallback):
    explicit = _ASSISTANT_LABELS.get(evidence_id)
    if explicit:
        return explicit
    composed = _points_composition_label(evidence_id)
    if composed:
        return composed
    subject = {
        'math': '수학',
        'korean': '국어',
        'ssen': '쎈수학',
    }.get(evidence_id.split('.')[1] if evidence_id.startswith('learning.') else '')
    period = '최근' if evidence_id.endswith('.current') else (
        '이전' if evidence_id.endswith('.previous') else ''
    )
    if '.performance.explicit_not_studied_days.' in evidence_id:
        return ' '.join(part for part in (period, subject, '명시적 미학습일') if part)
    if '.performance.unknown_days.' in evidence_id:
        return ' '.join(part for part in (period, subject, '기록 미확인 예정일') if part)
    if '.performance.extra_studied_days.' in evidence_id:
        return ' '.join(part for part in (period, subject, '예정 외 학습일') if part)
    if evidence_id.endswith('.performance.enough_days'):
        return f'{subject} 기간 비교 기준 충족 여부' if subject else '기간 비교 기준 충족 여부'
    if '.performance.expected_days.' in evidence_id:
        return ' '.join(part for part in (period, subject, '예정 학습일') if part)
    if '.performance.rate.' in evidence_id:
        return ' '.join(part for part in (period, subject, '학습 수행률') if part)
    if '.performance.confirmation.' in evidence_id:
        return ' '.join(part for part in (period, subject, '확인률') if part)
    rewritten = {
        '성장 자료': None,
        '내 기간 포인트': '최근 기간 포인트',
        '변화 기간 포인트': '포인트 변화',
        '현재 기준 누적 포인트': '현재 누적 포인트',
        '같은 학년 포인트 중앙값': '같은 학년 중앙값',
        '포인트 비교 인원': '비교 인원',
        '포인트 또래 차이': '중앙값과 차이',
    }.get(fallback)
    if rewritten:
        return rewritten
    if fallback and fallback != '성장 자료' and '성장 자료' not in str(fallback):
        return fallback
    return _label(evidence_id)


_COMPOSITION_TOTALS = {
    'net_points': '순포인트',
    'total_earn_points': '적립 포인트',
    'total_spend_points': '사용 포인트',
}
_COMPOSITION_CATEGORIES = {
    'textbook': '교재 포인트',
    'praise': '칭찬 포인트',
    'help': '도움 포인트',
    'extra_learning': '추가학습 포인트',
}


def _points_composition_label(evidence_id):
    if not evidence_id.startswith('points.composition.'):
        return None
    parts = evidence_id.split('.')
    period = '최근 기간' if evidence_id.endswith('.current') else (
        '이전 기간' if evidence_id.endswith('.previous') else ''
    )
    is_delta = _is_delta(evidence_id)
    if len(parts) >= 5 and parts[2] == 'subjects':
        name = subject_name(parts[3]) or parts[3]
        metric = parts[4]
        if metric == 'points':
            if is_delta:
                return f'{name} 포인트 변화'
            return ' '.join(part for part in (period, f'{name} 포인트') if part)
        if metric == 'active_days':
            if is_delta:
                return f'{name} 포인트 활동일 변화'
            return ' '.join(part for part in (period, f'{name} 포인트 활동일') if part)
    if len(parts) >= 7 and parts[2] == 'extra_learning' and parts[3] == 'by_subject':
        name = subject_name(parts[4]) or parts[4]
        if is_delta:
            return f'{name} 추가학습 포인트 변화'
        return ' '.join(part for part in (period, f'{name} 추가학습 포인트') if part)
    if len(parts) >= 4 and parts[2] == 'totals':
        metric = _COMPOSITION_TOTALS.get(parts[3], parts[3])
        if is_delta:
            return f'{metric} 변화'
        return ' '.join(part for part in (period, metric) if part)
    if len(parts) >= 4 and parts[2] in _COMPOSITION_CATEGORIES:
        metric = _COMPOSITION_CATEGORIES[parts[2]]
        if is_delta:
            return f'{metric} 변화'
        return ' '.join(part for part in (period, metric) if part)
    return None


def _focus_haystack(fact):
    return ' '.join((
        str(fact.get('label') or ''),
        str(fact.get('evidence_id') or ''),
        str(fact.get('evidence_id') or '').replace('.', ' '),
    ))


def _focus_score(fact, keys):
    haystack = _focus_haystack(fact)
    return sum(1 for _cue, aliases in keys if any(alias in haystack for alias in aliases))


def _fact_matches_focus(fact, focus):
    keys = [(cue, aliases) for cue, aliases in _FOCUS_KEYS if cue in (focus or '')]
    if not keys:
        return True
    return _focus_score(fact, keys) == len(keys)


def _with_display_unit(value, unit):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    rendered = str(int(number)) if number.is_integer() else f'{number:g}'
    return f'{rendered}{unit}'


def _directional_delta(value, display_value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return display_value
    if number == 0:
        return '변화 없음'
    rendered = str(display_value or value).lstrip('+-')
    return f"{rendered} {'증가' if number > 0 else '감소'}"


def _period(evidence_id):
    if evidence_id.endswith('.current'):
        return 'current'
    if evidence_id.endswith('.previous'):
        return 'previous'
    if _is_delta(evidence_id):
        return 'change'
    return None


def _parse_as_of(raw):
    if raw is None or raw == '':
        return None
    if hasattr(raw, 'isoformat') and not isinstance(raw, str):
        return raw
    return parse_activity_date_text(str(raw).strip())


def format_tool_facts(name, result, *, user_text='', focus=None):
    """사용자-facing 짧은 요약 + 2~5개 수치. canonical fact만 사용한다."""
    facts = list(result.get('facts') or ())
    child_name = ((result.get('child') or {}).get('name') or '').strip()
    if focus:
        focused = facts_matching_focus(facts, focus)
        return _format_focused_facts(focused, child_name=child_name, focus=focus)
    if name == 'get_points_facts':
        return _format_points_facts(facts, child_name=child_name)
    if name == 'get_reading_facts':
        return _format_reading_facts(facts, child_name=child_name)
    if name == 'get_learning_facts':
        return _format_learning_facts(facts, child_name=child_name, user_text=user_text)
    return _format_short_facts(facts, child_name=child_name, limit=5)


def format_all_domain_facts(items):
    sections = []
    used = []
    titles = {
        'get_learning_facts': '학습',
        'get_points_facts': '포인트',
        'get_reading_facts': '독서',
    }
    for item in items or ():
        name = item.get('name')
        result = item.get('result') or {}
        if name not in titles or not result.get('ok'):
            continue
        formatted = format_tool_facts(name, result)
        bullets = [
            line for line in (formatted.get('text') or '').split('\n')
            if line.startswith('- ')
        ][:4]
        if not bullets:
            continue
        sections.append(f"[{titles[name]}]\n" + '\n'.join(bullets))
        used.extend(formatted.get('used_facts') or ())
    text = '\n\n'.join(sections).strip()
    return {'text': text, 'used_facts': used}


def _format_points_facts(facts, *, child_name=''):
    current = _fact_by_id(facts, 'points.period_total.current')
    previous = _fact_by_id(facts, 'points.period_total.previous')
    delta = _fact_by_id(facts, 'points.period_total.delta')
    cumulative = _fact_by_id(facts, 'points.cumulative_as_of')
    median = _fact_by_id(facts, 'points.peer.peer_median')
    sample = _fact_by_id(facts, 'points.peer.n')
    difference = _fact_by_id(facts, 'points.peer.difference')
    used = []
    lines = []
    current_display = _fact_display(current)
    if child_name and current_display:
        lines.append(f'{child_name} 아동은 최근 기간에 {current_display}을 기록했습니다.')
        used.append(current)
    elif child_name:
        lines.append(f'{child_name} 아동의 최근 포인트 기록을 확인했습니다.')
    else:
        lines.append('최근 포인트 기록을 확인했습니다.')
    bullets = []
    if current_display:
        bullets.append(f'- 최근 기간: **{current_display}**')
        if current not in used:
            used.append(current)
    previous_display = _fact_display(previous)
    if previous_display:
        bullets.append(f'- 이전 기간: **{previous_display}**')
        used.append(previous)
    delta_display = _fact_display(delta)
    if delta_display:
        bullets.append(f'- 변화: **{delta_display}**')
        used.append(delta)
    cumulative_display = _fact_display(cumulative)
    if cumulative_display:
        bullets.append(f'- 현재 누적: **{cumulative_display}**')
        used.append(cumulative)
    median_display = _fact_display(median)
    sample_display = _fact_display(sample)
    if median_display:
        extra = f' (비교 인원 {sample_display})' if sample_display else ''
        bullets.append(f'- 같은 학년 중앙값: **{median_display}**{extra}')
        used.append(median)
        if sample:
            used.append(sample)
    lines.extend(bullets[:5])
    note = _points_peer_note(difference, median)
    if note:
        lines.append(note)
        used.append(difference)
    return {'text': '\n'.join(lines).strip(), 'used_facts': used}


def _points_peer_note(difference, median):
    if not difference or not median:
        return None
    try:
        number = float(difference.get('value'))
    except (TypeError, ValueError):
        return None
    shown = _fact_display(difference)
    if not shown:
        return None
    shown = str(shown).lstrip('+')
    if number == 0:
        return '현재 자료에서는 같은 학년 중앙값과 같게 관측됩니다.'
    direction = '낮게' if number < 0 else '높게'
    return (
        f'현재 자료에서는 같은 학년 중앙값보다 {shown} {direction} 관측됩니다.\n'
        '이는 기록된 포인트 기준의 비교이며 학습 능력을 의미하지 않습니다.'
    )


def _format_reading_facts(facts, *, child_name=''):
    families = (
        ('reading.activity_days', '독서 활동'),
        ('reading.completions', '완독'),
        ('reading.recommended.activity_days', '추천도서 활동'),
        ('reading.recommended.completions', '추천도서 완독'),
    )
    bullets = []
    used = []
    directions = []
    for stem, label in families:
        grouped, rows = _grouped_metric(facts, stem)
        if not grouped:
            continue
        bullets.append(f'- {label}: **{grouped}**')
        used.extend(rows)
        delta = _fact_by_id(facts, f'{stem}.delta')
        try:
            number = float(delta.get('value')) if delta else None
        except (TypeError, ValueError):
            number = None
        if number is not None:
            directions.append(number)
    if not bullets:
        return _format_short_facts(facts, child_name=child_name, limit=4)
    if directions and all(value < 0 for value in directions):
        headline = '최근 기간에는 독서 활동과 완독 기록이 이전 기간보다 감소했습니다.'
    elif directions and all(value > 0 for value in directions):
        headline = '최근 기간에는 독서 활동과 완독 기록이 이전 기간보다 증가했습니다.'
    else:
        headline = '최근 기간 독서 기록을 확인했습니다.'
    lines = [headline, *bullets[:4], '확인된 기록 기준의 변화입니다.']
    return {'text': '\n'.join(lines), 'used_facts': used}


def _format_learning_facts(facts, *, child_name='', user_text=''):
    subject = None
    for hint, key in (('쎈수학', 'ssen'), ('쎈', 'ssen'), ('수학', 'math'), ('국어', 'korean')):
        if hint in (user_text or ''):
            subject = key
            break
    prefix = f'learning.{subject}.performance' if subject else None
    picks = []
    if prefix:
        picks = [
            (f'{prefix}.expected_days.current', '예정 학습일'),
            (f'{prefix}.studied_days.current', '실제 학습일'),
            (f'{prefix}.unknown_days.current', '기록 미확인 예정일'),
            (f'{prefix}.rate.current', '학습 수행률'),
            (f'{prefix}.confirmation.current', '확인률'),
        ]
    bullets = []
    used = []
    for evidence_id, label in picks:
        fact = _fact_by_id(facts, evidence_id)
        display = _fact_display(fact)
        if display is None:
            continue
        bullets.append(f'- {label}: **{display}**')
        used.append(fact)
        if len(bullets) >= 5:
            break
    if not bullets:
        return _format_short_facts(facts, child_name=child_name, limit=5)
    subject_label = {'math': '수학', 'korean': '국어', 'ssen': '쎈수학'}.get(subject, '')
    if subject_label:
        headline = f'최근 {subject_label} 학습 기록을 확인했습니다.'
    else:
        headline = '최근 학습 기록을 확인했습니다.'
    return {'text': '\n'.join([headline, *bullets]), 'used_facts': used}


def _format_focused_facts(facts, *, child_name='', focus=''):
    if not facts:
        return {'text': '', 'used_facts': []}
    families = {}
    for fact in facts:
        evidence_id = str(fact.get('evidence_id') or '')
        family = evidence_id
        for suffix in ('.current', '.previous', '.delta', '.delta_pp'):
            if evidence_id.endswith(suffix):
                family = evidence_id[:-len(suffix)]
                break
        families.setdefault(family, []).append(fact)
    chosen = max(families.values(), key=len)
    current = next((row for row in chosen if str(row.get('evidence_id') or '').endswith('.current')), None)
    previous = next((row for row in chosen if str(row.get('evidence_id') or '').endswith('.previous')), None)
    delta = next((row for row in chosen if _is_delta(str(row.get('evidence_id') or ''))), None)
    used = [row for row in (current, previous, delta) if row]
    current_display = _fact_display(current)
    previous_display = _fact_display(previous)
    delta_display = _fact_display(delta)
    short = _short_metric_label((current or previous or delta or {}).get('label') or '해당 기록')
    if current_display and previous_display and delta_display:
        text = (
            f'최근 기간 {short}은 {current_display}, '
            f'이전 기간은 {previous_display}으로 {delta_display}했습니다.'
        )
    elif current_display and previous_display:
        text = f'최근 기간 {short}은 {current_display}, 이전 기간은 {previous_display}입니다.'
    elif current_display:
        text = f'{short}은 {current_display}입니다.'
    else:
        return _format_short_facts(facts, child_name=child_name, limit=3)
    return {'text': text, 'used_facts': used or list(facts)[:3]}


def _format_short_facts(facts, *, child_name='', limit=5):
    used = []
    bullets = []
    for fact in facts or ():
        if not fact.get('available'):
            continue
        display = _fact_display(fact)
        label = fact.get('label') or ''
        if display is None or not label or '성장 자료' in label:
            continue
        bullets.append(f'- {label}: **{display}**')
        used.append(fact)
        if len(bullets) >= limit:
            break
    if not bullets:
        return {'text': '', 'used_facts': []}
    headline = f'{child_name} 아동의 확인된 기록입니다.' if child_name else '확인된 기록입니다.'
    return {'text': '\n'.join([headline, *bullets]), 'used_facts': used}


def _grouped_metric(facts, stem):
    current = _fact_by_id(facts, f'{stem}.current')
    previous = _fact_by_id(facts, f'{stem}.previous')
    current_display = _fact_display(current)
    previous_display = _fact_display(previous)
    used = [row for row in (previous, current) if row]
    if previous_display and current_display:
        return f'{previous_display} → {current_display}', used
    if current_display:
        return current_display, used or [current]
    return None, []


def _short_metric_label(label):
    text = str(label or '해당 기록')
    for prefix in ('최근 기간 ', '이전 기간 ', '최근 ', '이전 '):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text or '해당 기록'


def _fact_by_id(facts, evidence_id):
    for fact in facts or ():
        if fact.get('evidence_id') == evidence_id and fact.get('available'):
            return fact
    return None


def _fact_display(fact):
    if not fact:
        return None
    display = fact.get('display_value')
    if display in (None, ''):
        display = fact.get('value')
    if display in (None, ''):
        return None
    return str(display)
