import tkinter as tk
import unittest
from datetime import datetime

from ui.find_form_dialog import FindFormDialog


class TestFindFormDialogBehavior(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable in test environment: {exc}")
        self.saved_payloads: list[dict[str, object]] = []
        self._dialogs: list[FindFormDialog] = []

    def tearDown(self):
        for dialog in self._dialogs:
            try:
                dialog.destroy()
            except tk.TclError:
                pass
        if hasattr(self, "root"):
            try:
                self.root.destroy()
            except tk.TclError:
                pass

    def _make_dialog(self) -> FindFormDialog:
        dialog = FindFormDialog(
            self.root,
            [(101, "#101 | CE A | Loc A")],
            {101: "Loc A"},
            {101: [(7, "Alice"), (8, "Bob")]},
            on_save=lambda payload: self.saved_payloads.append(payload) or True,
            initial_data={
                "id": 1,
                "location_id": 11,
                "collection_event_id": 101,
                "team_member_id": 8,
                "accepted_name": "Taxon A",
                "identified_name": "Taxon A",
            },
            title="Edit Find",
            is_new=False,
        )
        self._dialogs.append(dialog)
        return dialog

    def test_toggle_edit_off_saves_changed_payload(self):
        dialog = self._make_dialog()
        self.assertEqual(dialog._edit_var.get(), 0)
        dialog._on_edit_radio_click(None)
        source_occurrence_no = dialog._inputs["source_occurrence_no"]
        assert isinstance(source_occurrence_no, tk.Entry)
        source_occurrence_no.delete(0, "end")
        source_occurrence_no.insert(0, "SRC-002")

        dialog._on_edit_radio_click(None)

        self.assertEqual(dialog._edit_var.get(), 0)
        self.assertEqual(len(self.saved_payloads), 1)
        self.assertEqual(self.saved_payloads[0]["source_occurrence_no"], "SRC-002")

    def test_close_saves_when_changed(self):
        dialog = self._make_dialog()
        dialog._on_edit_radio_click(None)
        source_system = dialog._inputs["source_system"]
        assert isinstance(source_system, tk.Entry)
        source_system.delete(0, "end")
        source_system.insert(0, "GaiaGPS")

        dialog._close()

        self.assertEqual(len(self.saved_payloads), 1)
        self.assertEqual(self.saved_payloads[0]["source_system"], "GaiaGPS")
        self.assertFalse(dialog.winfo_exists())

    def test_close_does_not_save_when_unchanged(self):
        dialog = self._make_dialog()
        dialog._close()
        self.assertEqual(self.saved_payloads, [])

    def test_location_name_tracks_selected_collection_event_and_is_readonly(self):
        dialog = FindFormDialog(
            self.root,
            [(101, "#101 | CE A | Loc A"), (102, "#102 | CE B | Loc B")],
            {101: "Loc A", 102: "Loc B"},
            {101: [(7, "Alice")], 102: [(8, "Bob")]},
            on_save=lambda _payload: True,
            initial_data={"id": 1, "collection_event_id": 101},
            title="Edit Find",
            is_new=False,
        )
        self._dialogs.append(dialog)

        location_widget = dialog._inputs["location_name"]
        assert isinstance(location_widget, tk.Entry)
        self.assertEqual(str(location_widget.cget("state")), "readonly")
        self.assertEqual(location_widget.get(), "Loc A")

        dialog._on_edit_radio_click(None)
        dialog.collection_event_var.set("#102 | CE B | Loc B")
        dialog._sync_location_name_from_collection_event()

        self.assertEqual(str(location_widget.cget("state")), "readonly")
        self.assertEqual(location_widget.get(), "Loc B")

    def test_new_dialog_has_save_button_and_defaults_date_time(self):
        dialog = FindFormDialog(
            self.root,
            [(101, "#101 | CE A | Loc A")],
            {101: "Loc A"},
            {101: [(7, "Alice")]},
            on_save=lambda _payload: True,
            initial_data=None,
            title="New Find",
            is_new=True,
        )
        self._dialogs.append(dialog)

        self.assertEqual(dialog._edit_var.get(), 1)
        find_date = dialog._inputs["find_date"]
        find_time = dialog._inputs["find_time"]
        assert isinstance(find_date, tk.Entry)
        assert isinstance(find_time, tk.Entry)
        self.assertRegex(find_date.get(), r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(find_time.get(), r"^\d{2}:\d{2}$")
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(find_date.get(), today)

        texts: list[str] = []

        def _collect_button_texts(widget: tk.Misc) -> None:
            if widget.winfo_class() in {"Button", "TButton"}:
                texts.append(str(widget.cget("text")))
            for child in widget.winfo_children():
                _collect_button_texts(child)

        _collect_button_texts(dialog)
        self.assertIn("Save", texts)
        self.assertNotIn("Close", texts)


if __name__ == "__main__":
    unittest.main()
