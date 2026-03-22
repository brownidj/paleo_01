from typing import cast

from repository.domain_types import CollectionEventPayload, LocationPayloadMap, LocationRecord
from repository.repository_base import LOCATION_FIELDS


class RepositoryLocationMixin:
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

    def list_locations(self) -> list[LocationRecord]:
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
        locations = [cast(LocationRecord, dict(row)) for row in location_rows]
        events_by_location: dict[int, list[CollectionEventPayload]] = {}
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
            first_event = events[0] if events else None
            location["collection_name"] = first_event.get("collection_name") if first_event else None
            location["collection_subset"] = first_event.get("collection_subset") if first_event else None
        locations.sort(
            key=lambda r: (
                str(r.get("name", "")).lower(),
                str(r.get("lga", "")).lower(),
                str(r.get("state", "")).lower(),
            )
        )
        return locations

    def get_location(self, location_id: int) -> LocationRecord | None:
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
        location = cast(LocationRecord, dict(row))
        location_events = cast(
            list[CollectionEventPayload],
            [
                {"collection_name": event["collection_name"], "collection_subset": event["collection_subset"]}
                for event in events
            ],
        )
        location["collection_events"] = location_events
        first_event = location_events[0] if location_events else None
        location["collection_name"] = first_event.get("collection_name") if first_event else None
        location["collection_subset"] = first_event.get("collection_subset") if first_event else None
        return location

    def create_location(self, data: LocationPayloadMap) -> int:
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

    def update_location(self, location_id: int, data: LocationPayloadMap) -> None:
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
