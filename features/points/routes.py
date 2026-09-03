"""Machine-to-machine semantic batch endpoint.

GitHub Actions 등 외부 스케줄러가 Bearer token으로만 호출한다.
Flask-Login/session 인증과 섞지 않는다.
semantic category mapping만 변경한다. amount/net/accounting은 건드리지 않는다.
"""
from __future__ import annotations

import hmac
import os

from flask import Blueprint, jsonify, request

from features.points.semantic_classifier import classify_and_store_unmapped_labels

points_internal_bp = Blueprint('points_internal', __name__)

BATCH_TOKEN_ENV = 'POINT_SEMANTIC_BATCH_TOKEN'

# aggregate만. raw label / child / user / token / model response 금지.
RESPONSE_COUNT_KEYS = (
    'candidate_count',
    'classified_count',
    'stored_count',
    'failed_count',
    'remaining_count',
)


def _bearer_token(header_value):
    if not header_value:
        return None
    parts = str(header_value).split(None, 1)
    if len(parts) != 2 or parts[0] != 'Bearer':
        return None
    token = parts[1].strip()
    return token or None


def _auth_failure_response():
    """token env 미설정 → 503. 요청 token 없음/불일치 → 401. 통과 → None."""
    expected = (os.environ.get(BATCH_TOKEN_ENV) or '').strip()
    if not expected:
        return jsonify({'status': 'unavailable'}), 503
    provided = _bearer_token(request.headers.get('Authorization'))
    if provided is None:
        return jsonify({'status': 'unauthorized'}), 401
    if not hmac.compare_digest(expected.encode('utf-8'), provided.encode('utf-8')):
        return jsonify({'status': 'unauthorized'}), 401
    return None


def _collect_canonical_records():
    from app import db, fetch_child_daily_point_records
    rows = db.session.execute(
        db.text('SELECT DISTINCT child_id FROM daily_points ORDER BY child_id')
    ).fetchall()
    records = []
    for row in rows:
        records.extend(fetch_child_daily_point_records(row[0]))
    return records


@points_internal_bp.route('/internal/point-semantic-classify', methods=['POST'])
def point_semantic_classify():
    denied = _auth_failure_response()
    if denied is not None:
        return denied
    records = _collect_canonical_records()
    summary = classify_and_store_unmapped_labels(records)
    payload = {key: int(summary.get(key) or 0) for key in RESPONSE_COUNT_KEYS}
    if summary.get('error'):
        payload['status'] = 'failed'
        return jsonify(payload), 502
    payload['status'] = 'ok'
    return jsonify(payload), 200
