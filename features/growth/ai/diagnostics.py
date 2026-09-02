"""Growth AI generation/attempt 집계. UI/대시보드가 아니다.

OpenAI/AWS를 호출하지 않는다. 저장된 row만 집계한다.
아동 이름 등 식별자는 넣지 않는다.
"""
from __future__ import annotations

import json
import re
from collections import Counter

SUCCESS = 'SUCCESS'
FAILED = 'FAILED'
PENDING = 'PENDING'
ATTEMPT_FAIL = {
    'TIMEOUT',
    'GENERATOR_ERROR',
    'PARSE_ERROR',
    'VALIDATOR_REJECT',
    'SAFETY_REJECT',
    'SAFETY_ERROR',
    'CONFIG',
}
FAILURE_BUCKETS = (
    'TIMEOUT',
    'GENERATOR_ERROR',
    'PARSE_ERROR',
    'VALIDATOR_REJECT',
    'SAFETY_REJECT',
    'SAFETY_INTERVENED',
    'SAFETY_ERROR',
    'PERSISTENCE_ERROR',
)


def _load_json(value):
    if value is None or value == '':
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode('utf-8', errors='replace')
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _rate(num, den):
    if not den:
        return None
    return round(num / den, 4)


def _percentile(values, p):
    ordered = sorted(item for item in values if isinstance(item, (int, float)))
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    frac = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * frac


def _text_snippets(output, limit=4):
    parsed = _load_json(output)
    texts = []
    if isinstance(parsed, dict):
        for key in ('priority_insight', 'interpretation', 'next_check', 'summary'):
            item = parsed.get(key)
            if isinstance(item, dict) and isinstance(item.get('text'), str):
                texts.append(item['text'].strip())
            elif isinstance(item, str) and item.strip():
                texts.append(item.strip())
        for key in ('observations', 'next_actions', 'suggestions'):
            for item in parsed.get(key) or []:
                if isinstance(item, dict) and isinstance(item.get('text'), str):
                    texts.append(item['text'].strip())
                elif isinstance(item, str) and item.strip():
                    texts.append(item.strip())
    snippets = []
    for text in texts:
        cleaned = re.sub(r'\s+', ' ', text).strip()
        if cleaned:
            snippets.append(cleaned[:180])
        if len(snippets) >= limit:
            break
    return snippets


def _codes(value):
    parsed = _load_json(value)
    if isinstance(parsed, list):
        return [str(item) for item in parsed if item]
    if isinstance(parsed, str) and parsed:
        return [parsed]
    return []


def aggregate_growth_ai_logs(generations, attempts, *, prompt_version=None, runtime_signature=None):
    """generations/attempts: dict rows. child_id/name을 결과에 넣지 않는다."""
    gens = list(generations or [])
    if prompt_version:
        gens = [row for row in gens if row.get('prompt_version') == prompt_version]
    if runtime_signature:
        gens = [row for row in gens if row.get('runtime_signature') == runtime_signature]
    kept = {row.get('id') for row in gens}
    attempts_by_gen = {}
    for row in attempts or []:
        gid = row.get('generation_id')
        if gid not in kept:
            continue
        attempts_by_gen.setdefault(gid, []).append(row)
    for rows in attempts_by_gen.values():
        rows.sort(key=lambda item: (item.get('attempt_number') or 0, item.get('id') or 0))

    status_counts = Counter((row.get('status') or 'UNKNOWN') for row in gens)
    gen_failure = Counter((row.get('failure_code') or 'NONE') for row in gens if row.get('status') != SUCCESS)
    attempt_status = Counter()
    attempt_stage = Counter()
    attempt_failure = Counter()
    validator_codes = Counter()
    validator_codes_attempt = {1: Counter(), 2: Counter()}
    first_success = 0
    first_fail = 0
    logged = 0
    retried = 0
    recovered = 0
    retry_also_fail = 0
    pending_with_attempts = []
    pending_without_attempts = []
    fail_patterns = []
    unknown_ids = Counter()
    proxy_first_success = 0
    proxy_retry = 0
    proxy_recovered = 0
    proxy_retry_fail = 0
    latencies = []

    for gen in gens:
        gid = gen.get('id')
        rows = attempts_by_gen.get(gid) or []
        attempt_field = gen.get('attempt_count') or 1
        if gen.get('status') == SUCCESS and attempt_field <= 1:
            proxy_first_success += 1
        if attempt_field >= 2:
            proxy_retry += 1
            if gen.get('status') == SUCCESS:
                proxy_recovered += 1
            elif gen.get('status') == FAILED:
                proxy_retry_fail += 1
        if gen.get('status') == PENDING:
            info = {
                'generation_id': gid,
                'created_at': gen.get('created_at'),
                'attempt_count_field': gen.get('attempt_count'),
                'logged_attempts': len(rows),
            }
            if rows:
                pending_with_attempts.append(info)
            else:
                pending_without_attempts.append(info)
        if not rows:
            continue
        logged += 1
        first = rows[0]
        first_status = first.get('status')
        if first_status == SUCCESS:
            first_success += 1
        else:
            first_fail += 1
        if len(rows) >= 2:
            retried += 1
            second = rows[1]
            if first_status != SUCCESS and second.get('status') == SUCCESS and gen.get('status') == SUCCESS:
                recovered += 1
            elif first_status != SUCCESS and second.get('status') != SUCCESS:
                retry_also_fail += 1
        for row in rows:
            status = row.get('status') or 'UNKNOWN'
            attempt_status[status] += 1
            if row.get('stage'):
                attempt_stage[row.get('stage')] += 1
            if status != SUCCESS:
                attempt_failure[row.get('failure_code') or status] += 1
            latency = row.get('total_latency_ms')
            if isinstance(latency, (int, float)):
                latencies.append(latency)
            number = row.get('attempt_number')
            for code in _codes(row.get('validator_codes')):
                validator_codes[code] += 1
                if number in validator_codes_attempt:
                    validator_codes_attempt[number][code] += 1
            if status == 'VALIDATOR_REJECT':
                unknown = [
                    item.get('evidence_id')
                    for item in (_load_json(row.get('validator_issues')) or [])
                    if isinstance(item, dict) and item.get('code') == 'UNKNOWN_EVIDENCE_ID'
                    and item.get('evidence_id')
                ]
                for item in unknown:
                    unknown_ids[item] += 1
                fail_patterns.append({
                    'generation_id': gid,
                    'attempt_number': number,
                    'codes': _codes(row.get('validator_codes')),
                    'unknown_ids': unknown,
                    'snippets': _text_snippets(row.get('generated_output')),
                })

    buckets = {code: int(attempt_failure.get(code, 0)) for code in FAILURE_BUCKETS}
    buckets['OTHER'] = sum(
        count for code, count in attempt_failure.items() if code not in FAILURE_BUCKETS
    )
    gen_buckets = {code: int(gen_failure.get(code, 0)) for code in FAILURE_BUCKETS}
    gen_buckets['OTHER'] = sum(
        count for code, count in gen_failure.items()
        if code not in FAILURE_BUCKETS and code != 'NONE'
    )
    return {
        'generation_count': len(gens),
        'status_counts': dict(status_counts),
        'final_success_count': status_counts.get(SUCCESS, 0),
        'final_success_rate': _rate(status_counts.get(SUCCESS, 0), len(gens)),
        'logged_generation_count': logged,
        'first_attempt_success_count': first_success,
        'first_attempt_fail_count': first_fail,
        'first_attempt_success_rate': _rate(first_success, logged),
        'first_attempt_fail_rate': _rate(first_fail, logged),
        'retry_count': retried,
        'retry_rate': _rate(retried, logged),
        'retry_recovery_count': recovered,
        'retry_also_fail_count': retry_also_fail,
        'retry_recovery_rate': _rate(recovered, retried),
        'generation_proxy': {
            'first_attempt_success_count': proxy_first_success,
            'retry_count': proxy_retry,
            'retry_recovery_count': proxy_recovered,
            'retry_also_fail_count': proxy_retry_fail,
            'retry_recovery_rate': _rate(proxy_recovered, proxy_retry),
        },
        'unknown_evidence_id_counts': dict(unknown_ids),
        'generation_failure_codes': dict(gen_failure),
        'generation_failure_buckets': gen_buckets,
        'attempt_status_counts': dict(attempt_status),
        'attempt_stage_counts': dict(attempt_stage),
        'attempt_failure_buckets': buckets,
        'validator_code_counts': dict(validator_codes),
        'validator_codes_attempt_1': dict(validator_codes_attempt[1]),
        'validator_codes_attempt_2': dict(validator_codes_attempt[2]),
        'pending_with_attempts': pending_with_attempts,
        'pending_without_attempts': pending_without_attempts,
        'validator_reject_samples': fail_patterns[:12],
        'attempt_latency_p50_ms': _percentile(latencies, 0.5),
        'attempt_latency_p95_ms': _percentile(latencies, 0.95),
        'prompt_version_filter': prompt_version,
        'runtime_signature_filter': runtime_signature,
    }
