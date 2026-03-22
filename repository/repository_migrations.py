import sqlite3
from typing import Any

from repository.repository_base import LOCATION_FIELDS


class RepositoryMigrationMixin:
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
