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

    def test_list_collection_events_trip_filter_uses_collection_event_trip(self):
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
                "INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset) VALUES (?, ?, ?, ?)",
                (trip_a, location_id, "Shared Site", "CE-1"),
            )
            ce1 = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset) VALUES (?, ?, ?, ?)",
                (trip_b, location_id, "Shared Site", "CE-2"),
            )
            ce2 = int(cur.lastrowid)

            cur.execute(
                """
                INSERT INTO Finds (location_id, collection_event_id, source_system, source_occurrence_no)
                VALUES (?, ?, ?, ?)
                """,
                (location_id, ce1, "PBDB", "A-1"),
            )
            cur.execute(
                """
                INSERT INTO Finds (location_id, collection_event_id, source_system, source_occurrence_no)
                VALUES (?, ?, ?, ?)
                """,
                (location_id, ce2, "PBDB", "B-1"),
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
                "INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset) VALUES (?, ?, ?, ?)",
                (trip_a, location_id, "Filter Site", "CE-A"),
            )
            ce_a = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset) VALUES (?, ?, ?, ?)",
                (trip_b, location_id, "Filter Site", "CE-B"),
            )
            ce_b = int(cur.lastrowid)
            cur.execute(
                """
                INSERT INTO Finds (location_id, collection_event_id, source_system, source_occurrence_no)
                VALUES (?, ?, ?, ?)
                """,
                (location_id, ce_a, "PBDB", "F-A"),
            )
            cur.execute(
                """
                INSERT INTO Finds (location_id, collection_event_id, source_system, source_occurrence_no)
                VALUES (?, ?, ?, ?)
                """,
                (location_id, ce_b, "PBDB", "F-B"),
            )
            conn.commit()

        all_occurrences = {row["source_occurrence_no"] for row in self.repo.list_finds()}
        trip_a_rows = self.repo.list_finds(trip_a)
        trip_b_rows = self.repo.list_finds(trip_b)
        trip_a_occurrences = {row["source_occurrence_no"] for row in trip_a_rows}
        trip_b_occurrences = {row["source_occurrence_no"] for row in trip_b_rows}

        self.assertTrue({"F-A", "F-B"}.issubset(all_occurrences))
        self.assertEqual(trip_a_occurrences, {"F-A"})
        self.assertEqual(trip_b_occurrences, {"F-B"})
        self.assertEqual({row["trip_name"] for row in trip_a_rows}, {"Trip A"})
        self.assertEqual({row["trip_name"] for row in trip_b_rows}, {"Trip B"})

    def test_finds_schema_includes_collection_year_latest_estimate(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(Finds)").fetchall()]
        self.assertIn("collection_year_latest_estimate", columns)

    def test_create_find_requires_collection_event_and_sets_location(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Find Site", "-23.0", "143.0", "", "", "AU", "QLD", "", "", "site", ""),
            )
            location_id = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset) VALUES (?, ?, ?, ?)",
                (None, location_id, "Find Site", "CE-X"),
            )
            ce_id = int(cur.lastrowid)
            conn.commit()

        with self.assertRaises(ValueError):
            self.repo.create_find({"accepted_name": "X"})

        find_id = self.repo.create_find(
            {
                "collection_event_id": ce_id,
                "source_occurrence_no": "SRC-1",
                "accepted_name": "Taxon A",
                "identified_name": "Taxon A",
                "collection_year_latest_estimate": 1999,
            }
        )
        self.assertIsInstance(find_id, int)

        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT location_id, collection_event_id, source_occurrence_no, accepted_name, collection_year_latest_estimate "
                "FROM Finds WHERE id = ?",
                (find_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row[0], location_id)
        self.assertEqual(row[1], ce_id)
        self.assertEqual(row[2], "SRC-1")
        self.assertEqual(row[3], "Taxon A")
        self.assertEqual(row[4], 1999)

    def test_update_find_moves_collection_event_and_location(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Find Site A", "-23.0", "143.0", "", "", "AU", "QLD", "", "", "site", ""),
            )
            loc_a = int(cur.lastrowid)
            cur.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Find Site B", "-23.1", "143.1", "", "", "AU", "QLD", "", "", "site", ""),
            )
            loc_b = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset) VALUES (?, ?, ?, ?)",
                (None, loc_a, "Find Site A", "CE-A"),
            )
            ce_a = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset) VALUES (?, ?, ?, ?)",
                (None, loc_b, "Find Site B", "CE-B"),
            )
            ce_b = int(cur.lastrowid)
            cur.execute(
                """
                INSERT INTO Finds (location_id, collection_event_id, source_system, source_occurrence_no, accepted_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (loc_a, ce_a, "manual", "SRC-1", "Taxon A"),
            )
            find_id = int(cur.lastrowid)
            conn.commit()

        self.repo.update_find(
            find_id,
            {
                "collection_event_id": ce_b,
                "source_occurrence_no": "SRC-2",
                "accepted_name": "Taxon B",
                "identified_name": "Taxon B",
                "reference_no": "REF-2",
                "collection_year_latest_estimate": 2001,
            },
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT location_id, collection_event_id, source_occurrence_no, accepted_name, identified_name, reference_no, collection_year_latest_estimate "
                "FROM Finds WHERE id = ?",
                (find_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row[0], loc_b)
        self.assertEqual(row[1], ce_b)
        self.assertEqual(row[2], "SRC-2")
        self.assertEqual(row[3], "Taxon B")
        self.assertEqual(row[4], "Taxon B")
        self.assertEqual(row[5], "REF-2")
        self.assertEqual(row[6], 2001)


if __name__ == "__main__":
    unittest.main()
