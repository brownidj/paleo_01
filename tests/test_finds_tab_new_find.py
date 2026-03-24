import tkinter as tk
import unittest
from unittest import mock

from ui.finds_tab import FindsTab
from ui.find_form_dialog import FindFormDialog


class _FakeRepo:
    def __init__(self):
        self.trip_ids: list[int | None] = []
        self.updated: list[tuple[int, dict[str, object]]] = []

    def list_finds(self, _trip_id=None):
        return [
            {
                "id": 1,
                "trip_name": "Trip A",
                "collection_name": "Site A",
                "source_occurrence_no": "SRC-1",
                "accepted_name": "Taxon A",
            }
        ]

    def list_collection_events(self, trip_id=None):
        self.trip_ids.append(trip_id)
        return [
            {
                "id": 101,
                "collection_name": "Site A",
                "location_name": "Loc A",
            }
        ]

    def create_find(self, _payload):
        return 1

    def get_find(self, find_id: int):
        if find_id != 1:
            return None
        return {
            "id": 1,
            "collection_event_id": 101,
            "source_occurrence_no": "SRC-1",
            "accepted_name": "Taxon A",
            "identified_name": "Taxon A",
            "reference_no": "REF-1",
            "collection_year_latest_estimate": 1998,
        }

    def update_find(self, find_id: int, payload: dict[str, object]):
        self.updated.append((find_id, payload))


class TestFindsTabNewFind(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable in test environment: {exc}")
        self.repo = _FakeRepo()
        self.tab = FindsTab(self.root, self.repo)

    def tearDown(self):
        if hasattr(self, "tab"):
            self.tab.destroy()
        if hasattr(self, "root"):
            self.root.destroy()

    def test_new_find_scopes_collection_events_to_current_selected_trip(self):
        self.tab.trip_filter_var.set(0)
        self.tab._trip_filter_trip_id = 999
        self.tab.set_current_trip_provider(lambda: 42)

        with mock.patch("ui.finds_tab.FindFormDialog") as dialog_cls, mock.patch(
            "ui.finds_tab.messagebox.showinfo"
        ) as show_info:
            self.tab.new_find()

        self.assertEqual(self.repo.trip_ids[-1], 42)
        show_info.assert_not_called()
        dialog_cls.assert_called_once()

    def test_edit_find_opens_dialog_for_selected_row(self):
        self.tab.load_finds()
        self.tab.tree.selection_set("1")
        self.tab.set_current_trip_provider(lambda: 42)

        with mock.patch("ui.finds_tab.FindFormDialog") as dialog_cls, mock.patch(
            "ui.finds_tab.messagebox.showerror"
        ) as show_error:
            self.tab.edit_find()

        show_error.assert_not_called()
        dialog_cls.assert_called_once()
        self.assertEqual(self.repo.trip_ids[-1], 42)

    def test_edit_find_dialog_defaults_edit_toggle_off(self):
        dialog = FindFormDialog(
            self.root,
            [(101, "#101 | Site A | Loc A")],
            on_save=lambda _payload: True,
            initial_data={"id": 1, "collection_event_id": 101},
            title="Edit Find",
            is_new=False,
        )
        try:
            self.assertEqual(dialog._edit_var.get(), 0)
        finally:
            dialog.destroy()


if __name__ == "__main__":
    unittest.main()
