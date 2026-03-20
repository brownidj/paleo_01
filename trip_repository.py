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

LOCATION_FIELDS = [
    "name",
    "latitude",
    "longitude",
    "altitude_value",
    "altitude_unit",
    "country_code",
    "state",
    "lga",
    "basin",
    "geogscale",
    "geography_comments",
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

    def ensure_locations_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "Locations" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                )
                """
            )
            existing = {row["name"] for row in conn.execute('PRAGMA table_info("Locations")').fetchall()}
            for field in LOCATION_FIELDS:
                if field not in existing:
                    conn.execute(f'ALTER TABLE "Locations" ADD COLUMN "{field}" TEXT')
            self._migrate_legacy_county_to_lga(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "CollectionEvents" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_id INTEGER NOT NULL,
                    collection_name TEXT NOT NULL,
                    collection_subset TEXT,
                    FOREIGN KEY (location_id) REFERENCES Locations(id)
                )
                """
            )
            self._migrate_legacy_collection_fields(conn)
            self._rebuild_locations_table_without_legacy_columns(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "TripLocations" (
                    trip_code TEXT NOT NULL,
                    location_id INTEGER NOT NULL,
                    PRIMARY KEY (trip_code, location_id),
                    FOREIGN KEY (trip_code) REFERENCES Trips(trip_code),
                    FOREIGN KEY (location_id) REFERENCES Locations(id)
                )
                """
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trip_locations_trip ON "TripLocations"(trip_code)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trip_locations_location ON "TripLocations"(location_id)')
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_trips_trip_code_unique ON "Trips"(trip_code)')
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_collection_events_location ON "CollectionEvents"(location_id)'
            )

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

    def list_users(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT id, name, phone_number, active FROM "Users"'
            ).fetchall()
        users = [dict(row) for row in rows]
        users.sort(
            key=lambda u: (
                0 if int(u.get("active", 0)) == 1 else 1,
                self._last_name(str(u.get("name", ""))),
                str(u.get("name", "")).lower(),
            )
        )
        return users

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT id, name, phone_number, active FROM "Users" WHERE id = ?',
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_user(self, name: str, phone_number: str, active: bool) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                'INSERT INTO "Users" (name, phone_number, active) VALUES (?, ?, ?)',
                (name, phone_number, 1 if active else 0),
            )
            return int(cur.lastrowid)

    def update_user(self, user_id: int, name: str, phone_number: str, active: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                'UPDATE "Users" SET name = ?, phone_number = ?, active = ? WHERE id = ?',
                (name, phone_number, 1 if active else 0, user_id),
            )

    def delete_user(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute('DELETE FROM "Users" WHERE id = ?', (user_id,))

    def list_locations(self) -> list[dict[str, Any]]:
        self.ensure_locations_table()
        col_sql = ", ".join([f'"{f}"' for f in LOCATION_FIELDS])
        with self._connect() as conn:
            location_rows = conn.execute(f'SELECT id, {col_sql} FROM "Locations"').fetchall()
            event_rows = conn.execute(
                """
                SELECT location_id, collection_name, collection_subset
                FROM "CollectionEvents"
                ORDER BY id
                """
            ).fetchall()
        locations = [dict(row) for row in location_rows]
        events_by_location: dict[int, list[dict[str, Any]]] = {}
        for row in event_rows:
            location_id = int(row["location_id"])
            events_by_location.setdefault(location_id, []).append(
                {
                    "collection_name": row["collection_name"],
                    "collection_subset": row["collection_subset"],
                }
            )
        for location in locations:
            events = events_by_location.get(int(location["id"]), [])
            location["collection_events"] = events
            first_event = events[0] if events else {}
            location["collection_name"] = first_event.get("collection_name")
            location["collection_subset"] = first_event.get("collection_subset")
        locations.sort(
            key=lambda r: (
                str(r.get("name", "")).lower(),
                str(r.get("lga", "")).lower(),
                str(r.get("state", "")).lower(),
            )
        )
        return locations

    def get_location(self, location_id: int) -> dict[str, Any] | None:
        self.ensure_locations_table()
        col_sql = ", ".join([f'"{f}"' for f in LOCATION_FIELDS])
        with self._connect() as conn:
            row = conn.execute(
                f'SELECT id, {col_sql} FROM "Locations" WHERE id = ?',
                (location_id,),
            ).fetchone()
            events = conn.execute(
                """
                SELECT collection_name, collection_subset
                FROM "CollectionEvents"
                WHERE location_id = ?
                ORDER BY id
                """,
                (location_id,),
            ).fetchall()
        if not row:
            return None
        location = dict(row)
        location_events = [
            {"collection_name": event["collection_name"], "collection_subset": event["collection_subset"]}
            for event in events
        ]
        location["collection_events"] = location_events
        first_event = location_events[0] if location_events else {}
        location["collection_name"] = first_event.get("collection_name")
        location["collection_subset"] = first_event.get("collection_subset")
        return location

    def create_location(self, data: dict[str, Any]) -> int:
        self.ensure_locations_table()
        events = self._normalize_collection_events(data.get("collection_events"))
        insert_fields = [name for name in LOCATION_FIELDS if name in data]
        with self._connect() as conn:
            if insert_fields:
                col_sql = ", ".join([f'"{name}"' for name in insert_fields])
                placeholders = ", ".join(["?"] * len(insert_fields))
                values = [data.get(name) for name in insert_fields]
                cur = conn.execute(
                    f'INSERT INTO "Locations" ({col_sql}) VALUES ({placeholders})',
                    values,
                )
            else:
                cur = conn.execute('INSERT INTO "Locations" DEFAULT VALUES')
            location_id = int(cur.lastrowid)
            if events:
                conn.executemany(
                    """
                    INSERT INTO "CollectionEvents" (location_id, collection_name, collection_subset)
                    VALUES (?, ?, ?)
                    """,
                    [(location_id, event["collection_name"], event["collection_subset"]) for event in events],
                )
            return location_id

    def update_location(self, location_id: int, data: dict[str, Any]) -> None:
        self.ensure_locations_table()
        has_events_key = "collection_events" in data
        events = self._normalize_collection_events(data.get("collection_events"))
        update_fields = [name for name in LOCATION_FIELDS if name in data]
        if not update_fields and not has_events_key:
            raise ValueError("No valid Location fields supplied.")
        with self._connect() as conn:
            if update_fields:
                set_sql = ", ".join([f'"{name}" = ?' for name in update_fields])
                values = [data.get(name) for name in update_fields] + [location_id]
                conn.execute(
                    f'UPDATE "Locations" SET {set_sql} WHERE id = ?',
                    values,
                )
            if has_events_key:
                conn.execute('DELETE FROM "CollectionEvents" WHERE location_id = ?', (location_id,))
                if events:
                    conn.executemany(
                        """
                        INSERT INTO "CollectionEvents" (location_id, collection_name, collection_subset)
                        VALUES (?, ?, ?)
                        """,
                        [(location_id, event["collection_name"], event["collection_subset"]) for event in events],
                    )

    @staticmethod
    def _last_name(name: str) -> str:
        parts = [p for p in name.strip().lower().split(" ") if p]
        return parts[-1] if parts else ""

    @staticmethod
    def _normalize_collection_events(raw_events: Any) -> list[dict[str, str | None]]:
        if not isinstance(raw_events, list):
            return []
        events: list[dict[str, str | None]] = []
        for raw in raw_events:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("collection_name") or "").strip()
            subset_raw = raw.get("collection_subset")
            subset = str(subset_raw).strip() if subset_raw is not None else ""
            if not name:
                continue
            events.append(
                {
                    "collection_name": name,
                    "collection_subset": subset or None,
                }
            )
        return events

    @staticmethod
    def _migrate_legacy_collection_fields(conn: sqlite3.Connection) -> None:
        location_columns = {row["name"] for row in conn.execute('PRAGMA table_info("Locations")').fetchall()}
        if "collection_name" not in location_columns:
            return
        rows = conn.execute(
            'SELECT id, collection_name, collection_subset FROM "Locations" WHERE collection_name IS NOT NULL'
        ).fetchall()
        for row in rows:
            location_id = int(row["id"])
            collection_name = str(row["collection_name"] or "").strip()
            collection_subset = row["collection_subset"]
            if not collection_name:
                continue
            existing = conn.execute(
                """
                SELECT 1 FROM "CollectionEvents"
                WHERE location_id = ? AND collection_name = ? AND COALESCE(collection_subset, '') = COALESCE(?, '')
                LIMIT 1
                """,
                (location_id, collection_name, collection_subset),
            ).fetchone()
            if existing:
                continue
            conn.execute(
                """
                INSERT INTO "CollectionEvents" (location_id, collection_name, collection_subset)
                VALUES (?, ?, ?)
                """,
                (location_id, collection_name, collection_subset),
            )

    @staticmethod
    def _rebuild_locations_table_without_legacy_columns(conn: sqlite3.Connection) -> None:
        location_columns = [row["name"] for row in conn.execute('PRAGMA table_info("Locations")').fetchall()]
        if (
            "collection_name" not in location_columns
            and "collection_subset" not in location_columns
            and "collection_aka" not in location_columns
            and "county" not in location_columns
        ):
            return

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS "Locations_new" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                latitude TEXT,
                longitude TEXT,
                altitude_value TEXT,
                altitude_unit TEXT,
                country_code TEXT,
                state TEXT,
                lga TEXT,
                basin TEXT,
                geogscale TEXT,
                geography_comments TEXT
            )
            """
        )
        existing_fields = [field for field in LOCATION_FIELDS if field in location_columns]
        insert_columns = ["id"] + existing_fields
        col_sql = ", ".join([f'"{col}"' for col in insert_columns])
        conn.execute(f'INSERT INTO "Locations_new" ({col_sql}) SELECT {col_sql} FROM "Locations"')
        conn.execute('DROP TABLE "Locations"')
        conn.execute('ALTER TABLE "Locations_new" RENAME TO "Locations"')

    @staticmethod
    def _migrate_legacy_county_to_lga(conn: sqlite3.Connection) -> None:
        location_columns = {row["name"] for row in conn.execute('PRAGMA table_info("Locations")').fetchall()}
        if "county" not in location_columns or "lga" not in location_columns:
            return
        conn.execute(
            """
            UPDATE "Locations"
            SET lga = county
            WHERE (lga IS NULL OR TRIM(lga) = '')
              AND county IS NOT NULL
              AND TRIM(county) <> ''
            """
        )
