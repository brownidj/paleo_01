import os
import sqlite3
import tempfile
import tkinter as tk
import unittest
from contextlib import closing
from unittest import mock

from repository.trip_repository import TripRepository
from ui.finds_tab import FindsTab


class TestFindsTabIntegration(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_path = path
        self.repo = TripRepository(self.db_path)
        self.repo.ensure_trips_table()
        self.repo.ensure_locations_table()

        self.trip_a = self.repo.create_trip({"trip_name": "Trip A", "location": "Site"})
        self.trip_b = self.repo.create_trip({"trip_name": "Trip B", "location": "Site"})
        self.location_id = self.repo.create_location(
            {
                "name": "Site",
                "country_code": "AU",
                "state": "QLD",
                "collection_events": [],
            }
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset) VALUES (?, ?, ?, ?)",
                (self.trip_a, self.location_id, "Site", "CE-A"),
            )
            self.ce_a = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset) VALUES (?, ?, ?, ?)",
                (self.trip_b, self.location_id, "Site", "CE-B"),
            )
            self.ce_b = int(cur.lastrowid)
            cur.execute(
                """
                INSERT INTO Finds (location_id, collection_event_id, source_system, source_occurrence_no, accepted_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.location_id, self.ce_a, "manual", "A-1", "Taxon A"),
            )
            self.find_id = int(cur.lastrowid)
            conn.commit()

        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable in test environment: {exc}")
        self.tab = FindsTab(self.root, self.repo)
        self.tab.set_current_trip_provider(lambda: self.trip_a)

    def tearDown(self):
        if hasattr(self, "tab"):
            self.tab.destroy()
        if hasattr(self, "root"):
            self.root.destroy()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_new_find_uses_trip_scoped_collection_events_and_persists(self):
        captured_choices: list[tuple[int, str]] = []

        class _FakeDialog:
            def __init__(self, _parent, choices, _collection_event_locations, on_save, **_kwargs):
                captured_choices.extend(choices)
                on_save(
                    {
                        "collection_event_id": self._ce_id(choices),
                        "source_occurrence_no": "A-2",
                        "accepted_name": "Taxon New",
                    }
                )

            @staticmethod
            def _ce_id(choices):
                return int(choices[0][0])

        with mock.patch("ui.finds_tab.FindFormDialog", _FakeDialog):
            self.tab.new_find()

        self.assertEqual({ce_id for ce_id, _ in captured_choices}, {self.ce_a})
        trip_a_occurrences = {row["source_occurrence_no"] for row in self.repo.list_finds(self.trip_a)}
        self.assertIn("A-2", trip_a_occurrences)

    def test_edit_find_uses_trip_scoped_choices_and_updates_find(self):
        self.tab.load_finds()
        self.tab.tree.selection_set(str(self.find_id))
        captured_choices: list[tuple[int, str]] = []

        class _FakeDialog:
            def __init__(self, _parent, choices, _collection_event_locations, on_save, initial_data=None, **_kwargs):
                captured_choices.extend(choices)
                on_save(
                    {
                        "collection_event_id": initial_data["collection_event_id"] if initial_data else choices[0][0],
                        "source_occurrence_no": "A-1-upd",
                        "accepted_name": "Taxon Updated",
                        "identified_name": "Taxon Updated",
                    }
                )

        with mock.patch("ui.finds_tab.FindFormDialog", _FakeDialog):
            self.tab.edit_find()

        self.assertEqual({ce_id for ce_id, _ in captured_choices}, {self.ce_a})
        updated = self.repo.get_find(self.find_id)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["source_occurrence_no"], "A-1-upd")
        self.assertEqual(updated["accepted_name"], "Taxon Updated")


if __name__ == "__main__":
    unittest.main()
