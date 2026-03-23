import tkinter as tk
import unittest
from unittest import mock

from ui.location_form_dialog import LocationFormDialog
from ui.location_tab import LocationTab


class _FakeRepo:
    def __init__(self):
        self.updated_geology: list[tuple[int, dict[str, object]]] = []

    def list_locations(self):
        return []

    def list_geology_records(self):
        return [{"geology_id": 10, "location_name": "Geo Loc", "formation": "Fm A"}]

    def get_location(self, location_id: int):
        if location_id != 1:
            return None
        return {
            "id": 1,
            "name": "Loc A",
            "latitude": "-20.0",
            "longitude": "147.0",
            "altitude_value": "",
            "altitude_unit": "",
            "country_code": "AU",
            "state": "Queensland",
            "lga": "",
            "basin": "",
            "geogscale": "",
            "geography_comments": "",
            "geology_id": 10,
        }

    def update_location(self, location_id: int, payload: dict[str, object]):
        return None

    def get_geology_record(self, geology_id: int):
        if geology_id != 10:
            return None
        return {"geology_id": 10, "location_name": "Geo Loc", "lithology_rows": []}

    def update_geology_record(self, geology_id: int, payload: dict[str, object]):
        self.updated_geology.append((geology_id, dict(payload)))


class TestLocationGeologyUi(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable in test environment: {exc}")

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_location_form_new_mode_has_new_geology_option(self):
        captured: dict[str, object] = {}

        def _save(payload):
            captured.update(payload)
            return True

        dlg = LocationFormDialog(
            self.root,
            initial_data=None,
            on_save=_save,
            geology_choices=[(10, "Geo Loc | Fm A")],
            is_new=True,
        )
        self.assertIsNotNone(dlg.geology_combo)
        self.assertIn(LocationFormDialog.NEW_GEOLOGY_OPTION, list(dlg.geology_combo.cget("values")))
        dlg.geology_var.set(LocationFormDialog.NEW_GEOLOGY_OPTION)
        dlg._save()
        self.assertTrue(bool(captured.get("new_geology")))
        self.assertIsNone(captured.get("geology_id"))
        if dlg.winfo_exists():
            dlg.destroy()

    def test_location_form_edit_mode_shows_readonly_geology_and_edit_icon(self):
        edited_ids: list[int] = []

        def _save(_payload):
            return True

        dlg = LocationFormDialog(
            self.root,
            initial_data={
                "name": "Loc A",
                "country_code": "AU",
                "state": "Queensland",
                "geology_id": 10,
                "geology_name": "Geo Loc | Fm A",
            },
            on_save=_save,
            geology_choices=[(10, "Geo Loc | Fm A")],
            is_new=False,
            on_edit_geology=lambda gid: edited_ids.append(gid),
        )
        self.assertIsNone(dlg.geology_combo)
        self.assertIsNotNone(dlg.geology_display)
        self.assertEqual(str(dlg.geology_display.get()), "Geo Loc | Fm A")
        self.assertIsNotNone(dlg.geology_edit_button)
        dlg._edit_geology()
        self.assertEqual(edited_ids, [10])
        if dlg.winfo_exists():
            dlg.destroy()

    def test_location_tab_edit_location_wires_geology_edit_dialog(self):
        repo = _FakeRepo()
        tab = LocationTab(self.root, repo)
        tab.tree.insert("", "end", iid="1", values=("Loc A", "", "Queensland", "AU", "-20.0", "147.0"))
        tab.tree.selection_set("1")

        captured_form_kwargs: dict[str, object] = {}

        def _fake_location_form(*_args, **kwargs):
            captured_form_kwargs.update(kwargs)
            return object()

        with mock.patch("ui.location_tab.LocationFormDialog", side_effect=_fake_location_form), \
            mock.patch("ui.location_tab.GeologyFormDialog") as geology_form:
            tab.edit_location()
            on_edit = captured_form_kwargs.get("on_edit_geology")
            self.assertTrue(callable(on_edit))
            on_edit(10)
            self.assertEqual(geology_form.call_count, 1)

        tab.destroy()


if __name__ == "__main__":
    unittest.main()
