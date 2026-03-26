import csv
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.db_bootstrap import SCHEMA_VERSION, create_team_members_table, create_trips_table, initialize_database


class TestDbBootstrap(unittest.TestCase):
    def setUp(self):
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        self.db_path = Path(db_path)

        csv_fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(csv_fd)
        self.csv_path = Path(csv_path)
        with self.csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["section", "field"])
            writer.writeheader()
            writer.writerow({"section": "Trip", "field": "trip_name"})
            writer.writerow({"section": "Trip", "field": "region"})
            writer.writerow({"section": "Trip", "field": "start_date"})
            writer.writerow({"section": "Trip", "field": "end_date"})
            writer.writerow({"section": "Trip", "field": "trip_code"})  # should be excluded

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()
        if self.csv_path.exists():
            self.csv_path.unlink()

    def test_initialize_database_creates_expected_schema(self):
        fields = initialize_database(self.db_path, self.csv_path)

        self.assertEqual(fields, ["id", "trip_name", "location", "start_date", "end_date"])

        with closing(sqlite3.connect(self.db_path)) as conn:
            table_names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            self.assertTrue(
                {"Team_members", "User_Accounts", "Trips", "Locations", "TripLocations", "CollectionEvents", "Finds"}.issubset(
                    table_names
                )
            )

            trip_columns = {row[1] for row in conn.execute("PRAGMA table_info(Trips)").fetchall()}
            self.assertIn("trip_name", trip_columns)
            self.assertIn("location", trip_columns)
            self.assertNotIn("region", trip_columns)
            self.assertNotIn("trip_code", trip_columns)

            user_columns = {row[1] for row in conn.execute("PRAGMA table_info(Team_members)").fetchall()}
            self.assertIn("active", user_columns)
            self.assertIn("recruitment_date", user_columns)
            self.assertIn("retirement_date", user_columns)
            account_columns = {row[1] for row in conn.execute("PRAGMA table_info(User_Accounts)").fetchall()}
            self.assertTrue(
                {
                    "team_member_id",
                    "username",
                    "password_hash",
                    "role",
                    "must_change_password",
                    "password_changed_at",
                    "created_at",
                }.issubset(
                    account_columns
                )
            )
            self.assertNotIn("is_active", account_columns)
            account_sql = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='User_Accounts'"
            ).fetchone()[0]
            self.assertIn("'team'", account_sql)
            find_columns = {row[1] for row in conn.execute("PRAGMA table_info(Finds)").fetchall()}
            self.assertNotIn("trip_id", find_columns)

    def test_initialize_database_is_idempotent_and_preserves_data(self):
        fields_first = initialize_database(self.db_path, self.csv_path)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO Trips (trip_name, location, start_date, end_date) VALUES (?, ?, ?, ?)",
                ("Trip 1", "Site A", "2020-01-01", "2020-01-02"),
            )
            conn.commit()

        fields_second = initialize_database(self.db_path, self.csv_path)
        self.assertEqual(fields_first, fields_second)

        with closing(sqlite3.connect(self.db_path)) as conn:
            trip_count = conn.execute("SELECT COUNT(*) FROM Trips").fetchone()[0]
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(trip_count, 1)
            self.assertEqual(version, SCHEMA_VERSION)

    def test_initialize_database_upgrades_from_partial_schema_version(self):
        trip_fields = ["id", "trip_name", "location", "start_date", "end_date"]
        with closing(sqlite3.connect(self.db_path)) as conn:
            create_team_members_table(conn)
            create_trips_table(conn, trip_fields)
            conn.execute(
                "INSERT INTO Trips (trip_name, location, start_date, end_date) VALUES (?, ?, ?, ?)",
                ("Legacy Partial", "Site B", "2021-01-01", "2021-01-03"),
            )
            conn.execute("PRAGMA user_version = 1")
            conn.commit()

        initialize_database(self.db_path, self.csv_path)

        with closing(sqlite3.connect(self.db_path)) as conn:
            table_names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            self.assertIn("Locations", table_names)
            self.assertIn("CollectionEvents", table_names)
            self.assertIn("Finds", table_names)
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            trip_name = conn.execute("SELECT trip_name FROM Trips WHERE id = 1").fetchone()[0]
            self.assertEqual(version, SCHEMA_VERSION)
            self.assertEqual(trip_name, "Legacy Partial")
            find_columns = {row[1] for row in conn.execute("PRAGMA table_info(Finds)").fetchall()}
            self.assertNotIn("trip_id", find_columns)

    def test_initialize_database_removes_legacy_finds_trip_id_and_preserves_rows(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE Trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_name TEXT,
                    location TEXT,
                    start_date TEXT,
                    end_date TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE Locations (
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
            conn.execute(
                """
                CREATE TABLE CollectionEvents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER,
                    location_id INTEGER NOT NULL,
                    collection_name TEXT NOT NULL,
                    collection_subset TEXT,
                    event_year INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE Finds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER,
                    location_id INTEGER,
                    collection_event_id INTEGER,
                    source_system TEXT,
                    source_occurrence_no TEXT,
                    accepted_name TEXT,
                    collection_year_latest_estimate INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("INSERT INTO Trips (id, trip_name, location) VALUES (1, 'Legacy Trip', 'Legacy Site')")
            conn.execute(
                "INSERT INTO Locations (id, name, latitude, longitude, country_code, state) VALUES (1, 'Legacy Site', '-20', '140', 'AU', 'QLD')"
            )
            conn.execute(
                """
                INSERT INTO CollectionEvents (id, trip_id, location_id, collection_name, collection_subset, event_year)
                VALUES (1, 1, 1, 'Legacy Site', 'CE-1', 2000)
                """
            )
            conn.execute(
                """
                INSERT INTO Finds (
                    id, trip_id, location_id, collection_event_id, source_system, source_occurrence_no, accepted_name,
                    collection_year_latest_estimate
                ) VALUES (1, 1, 1, 1, 'PBDB', 'O-1', 'Taxon A', 2001)
                """
            )
            conn.execute("PRAGMA user_version = 2")
            conn.commit()

        initialize_database(self.db_path, self.csv_path)
        initialize_database(self.db_path, self.csv_path)

        with closing(sqlite3.connect(self.db_path)) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, SCHEMA_VERSION)
            find_columns = {row[1] for row in conn.execute("PRAGMA table_info(Finds)").fetchall()}
            self.assertNotIn("trip_id", find_columns)
            row = conn.execute(
                "SELECT id, location_id, collection_event_id, source_occurrence_no, accepted_name FROM Finds WHERE id = 1"
            ).fetchone()
            self.assertEqual(row, (1, 1, 1, "O-1", "Taxon A"))

    def test_initialize_database_removes_user_accounts_is_active_column(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE Team_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE User_Accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_member_id INTEGER NOT NULL,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'planner', 'reviewer', 'field_member')),
                    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_member_id) REFERENCES Team_members(id) ON DELETE CASCADE,
                    UNIQUE(team_member_id)
                )
                """
            )
            conn.execute(
                "INSERT INTO Team_members (id, name, phone_number, active) VALUES (1, 'Legacy User', '0400', 1)"
            )
            conn.execute(
                """
                INSERT INTO User_Accounts (id, team_member_id, username, password_hash, role, is_active, created_at)
                VALUES (1, 1, 'legacy', 'hash', 'admin', 1, '2026-01-01 00:00:00')
                """
            )
            conn.execute("PRAGMA user_version = 5")
            conn.commit()

        initialize_database(self.db_path, self.csv_path)

        with closing(sqlite3.connect(self.db_path)) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, SCHEMA_VERSION)
            account_columns = {row[1] for row in conn.execute("PRAGMA table_info(User_Accounts)").fetchall()}
            self.assertNotIn("is_active", account_columns)
            row = conn.execute(
                """
                SELECT id, team_member_id, username, password_hash, role, must_change_password, password_changed_at, created_at
                FROM User_Accounts
                """
            ).fetchone()
            self.assertEqual(row, (1, 1, "legacy", "hash", "admin", 1, None, "2026-01-01 00:00:00"))


if __name__ == "__main__":
    unittest.main()
