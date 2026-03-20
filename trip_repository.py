import sqlite3
import re
from pathlib import Path
from typing import Any


DEFAULT_TRIP_FIELDS = [
    "trip_code",
    "trip_name",
    "start_date",
    "end_date",
    "team",
    "region",
    "notes",
]


class TripRepository:
    def __init__(self, db_path: str = "paleo_trips_01.db"):
        self.db_path = Path(db_path).resolve()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_trips_table(self, fields: list[str] | None = None) -> None:
        trip_fields = fields or DEFAULT_TRIP_FIELDS
        cols = ", ".join([f'"{name}" TEXT' for name in trip_fields])
        with self._connect() as conn:
            conn.execute(f'CREATE TABLE IF NOT EXISTS "Trips" ({cols})')

    def get_fields(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute('PRAGMA table_info("Trips")').fetchall()
        fields = [row["name"] for row in rows]
        if fields:
            return fields
        self.ensure_trips_table()
        return DEFAULT_TRIP_FIELDS

    def list_trips(self) -> list[dict[str, Any]]:
        fields = self.get_fields()
        col_sql = ", ".join([f'"{name}"' for name in fields])
        with self._connect() as conn:
            rows = conn.execute(
                f'SELECT rowid, {col_sql} FROM "Trips" ORDER BY rowid DESC'
            ).fetchall()
        return [dict(row) for row in rows]

    def get_trip(self, row_id: int) -> dict[str, Any] | None:
        fields = self.get_fields()
        col_sql = ", ".join([f'"{name}"' for name in fields])
        with self._connect() as conn:
            row = conn.execute(
                f'SELECT rowid, {col_sql} FROM "Trips" WHERE rowid = ?',
                (row_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_trip(self, data: dict[str, Any]) -> int:
        fields = self.get_fields()
        insert_fields = [name for name in fields if name in data]
        if not insert_fields:
            raise ValueError("No valid Trip fields supplied.")
        col_sql = ", ".join([f'"{name}"' for name in insert_fields])
        placeholders = ", ".join(["?"] * len(insert_fields))
        values = [data[name] for name in insert_fields]
        with self._connect() as conn:
            cur = conn.execute(
                f'INSERT INTO "Trips" ({col_sql}) VALUES ({placeholders})',
                values,
            )
            return int(cur.lastrowid)

    def update_trip(self, row_id: int, data: dict[str, Any]) -> None:
        fields = self.get_fields()
        update_fields = [name for name in fields if name in data]
        if not update_fields:
            raise ValueError("No valid Trip fields supplied.")
        set_sql = ", ".join([f'"{name}" = ?' for name in update_fields])
        values = [data[name] for name in update_fields] + [row_id]
        with self._connect() as conn:
            conn.execute(
                f'UPDATE "Trips" SET {set_sql} WHERE rowid = ?',
                values,
            )

    def next_trip_code(self) -> str:
        with self._connect() as conn:
            rows = conn.execute('SELECT "trip_code" FROM "Trips"').fetchall()
        max_num = 0
        for row in rows:
            trip_code = row["trip_code"] or ""
            match = re.search(r"(\d+)$", trip_code)
            if match:
                max_num = max(max_num, int(match.group(1)))
        return f"TRIP-{max_num + 1:04d}"

    def list_active_users(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT name FROM "Users" WHERE active = 1 ORDER BY name'
            ).fetchall()
        return [row["name"] for row in rows]
