"""Canonical local SQLite Growth AI attempt 집계. 원격 DB/OpenAI/AWS 호출 없음."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features.growth.ai.diagnostics import aggregate_growth_ai_logs

CANONICAL = (ROOT / 'instance' / 'child_center.db').resolve()


def _rows(cur, sql):
    cur.execute(sql)
    cols = [item[0] for item in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def main():
    if not CANONICAL.exists():
        raise SystemExit('canonical sqlite missing')
    con = sqlite3.connect(str(CANONICAL))
    cur = con.cursor()
    generations = _rows(cur, """
        SELECT id, status, failure_code, attempt_count, created_at, completed_at
        FROM growth_ai_generation
        ORDER BY id
    """)
    attempts = _rows(cur, """
        SELECT id, generation_id, attempt_number, status, stage, failure_code,
               validator_codes, generated_output, started_at, completed_at
        FROM growth_ai_attempt
        ORDER BY generation_id, attempt_number
    """)
    con.close()
    stats = aggregate_growth_ai_logs(generations, attempts)
    print(json.dumps(stats, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
