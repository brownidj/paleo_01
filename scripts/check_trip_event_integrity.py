#!/usr/bin/env python3
import argparse
import sqlite3
from pathlib import Path


def enable_foreign_keys(conn: sqlite3.Connection) -> bool:
    conn.execute("PRAGMA foreign_keys = ON")
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    return bool(row and int(row[0]) == 1)


def collect_integrity_metrics(conn: sqlite3.Connection) -> dict[str, int]:
    metrics: dict[str, int] = {}
    metrics["finds_without_event"] = int(
        conn.execute("SELECT COUNT(*) FROM Finds WHERE collection_event_id IS NULL").fetchone()[0]
    )
    metrics["events_without_trip"] = int(
        conn.execute("SELECT COUNT(*) FROM CollectionEvents WHERE trip_id IS NULL").fetchone()[0]
    )
    metrics["find_event_trip_mismatch"] = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM Finds f
            JOIN CollectionEvents ce ON ce.id = f.collection_event_id
            WHERE (f.trip_id IS NULL AND ce.trip_id IS NOT NULL)
               OR (f.trip_id IS NOT NULL AND ce.trip_id IS NULL)
               OR (f.trip_id IS NOT NULL AND ce.trip_id IS NOT NULL AND f.trip_id <> ce.trip_id)
            """
        ).fetchone()[0]
    )
    metrics["mixed_trip_events"] = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT collection_event_id
                FROM Finds
                WHERE collection_event_id IS NOT NULL
                GROUP BY collection_event_id
                HAVING COUNT(DISTINCT trip_id) > 1
            )
            """
        ).fetchone()[0]
    )
    return metrics


def has_violations(metrics: dict[str, int]) -> bool:
    return any(v > 0 for v in metrics.values())


def main() -> None:
    parser = argparse.ArgumentParser(description="Check trip/event/find integrity constraints.")
    parser.add_argument("--db", default="data/paleo_trips_01.db", help="SQLite database path")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        fk_enabled = enable_foreign_keys(conn)
        metrics = collect_integrity_metrics(conn)
    finally:
        conn.close()

    print(f"db={db_path}")
    print(f"foreign_keys_enabled={1 if fk_enabled else 0}")
    for key in sorted(metrics):
        print(f"{key}={metrics[key]}")

    if not fk_enabled:
        raise SystemExit("Integrity check failed: foreign_keys pragma is not enabled.")
    if has_violations(metrics):
        raise SystemExit("Integrity check failed: one or more integrity metrics are non-zero.")

    print("Integrity check passed.")


if __name__ == "__main__":
    main()
