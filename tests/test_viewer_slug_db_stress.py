#!/usr/bin/env python
"""
DB-backed viewer_slug stress test (v1, minimum viable).

This script runs random add/delete/activity/reset operations against a PostgreSQL
database and validates viewer_slug behavior under repeated semester cycles.

Example:
  python tests/test_viewer_slug_db_stress.py --dsn "postgresql://..."
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Set

try:
    import psycopg2
except ImportError:  # pragma: no cover - runtime dependency guard
    psycopg2 = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from viewer_slug_utils import VIEWER_SLUG_RE, extract_viewer_slug, generate_viewer_slug


@dataclass
class Metrics:
    added: int = 0
    deleted: int = 0
    activity_writes: int = 0
    resets: int = 0
    valid_link_checks: int = 0
    broken_link_checks: int = 0
    invalid_link_checks: int = 0
    retired_link_checks: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stress-test viewer_slug lifecycle on PostgreSQL."
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL DSN. If omitted, DATABASE_URL env var is used.",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=6,
        help="How many semester cycles to simulate (default: 6).",
    )
    parser.add_argument(
        "--ops-per-cycle",
        type=int,
        default=500,
        help="Random operations per cycle before reset (default: 500).",
    )
    parser.add_argument(
        "--max-active",
        type=int,
        default=60,
        help="Soft cap for active synthetic children (default: 60).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260525,
        help="Random seed for reproducible failures (default: 20260525).",
    )
    parser.add_argument(
        "--check-every",
        type=int,
        default=25,
        help="Run invariant checks every N operations (default: 25).",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete all synthetic rows created by this run at the end.",
    )
    return parser.parse_args()


def is_viewer_slug(value: Optional[str]) -> bool:
    return bool(value and VIEWER_SLUG_RE.fullmatch(value))


def ensure_schema(cur) -> None:
    """Fail fast if required schema is missing."""
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'child' AND column_name = 'viewer_slug'
        """
    )
    if cur.fetchone() is None:
        raise RuntimeError(
            "Missing child.viewer_slug column. Add it first on this database."
        )

    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'child' AND column_name = 'cumulative_points'
        """
    )
    if cur.fetchone() is None:
        raise RuntimeError(
            "Missing child.cumulative_points column. Add it first on this database."
        )


def get_or_create_actor_user_id(cur, run_tag: str) -> int:
    """Pick an existing user, or create one if table is empty."""
    cur.execute('SELECT id FROM "user" ORDER BY id LIMIT 1')
    row = cur.fetchone()
    if row:
        return int(row[0])

    cur.execute(
        'INSERT INTO "user" (name, role, username) VALUES (%s, %s, %s) RETURNING id',
        (f"Stress Actor {run_tag}", "developer", f"stress_actor_{run_tag}"),
    )
    created = cur.fetchone()
    if created is None:
        raise RuntimeError("Failed to create fallback actor user.")
    return int(created[0])


def resolve_slug_to_child_id(cur, raw_token: str) -> Optional[int]:
    normalized = extract_viewer_slug(raw_token)
    if not normalized:
        return None
    cur.execute("SELECT id FROM child WHERE viewer_slug = %s LIMIT 1", (normalized,))
    row = cur.fetchone()
    return int(row[0]) if row else None


def generate_unique_slug(cur, reserved: Set[str]) -> str:
    """
    Generate a slug that is unused in DB and not reused in this test run.
    """
    for _ in range(500):
        candidate = generate_viewer_slug()
        if candidate in reserved:
            continue
        cur.execute("SELECT 1 FROM child WHERE viewer_slug = %s LIMIT 1", (candidate,))
        if cur.fetchone() is None:
            return candidate
    raise RuntimeError("Unable to generate unique viewer_slug after many attempts.")


def add_child(cur, rng: random.Random, serial: int, run_tag: str, reserved: Set[str]) -> tuple[int, str]:
    grade = rng.randint(1, 6)
    slug = generate_unique_slug(cur, reserved)
    name = f"STRESS_{run_tag}_{serial:05d}"
    cur.execute(
        """
        INSERT INTO child (name, grade, viewer_slug, cumulative_points, include_in_stats)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (name, grade, slug, 0, False),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Failed to insert synthetic child.")
    return int(row[0]), slug


def delete_child(cur, child_id: int) -> None:
    # Matches app behavior: manually clear non-cascade tables first.
    cur.execute("DELETE FROM points_history WHERE child_id = %s", (child_id,))
    cur.execute("DELETE FROM notification WHERE child_id = %s", (child_id,))
    cur.execute("DELETE FROM child_note WHERE child_id = %s", (child_id,))
    cur.execute("DELETE FROM daily_points WHERE child_id = %s", (child_id,))
    cur.execute("DELETE FROM learning_record WHERE child_id = %s", (child_id,))
    cur.execute("DELETE FROM child WHERE id = %s", (child_id,))


def write_activity_bundle(cur, rng: random.Random, child_id: int, actor_user_id: int) -> None:
    when = date.today() - timedelta(days=rng.randint(0, 180))
    korean = rng.choice((0, 100, 200))
    math = rng.choice((0, 100, 200))
    ssen = rng.choice((0, 100, 200))
    reading = rng.choice((0, 100, 200))
    manual = rng.choice((0, 50, 100))
    total = korean + math + ssen + reading + manual

    cur.execute(
        """
        INSERT INTO daily_points (
            child_id, date, korean_points, math_points, ssen_points, reading_points,
            manual_points, total_points, created_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (child_id, when, korean, math, ssen, reading, manual, total, actor_user_id),
    )

    cur.execute(
        """
        INSERT INTO learning_record (child_id, date, created_by)
        VALUES (%s, %s, %s)
        """,
        (child_id, when, actor_user_id),
    )

    cur.execute(
        """
        INSERT INTO child_note (child_id, note, created_by)
        VALUES (%s, %s, %s)
        """,
        (child_id, "stress note", actor_user_id),
    )

    cur.execute(
        """
        INSERT INTO points_history (
            child_id, date, changed_by, change_type, change_reason,
            old_total_points, new_total_points
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (child_id, when, actor_user_id, "update", "stress_test", 0, total),
    )

    cur.execute(
        """
        INSERT INTO notification (title, message, child_id, created_by, type, priority)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        ("stress", "stress notification", child_id, actor_user_id, "info", 1),
    )

    cur.execute(
        "UPDATE child SET cumulative_points = cumulative_points + %s WHERE id = %s",
        (total, child_id),
    )


def perform_semester_reset(
    cur,
    active_children: Dict[int, str],
    retired_slugs: Set[str],
    reserved_slugs: Set[str],
) -> None:
    if not active_children:
        return

    ids = list(active_children.keys())
    cur.execute("DELETE FROM points_history WHERE child_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM notification WHERE child_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM child_note WHERE child_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM daily_points WHERE child_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM learning_record WHERE child_id = ANY(%s)", (ids,))

    old_slugs = dict(active_children)
    for child_id, old_slug in old_slugs.items():
        retired_slugs.add(old_slug)
        new_slug = generate_unique_slug(cur, reserved_slugs)
        reserved_slugs.add(new_slug)
        active_children[child_id] = new_slug
        cur.execute(
            "UPDATE child SET cumulative_points = 0, viewer_slug = %s WHERE id = %s",
            (new_slug, child_id),
        )


def assert_invariants(
    cur,
    active_children: Dict[int, str],
    retired_slugs: Set[str],
    rng: random.Random,
    metrics: Metrics,
) -> None:
    if not active_children:
        return

    active_ids = list(active_children.keys())
    cur.execute(
        "SELECT id, viewer_slug FROM child WHERE id = ANY(%s) ORDER BY id",
        (active_ids,),
    )
    rows = cur.fetchall()
    assert len(rows) == len(active_children), (
        f"Active row mismatch: expected={len(active_children)}, fetched={len(rows)}"
    )

    seen = set()
    for child_id, slug in rows:
        child_id_int = int(child_id)
        assert child_id_int in active_children, f"Unexpected child id in DB: {child_id_int}"
        assert slug == active_children[child_id_int], (
            f"Slug mismatch for child_id={child_id_int}: db={slug}, mem={active_children[child_id_int]}"
        )
        assert is_viewer_slug(slug), f"Invalid slug format: {slug}"
        assert slug not in seen, f"Duplicate slug in active set: {slug}"
        seen.add(slug)

    # Validate valid + broken-link recovery path.
    sample_count = min(5, len(active_children))
    sample_pairs = rng.sample(list(active_children.items()), sample_count)
    for child_id, slug in sample_pairs:
        resolved = resolve_slug_to_child_id(cur, slug)
        assert resolved == child_id, f"Valid slug failed: {slug} -> {resolved} (expected {child_id})"
        metrics.valid_link_checks += 1

        broken_token = f"/viewer/report/{slug}%20%EC%B5%9C%EC%A2%85%20%ED%8F%AC%EC%9D%B8%ED%8A%B8"
        recovered = extract_viewer_slug(broken_token)
        assert recovered == slug, f"Broken-link extraction failed: token={broken_token}"
        recovered_resolved = resolve_slug_to_child_id(cur, broken_token)
        assert recovered_resolved == child_id, (
            f"Recovered slug failed: token={broken_token} -> {recovered_resolved}"
        )
        metrics.broken_link_checks += 1

    # Validate invalid links.
    for _ in range(3):
        invalid_token = "zz-invalid-token-" + str(rng.randint(100000, 999999))
        resolved = resolve_slug_to_child_id(cur, invalid_token)
        assert resolved is None, f"Invalid token unexpectedly resolved: {invalid_token} -> {resolved}"
        metrics.invalid_link_checks += 1

    # Validate retired links do not resolve anymore.
    if retired_slugs:
        retired_sample_size = min(5, len(retired_slugs))
        for retired in rng.sample(list(retired_slugs), retired_sample_size):
            resolved = resolve_slug_to_child_id(cur, retired)
            assert resolved is None, f"Retired slug unexpectedly resolved: {retired} -> {resolved}"
            metrics.retired_link_checks += 1


def cleanup_synthetic_rows(cur, run_tag: str) -> None:
    cur.execute("SELECT id FROM child WHERE name LIKE %s", (f"STRESS_{run_tag}_%",))
    ids = [int(row[0]) for row in cur.fetchall()]
    if not ids:
        return

    cur.execute("DELETE FROM points_history WHERE child_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM notification WHERE child_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM child_note WHERE child_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM daily_points WHERE child_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM learning_record WHERE child_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM child WHERE id = ANY(%s)", (ids,))


def run() -> int:
    args = parse_args()
    if psycopg2 is None:
        print(
            "ERROR: psycopg2 is required. Install with: pip install psycopg2-binary",
            file=sys.stderr,
        )
        return 2
    if not args.dsn:
        print("ERROR: missing --dsn and DATABASE_URL", file=sys.stderr)
        return 2
    if not args.dsn.startswith("postgresql://"):
        print("ERROR: this stress script expects a PostgreSQL DSN.", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    run_tag = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    metrics = Metrics()
    active_children: Dict[int, str] = {}
    retired_slugs: Set[str] = set()
    reserved_slugs: Set[str] = set()
    serial = 0

    started_at = time.time()
    print(
        f"[START] seed={args.seed} cycles={args.cycles} ops_per_cycle={args.ops_per_cycle} run_tag={run_tag}",
        flush=True,
    )

    with psycopg2.connect(args.dsn) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            ensure_schema(cur)
            actor_user_id = get_or_create_actor_user_id(cur, run_tag)
            conn.commit()

            print(f"[INFO] actor_user_id={actor_user_id}", flush=True)

            for cycle_idx in range(1, args.cycles + 1):
                for op_idx in range(1, args.ops_per_cycle + 1):
                    if not active_children:
                        operation = "add"
                    else:
                        roll = rng.random()
                        if len(active_children) < args.max_active and roll < 0.45:
                            operation = "add"
                        elif roll < 0.75:
                            operation = "delete"
                        else:
                            operation = "activity"

                    if operation == "add":
                        serial += 1
                        child_id, slug = add_child(cur, rng, serial, run_tag, reserved_slugs)
                        active_children[child_id] = slug
                        reserved_slugs.add(slug)
                        metrics.added += 1
                    elif operation == "delete" and active_children:
                        child_id = rng.choice(list(active_children.keys()))
                        old_slug = active_children.pop(child_id)
                        retired_slugs.add(old_slug)
                        delete_child(cur, child_id)
                        metrics.deleted += 1
                    elif operation == "activity" and active_children:
                        child_id = rng.choice(list(active_children.keys()))
                        write_activity_bundle(cur, rng, child_id, actor_user_id)
                        metrics.activity_writes += 1

                    if op_idx % args.check_every == 0:
                        assert_invariants(cur, active_children, retired_slugs, rng, metrics)

                    if op_idx % 100 == 0:
                        print(
                            f"[PROGRESS] cycle={cycle_idx}/{args.cycles} "
                            f"op={op_idx}/{args.ops_per_cycle} active={len(active_children)} "
                            f"added={metrics.added} deleted={metrics.deleted} "
                            f"activity={metrics.activity_writes}",
                            flush=True,
                        )

                    conn.commit()

                # Simulate semester reset at end of each cycle.
                perform_semester_reset(cur, active_children, retired_slugs, reserved_slugs)
                metrics.resets += 1
                assert_invariants(cur, active_children, retired_slugs, rng, metrics)
                conn.commit()
                print(
                    f"[CYCLE_DONE] cycle={cycle_idx}/{args.cycles} active={len(active_children)} "
                    f"resets={metrics.resets}",
                    flush=True,
                )

            if args.cleanup:
                cleanup_synthetic_rows(cur, run_tag)
                conn.commit()
                print(f"[CLEANUP] removed synthetic run rows for {run_tag}", flush=True)

    elapsed = time.time() - started_at
    print("[PASS] viewer_slug DB stress v1 completed", flush=True)
    print(
        f"[METRICS] added={metrics.added} deleted={metrics.deleted} "
        f"activity={metrics.activity_writes} resets={metrics.resets} "
        f"valid={metrics.valid_link_checks} broken={metrics.broken_link_checks} "
        f"invalid={metrics.invalid_link_checks} retired={metrics.retired_link_checks} "
        f"active_end={len(active_children)} elapsed_sec={elapsed:.1f}",
        flush=True,
    )
    print(f"[REPRODUCE] --seed {args.seed}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except AssertionError as exc:
        print(f"[FAIL] invariant assertion failed: {exc}", file=sys.stderr, flush=True)
        raise
