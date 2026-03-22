#!/usr/bin/env python3
import csv
import sqlite3
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_db_path(db_arg: str) -> Path:
    path = Path(db_arg)
    if path.is_absolute():
        return path
    return project_root() / path


def resolve_classification_csv(path_arg: str) -> Path:
    path = Path(path_arg)
    if path.is_absolute():
        return path
    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate
    return project_root() / path


def get_trip_fields(classification_csv: Path) -> list[str]:
    fields: list[str] = []
    with classification_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("section") == "Trip":
                field_name = (row.get("field") or "").strip()
                if field_name:
                    fields.append(field_name)

    seen: set[str] = set()
    unique_fields: list[str] = []
    for field in fields:
        if field not in seen:
            unique_fields.append(field)
            seen.add(field)
    return normalize_trip_fields(unique_fields)


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


def _migrate_legacy_collection_fields(conn: sqlite3.Connection) -> None:
    location_columns = {row[1] for row in conn.execute("PRAGMA table_info(Locations)").fetchall()}
    if "collection_name" not in location_columns:
        return
    rows = conn.execute(
        "SELECT id, collection_name, collection_subset FROM Locations WHERE collection_name IS NOT NULL"
    ).fetchall()
    for row in rows:
        location_id = int(row[0])
        collection_name = str(row[1] or "").strip()
        collection_subset = row[2]
        if not collection_name:
            continue
        existing = conn.execute(
            """
            SELECT 1 FROM CollectionEvents
            WHERE location_id = ? AND collection_name = ? AND COALESCE(collection_subset, '') = COALESCE(?, '')
            LIMIT 1
            """,
            (location_id, collection_name, collection_subset),
        ).fetchone()
        if existing:
            continue
        conn.execute(
            "INSERT INTO CollectionEvents (location_id, collection_name, collection_subset) VALUES (?, ?, ?)",
            (location_id, collection_name, collection_subset),
        )


def _rebuild_locations_table_without_legacy_columns(conn: sqlite3.Connection) -> None:
    location_columns = [row[1] for row in conn.execute("PRAGMA table_info(Locations)").fetchall()]
    if (
        "collection_name" not in location_columns
        and "collection_subset" not in location_columns
        and "collection_aka" not in location_columns
        and "county" not in location_columns
    ):
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Locations_new (
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
    fields = [field for field in location_fields_for_rebuild() if field in location_columns]
    insert_columns = ["id"] + fields
    col_sql = ", ".join(f'"{name}"' for name in insert_columns)
    conn.execute(f"INSERT INTO Locations_new ({col_sql}) SELECT {col_sql} FROM Locations")
    conn.execute("DROP TABLE Locations")
    conn.execute("ALTER TABLE Locations_new RENAME TO Locations")


def location_fields_for_rebuild() -> list[str]:
    return [
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


def _migrate_legacy_county_to_lga(conn: sqlite3.Connection) -> None:
    location_columns = {row[1] for row in conn.execute("PRAGMA table_info(Locations)").fetchall()}
    if "county" not in location_columns or "lga" not in location_columns:
        return
    conn.execute(
        """
        UPDATE Locations
        SET lga = county
        WHERE (lga IS NULL OR TRIM(lga) = '')
          AND county IS NOT NULL
          AND TRIM(county) <> ''
        """
    )


def initialize_database(db_path: Path, classification_csv: Path) -> list[str]:
    trip_fields = get_trip_fields(classification_csv)
    with sqlite3.connect(db_path) as conn:
        create_users_table(conn)
        create_trips_table(conn, trip_fields)
        create_locations_table(conn)
        conn.commit()
    return trip_fields


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


def _migrate_legacy_trips_table(conn: sqlite3.Connection, trip_fields: list[str]) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(Trips)").fetchall()]
    needs_rebuild = "id" not in columns or "trip_code" in columns
    if not needs_rebuild:
        return
    conn.execute("DROP TABLE IF EXISTS TripLocations")
    non_id_columns = [name for name in trip_fields if name != "id"]
    col_sql = ",\n            ".join(f'"{name}" TEXT' for name in non_id_columns)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS Trips_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT
            {"," if col_sql else ""}
            {col_sql}
        )
        """
    )
    insert_columns: list[str] = []
    select_columns: list[str] = []
    for field in non_id_columns:
        if field in columns:
            insert_columns.append(f'"{field}"')
            select_columns.append(f'"{field}"')
        elif field == "location" and "region" in columns:
            insert_columns.append('"location"')
            select_columns.append('"region"')
    if insert_columns:
        conn.execute(
            f"INSERT INTO Trips_new ({', '.join(insert_columns)}) SELECT {', '.join(select_columns)} FROM Trips"
        )
    conn.execute("DROP TABLE Trips")
    conn.execute("ALTER TABLE Trips_new RENAME TO Trips")


def _migrate_legacy_trip_locations(conn: sqlite3.Connection) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(TripLocations)").fetchall()]
    if "trip_code" not in columns:
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS TripLocations_new (
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
            INSERT OR IGNORE INTO TripLocations_new (id, location_id)
            SELECT t.id, tl.location_id
            FROM TripLocations tl
            JOIN Trips t ON t.trip_code = tl.trip_code
            """
        )
    conn.execute("DROP TABLE TripLocations")
    conn.execute("ALTER TABLE TripLocations_new RENAME TO TripLocations")


def _migrate_legacy_region_to_location(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(Trips)").fetchall()}
    if "location" not in columns or "region" not in columns:
        return
    conn.execute(
        """
        UPDATE Trips
        SET location = region
        WHERE (location IS NULL OR TRIM(location) = '')
          AND region IS NOT NULL
          AND TRIM(region) <> ''
        """
    )


def _rebuild_trips_table_without_region(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(Trips)").fetchall()
    names = [row[1] for row in rows]
    if "region" not in names:
        return
    conn.execute("DROP TABLE IF EXISTS TripLocations")
    kept_rows = [row for row in rows if row[1] != "region"]
    column_defs: list[str] = []
    for row in kept_rows:
        name = row[1]
        col_type = row[2] or "TEXT"
        is_not_null = int(row[3]) == 1
        default_value = row[4]
        is_pk = int(row[5]) == 1
        if is_pk and name == "id":
            column_defs.append('"id" INTEGER PRIMARY KEY AUTOINCREMENT')
            continue
        definition = f'"{name}" {col_type}'
        if is_not_null:
            definition += " NOT NULL"
        if default_value is not None:
            definition += f" DEFAULT {default_value}"
        column_defs.append(definition)
    conn.execute(f"CREATE TABLE IF NOT EXISTS Trips_new ({', '.join(column_defs)})")
    cols_sql = ", ".join([f'"{row[1]}"' for row in kept_rows])
    conn.execute(f"INSERT INTO Trips_new ({cols_sql}) SELECT {cols_sql} FROM Trips")
    conn.execute("DROP TABLE Trips")
    conn.execute("ALTER TABLE Trips_new RENAME TO Trips")
