import os
import sqlite3
import tempfile
import unittest
from contextlib import closing

import tkinter as tk

from repository.trip_repository import TripRepository
from ui.collection_events_tab import CollectionEventsTab
from ui.finds_tab import FindsTab


class TestTabFilterRegression(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_path = path
        self.repo = TripRepository(self.db_path)
        self.repo.ensure_trips_table()
        self.repo.ensure_locations_table()

        self.trip_a = self.repo.create_trip({"trip_name": "Trip A", "location": "Site Alpha"})
        self.trip_b = self.repo.create_trip({"trip_name": "Trip B", "location": "Site Alpha"})
        self.location_id = self.repo.create_location(
            {
                "name": "Site Alpha",
                "country_code": "AU",
                "state": "QLD",
                "collection_events": [
                    {"collection_name": "Site Alpha", "collection_subset": "CE-1"},
                    {"collection_name": "Site Alpha", "collection_subset": "CE-2"},
                ],
            }
        )
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            event_rows = cur.execute(
                """
                SELECT id, collection_subset
                FROM CollectionEvents
                WHERE location_id = ?
                ORDER BY id
                """,
                (self.location_id,),
            ).fetchall()
            events = {row["collection_subset"]: int(row["id"]) for row in event_rows}
            cur.execute("UPDATE CollectionEvents SET trip_id = ? WHERE id = ?", (self.trip_a, events["CE-1"]))
            cur.execute("UPDATE CollectionEvents SET trip_id = ? WHERE id = ?", (self.trip_b, events["CE-2"]))
            cur.execute(
                "INSERT OR IGNORE INTO TripLocations (id, location_id) VALUES (?, ?)",
                (self.trip_a, self.location_id),
            )
            cur.execute(
                "INSERT OR IGNORE INTO TripLocations (id, location_id) VALUES (?, ?)",
                (self.trip_b, self.location_id),
            )
            cur.execute(
                """
                INSERT INTO Finds (location_id, collection_event_id, source_system, source_occurrence_no, accepted_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.location_id, events["CE-1"], "PBDB", "A-001", "Taxon A"),
            )
            cur.execute(
                """
                INSERT INTO Finds (location_id, collection_event_id, source_system, source_occurrence_no, accepted_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.location_id, events["CE-2"], "PBDB", "B-001", "Taxon B"),
            )
            conn.commit()

        self.root = None
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable in test environment: {exc}")

    def tearDown(self):
        if self.root is not None:
            self.root.destroy()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_collection_events_trip_filter_repeat_activation_keeps_rows_visible(self):
        tab = CollectionEventsTab(self.root, self.repo)
        tab.load_collection_events()
        self.assertEqual(tab.trip_filter_var.get(), 1)
        all_count = len(tab.tree.get_children())
        self.assertGreaterEqual(all_count, 2)

        # Regression target: repeated handoffs from Trip Record should not blank the tab.
        tab.activate_trip_filter(self.trip_a)
        tab.activate_trip_filter(self.trip_a)
        tab.activate_trip_filter(self.trip_a)
        filtered_count = len(tab.tree.get_children())
        self.assertEqual(filtered_count, 1)

        # Toggle filter off should restore unfiltered rows.
        tab._on_trip_filter_click(None)
        unfiltered_again_count = len(tab.tree.get_children())
        self.assertGreaterEqual(unfiltered_again_count, 2)
        self.assertEqual(tab.trip_filter_var.get(), 0)

    def test_collection_events_new_button_requires_trip_filter_and_creates_for_selected_trip(self):
        tab = CollectionEventsTab(self.root, self.repo)
        tab.load_collection_events()

        self.assertEqual(str(tab.new_event_button.cget("state")), "disabled")
        with self.assertRaises(ValueError):
            tab.create_collection_event_for_active_trip("New CE")

        tab.activate_trip_filter(self.trip_a)
        self.assertEqual(str(tab.new_event_button.cget("state")), "normal")

        new_event_id = tab.create_collection_event_for_active_trip("Site Alpha", 2026)
        self.assertIsInstance(new_event_id, int)
        tab.load_collection_events()
        values = [tab.tree.item(iid, "values")[0] for iid in tab.tree.get_children()]
        self.assertTrue(any(str(v).startswith("Site Alpha [#") for v in values))

        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT trip_id, event_year FROM CollectionEvents WHERE id = ?",
                (new_event_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(int(row[0]), self.trip_a)
        self.assertEqual(int(row[1]), 2026)

    def test_finds_trip_filter_repeat_activation_keeps_rows_visible(self):
        tab = FindsTab(self.root, self.repo)
        tab.load_finds()
        all_count = len(tab.tree.get_children())
        self.assertGreaterEqual(all_count, 2)

        tab.activate_trip_filter(self.trip_b)
        tab.activate_trip_filter(self.trip_b)
        tab.activate_trip_filter(self.trip_b)
        filtered_count = len(tab.tree.get_children())
        self.assertEqual(filtered_count, 1)

        tab._on_trip_filter_click(None)
        unfiltered_again_count = len(tab.tree.get_children())
        self.assertGreaterEqual(unfiltered_again_count, 2)
        self.assertEqual(tab.trip_filter_var.get(), 0)

    def test_collection_events_trip_filter_uses_selected_trip_provider(self):
        tab = CollectionEventsTab(self.root, self.repo)
        tab.set_current_trip_provider(lambda: self.trip_b)
        tab.load_collection_events()
        expected_rows = self.repo.list_collection_events(self.trip_b)
        self.assertEqual(len(expected_rows), 1)
        expected_event_id = str(expected_rows[0]["id"])
        self.assertEqual(tab.trip_filter_var.get(), 1)
        visible_iids = list(tab.tree.get_children())
        self.assertEqual(visible_iids, [expected_event_id])

    def test_collection_events_double_click_edit_updates_selected_event(self):
        tab = CollectionEventsTab(self.root, self.repo)
        tab.activate_trip_filter(self.trip_a)
        visible_iids = list(tab.tree.get_children())
        self.assertEqual(len(visible_iids), 1)
        event_id = int(visible_iids[0])

        tab.edit_collection_event_by_id(event_id, "Edited CE")

        refreshed_values = tab.tree.item(str(event_id), "values")
        self.assertTrue(str(refreshed_values[0]).startswith("Edited CE [#"))
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT collection_name FROM CollectionEvents WHERE id = ?",
                (event_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row[0], f"Edited CE [#{event_id}]")


if __name__ == "__main__":
    unittest.main()
