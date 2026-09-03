"""Developer-only semantic mapping batch. scheduler 아님.

local canonical DB의 unmapped label을 한 번 분류한다.
OPENAI_API_KEY가 있으면 실제 API를 1회 호출한다.
API key 값 / 아동 이름 / created_by 를 출력하지 않는다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_local_env(env_path=None):
    from dotenv import load_dotenv
    path = Path(env_path) if env_path is not None else ROOT / '.env'
    load_dotenv(path, override=False)


def collect_canonical_records():
    from app import db, fetch_child_daily_point_records
    rows = db.session.execute(
        db.text('SELECT DISTINCT child_id FROM daily_points ORDER BY child_id')
    ).fetchall()
    records = []
    for row in rows:
        records.extend(fetch_child_daily_point_records(row[0]))
    return records


def main():
    load_local_env()
    from app import app
    from features.points.semantic_classifier import (
        MODEL_ENV,
        classify_and_store_unmapped_labels,
        resolve_semantic_model,
    )

    if not os.environ.get('OPENAI_API_KEY'):
        print('not run: OPENAI_API_KEY is not set')
        return 2
    model = resolve_semantic_model()
    if not model:
        print(f'not run: {MODEL_ENV} (or GROWTH_AI_MODEL) is not set')
        return 2

    with app.app_context():
        records = collect_canonical_records()
        summary = classify_and_store_unmapped_labels(records)
        print('model_env', MODEL_ENV)
        print('candidate_count', summary['candidate_count'])
        print('llm_calls', summary['llm_calls'])
        print('classified_count', summary['classified_count'])
        print('stored_count', summary['stored_count'])
        print('failed_count', summary['failed_count'])
        if summary.get('error'):
            print('error', summary['error'])
    return 0 if not summary.get('error') else 1


if __name__ == '__main__':
    raise SystemExit(main())
