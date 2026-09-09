"""Reading analysis facts. 8+8 raw-text selector.

Growth 30-day reading_metrics 와 창을 섞지 않는다.
review_text raw 는 이 모듈과 Reading-specific AI runtime만 읽는다.
Overall Growth Evidence Packet / prompt 로 전달하지 않는다.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import joinedload

from feature_models import STATUS_COMPLETED, ChildReading, ReadingDay
from features.growth.windows import on_or_before, resolve_as_of

ANALYZER_VERSION = 'reading_analysis_v1'
TEXT_WINDOW_LIMIT = 8
TIER_MAJOR = 'major'
TIER_LIMITED = 'limited'
TIER_NO_CHANGE = 'no_change_conclusion'

_SENTENCE_SPLIT = re.compile(r'[.!?。！？\n]+')


@dataclass(frozen=True)
class TextRecord:
    day_id: int
    reading_id: int
    date: date
    review_text: str
    book_title: str | None
    status: str
    program_type: str
    started_on: date | None
    completed_on: date | None


@dataclass(frozen=True)
class TextSelection:
    as_of: date
    recent: tuple[TextRecord, ...]
    previous: tuple[TextRecord, ...]
    all_text_count: int


def trim_review(value):
    if value is None:
        return ''
    return str(value).strip()


def is_nonempty_review(value):
    return bool(trim_review(value))


def character_count(value):
    """수정하지 않은 원문의 trimmed length. 빈 감상은 sample에서 제외한다."""
    text = trim_review(value)
    if not text:
        return None
    return len(text)


def sentence_count(value):
    """punctuation/newline 기준. 비어 있지 않은데 delimiter가 없으면 1문장."""
    text = trim_review(value)
    if not text:
        return None
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]
    if not parts:
        return 1
    return len(parts)


def sufficiency_tier(recent_count, previous_count):
    recent_n = int(recent_count)
    previous_n = int(previous_count)
    if recent_n <= 2 or previous_n <= 2:
        return TIER_NO_CHANGE
    if recent_n >= 5 and previous_n >= 5:
        return TIER_MAJOR
    return TIER_LIMITED


def select_text_records(child_id, as_of=None):
    """date <= as_of 이고 원문이 비어 있지 않은 ReadingDay만.

    정렬: date DESC, id DESC (같은 날이면 더 큰 id가 최신).
    최신 최대 8개 = recent, 그 직전 최대 8개 = previous.
    아동별 latest reading date를 as_of로 쓰지 않는다.
    """
    as_of = resolve_as_of(as_of)
    rows = (
        ReadingDay.query
        .join(ChildReading)
        .options(joinedload(ReadingDay.child_reading).joinedload(ChildReading.book))
        .filter(
            ChildReading.child_id == child_id,
            ReadingDay.date <= as_of,
        )
        .order_by(ReadingDay.date.desc(), ReadingDay.id.desc())
        .all()
    )
    records = []
    for day in rows:
        if not is_nonempty_review(day.review_text):
            continue
        records.append(_to_record(day))
    recent = tuple(records[:TEXT_WINDOW_LIMIT])
    previous = tuple(records[TEXT_WINDOW_LIMIT:TEXT_WINDOW_LIMIT * 2])
    return TextSelection(
        as_of=as_of,
        recent=recent,
        previous=previous,
        all_text_count=len(records),
    )


def apply_allowed_ids(selection, allowed_day_ids):
    """safety 통과 record만 남긴다. original recent/previous membership은 유지한다.

    합친 뒤 다시 8+8 slice 하지 않는다. 더 오래된 기록으로 backfill하지 않는다.
    """
    allowed = set(int(item) for item in allowed_day_ids)
    recent = tuple(row for row in selection.recent if row.day_id in allowed)
    previous = tuple(row for row in selection.previous if row.day_id in allowed)
    return TextSelection(
        as_of=selection.as_of,
        recent=recent,
        previous=previous,
        all_text_count=selection.all_text_count,
    )


def public_record_meta(record: TextRecord):
    return {
        'record_id': int(record.day_id),
        'date': record.date.isoformat() if record.date else None,
        'book_title': record.book_title,
        'status': record.status,
        'program_type': record.program_type,
    }


def build_public_facts(child_id, as_of=None, selection=None):
    """UI / cache / 이후 Step 7이 받을 수 있는 safe facts. review_text 없음."""
    as_of = resolve_as_of(as_of)
    if selection is None:
        selection = select_text_records(child_id, as_of=as_of)
    recent_count = len(selection.recent)
    previous_count = len(selection.previous)
    completed = _completed_books(child_id, as_of)
    durations = []
    for reading in completed:
        if reading.started_on is None or reading.completed_on is None:
            continue
        durations.append((reading.completed_on - reading.started_on).days + 1)
    facts = {
        'as_of': as_of.isoformat(),
        'analyzer_version': ANALYZER_VERSION,
        'window': {
            'recent_limit': TEXT_WINDOW_LIMIT,
            'previous_limit': TEXT_WINDOW_LIMIT,
        },
        'text_record_count': int(selection.all_text_count),
        'recent_count': recent_count,
        'previous_count': previous_count,
        'sufficiency': sufficiency_tier(recent_count, previous_count),
        'character_count': _side_stats(selection.recent, selection.previous, character_count),
        'sentence_count': _side_stats(selection.recent, selection.previous, sentence_count),
        'completed_count': len(completed),
        'completion_duration_median': (
            None if not durations else _json_number(statistics.median(durations))
        ),
        'recent_records': [public_record_meta(row) for row in selection.recent],
        'previous_records': [public_record_meta(row) for row in selection.previous],
    }
    return facts


def fingerprint_payload(selection: TextSelection, facts, runtime_parts):
    """해시 입력. DB에는 이 dict를 저장하지 않고 hash만 저장한다."""
    return {
        'as_of': selection.as_of.isoformat(),
        'selected_ids': {
            'recent': [row.day_id for row in selection.recent],
            'previous': [row.day_id for row in selection.previous],
        },
        'raw_texts': {
            'recent': [row.review_text for row in selection.recent],
            'previous': [row.review_text for row in selection.previous],
        },
        'metadata': {
            'recent': [public_record_meta(row) for row in selection.recent],
            'previous': [public_record_meta(row) for row in selection.previous],
        },
        'facts': _facts_without_records_copy(facts),
        'window': {
            'recent_limit': TEXT_WINDOW_LIMIT,
            'previous_limit': TEXT_WINDOW_LIMIT,
        },
        'runtime': dict(runtime_parts),
    }


def ai_input_records(selection: TextSelection):
    """Reading AI에만 전달. Overall Growth packet에 넣지 않는다."""
    return {
        'recent': [_ai_record(row) for row in selection.recent],
        'previous': [_ai_record(row) for row in selection.previous],
    }


def allowed_evidence_refs(selection: TextSelection):
    return tuple(public_record_meta(row) for row in list(selection.recent) + list(selection.previous))


def _ai_record(record: TextRecord):
    meta = public_record_meta(record)
    meta['text'] = record.review_text
    return meta


def _facts_without_records_copy(facts):
    payload = dict(facts or {})
    payload.pop('blocked_record_count', None)
    return payload


def _side_stats(recent, previous, metric_fn):
    recent_values = [metric_fn(row.review_text) for row in recent]
    previous_values = [metric_fn(row.review_text) for row in previous]
    recent_values = [value for value in recent_values if value is not None]
    previous_values = [value for value in previous_values if value is not None]
    return {
        'recent_median': None if not recent_values else _json_number(statistics.median(recent_values)),
        'previous_median': (
            None if not previous_values else _json_number(statistics.median(previous_values))
        ),
        'recent_sample_count': len(recent_values),
        'previous_sample_count': len(previous_values),
    }


def _json_number(value):
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, (int, float)):
        return value
    return float(value)


def _completed_books(child_id, as_of):
    readings = ChildReading.query.filter_by(child_id=child_id, status=STATUS_COMPLETED).all()
    return [
        reading for reading in readings
        if on_or_before(reading.completed_on, as_of)
    ]


def _to_record(day):
    reading = day.child_reading
    book = reading.book if reading is not None else None
    return TextRecord(
        day_id=int(day.id),
        reading_id=int(day.child_reading_id),
        date=day.date,
        review_text=day.review_text,
        book_title=book.title if book is not None else None,
        status=reading.status if reading is not None else '',
        program_type=reading.program_type if reading is not None else '',
        started_on=reading.started_on if reading is not None else None,
        completed_on=reading.completed_on if reading is not None else None,
    )
