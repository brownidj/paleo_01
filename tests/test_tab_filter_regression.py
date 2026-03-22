import os
import sqlite3
import tempfile
import unittest

import tkinter as tk

from trip_repository import TripRepository
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
        with sqlite3.connect(self.db_path) as conn:
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
                INSERT INTO Finds (trip_id, location_id, collection_event_id, source_system, source_occurrence_no, accepted_name)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (self.trip_a, self.location_id, events["CE-1"], "PBDB", "A-001", "Taxon A"),
            )
            cur.execute(
                """
                INSERT INTO Finds (trip_id, location_id, collection_event_id, source_system, source_occurrence_no, accepted_name)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (self.trip_b, self.location_id, events["CE-2"], "PBDB", "B-001", "Taxon B"),
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


if __name__ == "__main__":
    unittest.main()
