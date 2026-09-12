"""Tool Policy Gate. LLM 제안과 무관하게 서버에서 실행을 막는다.

매 tool call마다 독립적으로 통과해야 한다. 이전 call 허용을 재사용하지 않는다.
deny-by-default: allowlist 밖 이름, 스키마 밖 인자, 잘못된 타입은 실행하지 않는다.
"""
from __future__ import annotations

import time

from features.assistant.config import current_role, is_teacher_ui_user
from features.assistant.navigation import lookup_child, spec_for
from features.assistant.tools import ALLOWED_TOOLS, TOOL_SCHEMAS, execute_tool

WRITE_TOOLS = frozenset()
BLOCKED_ARG_KEYS = frozenset({
    'url', 'href', 'sql', 'query_sql', 'orm', 'raw_sql',
    'review_text', 'packet', 'observations', 'fill_missing', 'impute',
    'interpolate', 'fillna',
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
    'unknown_tool',
    'forbidden',
    'invalid_child',
    'unknown_destination',
    'unexpected_argument',
    'malformed_argument',
})
_INT_TYPES = frozenset({'integer'})
_STR_TYPES = frozenset({'string'})


def _build_arg_specs():
    specs = {}
    for schema in TOOL_SCHEMAS:
        name = schema.get('name')
        params = schema.get('parameters') or {}
        props = params.get('properties') or {}
        enums = {}
        types = {}
        for key, spec in props.items():
            if not isinstance(spec, dict):
                continue
            types[key] = spec.get('type')
            if isinstance(spec.get('enum'), (list, tuple)):
                enums[key] = frozenset(spec['enum'])
        specs[name] = {
            'keys': frozenset(props),
            'required': frozenset(params.get('required') or ()),
            'types': types,
            'enums': enums,
        }
    peer = specs.get('get_subject_peer_reference') or {
        'keys': frozenset({'child_id', 'as_of', 'subject_key'}),
        'required': frozenset(),
        'types': {'child_id': 'integer', 'as_of': 'string', 'subject_key': 'string'},
        'enums': {'subject_key': frozenset({'math', 'korean', 'ssen'})},
    }
    specs['get_peer_facts'] = peer
    return specs


ARG_SPECS = _build_arg_specs()


def gated_execute(name, arguments, *, page_context=None, role=None, conversation_state=None, audit=None):
    role = current_role() if role is None else role
    page_context = page_context or {}
    started = time.perf_counter()
    if not is_teacher_ui_user(role):
        result = {'ok': False, 'error': 'forbidden'}
        _audit_tool(audit, name, arguments, result, allowed=False, started=started)
        return result
    if name not in ALLOWED_TOOLS or name in WRITE_TOOLS:
        result = {'ok': False, 'error': 'unknown_tool'}
        _audit_tool(audit, name, arguments, result, allowed=False, started=started)
        return result
    args, error = _validated_args(name, arguments)
    if error:
        result = {'ok': False, 'error': error}
        _audit_tool(audit, name, arguments if isinstance(arguments, dict) else {}, result, allowed=False, started=started)
        return result
    if name in FACT_CHILD_TOOLS:
        args, child_error = _bind_child_arg(args, page_context=page_context, conversation_state=conversation_state)
        if child_error:
            result = {'ok': False, 'error': child_error}
            _audit_tool(audit, name, args, result, allowed=False, started=started)
            return result
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


def _validated_args(name, arguments):
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return {}, 'malformed_argument'
    spec = ARG_SPECS.get(name)
    if spec is None:
        return {}, 'unknown_tool'
    for key in arguments:
        if key in BLOCKED_ARG_KEYS:
            return {}, 'forbidden'
        if key not in spec['keys']:
            return {}, 'unexpected_argument'
    args = {}
    for key, value in arguments.items():
        if value is None:
            continue
        coerced, type_error = _coerce_arg(spec, key, value)
        if type_error:
            return {}, type_error
        args[key] = coerced
    if name == 'search_child' and not args.get('continuation'):
        args['continuation'] = 'search_only'
    for key in spec['required']:
        if key not in args or args.get(key) in (None, ''):
            return {}, 'malformed_argument'
    return args, None


def _coerce_arg(spec, key, value):
    expected = spec['types'].get(key)
    enums = spec['enums'].get(key)
    if expected in _INT_TYPES:
        parsed = _as_int(value)
        if parsed is None:
            return None, 'malformed_argument'
        value = parsed
    elif expected in _STR_TYPES:
        if isinstance(value, bool) or not isinstance(value, str):
            return None, 'malformed_argument'
        value = value.strip()
        if key in {'query', 'child_query', 'focus'}:
            value = value[:200]
        elif key == 'as_of':
            value = value[:32]
        else:
            value = value[:80]
    if enums is not None and value not in enums:
        if key == 'destination':
            return None, 'unknown_destination'
        return None, 'malformed_argument'
    return value, None


def _as_int(value):
    if isinstance(value, bool) or isinstance(value, float):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _bind_child_arg(args, *, page_context, conversation_state):
    """명시적 child_id가 있으면 그 값만 쓴다. 실패 시 conversation child로 조용히 바꾸지 않는다."""
    if 'child_id' in args and args.get('child_id') not in (None, '', False):
        child = lookup_child(args.get('child_id'))
        if child is None:
            return args, 'invalid_child'
        args['child_id'] = child.id
        return args, None
    convo_child = lookup_child((conversation_state or {}).get('active_child_id'))
    if convo_child is not None:
        args['child_id'] = convo_child.id
        return args, None
    page_child = lookup_child((page_context or {}).get('child_id'))
    if page_child is not None:
        args['child_id'] = page_child.id
        return args, None
    return args, None
