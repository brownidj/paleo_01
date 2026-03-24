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
        accepted = dialog._inputs["accepted_name"]
        assert isinstance(accepted, tk.Entry)
        accepted.delete(0, "end")
        accepted.insert(0, "Taxon B")

        dialog._on_edit_radio_click(None)

        self.assertEqual(dialog._edit_var.get(), 0)
        self.assertEqual(len(self.saved_payloads), 1)
        self.assertEqual(self.saved_payloads[0]["accepted_name"], "Taxon B")

    def test_close_saves_when_changed(self):
        dialog = self._make_dialog()
        dialog._on_edit_radio_click(None)
        identified = dialog._inputs["identified_name"]
        assert isinstance(identified, tk.Entry)
        identified.delete(0, "end")
        identified.insert(0, "Taxon C")

        dialog._close()

        self.assertEqual(len(self.saved_payloads), 1)
        self.assertEqual(self.saved_payloads[0]["identified_name"], "Taxon C")
        self.assertFalse(dialog.winfo_exists())

    def test_close_does_not_save_when_unchanged(self):
        dialog = self._make_dialog()
        dialog._close()
        self.assertEqual(self.saved_payloads, [])


if __name__ == "__main__":
    unittest.main()
