#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from psycopg import connect
from psycopg.rows import dict_row

from scripts.db.migrate_sqlite_to_postgres_schema_helpers import ensure_schema, sync_sequences, truncate_all
from scripts.db.migrate_sqlite_to_postgres_sync_chunks import (
    sync_collection_events_and_finds,
    sync_geology_and_trips,
    sync_people_and_locations,
)




def migrate(sqlite_path: Path, postgres_url: str, truncate_first: bool) -> dict[str, int]:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite file not found: {sqlite_path}")

    with sqlite3.connect(sqlite_path) as sqlite_conn, connect(postgres_url, row_factory=dict_row) as pg_conn:
        ensure_schema(pg_conn)
        if truncate_first:
            truncate_all(pg_conn)

        counts: dict[str, int] = {}
        counts.update(sync_people_and_locations(sqlite_conn, pg_conn))
        counts.update(sync_geology_and_trips(sqlite_conn, pg_conn))
        counts.update(sync_collection_events_and_finds(sqlite_conn, pg_conn))

        sync_sequences(
            pg_conn,
            [
                "team_members",
                "user_accounts",
                "locations",
                "geology_context",
                "lithology",
                "trips",
                "collection_events",
                "finds",
            ],
        )
        pg_conn.commit()
        return counts


def _resolve_postgres_url(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    env_value = os.getenv("DATABASE_URL", "").strip()
    if env_value:
        return env_value
    raise ValueError("DATABASE_URL is required. Pass --postgres-url or export DATABASE_URL.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite paleo data into PostgreSQL.")
    parser.add_argument("--sqlite", default="data/paleo_trips_01.db", help="Path to source SQLite DB.")
    parser.add_argument("--postgres-url", default=None, help="PostgreSQL DSN. Defaults to DATABASE_URL env var.")
    parser.add_argument(
        "--truncate-first",
        action="store_true",
        help="Truncate target tables before importing.",
    )
    args = parser.parse_args()

    postgres_url = _resolve_postgres_url(args.postgres_url)
    counts = migrate(Path(args.sqlite), postgres_url, truncate_first=args.truncate_first)
    print("Migration complete.")
    for table, count in counts.items():
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()
