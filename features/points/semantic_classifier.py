"""Semantic mapping LLM batch. amount/net을 정하지 않는다.

Growth Luna prompt / quota / generation lifecycle과 분리한다.
scheduler는 이 모듈에 없다.
"""
from __future__ import annotations

import json
import os

from features.points.semantic import (
    ALLOWED_CATEGORIES,
    ALLOWED_ITEM_KEYS,
    ALLOWED_SUBJECT_KEYS,
    SOURCE_SEMANTIC_LLM,
    unmapped_manual_label_counts,
    upsert_semantic_mapping,
)
from features.points.text import compact_lookup

PROMPT_VERSION = 'point_semantic_classifier_v1'
SCHEMA_VERSION = 'point_semantic_mappings_v1'
SCHEMA_NAME = 'point_semantic_mappings_v1'
API_KEY_ENV = 'OPENAI_API_KEY'
MODEL_ENV = 'POINT_SEMANTIC_MODEL'
GROWTH_MODEL_ENV = 'GROWTH_AI_MODEL'
PROVIDER_NAME = 'openai'

# v1 정책: 한 실행(=한 batch)당 신규 unique label 최대 100개.
# 초과분은 저장되지 않았으므로 다음 실행에서 다시 candidate가 된다.
MAX_LABELS_PER_RUN = 100

_SUBJECT_KEYS_TEXT = ', '.join(sorted(ALLOWED_SUBJECT_KEYS))
_ITEM_KEYS_TEXT = ', '.join(sorted(ALLOWED_ITEM_KEYS))

SYSTEM_PROMPT = f"""너는 아동학습센터 수동 포인트 label을 분류한다.
문구 자체만 보고, 아래 taxonomy 중 하나로만 분류한다.

TEXTBOOK_COMPLETE: 교재/문제집 등 일정 단위를 끝까지 완료해서 받은 보상
PRAISE: 교사가 특정 행동/성과를 칭찬해서 받은 보상
HELP_CONTRIBUTION: 교사/친구/센터의 정리·도우미 등 실제 도움/기여 활동 보상
EXTRA_LEARNING: 기본/정해진 학습량보다 문제·교재·학습을 추가 수행한 보상
ACTIVITY_MATERIAL: 프린트/클레이/비즈/만들기 재료 등 활동 재료 관련 포인트
STATIONERY: 연필/지우개/필통/공책 등 문구/학용품 관련 포인트
UNCLASSIFIED: 문구만으로 위 의미를 확정하기 어려움

규칙:
- 추측하지 않는다. 애매하면 UNCLASSIFIED.
- 성격/태도/능력/심리/사회성을 추론하지 않는다.
- 금액, 날짜, 아동 정보는 없다. 사용하지도 않는다.
- 새 category를 만들지 않는다.
- 입력 labels만 결과에 넣는다. 없는 label을 만들지 않는다.
- subject_key는 문구에 과목이 하나 명확할 때만 둔다: {_SUBJECT_KEYS_TEXT}. 없거나 여러 개면 null.
- item_key는 {_ITEM_KEYS_TEXT} 만. 불명확하면 null.
- 자유 설명 문장을 쓰지 않는다.
"""


class SemanticClassifierError(Exception):
    """분류 실패. payload/API key를 메시지에 넣지 않는다."""


class SemanticClassifierConfigError(SemanticClassifierError):
    """API key / model 설정 오류."""


class SemanticClassifierAPIError(SemanticClassifierError):
    """원격 API 오류 / timeout."""


class SemanticClassifierParseError(SemanticClassifierError):
    """빈 응답, JSON/schema parse 실패."""


def resolve_semantic_model(model=None):
    """POINT_SEMANTIC_MODEL, 없으면 GROWTH_AI_MODEL. 모델명 하드코딩 없음."""
    if model:
        return str(model).strip()
    return (
        (os.environ.get(MODEL_ENV) or '').strip()
        or (os.environ.get(GROWTH_MODEL_ENV) or '').strip()
    )


def structured_output_format():
    categories = sorted(ALLOWED_CATEGORIES)
    subjects = sorted(ALLOWED_SUBJECT_KEYS)
    items = sorted(ALLOWED_ITEM_KEYS)
    return {
        'type': 'json_schema',
        'name': SCHEMA_NAME,
        'strict': True,
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['mappings'],
            'properties': {
                'mappings': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'required': ['label', 'category', 'subject_key', 'item_key'],
                        'properties': {
                            'label': {'type': 'string'},
                            'category': {'type': 'string', 'enum': categories},
                            'subject_key': {
                                'anyOf': [
                                    {'type': 'string', 'enum': subjects},
                                    {'type': 'null'},
                                ],
                            },
                            'item_key': {
                                'anyOf': [
                                    {'type': 'string', 'enum': items},
                                    {'type': 'null'},
                                ],
                            },
                        },
                    },
                },
            },
        },
    }


def build_classifier_payload(labels):
    """LLM input. label 문자열만. count/amount/개인정보 없음."""
    cleaned = []
    seen = set()
    for raw in labels or ():
        key = compact_lookup(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(key)
    return {'labels': cleaned}


def classify_unmapped_labels(labels, *, client=None, model=None, api_key=None):
    """labels → validated mapping dicts. 저장하지 않는다. 한 batch."""
    payload = build_classifier_payload(labels)
    if not payload['labels']:
        return []
    parsed = _request_mappings(payload, client=client, model=model, api_key=api_key)
    return validate_classifier_mappings(payload['labels'], parsed)


def classify_and_store_unmapped_labels(
    records,
    *,
    client=None,
    model=None,
    api_key=None,
    max_labels=MAX_LABELS_PER_RUN,
):
    """candidate 조회 → 최대 max_labels개 1 batch → validate → upsert."""
    from extensions import db

    candidates = unmapped_manual_label_counts(records)
    all_labels = [row['label'] for row in candidates]
    limit = len(all_labels) if max_labels is None else max(0, int(max_labels))
    labels = all_labels[:limit]
    summary = {
        'candidate_count': len(all_labels),
        'remaining_count': len(all_labels) - len(labels),
        'classified_count': 0,
        'stored_count': 0,
        'failed_count': 0,
        'llm_calls': 0,
        'error': None,
    }
    if not labels:
        return summary
    summary['llm_calls'] = 1
    try:
        mappings = classify_unmapped_labels(
            labels, client=client, model=model, api_key=api_key,
        )
    except SemanticClassifierError as exc:
        summary['failed_count'] = len(labels)
        summary['error'] = str(exc)
        return summary

    summary['classified_count'] = len(mappings)
    stored = 0
    try:
        for item in mappings:
            upsert_semantic_mapping(
                item['label'],
                item['category'],
                subject_key=item.get('subject_key'),
                item_key=item.get('item_key'),
                source=SOURCE_SEMANTIC_LLM,
            )
            stored += 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        summary['stored_count'] = 0
        summary['failed_count'] = len(labels)
        summary['error'] = 'semantic mapping store failed'
        return summary
    summary['stored_count'] = stored
    summary['failed_count'] = len(labels) - stored
    return summary


def validate_classifier_mappings(input_labels, parsed):
    """구조가 완전히 깨지면 ParseError. 항목 단위 invalid는 건너뛴다."""
    if not isinstance(parsed, dict) or 'mappings' not in parsed:
        raise SemanticClassifierParseError('malformed semantic classifier output')
    rows = parsed.get('mappings')
    if not isinstance(rows, list):
        raise SemanticClassifierParseError('malformed semantic classifier output')

    allowed = {compact_lookup(label) for label in input_labels if compact_lookup(label)}
    accepted = {}
    conflicts = set()
    for row in rows:
        item = _normalize_mapping_row(row, allowed)
        if item is None:
            continue
        key = item['label']
        identity = (item['category'], item['subject_key'], item['item_key'])
        previous = accepted.get(key)
        if previous is None:
            accepted[key] = item
            continue
        if (
            previous['category'],
            previous['subject_key'],
            previous['item_key'],
        ) != identity:
            conflicts.add(key)

    return tuple(
        accepted[key]
        for key in accepted
        if key not in conflicts
    )


def _normalize_mapping_row(row, allowed_labels):
    if not isinstance(row, dict):
        return None
    label = compact_lookup(row.get('label'))
    if not label or label not in allowed_labels:
        return None
    category = row.get('category')
    if category not in ALLOWED_CATEGORIES:
        return None
    subject_key = _optional_allowed(row.get('subject_key'), ALLOWED_SUBJECT_KEYS)
    item_key = _optional_allowed(row.get('item_key'), ALLOWED_ITEM_KEYS)
    return {
        'label': label,
        'category': category,
        'subject_key': subject_key,
        'item_key': item_key,
    }


def _optional_allowed(value, allowed):
    if value is None or value == '':
        return None
    text = str(value).strip()
    if text not in allowed:
        return None
    return text


def _request_mappings(payload, *, client=None, model=None, api_key=None):
    resolved_model = resolve_semantic_model(model)
    if not resolved_model:
        raise SemanticClassifierConfigError('POINT_SEMANTIC_MODEL is not set')
    request_client = client or _build_client(api_key=api_key)
    try:
        response = request_client.responses.create(
            model=resolved_model,
            instructions=SYSTEM_PROMPT,
            input=json.dumps(payload, ensure_ascii=False),
            store=False,
            text={'format': structured_output_format()},
        )
    except SemanticClassifierError:
        raise
    except Exception as exc:
        raise _api_error(exc) from exc
    return _parse_response(response)


def _build_client(*, api_key=None, timeout_s=None):
    key = api_key or os.environ.get(API_KEY_ENV)
    if not key:
        raise SemanticClassifierConfigError('OPENAI_API_KEY is not set')
    from openai import OpenAI
    kwargs = {'api_key': key, 'max_retries': 0}
    if timeout_s is not None:
        kwargs['timeout'] = float(timeout_s)
    return OpenAI(**kwargs)


def _parse_response(response):
    status = getattr(response, 'status', None)
    if status not in (None, 'completed'):
        raise SemanticClassifierParseError('incomplete semantic classifier response')
    text = getattr(response, 'output_text', None)
    if not text or not str(text).strip():
        raise SemanticClassifierParseError('empty semantic classifier output')
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise SemanticClassifierParseError('malformed semantic classifier output') from exc
    if not isinstance(parsed, dict):
        raise SemanticClassifierParseError('malformed semantic classifier output')
    return parsed


def _api_error(exc):
    try:
        from openai import APIConnectionError, APIStatusError, APITimeoutError
    except ImportError:
        return SemanticClassifierAPIError('openai api request failed')
    if isinstance(exc, APITimeoutError):
        return SemanticClassifierAPIError('openai api timeout')
    if isinstance(exc, APIConnectionError):
        return SemanticClassifierAPIError('openai api connection failed')
    if isinstance(exc, APIStatusError):
        status = getattr(exc, 'status_code', None)
        return SemanticClassifierAPIError(
            f'openai api error{"" if status is None else f" ({status})"}'
        )
    return SemanticClassifierAPIError('openai api request failed')