import os
import sqlite3
import tempfile
import unittest

from scripts.db_bootstrap import create_locations_table, create_users_table
from trip_repository import TripRepository


class TestTripRepository(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_path = path
        self.repo = TripRepository(self.db_path)
        self.repo.ensure_trips_table()
        with sqlite3.connect(self.db_path) as conn:
            create_users_table(conn)
            create_locations_table(conn)
            conn.executemany(
                "INSERT INTO Users (name, phone_number, active) VALUES (?, ?, ?)",
                [
                    ("Alice", "0061-412-345-678", 1),
                    ("Bob", "0061-412-345-678", 0),
                    ("Carol", "0061-412-345-678", 1),
                ],
            )
            conn.commit()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_and_fetch_trip(self):
        row_id = self.repo.create_trip(
            {
                "trip_name": "Test Trip",
                "location": "Queensland, AU",
            }
        )
        trip = self.repo.get_trip(row_id)
        self.assertIsNotNone(trip)
        self.assertEqual(trip["trip_name"], "Test Trip")
        self.assertEqual(trip["id"], row_id)

    def test_list_active_users(self):
        active = self.repo.list_active_users()
        self.assertEqual(active, ["Alice", "Carol"])

    def test_list_users_active_group_and_last_name_order(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO Users (name, phone_number, active) VALUES (?, ?, ?)",
                ("Zoe Adams", "0061-412-345-678", 1),
            )
            conn.execute(
                "INSERT INTO Users (name, phone_number, active) VALUES (?, ?, ?)",
                ("Aaron Brown", "0061-412-345-678", 1),
            )
            conn.execute(
                "INSERT INTO Users (name, phone_number, active) VALUES (?, ?, ?)",
                ("Ivy Aaron", "0061-412-345-678", 0),
            )
            conn.commit()

        users = self.repo.list_users()
        names = [u["name"] for u in users]
        actives = [u["active"] for u in users]

        # Active users should come first.
        first_inactive_idx = next((i for i, v in enumerate(actives) if v == 0), len(actives))
        self.assertTrue(all(v == 1 for v in actives[:first_inactive_idx]))
        self.assertTrue(all(v == 0 for v in actives[first_inactive_idx:]))

        # Within active users, sort by last name.
        active_names = names[:first_inactive_idx]
        self.assertEqual(active_names, ["Zoe Adams", "Alice", "Aaron Brown", "Carol"])

    def test_location_create_list_update(self):
        loc_id = self.repo.create_location(
            {
                "name": "Alpha Ridge",
                "lga": "LGA A",
                "country_code": "AU",
                "collection_events": [
                    {"collection_name": "Alpha Site", "collection_subset": "Subset A"},
                    {"collection_name": "Alpha Site", "collection_subset": "Subset B"},
                ],
            }
        )
        all_locations = self.repo.list_locations()
        self.assertEqual(len(all_locations), 1)
        self.assertEqual(all_locations[0]["name"], "Alpha Ridge")
        self.assertEqual(all_locations[0]["lga"], "LGA A")
        self.assertEqual(all_locations[0]["collection_name"], "Alpha Site")
        self.assertEqual(all_locations[0]["collection_subset"], "Subset A")
        self.assertEqual(all_locations[0]["country_code"], "AU")
        self.assertEqual(len(all_locations[0]["collection_events"]), 2)

        self.repo.update_location(
            loc_id,
            {
                "collection_events": [{"collection_name": "Beta Site", "collection_subset": None}],
            },
        )
        updated = self.repo.get_location(loc_id)
        self.assertEqual(updated["collection_name"], "Beta Site")
        self.assertIsNone(updated["collection_subset"])
        self.assertEqual(len(updated["collection_events"]), 1)

    def test_location_can_have_zero_collection_events(self):
        loc_id = self.repo.create_location(
            {
                "name": "No Event Site",
                "country_code": "AU",
                "collection_events": [],
            }
        )
        location = self.repo.get_location(loc_id)
        self.assertIsNotNone(location)
        self.assertEqual(location["name"], "No Event Site")
        self.assertEqual(location["collection_events"], [])

    def test_migrate_region_to_location_and_drop_region_column(self):
        with sqlite3.connect(self.db_path) as conn:
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

        with sqlite3.connect(self.db_path) as conn:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(Trips)").fetchall()]
            self.assertIn("location", cols)
            self.assertNotIn("region", cols)
            row = conn.execute("SELECT trip_name, location, notes FROM Trips").fetchone()
            self.assertEqual(row[0], "Legacy Trip")
            self.assertEqual(row[1], "Queensland, AU")
            self.assertEqual(row[2], "migrated")

    def test_list_location_names_sorted_and_non_blank(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Beta Site", "-27.1", "153.1", "12", "m", "AU", "QLD", "Brisbane", "X", "local", "c1"),
            )
            conn.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("", "-27.2", "153.2", "13", "m", "AU", "QLD", "Brisbane", "X", "local", "c2"),
            )
            conn.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Alpha Site", "-27.3", "153.3", "14", "m", "AU", "QLD", "Brisbane", "X", "local", "c3"),
            )
            conn.commit()

        names = self.repo.list_location_names()
        self.assertEqual(names, ["Alpha Site", "Beta Site"])


if __name__ == "__main__":
    unittest.main()
