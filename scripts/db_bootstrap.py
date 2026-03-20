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
    return unique_fields


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
    if not fields:
        raise ValueError("No Trip fields found in classification CSV.")
    column_sql = ",\n            ".join(f'"{name}" TEXT' for name in fields)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS Trips (
            {column_sql}
        )
        """
    )


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
            trip_code TEXT NOT NULL,
            location_id INTEGER NOT NULL,
            PRIMARY KEY (trip_code, location_id),
            FOREIGN KEY (trip_code) REFERENCES Trips(trip_code),
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
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trips_trip_code_unique ON Trips(trip_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_locations_trip ON TripLocations(trip_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_locations_location ON TripLocations(location_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_collection_events_location ON CollectionEvents(location_id)")
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
