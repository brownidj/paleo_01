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
            split_tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('FindFieldObservations', 'FindTaxonomy')"
                ).fetchall()
            }
        self.assertIn("collection_year_latest_estimate", columns)
        self.assertIn("find_date", columns)
        self.assertIn("find_time", columns)
        self.assertIn("latitude", columns)
        self.assertIn("longitude", columns)
        self.assertEqual(split_tables, {"FindFieldObservations", "FindTaxonomy"})

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
                "find_date": "2026-03-28",
                "find_time": "14:35",
                "latitude": "-22.12345",
                "longitude": "147.54321",
            }
        )
        self.assertIsInstance(find_id, int)

        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT location_id, collection_event_id, source_occurrence_no, find_date, find_time, latitude, longitude "
                "FROM Finds WHERE id = ?",
                (find_id,),
            ).fetchone()
            field_row = conn.execute(
                "SELECT provisional_identification, notes, abund_value, abund_unit FROM FindFieldObservations WHERE find_id = ?",
                (find_id,),
            ).fetchone()
            taxonomy_row = conn.execute(
                "SELECT identified_name, accepted_name, collection_year_latest_estimate FROM FindTaxonomy WHERE find_id = ?",
                (find_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertIsNotNone(field_row)
        self.assertIsNotNone(taxonomy_row)
        assert field_row is not None
        assert taxonomy_row is not None
        self.assertEqual(row[0], location_id)
        self.assertEqual(row[1], ce_id)
        self.assertEqual(row[2], "SRC-1")
        self.assertEqual(row[3], "2026-03-28")
        self.assertEqual(row[4], "14:35")
        self.assertEqual(row[5], "-22.12345")
        self.assertEqual(row[6], "147.54321")
        self.assertEqual(field_row[0], "Taxon A")
        self.assertEqual(taxonomy_row[0], "Taxon A")
        self.assertEqual(taxonomy_row[1], "Taxon A")
        self.assertEqual(taxonomy_row[2], 1999)

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
                "find_date": "2026-03-29",
                "find_time": "09:10",
                "latitude": "-23.10000",
                "longitude": "143.10000",
            },
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT location_id, collection_event_id, source_occurrence_no, find_date, find_time, latitude, longitude "
                "FROM Finds WHERE id = ?",
                (find_id,),
            ).fetchone()
            field_row = conn.execute(
                "SELECT provisional_identification, notes, occurrence_comments, research_group FROM FindFieldObservations WHERE find_id = ?",
                (find_id,),
            ).fetchone()
            taxonomy_row = conn.execute(
                "SELECT identified_name, accepted_name, reference_no, collection_year_latest_estimate FROM FindTaxonomy WHERE find_id = ?",
                (find_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertIsNotNone(field_row)
        self.assertIsNotNone(taxonomy_row)
        assert field_row is not None
        assert taxonomy_row is not None
        self.assertEqual(row[0], loc_b)
        self.assertEqual(row[1], ce_b)
        self.assertEqual(row[2], "SRC-2")
        self.assertEqual(row[3], "2026-03-29")
        self.assertEqual(row[4], "09:10")
        self.assertEqual(row[5], "-23.10000")
        self.assertEqual(row[6], "143.10000")
        self.assertEqual(field_row[0], "Taxon B")
        self.assertEqual(taxonomy_row[0], "Taxon B")
        self.assertEqual(taxonomy_row[1], "Taxon B")
        self.assertEqual(taxonomy_row[2], "REF-2")
        self.assertEqual(taxonomy_row[3], 2001)

    def test_create_collection_event_for_trip_uses_trip_location(self):
        trip_id = self.repo.create_trip({"trip_name": "Trip CE", "location": "Plan Site"})
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Plan Site", "-22.1", "143.1", "", "", "AU", "QLD", "", "", "site", ""),
            )
            location_id = int(cur.lastrowid)
            conn.commit()

        event_id = self.repo.create_collection_event_for_trip(trip_id, "CE-Plan-1")
        self.assertIsInstance(event_id, int)

        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT trip_id, location_id, collection_name FROM CollectionEvents WHERE id = ?",
                (event_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row[0], trip_id)
        self.assertEqual(row[1], location_id)
        self.assertEqual(row[2], f"CE-Plan-1 [#{event_id}]")

    def test_update_collection_event_name(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Edit CE Site", "-22.0", "143.0", "", "", "AU", "QLD", "", "", "site", ""),
            )
            location_id = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset) VALUES (?, ?, ?, ?)",
                (None, location_id, "Old CE", None),
            )
            event_id = int(cur.lastrowid)
            conn.commit()

        self.repo.update_collection_event_name(event_id, "Updated CE")

        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute("SELECT collection_name FROM CollectionEvents WHERE id = ?", (event_id,)).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row[0], f"Updated CE [#{event_id}]")

    def test_update_trip_location_repoints_collection_event_location(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Site A", "-22.0", "143.0", "", "", "AU", "QLD", "", "", "site", ""),
            )
            site_a = int(cur.lastrowid)
            cur.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Site B", "-22.1", "143.1", "", "", "AU", "QLD", "", "", "site", ""),
            )
            site_b = int(cur.lastrowid)
            conn.commit()

        trip_id = self.repo.create_trip({"trip_name": "Trip Loc Sync", "location": "Site A"})
        event_id = self.repo.create_collection_event_for_trip(trip_id, "CE-Loc-Sync")

        with closing(sqlite3.connect(self.db_path)) as conn:
            before_row = conn.execute(
                "SELECT location_id FROM CollectionEvents WHERE id = ?",
                (event_id,),
            ).fetchone()
        self.assertIsNotNone(before_row)
        assert before_row is not None
        self.assertEqual(int(before_row[0]), site_a)

        self.repo.update_trip(trip_id, {"location": "Site B"})

        with closing(sqlite3.connect(self.db_path)) as conn:
            after_row = conn.execute(
                "SELECT location_id FROM CollectionEvents WHERE id = ?",
                (event_id,),
            ).fetchone()
        self.assertIsNotNone(after_row)
        assert after_row is not None
        self.assertEqual(int(after_row[0]), site_b)

    def test_backfill_collection_event_codes(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO Locations (
                    name, latitude, longitude, altitude_value, altitude_unit,
                    country_code, state, lga, basin, geogscale, geography_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("Backfill CE Site", "-22.0", "143.0", "", "", "AU", "QLD", "", "", "site", ""),
            )
            location_id = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset) VALUES (?, ?, ?, ?)",
                (None, location_id, "Backfill Name", None),
            )
            event_id = int(cur.lastrowid)
            conn.commit()

        updated = self.repo.backfill_collection_event_codes()
        self.assertGreaterEqual(updated, 1)

        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute("SELECT collection_name FROM CollectionEvents WHERE id = ?", (event_id,)).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row[0], f"Backfill Name [#{event_id}]")


if __name__ == "__main__":
    unittest.main()
