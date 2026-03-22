import sqlite3
import unittest
from contextlib import closing

from tests._repo_test_base import RepoTestCase


class TestTripRepositoryLocationFinds(RepoTestCase):
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

    def test_list_location_names_sorted_and_non_blank(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
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

    def test_list_collection_events_trip_filter_uses_finds_assignment(self):
        trip_a = self.repo.create_trip({"trip_name": "Trip A", "location": "Shared Site"})
        trip_b = self.repo.create_trip({"trip_name": "Trip B", "location": "Shared Site"})
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Shared Site", "-22.1", "143.1", "", "", "AU", "QLD", "", "", "site", ""),
            )
            location_id = int(cur.lastrowid)
            cur.execute("INSERT INTO TripLocations (id, location_id) VALUES (?, ?)", (trip_a, location_id))
            cur.execute("INSERT INTO TripLocations (id, location_id) VALUES (?, ?)", (trip_b, location_id))

            cur.execute(
                "INSERT INTO CollectionEvents (location_id, collection_name, collection_subset) VALUES (?, ?, ?)",
                (location_id, "Shared Site", "CE-1"),
            )
            ce1 = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO CollectionEvents (location_id, collection_name, collection_subset) VALUES (?, ?, ?)",
                (location_id, "Shared Site", "CE-2"),
            )
            ce2 = int(cur.lastrowid)

            cur.execute(
                """
                INSERT INTO Finds (trip_id, location_id, collection_event_id, source_system, source_occurrence_no)
                VALUES (?, ?, ?, ?, ?)
                """,
                (trip_a, location_id, ce1, "PBDB", "A-1"),
            )
            cur.execute(
                """
                INSERT INTO Finds (trip_id, location_id, collection_event_id, source_system, source_occurrence_no)
                VALUES (?, ?, ?, ?, ?)
                """,
                (trip_b, location_id, ce2, "PBDB", "B-1"),
            )
            conn.commit()

        all_events = self.repo.list_collection_events()
        trip_a_events = self.repo.list_collection_events(trip_a)
        trip_b_events = self.repo.list_collection_events(trip_b)

        all_subsets = {row["collection_subset"] for row in all_events}
        trip_a_subsets = {row["collection_subset"] for row in trip_a_events}
        trip_b_subsets = {row["collection_subset"] for row in trip_b_events}

        self.assertTrue({"CE-1", "CE-2"}.issubset(all_subsets))
        self.assertEqual(trip_a_subsets, {"CE-1"})
        self.assertEqual(trip_b_subsets, {"CE-2"})

    def test_list_finds_trip_filter(self):
        trip_a = self.repo.create_trip({"trip_name": "Trip A", "location": "Filter Site"})
        trip_b = self.repo.create_trip({"trip_name": "Trip B", "location": "Filter Site"})
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Filter Site", "-22.2", "143.2", "", "", "AU", "QLD", "", "", "site", ""),
            )
            location_id = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO CollectionEvents (location_id, collection_name, collection_subset) VALUES (?, ?, ?)",
                (location_id, "Filter Site", "CE-F"),
            )
            ce_id = int(cur.lastrowid)
            cur.execute(
                """
                INSERT INTO Finds (trip_id, location_id, collection_event_id, source_system, source_occurrence_no)
                VALUES (?, ?, ?, ?, ?)
                """,
                (trip_a, location_id, ce_id, "PBDB", "F-A"),
            )
            cur.execute(
                """
                INSERT INTO Finds (trip_id, location_id, collection_event_id, source_system, source_occurrence_no)
                VALUES (?, ?, ?, ?, ?)
                """,
                (trip_b, location_id, ce_id, "PBDB", "F-B"),
            )
            conn.commit()

        all_occurrences = {row["source_occurrence_no"] for row in self.repo.list_finds()}
        trip_a_occurrences = {row["source_occurrence_no"] for row in self.repo.list_finds(trip_a)}
        trip_b_occurrences = {row["source_occurrence_no"] for row in self.repo.list_finds(trip_b)}

        self.assertTrue({"F-A", "F-B"}.issubset(all_occurrences))
        self.assertEqual(trip_a_occurrences, {"F-A"})
        self.assertEqual(trip_b_occurrences, {"F-B"})


if __name__ == "__main__":
    unittest.main()
