import unittest
from unittest import mock

from ui.trip_dialog_controller import TripDialogController


class _FakeRepo:
    def __init__(self):
        self.created_payloads: list[dict] = []
        self.updated_payloads: list[tuple[int, dict]] = []
        self._next_id = 2

    def list_active_team_members(self):
        return ["Alice"]

    def list_location_names(self):
        return ["Site A"]

    def get_trip(self, trip_id: int):
        if trip_id == 1:
            return {"id": 1, "trip_name": "Trip One", "location": "Site A", "start_date": "2020-01-01", "end_date": "2020-01-02"}
        if trip_id == 2:
            return {"id": 2, "trip_name": "Trip Two", "location": "Site A", "start_date": "", "end_date": ""}
        return None

    def create_trip(self, payload: dict):
        self.created_payloads.append(dict(payload))
        current = self._next_id
        self._next_id += 1
        return current

    def update_trip(self, trip_id: int, payload: dict):
        self.updated_payloads.append((trip_id, dict(payload)))

    def count_collection_events_for_trip(self, trip_id: int):
        return 1

    def count_finds_for_trip(self, trip_id: int):
        return 2


class _FakeTree:
    def __init__(self, selected=None):
        self._selected = selected or []

    def selection(self):
        return self._selected


class _FakeDialog:
    def __init__(self, exists=True):
        self._exists = exists
        self.destroy_calls = 0
        self.lift_calls = 0
        self.focus_calls = 0

    def winfo_exists(self):
        return self._exists

    def destroy(self):
        self.destroy_calls += 1

    def lift(self):
        self.lift_calls += 1

    def focus_force(self):
        self.focus_calls += 1


class TestTripDialogController(unittest.TestCase):
    def setUp(self):
        self.repo = _FakeRepo()
        self.tree = _FakeTree()
        self.load_trips_calls = 0
        self.closed_row_ids: list[int] = []
        self.form_calls: list[tuple[tuple, dict]] = []

        def _load_trips():
            self.load_trips_calls += 1

        self.controller = TripDialogController(
            parent=object(),
            repo=self.repo,
            edit_fields=["trip_name", "start_date", "end_date", "location", "team", "notes"],
            trips_tree=self.tree,
            load_trips=_load_trips,
            on_open_collection_events=lambda *_: None,
            on_open_finds=lambda *_: None,
            on_open_team=lambda *_: None,
            on_edit_dialog_closed=lambda rid: self.closed_row_ids.append(rid),
        )

    def _patch_form_dialog(self):
        def _factory(*args, **kwargs):
            self.form_calls.append((args, kwargs))
            return _FakeDialog()

        return mock.patch("ui.trip_dialog_controller.TripFormDialog", side_effect=_factory)

    def test_new_trip_opens_form_and_save_callback_creates_trip(self):
        with self._patch_form_dialog():
            self.controller.new_trip()

        self.assertEqual(len(self.form_calls), 1)
        _, kwargs = self.form_calls[0]
        self.assertTrue(kwargs["modal"])
        self.assertIsNone(kwargs["trip_id"])
        save_cb = self.form_calls[0][0][3]
        ok = save_cb({"trip_name": "New Trip", "start_date": "", "end_date": "", "location": "Site A", "team": "", "notes": ""})
        self.assertTrue(ok)
        self.assertEqual(self.load_trips_calls, 1)
        self.assertEqual(
            self.repo.created_payloads[-1],
            {"trip_name": "New Trip", "start_date": None, "end_date": None, "location": "Site A", "team": None, "notes": None},
        )

    def test_edit_selected_builds_save_and_duplicate_callbacks(self):
        self.tree._selected = ["1"]
        captured: dict[str, object] = {}

        def _capture_open(trip_id, trip, save_edit, duplicate_trip):
            captured["trip_id"] = trip_id
            captured["trip"] = trip
            captured["save_edit"] = save_edit
            captured["duplicate_trip"] = duplicate_trip

        with mock.patch.object(self.controller, "_open_edit_dialog", side_effect=_capture_open):
            self.controller.edit_selected()

        self.assertEqual(captured["trip_id"], 1)
        self.assertEqual(captured["trip"]["trip_name"], "Trip One")

        with mock.patch("ui.trip_dialog_controller.messagebox.showerror") as showerror:
            self.assertFalse(captured["save_edit"]({"trip_name": ""}))
            showerror.assert_called_once()

        ok = captured["save_edit"]({"trip_name": "Edited Trip", "start_date": "", "end_date": "", "location": "Site A", "team": "", "notes": ""})
        self.assertTrue(ok)
        self.assertEqual(self.repo.updated_payloads[-1][0], 1)
        self.assertEqual(self.load_trips_calls, 1)

        self.controller.open_edit_dialogs[1] = _FakeDialog(exists=True)
        opened_new: list[tuple[int, dict]] = []
        with mock.patch.object(self.controller, "_open_edit_dialog", side_effect=lambda tid, trip: opened_new.append((tid, trip))):
            dup_ok = captured["duplicate_trip"](
                {"trip_name": "Copied Trip", "start_date": "2020-01-01", "end_date": "2020-01-03", "location": "Site A", "team": "", "notes": ""}
            )
        self.assertTrue(dup_ok)
        self.assertEqual(self.repo.created_payloads[-1]["start_date"], None)
        self.assertEqual(self.repo.created_payloads[-1]["end_date"], None)
        self.assertEqual(self.controller.open_edit_dialogs[1].destroy_calls, 1)
        self.assertEqual(opened_new[0][0], 2)

    def test_open_edit_dialog_respects_max_open_limit(self):
        with mock.patch.object(self.controller, "_active_edit_dialogs", return_value=[object(), object()]):
            with mock.patch("ui.trip_dialog_controller.messagebox.showinfo") as showinfo:
                with mock.patch("ui.trip_dialog_controller.TripFormDialog") as form:
                    self.controller._open_edit_dialog(1, {"trip_name": "Trip One"})
        showinfo.assert_called_once()
        form.assert_not_called()


if __name__ == "__main__":
    unittest.main()
