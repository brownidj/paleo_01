#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from psycopg import connect
from psycopg.rows import dict_row


TABLE_COPY_ORDER = [
    ("Team_members", "team_members"),
    ("User_Accounts", "user_accounts"),
    ("Trips", "trips"),
    ("Locations", "locations"),
    ("GeologyContext", "geology_context"),
    ("Lithology", "lithology"),
    ("TripLocations", "trip_locations"),
    ("CollectionEvents", "collection_events"),
    ("Finds", "finds"),
]

SQLITE_FROM_POSTGRES_COLUMN_MAP = {
    "TripLocations": {
        "id": "trip_id",
    },
}


def _parse_sqlite_default(default_value: str | None):
    if default_value is None:
        return None
    raw = str(default_value).strip()
    if not raw:
        return None
    upper = raw.upper()
    if upper == "CURRENT_TIMESTAMP":
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _load_dotenv_if_present() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _sqlite_table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return [str(row[1]) for row in rows]


def _sqlite_not_null_info(conn: sqlite3.Connection, table_name: str) -> dict[str, tuple[bool, str, object]]:
    rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    info: dict[str, tuple[bool, str, object]] = {}
    for row in rows:
        col = str(row[1])
        col_type = str(row[2] or "")
        is_not_null = int(row[3] or 0) == 1
        default_value = _parse_sqlite_default(row[4])
        info[col] = (is_not_null, col_type, default_value)
    return info


def _coerce_sqlite_value(value, is_not_null: bool, col_type: str, default_value: object):
    if isinstance(value, datetime):
        value = value.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(value, date):
        value = value.isoformat()
    if value is not None:
        return value
    if not is_not_null:
        return None
    if default_value is not None:
        return default_value
    return 0 if "INT" in col_type.upper() else ""


def sync(sqlite_path: Path, database_url: str) -> None:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite file not found: {sqlite_path}")
    with connect(database_url, row_factory=dict_row) as pg_conn, sqlite3.connect(sqlite_path) as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_conn.execute("PRAGMA foreign_keys = OFF")
        for sqlite_table, postgres_table in TABLE_COPY_ORDER:
            sqlite_columns = _sqlite_table_columns(sqlite_conn, sqlite_table)
            sqlite_info = _sqlite_not_null_info(sqlite_conn, sqlite_table)
            col_map = SQLITE_FROM_POSTGRES_COLUMN_MAP.get(sqlite_table, {})
            with pg_conn.cursor() as cur:
                cur.execute(f'SELECT * FROM "{postgres_table}"')
                pg_rows = cur.fetchall()

            sqlite_conn.execute(f'DELETE FROM "{sqlite_table}"')
            if pg_rows:
                pg_column_names = set(pg_rows[0].keys())
                available_cols = [c for c in sqlite_columns if (c in pg_column_names or col_map.get(c) in pg_column_names)]
                if available_cols:
                    placeholders = ", ".join(["?"] * len(available_cols))
                    col_sql = ", ".join([f'"{c}"' for c in available_cols])
                    sqlite_conn.executemany(
                        f'INSERT INTO "{sqlite_table}" ({col_sql}) VALUES ({placeholders})',
                        [
                            tuple(
                                _coerce_sqlite_value(
                                    row[col if col in row else col_map.get(col, col)],
                                    sqlite_info.get(col, (False, "", None))[0],
                                    sqlite_info.get(col, (False, "", None))[1],
                                    sqlite_info.get(col, (False, "", None))[2],
                                )
                                for col in available_cols
                            )
                            for row in pg_rows
                        ],
                    )
                # keep sqlite autoincrement sequence aligned
                if "id" in sqlite_columns:
                    max_id = max(int(row.get("id") or 0) for row in pg_rows)
                    sqlite_conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (sqlite_table,))
                    sqlite_conn.execute("INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)", (sqlite_table, max_id))
        sqlite_conn.commit()
        sqlite_conn.execute("PRAGMA foreign_keys = ON")


def main() -> None:
    _load_dotenv_if_present()
    sqlite_path = Path(os.getenv("SQLITE_PATH", "data/paleo_trips_01.db")).resolve()
    database_url = os.getenv("PALEO_DESKTOP_DATABASE_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("PALEO_DESKTOP_DATABASE_URL or DATABASE_URL is required.")
    sync(sqlite_path, database_url)
    print(f"Synced PostgreSQL -> SQLite: {sqlite_path}")


if __name__ == "__main__":
    main()
