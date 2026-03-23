import sqlite3
import unittest
from contextlib import closing

from tests._repo_test_base import RepoTestCase


class TestTripRepositoryMigrationsConnection(RepoTestCase):
    def test_migrate_region_to_location_and_drop_region_column(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("DROP TABLE Trips")
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
                ("Legacy Trip", "Queensland, AU", "migrated"),
            )
            conn.commit()

        self.repo.ensure_trips_table()

        with closing(sqlite3.connect(self.db_path)) as conn:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(Trips)").fetchall()]
            self.assertIn("location", cols)
            self.assertNotIn("region", cols)
            row = conn.execute("SELECT trip_name, location, notes FROM Trips").fetchone()
            self.assertEqual(row[0], "Legacy Trip")
            self.assertEqual(row[1], "Queensland, AU")
            self.assertEqual(row[2], "migrated")

    def test_connect_context_manager_commits_and_closes(self):
        with self.repo._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS __connect_test (id INTEGER PRIMARY KEY, value TEXT)"
            )
            conn.execute("INSERT INTO __connect_test (value) VALUES (?)", ("committed",))
            conn_ref = conn

        with self.assertRaises(sqlite3.ProgrammingError):
            conn_ref.execute("SELECT 1")

        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute("SELECT value FROM __connect_test").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "committed")

    def test_connect_context_manager_enables_foreign_keys(self):
        with self.repo._connect() as conn:
            row = conn.execute("PRAGMA foreign_keys").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(int(row[0]), 1)

    def test_connect_context_manager_rolls_back_and_closes_on_error(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS __rollback_test (id INTEGER PRIMARY KEY, value TEXT)"
            )
            conn.commit()

        with self.assertRaises(RuntimeError):
            with self.repo._connect() as conn:
                conn.execute("INSERT INTO __rollback_test (value) VALUES (?)", ("rolled_back",))
                conn_ref = conn
                raise RuntimeError("boom")

        with self.assertRaises(sqlite3.ProgrammingError):
            conn_ref.execute("SELECT 1")

        with closing(sqlite3.connect(self.db_path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM __rollback_test").fetchone()[0]
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
