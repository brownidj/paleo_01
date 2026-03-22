import csv
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.db_bootstrap import SCHEMA_VERSION, initialize_database


class TestDbLegacyMigrations(unittest.TestCase):
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

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()
        if self.csv_path.exists():
            self.csv_path.unlink()

    def test_upgrade_pre_location_trips_from_legacy_snapshot(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE Trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_name TEXT,
                    region TEXT,
                    notes TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO Trips (trip_name, region, notes) VALUES (?, ?, ?)",
                ("Legacy Trip", "Queensland, AU", "legacy"),
            )
            conn.execute("PRAGMA user_version = 0")
            conn.commit()

        initialize_database(self.db_path, self.csv_path)

        with closing(sqlite3.connect(self.db_path)) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            cols = {row[1] for row in conn.execute("PRAGMA table_info(Trips)").fetchall()}
            row = conn.execute("SELECT trip_name, location, notes FROM Trips WHERE trip_name = ?", ("Legacy Trip",)).fetchone()
            self.assertEqual(version, SCHEMA_VERSION)
            self.assertIn("location", cols)
            self.assertNotIn("region", cols)
            self.assertIsNotNone(row)
            self.assertEqual(row[1], "Queensland, AU")
            self.assertEqual(row[2], "legacy")

    def test_upgrade_legacy_trip_locations_with_trip_code(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE Trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_code TEXT,
                    trip_name TEXT,
                    location TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE Locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE TripLocations (
                    trip_code TEXT NOT NULL,
                    location_id INTEGER NOT NULL,
                    PRIMARY KEY (trip_code, location_id)
                )
                """
            )
            conn.execute("INSERT INTO Trips (trip_code, trip_name, location) VALUES (?, ?, ?)", ("T001", "Trip A", "Site A"))
            conn.execute("INSERT INTO Trips (trip_code, trip_name, location) VALUES (?, ?, ?)", ("T002", "Trip B", "Site B"))
            conn.execute("INSERT INTO Locations (name) VALUES (?)", ("Site A",))
            conn.execute("INSERT INTO Locations (name) VALUES (?)", ("Site B",))
            conn.execute("INSERT INTO TripLocations (trip_code, location_id) VALUES (?, ?)", ("T001", 1))
            conn.execute("INSERT INTO TripLocations (trip_code, location_id) VALUES (?, ?)", ("T002", 2))
            conn.execute("PRAGMA user_version = 1")
            conn.commit()

        initialize_database(self.db_path, self.csv_path)

        with closing(sqlite3.connect(self.db_path)) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            cols = [row[1] for row in conn.execute("PRAGMA table_info(TripLocations)").fetchall()]
            rows = conn.execute("SELECT id, location_id FROM TripLocations ORDER BY id, location_id").fetchall()
            self.assertEqual(version, SCHEMA_VERSION)
            self.assertIn("id", cols)
            self.assertNotIn("trip_code", cols)
            self.assertEqual(rows, [(1, 1), (2, 2)])

        initialize_database(self.db_path, self.csv_path)
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute("SELECT id, location_id FROM TripLocations ORDER BY id, location_id").fetchall()
            self.assertEqual(rows, [(1, 1), (2, 2)])

    def test_upgrade_legacy_location_collection_columns(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE Locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    county TEXT,
                    lga TEXT,
                    collection_name TEXT,
                    collection_subset TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO Locations (name, county, lga, collection_name, collection_subset)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("Legacy Site", "Legacy County", None, "Legacy Collection", "Subset A"),
            )
            conn.execute("PRAGMA user_version = 1")
            conn.commit()

        initialize_database(self.db_path, self.csv_path)

        with closing(sqlite3.connect(self.db_path)) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            location_cols = {row[1] for row in conn.execute("PRAGMA table_info(Locations)").fetchall()}
            location_row = conn.execute("SELECT name, lga FROM Locations WHERE id = 1").fetchone()
            event_row = conn.execute(
                "SELECT location_id, collection_name, collection_subset FROM CollectionEvents WHERE location_id = 1"
            ).fetchone()
            self.assertEqual(version, SCHEMA_VERSION)
            self.assertNotIn("collection_name", location_cols)
            self.assertNotIn("collection_subset", location_cols)
            self.assertNotIn("county", location_cols)
            self.assertEqual(location_row, ("Legacy Site", "Legacy County"))
            self.assertEqual(event_row, (1, "Legacy Collection", "Subset A"))

        initialize_database(self.db_path, self.csv_path)
        with closing(sqlite3.connect(self.db_path)) as conn:
            event_count = conn.execute("SELECT COUNT(*) FROM CollectionEvents WHERE location_id = 1").fetchone()[0]
            self.assertEqual(event_count, 1)


if __name__ == "__main__":
    unittest.main()
