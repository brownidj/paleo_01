import tkinter as tk
import unittest

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
            on_save=lambda payload: self.saved_payloads.append(payload) or True,
            initial_data={
                "id": 1,
                "location_id": 11,
                "collection_event_id": 101,
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


if __name__ == "__main__":
    unittest.main()
