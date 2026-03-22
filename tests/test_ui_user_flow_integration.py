import os
import sqlite3
import tempfile
import tkinter as tk
import unittest
from contextlib import closing

from trip_repository import TripRepository
from ui.planning_phase_window import PlanningPhaseWindow


class TestUiUserFlowIntegration(unittest.TestCase):
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
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS Users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))
                )
                """
            )
            cur.execute(
                "INSERT INTO Users (name, phone_number, active) VALUES (?, ?, ?)",
                ("Alice Example", "+61 400 000 001", 1),
            )
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
            cur.execute("INSERT OR IGNORE INTO TripLocations (id, location_id) VALUES (?, ?)", (self.trip_a, self.location_id))
            cur.execute("INSERT OR IGNORE INTO TripLocations (id, location_id) VALUES (?, ?)", (self.trip_b, self.location_id))
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
        self.window: PlanningPhaseWindow | None = None

    def tearDown(self):
        if self.window is not None:
            self.window.destroy()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_trip_dialog_handoff_and_filter_toggles_restore_cleanly(self):
        try:
            self.window = PlanningPhaseWindow(self.db_path)
            self.window.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable in test environment: {exc}")

        self.window.trips_tree.selection_set(str(self.trip_a))
        self.window.edit_selected()
        dialog = self.window.dialog_controller.open_edit_dialogs[self.trip_a]

        dialog._open_collection_events()
        self.assertEqual(self.window.tabs.select(), str(self.window.collection_events_tab))
        self.assertEqual(self.window.collection_events_tab.trip_filter_var.get(), 1)
        self.assertEqual(len(self.window.collection_events_tab.tree.get_children()), 1)

        self.window.collection_events_tab._on_trip_filter_click(None)
        self.assertEqual(self.window.collection_events_tab.trip_filter_var.get(), 0)
        self.assertGreaterEqual(len(self.window.collection_events_tab.tree.get_children()), 2)

        self.window.collection_events_tab._on_trip_filter_click(None)
        self.assertEqual(self.window.collection_events_tab.trip_filter_var.get(), 1)
        self.assertEqual(len(self.window.collection_events_tab.tree.get_children()), 1)

        self.window.tabs.select(str(self.window.trips_tab))
        self.window._on_tab_changed(None)
        self.assertEqual(tuple(self.window.trips_tree.selection()), (str(self.trip_a),))
        self.assertEqual(int(dialog.winfo_viewable()), 1)

        dialog._open_finds()
        self.assertEqual(self.window.tabs.select(), str(self.window.finds_tab))
        self.assertEqual(self.window.finds_tab.trip_filter_var.get(), 1)
        self.assertEqual(len(self.window.finds_tab.tree.get_children()), 1)

        self.window.finds_tab._on_trip_filter_click(None)
        self.assertEqual(self.window.finds_tab.trip_filter_var.get(), 0)
        self.assertGreaterEqual(len(self.window.finds_tab.tree.get_children()), 2)

        self.window.finds_tab._on_trip_filter_click(None)
        self.assertEqual(self.window.finds_tab.trip_filter_var.get(), 1)
        self.assertEqual(len(self.window.finds_tab.tree.get_children()), 1)

        self.window.tabs.select(str(self.window.trips_tab))
        self.window._on_tab_changed(None)
        self.assertEqual(tuple(self.window.trips_tree.selection()), (str(self.trip_a),))
        self.assertEqual(int(dialog.winfo_viewable()), 1)


if __name__ == "__main__":
    unittest.main()
