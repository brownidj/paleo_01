import sqlite3


def _migrate_legacy_collection_fields(conn: sqlite3.Connection) -> None:
    location_columns = {row[1] for row in conn.execute("PRAGMA table_info(Locations)").fetchall()}
    if "collection_name" not in location_columns:
        return
    subset_expr = "collection_subset" if "collection_subset" in location_columns else "NULL"
    rows = conn.execute(
        f"SELECT id, collection_name, {subset_expr} FROM Locations WHERE collection_name IS NOT NULL"
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
        if field == "location":
            if "location" in columns and "region" in columns:
                insert_columns.append('"location"')
                select_columns.append("COALESCE(NULLIF(TRIM(\"location\"), ''), \"region\")")
            elif "location" in columns:
                insert_columns.append('"location"')
                select_columns.append('"location"')
            elif "region" in columns:
                insert_columns.append('"location"')
                select_columns.append('"region"')
        elif field in columns:
            insert_columns.append(f'"{field}"')
            select_columns.append(f'"{field}"')
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


def _rebuild_finds_table_without_trip_id(conn: sqlite3.Connection) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(Finds)").fetchall()]
    if "trip_id" not in columns:
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Finds_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER,
            collection_event_id INTEGER,
            team_member_id INTEGER,
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
            collection_year_latest_estimate INTEGER,
            find_date TEXT,
            find_time TEXT,
            latitude TEXT,
            longitude TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES Locations(id) ON DELETE SET NULL,
            FOREIGN KEY (collection_event_id) REFERENCES CollectionEvents(id) ON DELETE SET NULL
        )
        """
    )
    copy_columns = [
        "id",
        "location_id",
        "collection_event_id",
        "team_member_id",
        "source_system",
        "source_occurrence_no",
        "identified_name",
        "accepted_name",
        "identified_rank",
        "accepted_rank",
        "difference",
        "identified_no",
        "accepted_no",
        "phylum",
        "class_name",
        "taxon_order",
        "family",
        "genus",
        "abund_value",
        "abund_unit",
        "reference_no",
        "taxonomy_comments",
        "occurrence_comments",
        "research_group",
        "notes",
        "collection_year_latest_estimate",
        "find_date",
        "find_time",
        "latitude",
        "longitude",
        "created_at",
        "updated_at",
    ]
    cols_sql = ", ".join([f'"{c}"' for c in copy_columns if c in columns])
    conn.execute(f"INSERT INTO Finds_new ({cols_sql}) SELECT {cols_sql} FROM Finds")
    conn.execute("DROP TABLE Finds")
    conn.execute("ALTER TABLE Finds_new RENAME TO Finds")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finds_location ON Finds(location_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finds_collection_event ON Finds(collection_event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finds_team_member ON Finds(team_member_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finds_source_occurrence ON Finds(source_occurrence_no)")
