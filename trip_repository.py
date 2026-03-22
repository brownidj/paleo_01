import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any


DEFAULT_TRIP_FIELDS = [
    "trip_name",
    "start_date",
    "end_date",
    "team",
    "location",
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

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_trips_table(self, fields: list[str] | None = None) -> None:
        trip_fields = self._normalize_trip_fields(fields or DEFAULT_TRIP_FIELDS)
        cols = ", ".join([f'"{name}" TEXT' for name in trip_fields if name != "id"])
        with self._connect() as conn:
            conn.execute(
                f'''
                CREATE TABLE IF NOT EXISTS "Trips" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                    {", " + cols if cols else ""}
                )
                '''
            )
            self._migrate_legacy_trips_table(conn, trip_fields)
            existing = {row["name"] for row in conn.execute('PRAGMA table_info("Trips")').fetchall()}
            for field in trip_fields:
                if field not in existing:
                    conn.execute(f'ALTER TABLE "Trips" ADD COLUMN "{field}" TEXT')
            self._migrate_legacy_region_to_location(conn)
            self._rebuild_trips_table_without_region(conn)

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
                    id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    PRIMARY KEY (id, location_id),
                    FOREIGN KEY (id) REFERENCES Trips(id),
                    FOREIGN KEY (location_id) REFERENCES Locations(id)
                )
                """
            )
            self._migrate_legacy_trip_locations(conn)
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trip_locations_trip ON "TripLocations"(id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trip_locations_location ON "TripLocations"(location_id)')
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_collection_events_location ON "CollectionEvents"(location_id)'
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "Finds" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER,
                    location_id INTEGER,
                    collection_event_id INTEGER,
                    source_system TEXT,
                    source_occurrence_no TEXT,
                    identified_name TEXT,
                    accepted_name TEXT,
                    identified_rank TEXT,
                    accepted_rank TEXT,
                    difference TEXT,
                    identified_no TEXT,
                    accepted_no TEXT,
                    phylum TEXT,
                    class_name TEXT,
                    taxon_order TEXT,
                    family TEXT,
                    genus TEXT,
                    abund_value TEXT,
                    abund_unit TEXT,
                    reference_no TEXT,
                    taxonomy_comments TEXT,
                    occurrence_comments TEXT,
                    research_group TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (trip_id) REFERENCES Trips(id) ON DELETE SET NULL,
                    FOREIGN KEY (location_id) REFERENCES Locations(id) ON DELETE SET NULL,
                    FOREIGN KEY (collection_event_id) REFERENCES CollectionEvents(id) ON DELETE SET NULL
                )
                """
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_finds_trip ON "Finds"(trip_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_finds_location ON "Finds"(location_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_finds_collection_event ON "Finds"(collection_event_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_finds_source_occurrence ON "Finds"(source_occurrence_no)')

    def get_fields(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute('PRAGMA table_info("Trips")').fetchall()
        fields = [row["name"] for row in rows]
        if fields:
            return fields
        self.ensure_trips_table()
        return self._normalize_trip_fields(DEFAULT_TRIP_FIELDS)

    def list_trips(self) -> list[dict[str, Any]]:
        fields = self.get_fields()
        col_sql = ", ".join([f'"{name}"' for name in fields])
        with self._connect() as conn:
            rows = conn.execute(
                f'''
                SELECT {col_sql}
                FROM "Trips"
                ORDER BY
                    LOWER(COALESCE(trip_name, '')),
                    COALESCE(start_date, ''),
                    id
                '''
            ).fetchall()
        return [dict(row) for row in rows]

    def get_trip(self, trip_id: int) -> dict[str, Any] | None:
        fields = self.get_fields()
        col_sql = ", ".join([f'"{name}"' for name in fields])
        with self._connect() as conn:
            row = conn.execute(
                f'SELECT {col_sql} FROM "Trips" WHERE id = ?',
                (trip_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_trip(self, data: dict[str, Any]) -> int:
        fields = self.get_fields()
        with self._connect() as conn:
            insert_fields = [name for name in fields if name != "id" and name in data]
            if insert_fields:
                col_sql = ", ".join([f'"{name}"' for name in insert_fields])
                placeholders = ", ".join(["?"] * len(insert_fields))
                values = [data[name] for name in insert_fields]
                cur = conn.execute(
                    f'INSERT INTO "Trips" ({col_sql}) VALUES ({placeholders})',
                    values,
                )
            else:
                cur = conn.execute('INSERT INTO "Trips" DEFAULT VALUES')
            return int(cur.lastrowid)

    def update_trip(self, trip_id: int, data: dict[str, Any]) -> None:
        fields = self.get_fields()
        update_fields = [name for name in fields if name != "id" and name in data]
        if not update_fields:
            raise ValueError("No valid Trip fields supplied.")
        set_sql = ", ".join([f'"{name}" = ?' for name in update_fields])
        values = [data[name] for name in update_fields] + [trip_id]
        with self._connect() as conn:
            conn.execute(
                f'UPDATE "Trips" SET {set_sql} WHERE id = ?',
                values,
            )

    def list_active_users(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT name FROM "Users" WHERE active = 1 ORDER BY name'
            ).fetchall()
        return [row["name"] for row in rows]

    def list_location_names(self) -> list[str]:
        self.ensure_locations_table()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM "Locations"
                WHERE name IS NOT NULL AND TRIM(name) <> ''
                ORDER BY name
                """
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

    def ensure_geology_tables(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "GeologyContext" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_id INTEGER NOT NULL,
                    location_name TEXT NOT NULL,
                    source_system TEXT NOT NULL DEFAULT 'PBDB',
                    source_reference_no TEXT,
                    early_interval TEXT,
                    late_interval TEXT,
                    max_ma REAL,
                    min_ma REAL,
                    environment TEXT,
                    geogscale TEXT,
                    geology_comments TEXT,
                    formation TEXT,
                    stratigraphy_group TEXT,
                    member TEXT,
                    stratscale TEXT,
                    stratigraphy_comments TEXT,
                    geoplate TEXT,
                    paleomodel TEXT,
                    paleolat REAL,
                    paleolng REAL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (location_id) REFERENCES Locations(id) ON DELETE CASCADE
                )
                """
            )
            columns = {row["name"] for row in conn.execute('PRAGMA table_info("GeologyContext")').fetchall()}
            if "collection_event_id" in columns and "location_id" not in columns:
                self._migrate_legacy_geology_to_locations(conn)
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS "uq_geology_context_event_source"
                ON "GeologyContext"(location_id, source_system)
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS "uq_geology_context_location_name"
                ON "GeologyContext"(LOWER(TRIM(location_name)))
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "Lithology" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    geology_context_id INTEGER NOT NULL,
                    slot INTEGER NOT NULL,
                    lithology TEXT,
                    lithification TEXT,
                    minor_lithology TEXT,
                    lithology_adjectives TEXT,
                    fossils_from TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (geology_context_id) REFERENCES GeologyContext(id) ON DELETE CASCADE,
                    UNIQUE (geology_context_id, slot)
                )
                """
            )
            self._ensure_locations_geology_fk(conn)
            self._link_locations_to_geology(conn)

    def list_geology_records(self) -> list[dict[str, Any]]:
        self.ensure_locations_table()
        self.ensure_geology_tables()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    gc.id AS geology_id,
                    gc.source_reference_no,
                    gc.early_interval,
                    gc.late_interval,
                    gc.max_ma,
                    gc.min_ma,
                    gc.environment,
                    gc.formation,
                    gc.stratigraphy_group,
                    gc.member,
                    gc.stratigraphy_comments,
                    gc.geology_comments,
                    gc.geoplate,
                    gc.paleomodel,
                    gc.paleolat,
                    gc.paleolng,
                    l.id AS location_id,
                    l.name AS location_name,
                    l.state,
                    l.country_code
                FROM "GeologyContext" gc
                JOIN "Locations" l ON l.id = gc.location_id
                ORDER BY
                    COALESCE(l.name, ''),
                    gc.id
                """
            ).fetchall()
            lith_rows = conn.execute(
                """
                SELECT
                    geology_context_id,
                    slot,
                    lithology,
                    lithification,
                    minor_lithology,
                    lithology_adjectives,
                    fossils_from
                FROM "Lithology"
                ORDER BY geology_context_id, slot
                """
            ).fetchall()

        lithology_by_geology: dict[int, list[dict[str, Any]]] = {}
        for row in lith_rows:
            geology_id = int(row["geology_context_id"])
            lithology_by_geology.setdefault(geology_id, []).append(
                {
                    "slot": row["slot"],
                    "lithology": row["lithology"],
                    "lithification": row["lithification"],
                    "minor_lithology": row["minor_lithology"],
                    "lithology_adjectives": row["lithology_adjectives"],
                    "fossils_from": row["fossils_from"],
                }
            )

        records: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            geology_id = int(record["geology_id"])
            lithology_rows = lithology_by_geology.get(geology_id, [])
            summary_parts: list[str] = []
            for lith in lithology_rows:
                label = str(lith.get("lithology") or "").strip()
                if label:
                    summary_parts.append(label)
            record["lithology_rows"] = lithology_rows
            record["lithology_summary"] = ", ".join(summary_parts)
            records.append(record)
        return records

    def get_geology_record(self, geology_id: int) -> dict[str, Any] | None:
        self.ensure_locations_table()
        self.ensure_geology_tables()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    gc.id AS geology_id,
                    gc.location_id,
                    gc.location_name,
                    gc.source_reference_no,
                    gc.early_interval,
                    gc.late_interval,
                    gc.max_ma,
                    gc.min_ma,
                    gc.environment,
                    gc.geogscale,
                    gc.geology_comments,
                    gc.formation,
                    gc.stratigraphy_group,
                    gc.member,
                    gc.stratscale,
                    gc.stratigraphy_comments,
                    gc.geoplate,
                    gc.paleomodel,
                    gc.paleolat,
                    gc.paleolng
                FROM "GeologyContext" gc
                WHERE gc.id = ?
                """,
                (geology_id,),
            ).fetchone()
            if not row:
                return None
            lith_rows = conn.execute(
                """
                SELECT
                    slot,
                    lithology,
                    lithification,
                    minor_lithology,
                    lithology_adjectives,
                    fossils_from
                FROM "Lithology"
                WHERE geology_context_id = ?
                ORDER BY slot
                """,
                (geology_id,),
            ).fetchall()

        record = dict(row)
        record["lithology_rows"] = [dict(r) for r in lith_rows]
        return record

    def update_geology_record(self, geology_id: int, data: dict[str, Any]) -> None:
        self.ensure_locations_table()
        self.ensure_geology_tables()
        allowed_fields = [
            "source_reference_no",
            "early_interval",
            "late_interval",
            "max_ma",
            "min_ma",
            "environment",
            "geogscale",
            "geology_comments",
            "formation",
            "stratigraphy_group",
            "member",
            "stratscale",
            "stratigraphy_comments",
            "geoplate",
            "paleomodel",
            "paleolat",
            "paleolng",
        ]
        update_fields = [f for f in allowed_fields if f in data]
        lithology_rows = data.get("lithology_rows", [])
        with self._connect() as conn:
            if update_fields:
                set_sql = ", ".join([f'"{name}" = ?' for name in update_fields])
                values = [data.get(name) for name in update_fields] + [geology_id]
                conn.execute(f'UPDATE "GeologyContext" SET {set_sql} WHERE id = ?', values)
                conn.execute(
                    'UPDATE "GeologyContext" SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (geology_id,),
                )
            conn.execute('DELETE FROM "Lithology" WHERE geology_context_id = ?', (geology_id,))
            inserts: list[tuple[Any, ...]] = []
            if isinstance(lithology_rows, list):
                for raw in lithology_rows:
                    if not isinstance(raw, dict):
                        continue
                    slot = raw.get("slot")
                    if slot not in {1, 2}:
                        continue
                    lithology = raw.get("lithology")
                    lithification = raw.get("lithification")
                    minor_lithology = raw.get("minor_lithology")
                    lithology_adjectives = raw.get("lithology_adjectives")
                    fossils_from = raw.get("fossils_from")
                    if not any([lithology, lithification, minor_lithology, lithology_adjectives, fossils_from]):
                        continue
                    inserts.append(
                        (
                            geology_id,
                            slot,
                            lithology,
                            lithification,
                            minor_lithology,
                            lithology_adjectives,
                            fossils_from,
                        )
                    )
            if inserts:
                conn.executemany(
                    """
                    INSERT INTO "Lithology" (
                        geology_context_id,
                        slot,
                        lithology,
                        lithification,
                        minor_lithology,
                        lithology_adjectives,
                        fossils_from
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    inserts,
                )

    def list_collection_events(self, trip_id: int | None = None) -> list[dict[str, Any]]:
        self.ensure_locations_table()
        with self._connect() as conn:
            if trip_id is None:
                rows = conn.execute(
                    """
                    SELECT
                        ce.id,
                        ce.collection_name,
                        ce.collection_subset,
                        l.name AS location_name,
                        COUNT(f.id) AS find_count
                    FROM "CollectionEvents" ce
                    JOIN "Locations" l ON l.id = ce.location_id
                    LEFT JOIN "Finds" f ON f.collection_event_id = ce.id
                    GROUP BY ce.id, ce.collection_name, ce.collection_subset, l.name
                    ORDER BY LOWER(COALESCE(l.name, '')), LOWER(COALESCE(ce.collection_subset, '')), ce.id
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        ce.id,
                        ce.collection_name,
                        ce.collection_subset,
                        l.name AS location_name,
                        COUNT(f.id) AS find_count
                    FROM "CollectionEvents" ce
                    JOIN "Locations" l ON l.id = ce.location_id
                    LEFT JOIN "Finds" f ON f.collection_event_id = ce.id
                    WHERE ce.id IN (
                        SELECT DISTINCT f2.collection_event_id
                        FROM "Finds" f2
                        WHERE f2.trip_id = ? AND f2.collection_event_id IS NOT NULL
                    )
                    GROUP BY ce.id, ce.collection_name, ce.collection_subset, l.name
                    ORDER BY LOWER(COALESCE(l.name, '')), LOWER(COALESCE(ce.collection_subset, '')), ce.id
                    """,
                    (trip_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def list_finds(self, trip_id: int | None = None) -> list[dict[str, Any]]:
        self.ensure_locations_table()
        with self._connect() as conn:
            if trip_id is None:
                rows = conn.execute(
                    """
                    SELECT
                        f.id,
                        f.source_occurrence_no,
                        f.accepted_name,
                        f.identified_name,
                        f.reference_no,
                        t.trip_name,
                        l.name AS location_name,
                        ce.collection_subset
                    FROM "Finds" f
                    LEFT JOIN "Trips" t ON t.id = f.trip_id
                    LEFT JOIN "Locations" l ON l.id = f.location_id
                    LEFT JOIN "CollectionEvents" ce ON ce.id = f.collection_event_id
                    ORDER BY LOWER(COALESCE(l.name, '')), f.id
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        f.id,
                        f.source_occurrence_no,
                        f.accepted_name,
                        f.identified_name,
                        f.reference_no,
                        t.trip_name,
                        l.name AS location_name,
                        ce.collection_subset
                    FROM "Finds" f
                    LEFT JOIN "Trips" t ON t.id = f.trip_id
                    LEFT JOIN "Locations" l ON l.id = f.location_id
                    LEFT JOIN "CollectionEvents" ce ON ce.id = f.collection_event_id
                    WHERE f.trip_id = ?
                    ORDER BY LOWER(COALESCE(l.name, '')), f.id
                    """,
                    (trip_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def count_collection_events_for_trip(self, trip_id: int) -> int:
        self.ensure_locations_table()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(DISTINCT f.collection_event_id) AS event_count
                FROM "Finds" f
                WHERE f.trip_id = ? AND f.collection_event_id IS NOT NULL
                """,
                (trip_id,),
            ).fetchone()
        return int(row["event_count"] if row else 0)

    def count_finds_for_trip(self, trip_id: int) -> int:
        self.ensure_locations_table()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS find_count
                FROM "Finds"
                WHERE trip_id = ?
                """,
                (trip_id,),
            ).fetchone()
        return int(row["find_count"] if row else 0)

    @staticmethod
    def _migrate_legacy_geology_to_locations(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS "GeologyContext_new" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                location_name TEXT NOT NULL,
                source_system TEXT NOT NULL DEFAULT 'PBDB',
                source_reference_no TEXT,
                early_interval TEXT,
                late_interval TEXT,
                max_ma REAL,
                min_ma REAL,
                environment TEXT,
                geogscale TEXT,
                geology_comments TEXT,
                formation TEXT,
                stratigraphy_group TEXT,
                member TEXT,
                stratscale TEXT,
                stratigraphy_comments TEXT,
                geoplate TEXT,
                paleomodel TEXT,
                paleolat REAL,
                paleolng REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES Locations(id) ON DELETE CASCADE
            )
            """
        )
        rows = conn.execute(
            """
            SELECT
                gc.id,
                ce.location_id,
                l.name AS location_name,
                gc.source_system,
                gc.source_reference_no,
                gc.early_interval,
                gc.late_interval,
                gc.max_ma,
                gc.min_ma,
                gc.environment,
                gc.geogscale,
                gc.geology_comments,
                gc.formation,
                gc.stratigraphy_group,
                gc.member,
                gc.stratscale,
                gc.stratigraphy_comments,
                gc.geoplate,
                gc.paleomodel,
                gc.paleolat,
                gc.paleolng,
                gc.created_at,
                gc.updated_at
            FROM "GeologyContext" gc
            JOIN "CollectionEvents" ce ON ce.id = gc.collection_event_id
            JOIN "Locations" l ON l.id = ce.location_id
            ORDER BY gc.id
            """
        ).fetchall()
        seen_names: set[str] = set()
        for row in rows:
            location_name = str(row["location_name"] or "").strip()
            key = location_name.lower()
            if not key or key in seen_names:
                continue
            seen_names.add(key)
            conn.execute(
                """
                INSERT INTO "GeologyContext_new" (
                    id, location_id, location_name, source_system, source_reference_no,
                    early_interval, late_interval, max_ma, min_ma, environment, geogscale,
                    geology_comments, formation, stratigraphy_group, member, stratscale,
                    stratigraphy_comments, geoplate, paleomodel, paleolat, paleolng,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["location_id"],
                    location_name,
                    row["source_system"],
                    row["source_reference_no"],
                    row["early_interval"],
                    row["late_interval"],
                    row["max_ma"],
                    row["min_ma"],
                    row["environment"],
                    row["geogscale"],
                    row["geology_comments"],
                    row["formation"],
                    row["stratigraphy_group"],
                    row["member"],
                    row["stratscale"],
                    row["stratigraphy_comments"],
                    row["geoplate"],
                    row["paleomodel"],
                    row["paleolat"],
                    row["paleolng"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        kept_ids = {row["id"] for row in conn.execute('SELECT id FROM "GeologyContext_new"').fetchall()}
        if kept_ids:
            placeholders = ", ".join(["?"] * len(kept_ids))
            conn.execute(
                f'DELETE FROM "Lithology" WHERE geology_context_id NOT IN ({placeholders})',
                tuple(kept_ids),
            )
        else:
            conn.execute('DELETE FROM "Lithology"')
        conn.execute('DROP TABLE "GeologyContext"')
        conn.execute('ALTER TABLE "GeologyContext_new" RENAME TO "GeologyContext"')

    @staticmethod
    def _ensure_locations_geology_fk(conn: sqlite3.Connection) -> None:
        location_columns = [row["name"] for row in conn.execute('PRAGMA table_info("Locations")').fetchall()]
        if "geology_id" in location_columns:
            conn.execute('CREATE INDEX IF NOT EXISTS idx_locations_geology ON "Locations"(geology_id)')
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
                geography_comments TEXT,
                geology_id INTEGER,
                FOREIGN KEY (geology_id) REFERENCES GeologyContext(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO "Locations_new" (
                id, name, latitude, longitude, altitude_value, altitude_unit,
                country_code, state, lga, basin, geogscale, geography_comments
            )
            SELECT
                id, name, latitude, longitude, altitude_value, altitude_unit,
                country_code, state, lga, basin, geogscale, geography_comments
            FROM "Locations"
            """
        )
        conn.execute('DROP TABLE "Locations"')
        conn.execute('ALTER TABLE "Locations_new" RENAME TO "Locations"')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_locations_geology ON "Locations"(geology_id)')

    @staticmethod
    def _link_locations_to_geology(conn: sqlite3.Connection) -> None:
        # Every location points to geology by normalized location name.
        conn.execute(
            """
            UPDATE "Locations"
            SET geology_id = (
                SELECT gc.id
                FROM "GeologyContext" gc
                WHERE LOWER(TRIM(gc.location_name)) = LOWER(TRIM("Locations".name))
                LIMIT 1
            )
            WHERE name IS NOT NULL AND TRIM(name) <> ''
            """
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

    @staticmethod
    def _normalize_trip_fields(fields: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = ["id"]
        for field in fields:
            mapped = "location" if field == "region" else field
            if mapped in {"id", "trip_code"}:
                continue
            if mapped not in seen:
                result.append(mapped)
                seen.add(mapped)
        return result

    @staticmethod
    def _migrate_legacy_trips_table(conn: sqlite3.Connection, trip_fields: list[str]) -> None:
        columns = [row["name"] for row in conn.execute('PRAGMA table_info("Trips")').fetchall()]
        needs_rebuild = "id" not in columns or "trip_code" in columns
        if not needs_rebuild:
            return
        conn.execute('DROP TABLE IF EXISTS "TripLocations"')
        conn.execute(
            f'''
            CREATE TABLE IF NOT EXISTS "Trips_new" (
                id INTEGER PRIMARY KEY AUTOINCREMENT
                {", " + ", ".join([f'"{name}" TEXT' for name in trip_fields if name != "id"]) if len(trip_fields) > 1 else ""}
            )
            '''
        )
        insert_columns: list[str] = []
        select_columns: list[str] = []
        for field in trip_fields:
            if field == "id":
                continue
            if field in columns:
                insert_columns.append(f'"{field}"')
                select_columns.append(f'"{field}"')
            elif field == "location" and "region" in columns:
                insert_columns.append('"location"')
                select_columns.append('"region"')
        if insert_columns:
            conn.execute(
                f'INSERT INTO "Trips_new" ({", ".join(insert_columns)}) SELECT {", ".join(select_columns)} FROM "Trips"'
            )
        conn.execute('DROP TABLE "Trips"')
        conn.execute('ALTER TABLE "Trips_new" RENAME TO "Trips"')

    @staticmethod
    def _migrate_legacy_trip_locations(conn: sqlite3.Connection) -> None:
        columns = [row["name"] for row in conn.execute('PRAGMA table_info("TripLocations")').fetchall()]
        if not columns:
            return
        if "trip_code" not in columns:
            return
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS "TripLocations_new" (
                id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                PRIMARY KEY (id, location_id),
                FOREIGN KEY (id) REFERENCES Trips(id),
                FOREIGN KEY (location_id) REFERENCES Locations(id)
            )
            """
        )
        has_trips_trip_code = conn.execute(
            "SELECT COUNT(*) FROM pragma_table_info('Trips') WHERE name = 'trip_code'"
        ).fetchone()[0]
        if has_trips_trip_code:
            conn.execute(
                """
                INSERT OR IGNORE INTO "TripLocations_new" (id, location_id)
                SELECT t.id, tl.location_id
                FROM "TripLocations" tl
                JOIN "Trips" t ON t.trip_code = tl.trip_code
                """
            )
        conn.execute('DROP TABLE "TripLocations"')
        conn.execute('ALTER TABLE "TripLocations_new" RENAME TO "TripLocations"')

    @staticmethod
    def _migrate_legacy_region_to_location(conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute('PRAGMA table_info("Trips")').fetchall()}
        if "location" not in columns or "region" not in columns:
            return
        conn.execute(
            """
            UPDATE "Trips"
            SET location = region
            WHERE (location IS NULL OR TRIM(location) = '')
              AND region IS NOT NULL
              AND TRIM(region) <> ''
            """
        )

    @staticmethod
    def _rebuild_trips_table_without_region(conn: sqlite3.Connection) -> None:
        rows = conn.execute('PRAGMA table_info("Trips")').fetchall()
        names = [row["name"] for row in rows]
        if "region" not in names:
            return
        conn.execute('DROP TABLE IF EXISTS "TripLocations"')
        kept_rows = [row for row in rows if row["name"] != "region"]
        column_defs: list[str] = []
        for row in kept_rows:
            name = row["name"]
            col_type = row["type"] or "TEXT"
            if int(row["pk"]) == 1 and name == "id":
                column_defs.append('"id" INTEGER PRIMARY KEY AUTOINCREMENT')
                continue
            definition = f'"{name}" {col_type}'
            if int(row["notnull"]) == 1:
                definition += " NOT NULL"
            if row["dflt_value"] is not None:
                definition += f" DEFAULT {row['dflt_value']}"
            column_defs.append(definition)
        conn.execute(f'CREATE TABLE IF NOT EXISTS "Trips_new" ({", ".join(column_defs)})')
        kept_columns_sql = ", ".join([f'"{row["name"]}"' for row in kept_rows])
        conn.execute(f'INSERT INTO "Trips_new" ({kept_columns_sql}) SELECT {kept_columns_sql} FROM "Trips"')
        conn.execute('DROP TABLE "Trips"')
        conn.execute('ALTER TABLE "Trips_new" RENAME TO "Trips"')
