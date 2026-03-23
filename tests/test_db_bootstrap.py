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
            self.assertTrue({"Team_members", "Trips", "Locations", "TripLocations", "CollectionEvents", "Finds"}.issubset(table_names))

            trip_columns = {row[1] for row in conn.execute("PRAGMA table_info(Trips)").fetchall()}
            self.assertIn("trip_name", trip_columns)
            self.assertIn("location", trip_columns)
            self.assertNotIn("region", trip_columns)
            self.assertNotIn("trip_code", trip_columns)

            user_columns = {row[1] for row in conn.execute("PRAGMA table_info(Team_members)").fetchall()}
            self.assertIn("active", user_columns)
            self.assertIn("recruitment_date", user_columns)
            self.assertIn("retirement_date", user_columns)

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


if __name__ == "__main__":
    unittest.main()
