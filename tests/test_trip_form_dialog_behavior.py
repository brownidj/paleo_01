import tkinter as tk
import unittest

from ui.trip_form_dialog import TripFormDialog


class TestTripFormDialogBehavior(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable in test environment: {exc}")
        self._dialogs: list[TripFormDialog] = []

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

    def _make_dialog(self, trip_id: int | None) -> TripFormDialog:
        dialog = TripFormDialog(
            self.root,
            fields=["trip_name", "start_date", "end_date", "location", "team", "notes"],
            initial_data={
                "trip_name": "Trip One",
                "start_date": "2020-01-01",
                "end_date": "2020-01-02",
                "location": "Site A",
                "team": "Alice",
                "notes": "Note",
            },
            on_save=lambda _payload: True,
            readonly_fields=set(),
            active_users=["Alice", "Bob"],
            location_names=["Site A"],
            modal=False,
            trip_id=trip_id,
        )
        self._dialogs.append(dialog)
        return dialog

    def test_new_trip_has_no_edit_radio_and_all_fields_editable(self):
        dialog = self._make_dialog(trip_id=None)
        self.assertIsNone(dialog._edit_radio)
        for field, widget in dialog.inputs.items():
            if isinstance(widget, tk.Text):
                self.assertEqual(str(widget.cget("state")), "normal")
            else:
                self.assertEqual(str(widget.cget("state")), "normal", msg=f"{field} should be editable for new trip")

    def test_existing_trip_starts_readonly_with_edit_radio(self):
        dialog = self._make_dialog(trip_id=1)
        self.assertIsNotNone(dialog._edit_radio)
        trip_name = dialog.inputs["trip_name"]
        assert isinstance(trip_name, tk.Entry)
        self.assertEqual(str(trip_name.cget("state")), "readonly")


if __name__ == "__main__":
    unittest.main()
