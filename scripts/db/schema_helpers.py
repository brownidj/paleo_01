import sqlite3

from scripts.db.migration_helpers import (
    _migrate_legacy_collection_fields,
    _migrate_legacy_county_to_lga,
    _migrate_legacy_region_to_location,
    _migrate_legacy_trip_locations,
    _migrate_legacy_trips_table,
    _rebuild_finds_table_without_trip_id,
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


def create_team_members_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            institution TEXT,
            recruitment_date TEXT,
            retirement_date TEXT,
            active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))
        )
        """
    )
    legacy_users_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='Users' LIMIT 1"
    ).fetchone()
    if legacy_users_exists:
        conn.execute(
            """
            INSERT OR IGNORE INTO Team_members (id, name, phone_number, active)
            SELECT id, name, phone_number, COALESCE(active, 0)
            FROM Users
            """
        )
        conn.execute("DROP TABLE Users")

    columns = [row[1] for row in conn.execute("PRAGMA table_info(Team_members)").fetchall()]
    if "institution" not in columns:
        conn.execute("ALTER TABLE Team_members ADD COLUMN institution TEXT")
        columns = [row[1] for row in conn.execute("PRAGMA table_info(Team_members)").fetchall()]
    if "recruitment_date" not in columns:
        conn.execute("ALTER TABLE Team_members ADD COLUMN recruitment_date TEXT")
        columns = [row[1] for row in conn.execute("PRAGMA table_info(Team_members)").fetchall()]
    if "retirement_date" not in columns:
        conn.execute("ALTER TABLE Team_members ADD COLUMN retirement_date TEXT")
        columns = [row[1] for row in conn.execute("PRAGMA table_info(Team_members)").fetchall()]
    if "active" not in columns:
        conn.execute(
            "ALTER TABLE Team_members ADD COLUMN active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))"
        )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS User_Accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_member_id INTEGER NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'team', 'planner', 'reviewer', 'field_member')),
            must_change_password INTEGER NOT NULL DEFAULT 1 CHECK(must_change_password IN (0, 1)),
            password_changed_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_member_id) REFERENCES Team_members(id) ON DELETE CASCADE,
            UNIQUE(team_member_id)
        )
        """
    )
    account_columns = [row[1] for row in conn.execute("PRAGMA table_info(User_Accounts)").fetchall()]
    user_accounts_sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='User_Accounts'"
    ).fetchone()
    user_accounts_sql = str(user_accounts_sql_row[0] if user_accounts_sql_row else "")
    if "is_active" in account_columns or "'team'" not in user_accounts_sql:
        _rebuild_user_accounts_without_is_active(conn)
        account_columns = [row[1] for row in conn.execute("PRAGMA table_info(User_Accounts)").fetchall()]
    if "must_change_password" not in account_columns:
        conn.execute(
            "ALTER TABLE User_Accounts ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 1 CHECK(must_change_password IN (0, 1))"
        )
    if "password_changed_at" not in account_columns:
        conn.execute("ALTER TABLE User_Accounts ADD COLUMN password_changed_at TEXT")


def _rebuild_user_accounts_without_is_active(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS User_Accounts_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_member_id INTEGER NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'team', 'planner', 'reviewer', 'field_member')),
            must_change_password INTEGER NOT NULL DEFAULT 1 CHECK(must_change_password IN (0, 1)),
            password_changed_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_member_id) REFERENCES Team_members(id) ON DELETE CASCADE,
            UNIQUE(team_member_id)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO User_Accounts_new (
            id,
            team_member_id,
            username,
            password_hash,
            role,
            must_change_password,
            password_changed_at,
            created_at
        )
        SELECT
            id,
            team_member_id,
            username,
            password_hash,
            role,
            1,
            NULL,
            COALESCE(created_at, CURRENT_TIMESTAMP)
        FROM User_Accounts
        """
    )
    conn.execute("DROP TABLE User_Accounts")
    conn.execute("ALTER TABLE User_Accounts_new RENAME TO User_Accounts")


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
        "proterozoic_province",
        "orogen",
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
            trip_id INTEGER,
            location_id INTEGER NOT NULL,
            collection_name TEXT NOT NULL,
            collection_subset TEXT,
            event_year INTEGER,
            FOREIGN KEY (trip_id) REFERENCES Trips(id) ON DELETE SET NULL,
            FOREIGN KEY (location_id) REFERENCES Locations(id)
        )
        """
    )
    ce_columns = [row[1] for row in conn.execute("PRAGMA table_info(CollectionEvents)").fetchall()]
    if "trip_id" not in ce_columns:
        conn.execute("ALTER TABLE CollectionEvents ADD COLUMN trip_id INTEGER")
        ce_columns = [row[1] for row in conn.execute("PRAGMA table_info(CollectionEvents)").fetchall()]
    if "event_year" not in ce_columns:
        conn.execute("ALTER TABLE CollectionEvents ADD COLUMN event_year INTEGER")
    _migrate_legacy_trip_locations(conn)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_locations_trip ON TripLocations(id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_locations_location ON TripLocations(location_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_collection_events_location ON CollectionEvents(location_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_collection_events_trip ON CollectionEvents(trip_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_collection_events_event_year ON CollectionEvents(event_year)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Finds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            collection_year_latest_estimate INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES Locations(id) ON DELETE SET NULL,
            FOREIGN KEY (collection_event_id) REFERENCES CollectionEvents(id) ON DELETE SET NULL
        )
        """
    )
    _rebuild_finds_table_without_trip_id(conn)
    find_columns = [row[1] for row in conn.execute("PRAGMA table_info(Finds)").fetchall()]
    if "collection_year_latest_estimate" not in find_columns:
        conn.execute("ALTER TABLE Finds ADD COLUMN collection_year_latest_estimate INTEGER")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finds_location ON Finds(location_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finds_collection_event ON Finds(collection_event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finds_source_occurrence ON Finds(source_occurrence_no)")
    _migrate_legacy_collection_fields(conn)
    _rebuild_locations_table_without_legacy_columns(conn)
