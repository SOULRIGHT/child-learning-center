"""Server-side assistant audit log. browser conversation / LLM context와 섞지 않는다.

append-only JSONL. API key / cookie / system prompt / raw Reading / raw provider payload 금지.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

AUDIT_ENV = 'TEACHER_ASSISTANT_AUDIT_PATH'
BLOCKED_KEYS = frozenset({
    'api_key', 'authorization', 'cookie', 'token', 'password', 'secret',
    'review_text', 'review', 'observations', 'packet', 'supporting_facts',
    'system_prompt', 'developer_prompt', 'instructions', 'raw_output',
    'sql', 'orm',
})
BLOCKED_VALUE_MARKERS = (
    'sk-', 'OPENAI_API_KEY', 'review_text', 'SYSTEM_PROMPT', 'Bearer ',
)
SAFE_ARG_KEYS = frozenset({
    'destination', 'child_id', 'query', 'child_query', 'continuation', 'requested_metric',
    'as_of', 'subject_key',
})
MAX_TEXT = 2000


def new_request_id():
    return str(uuid.uuid4())


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def audit_path():
    raw = (os.environ.get(AUDIT_ENV) or '').strip()
    if raw:
        return Path(raw)
    if os.environ.get('CLC_TESTING') == '1':
        return None
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            folder = Path(current_app.instance_path) / 'assistant_audit'
            folder.mkdir(parents=True, exist_ok=True)
            return folder / 'assistant_audit.jsonl'
    except Exception:
        pass
    folder = Path('logs')
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'assistant_audit.jsonl'


def safe_text(value, limit=MAX_TEXT):
    text = ' '.join(str(value or '').split())
    for marker in BLOCKED_VALUE_MARKERS:
        if marker in text:
            text = text.replace(marker, '[redacted]')
    if 'review_text' in text or len(text) > 8000:
        return text[:120] + '…'
    return text[:limit]


def safe_args(arguments):
    args = arguments if isinstance(arguments, dict) else {}
    out = {}
    for key, value in args.items():
        if key in BLOCKED_KEYS:
            continue
        if key not in SAFE_ARG_KEYS:
            continue
        if key == 'query':
            out[key] = safe_text(value, 120)
        else:
            out[key] = value if isinstance(value, (int, float, bool)) or value is None else str(value)[:80]
    return out


def safe_error(code):
    allowed = {
        'unknown_tool', 'forbidden', 'invalid_child', 'unknown_destination',
        'missing_child', 'provider_error', 'invalid_request', 'question_limit',
        'tool_round_limit', 'disabled',
    }
    raw = str(code or '')
    if raw in allowed:
        return raw
    if raw:
        return 'error'
    return None


def safe_state_summary(state):
    raw = state if isinstance(state, dict) else {}
    pending = raw.get('pending_action') if isinstance(raw.get('pending_action'), dict) else {}
    summary = {
        'active_child_id': raw.get('active_child_id'),
        'active_subject': str(raw.get('active_subject') or '')[:20] or None,
        'active_topic': str(raw.get('active_topic') or '')[:20] or None,
    }
    if pending:
        summary['pending_action'] = {
            'type': str(pending.get('type') or '')[:20],
            'destination': str(pending.get('destination') or '')[:40] or None,
            'tool': str(pending.get('tool') or '')[:40] or None,
            'awaiting': str(pending.get('awaiting') or '')[:30],
            'missing': [
                str(item)[:20]
                for item in (pending.get('missing') or ())
                if isinstance(item, str)
            ][:4],
            'candidate_child_id': pending.get('candidate_child_id'),
            'candidate_count': len(pending.get('candidates') or ()),
            'match_type': str(pending.get('match_type') or '')[:20] or None,
        }
    return summary


def append_event(event):
    path = audit_path()
    if path is None:
        return
    payload = dict(event or {})
    payload['logged_at'] = now_iso()
    line = json.dumps(payload, ensure_ascii=False, default=str)
    if any(marker in line for marker in ('sk-', 'OPENAI_API_KEY')):
        line = json.dumps({'event': payload.get('event'), 'request_id': payload.get('request_id'), 'redacted': True})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(line + '\n')
    except OSError:
        return


def record_request_start(recorder):
    append_event({
        'event': 'request',
        'request_id': recorder.get('request_id'),
        'timestamp': recorder.get('timestamp') or now_iso(),
        'user_id': recorder.get('user_id'),
        'user_role': recorder.get('user_role'),
        'page_endpoint': recorder.get('page_endpoint'),
        'page_child_id': recorder.get('page_child_id'),
        'as_of': recorder.get('as_of'),
        'user_prompt': safe_text(recorder.get('user_prompt')),
        'provider': recorder.get('provider'),
        'model': recorder.get('model'),
        'intent': recorder.get('intent'),
        'source_kind': recorder.get('source_kind'),
        'conversation_state': safe_state_summary(recorder.get('conversation_state')),
    })


def record_tool(recorder, *, name, arguments, allowed, success, error=None, latency_ms=None, destination=None):
    append_event({
        'event': 'tool',
        'request_id': recorder.get('request_id'),
        'tool_name': name,
        'safe_args': safe_args(arguments),
        'allowed': bool(allowed),
        'success': bool(success),
        'latency_ms': latency_ms,
        'error': safe_error(error),
        'navigation_destination': destination,
    })


def record_request_end(recorder):
    event = {
        'event': 'response',
        'request_id': recorder.get('request_id'),
        'resolved_child_id': recorder.get('resolved_child_id'),
        'resolved_subject': recorder.get('resolved_subject'),
        'resolved_topic': recorder.get('resolved_topic'),
        'rag_source_ids': recorder.get('rag_source_ids') or [],
        'navigation_destination': recorder.get('navigation_destination'),
        'final_status': recorder.get('final_status') or 'ok',
        'displayed_response': safe_text(recorder.get('displayed_response')),
        'total_latency_ms': recorder.get('total_latency_ms'),
        'safe_error_code': safe_error(recorder.get('error')),
        'tool_round_limit': bool(recorder.get('tool_round_limit')),
        'feedback_enabled': bool(recorder.get('feedback_enabled')),
        'conversation_state': safe_state_summary(recorder.get('conversation_state')),
        'last_user_kind': recorder.get('last_user_kind'),
    }
    if recorder.get('candidate_count') is not None:
        try:
            event['candidate_count'] = int(recorder.get('candidate_count'))
        except (TypeError, ValueError):
            pass
    match_type = recorder.get('match_type')
    if match_type in {'exact', 'partial', 'fuzzy'}:
        event['match_type'] = match_type
    if recorder.get('selected_candidate_index') is not None:
        try:
            event['selected_candidate_index'] = int(recorder.get('selected_candidate_index'))
        except (TypeError, ValueError):
            pass
    append_event(event)


def record_feedback(*, request_id, user_id, rating):
    if rating not in {'positive', 'negative'}:
        return False
    if not isinstance(request_id, str) or not re.match(r'^[0-9a-fA-F-]{8,36}$', request_id):
        return False
    append_event({
        'event': 'feedback',
        'request_id': request_id[:36],
        'user_id': user_id,
        'feedback': rating,
    })
    return True


def start_timer():
    return time.perf_counter()


def elapsed_ms(started):
    if not started:
        return None
    return int((time.perf_counter() - started) * 1000)
