import os
import sqlite3
import tempfile
import tkinter as tk
import unittest
from contextlib import closing
from unittest import mock

from repository.trip_repository import TripRepository
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
                CREATE TABLE IF NOT EXISTS Team_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))
                )
                """
            )
            cur.execute(
                "INSERT INTO Team_members (name, phone_number, active) VALUES (?, ?, ?)",
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
            self.ce_a = events["CE-1"]
            self.ce_b = events["CE-2"]
            cur.execute("UPDATE CollectionEvents SET trip_id = ? WHERE id = ?", (self.trip_a, events["CE-1"]))
            cur.execute("UPDATE CollectionEvents SET trip_id = ? WHERE id = ?", (self.trip_b, events["CE-2"]))
            cur.execute("INSERT OR IGNORE INTO TripLocations (id, location_id) VALUES (?, ?)", (self.trip_a, self.location_id))
            cur.execute("INSERT OR IGNORE INTO TripLocations (id, location_id) VALUES (?, ?)", (self.trip_b, self.location_id))
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

    def test_full_journey_new_and_edit_find_via_trip_dialog_handoff(self):
        try:
            self.window = PlanningPhaseWindow(self.db_path)
            self.window.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable in test environment: {exc}")

        self.window.trips_tree.selection_set(str(self.trip_a))
        self.window.edit_selected()
        dialog = self.window.dialog_controller.open_edit_dialogs[self.trip_a]

        dialog._open_finds()
        self.assertEqual(self.window.tabs.select(), str(self.window.finds_tab))
        self.assertEqual(self.window.finds_tab.trip_filter_var.get(), 1)

        class _FakeFindDialog:
            def __init__(self, _parent, choices, on_save, initial_data=None, **_kwargs):
                if initial_data is None:
                    on_save(
                        {
                            "collection_event_id": self._trip_scoped_ce(choices),
                            "source_occurrence_no": "A-NEW",
                            "accepted_name": "Taxon New",
                            "identified_name": "Taxon New",
                        }
                    )
                else:
                    on_save(
                        {
                            "collection_event_id": initial_data["collection_event_id"],
                            "source_occurrence_no": "A-NEW-UPD",
                            "accepted_name": "Taxon New Updated",
                            "identified_name": "Taxon New Updated",
                        }
                    )

            @staticmethod
            def _trip_scoped_ce(choices):
                return int(choices[0][0])

        with mock.patch("ui.finds_tab.FindFormDialog", _FakeFindDialog):
            self.window.finds_tab.new_find()
            self.window.finds_tab.load_finds()
            new_find_id = None
            for iid in self.window.finds_tab.tree.get_children():
                values = self.window.finds_tab.tree.item(iid, "values")
                if "A-NEW" in values:
                    new_find_id = int(iid)
                    break
            self.assertIsNotNone(new_find_id)
            assert new_find_id is not None
            self.window.finds_tab.tree.selection_set(str(new_find_id))
            self.window.finds_tab.edit_find()

        updated = self.repo.get_find(new_find_id)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["source_occurrence_no"], "A-NEW-UPD")
        self.assertEqual(updated["accepted_name"], "Taxon New Updated")

        self.window.tabs.select(str(self.window.trips_tab))
        self.window._on_tab_changed(None)
        self.assertEqual(tuple(self.window.trips_tree.selection()), (str(self.trip_a),))
        self.assertEqual(int(dialog.winfo_viewable()), 1)

        dialog._open_finds()
        self.assertEqual(self.window.tabs.select(), str(self.window.finds_tab))
        self.assertEqual(self.window.finds_tab.trip_filter_var.get(), 1)
        self.assertEqual(len(self.window.finds_tab.tree.get_children()), 2)

        self.window.finds_tab._on_trip_filter_click(None)
        self.assertEqual(self.window.finds_tab.trip_filter_var.get(), 0)
        self.assertGreaterEqual(len(self.window.finds_tab.tree.get_children()), 3)

        self.window.finds_tab._on_trip_filter_click(None)
        self.assertEqual(self.window.finds_tab.trip_filter_var.get(), 1)
        self.assertEqual(len(self.window.finds_tab.tree.get_children()), 2)

        self.window.tabs.select(str(self.window.trips_tab))
        self.window._on_tab_changed(None)
        self.assertEqual(tuple(self.window.trips_tree.selection()), (str(self.trip_a),))
        self.assertEqual(int(dialog.winfo_viewable()), 1)


if __name__ == "__main__":
    unittest.main()
