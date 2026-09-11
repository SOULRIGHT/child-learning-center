"""Tool Policy Gate. LLM 제안과 무관하게 서버에서 실행을 막는다.

매 tool call마다 독립적으로 통과해야 한다. 이전 call 허용을 재사용하지 않는다.
"""
from __future__ import annotations

import time

from features.assistant.config import current_role
from features.assistant.navigation import lookup_child, spec_for
from features.assistant.tools import ALLOWED_TOOLS, execute_tool

WRITE_TOOLS = frozenset()
BLOCKED_ARG_KEYS = frozenset({
    'url', 'href', 'sql', 'query_sql', 'orm', 'raw_sql',
    'review_text', 'packet', 'observations',
})
FACT_CHILD_TOOLS = frozenset({
    'get_growth_facts',
    'get_learning_facts',
    'get_points_facts',
    'get_reading_facts',
    'get_peer_facts',
    'get_subject_peer_reference',
    'navigate',
})


GATE_DENY = frozenset({
    'unknown_tool', 'forbidden', 'invalid_child', 'unknown_destination',
})


def gated_execute(name, arguments, *, page_context=None, role=None, conversation_state=None, audit=None):
    role = current_role() if role is None else role
    page_context = page_context or {}
    started = time.perf_counter()
    if name not in ALLOWED_TOOLS or name in WRITE_TOOLS:
        result = {'ok': False, 'error': 'unknown_tool'}
        _audit_tool(audit, name, arguments, result, allowed=False, started=started)
        return result
    args = _sanitize_args(arguments)
    if name in FACT_CHILD_TOOLS:
        args = _bind_child_arg(args, page_context=page_context, conversation_state=conversation_state)
        if name not in {'navigate', 'search_child'} and lookup_child(args.get('child_id')) is None:
            result = {'ok': False, 'error': 'invalid_child'}
            _audit_tool(audit, name, args, result, allowed=False, started=started)
            return result
        if name == 'navigate':
            dest = spec_for(args.get('destination'))
            if dest is None:
                result = {'ok': False, 'error': 'unknown_destination'}
                _audit_tool(audit, name, args, result, allowed=False, started=started)
                return result
    if name == 'search_help':
        args['query'] = str(args.get('query') or '')[:200]
    result = execute_tool(name, args, page_context=page_context, role=role)
    error = result.get('error') if isinstance(result, dict) else None
    allowed = error not in GATE_DENY
    _audit_tool(audit, name, args, result, allowed=allowed, started=started)
    return result


def _audit_tool(audit, name, arguments, result, *, allowed, started):
    if not audit:
        return
    from features.assistant.audit import elapsed_ms, record_tool
    result = result if isinstance(result, dict) else {}
    dest = result.get('destination') if name == 'navigate' else None
    record_tool(
        audit,
        name=name,
        arguments=arguments,
        allowed=allowed,
        success=bool(result.get('ok')),
        error=result.get('error'),
        latency_ms=elapsed_ms(started),
        destination=dest,
    )


def _sanitize_args(arguments):
    args = dict(arguments) if isinstance(arguments, dict) else {}
    for key in list(args):
        if key in BLOCKED_ARG_KEYS:
            args.pop(key, None)
    return args


def _bind_child_arg(args, *, page_context, conversation_state):
    if args.get('child_id') not in (None, '', False):
        child = lookup_child(args.get('child_id'))
        if child is None:
            args.pop('child_id', None)
        else:
            args['child_id'] = child.id
            return args
    convo_child = lookup_child((conversation_state or {}).get('active_child_id'))
    if convo_child is not None:
        args['child_id'] = convo_child.id
        return args
    page_child = lookup_child((page_context or {}).get('child_id'))
    if page_child is not None:
        args['child_id'] = page_child.id
    return args
