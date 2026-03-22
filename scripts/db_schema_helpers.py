import sqlite3

try:
    from .db_migration_helpers import (
        _migrate_legacy_collection_fields,
        _migrate_legacy_county_to_lga,
        _migrate_legacy_region_to_location,
        _migrate_legacy_trip_locations,
        _migrate_legacy_trips_table,
        _rebuild_locations_table_without_legacy_columns,
        _rebuild_trips_table_without_region,
    )
except ImportError:
    from db_migration_helpers import (
        _migrate_legacy_collection_fields,
        _migrate_legacy_county_to_lga,
        _migrate_legacy_region_to_location,
        _migrate_legacy_trip_locations,
        _migrate_legacy_trips_table,
        _rebuild_locations_table_without_legacy_columns,
        _rebuild_trips_table_without_region,
    )


def normalize_trip_fields(fields: list[str]) -> list[str]:
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


def create_users_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))
        )
        """
    )
    columns = [row[1] for row in conn.execute("PRAGMA table_info(Users)").fetchall()]
    if "active" not in columns:
        conn.execute(
            "ALTER TABLE Users ADD COLUMN active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))"
        )


def create_trips_table(conn: sqlite3.Connection, fields: list[str]) -> None:
    normalized_fields = normalize_trip_fields(fields)
    if len(normalized_fields) == 1:
        raise ValueError("No Trip fields found in classification CSV.")
    column_sql = ",\n            ".join(f'"{name}" TEXT' for name in normalized_fields if name != "id")
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS Trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT
            {"," if column_sql else ""}
            {column_sql}
        )
        """
    )
    _migrate_legacy_trips_table(conn, normalized_fields)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(Trips)").fetchall()}
    for field in normalized_fields:
        if field != "id" and field not in existing:
            conn.execute(f'ALTER TABLE Trips ADD COLUMN "{field}" TEXT')
    _migrate_legacy_region_to_location(conn)
    _rebuild_trips_table_without_region(conn)


def create_locations_table(conn: sqlite3.Connection) -> None:
    location_fields = [
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )
        """
    )
    existing = {row[1] for row in conn.execute("PRAGMA table_info(Locations)").fetchall()}
    for field in location_fields:
        if field not in existing:
            conn.execute(f'ALTER TABLE Locations ADD COLUMN "{field}" TEXT')
    _migrate_legacy_county_to_lga(conn)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS TripLocations (
            id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            PRIMARY KEY (id, location_id),
            FOREIGN KEY (id) REFERENCES Trips(id),
            FOREIGN KEY (location_id) REFERENCES Locations(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS CollectionEvents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            collection_name TEXT NOT NULL,
            collection_subset TEXT,
            FOREIGN KEY (location_id) REFERENCES Locations(id)
        )
        """
    )
    _migrate_legacy_trip_locations(conn)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_locations_trip ON TripLocations(id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_locations_location ON TripLocations(location_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_collection_events_location ON CollectionEvents(location_id)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Finds (
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finds_trip ON Finds(trip_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finds_location ON Finds(location_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finds_collection_event ON Finds(collection_event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finds_source_occurrence ON Finds(source_occurrence_no)")
    _migrate_legacy_collection_fields(conn)
    _rebuild_locations_table_without_legacy_columns(conn)
