import unittest
from unittest import mock

import ui.planning_phase_window as ppw


class _FakeRepo:
    def __init__(self):
        self.records = [
            {"id": 1, "trip_name": "Trip 1", "start_date": "2020-01-01", "end_date": "2020-01-02", "location": "Site A"}
        ]

    def ensure_trips_table(self):
        return None

    def get_fields(self):
        return ["id", "trip_name", "start_date", "end_date", "location", "team", "notes"]

    def list_trips(self):
        return list(self.records)


class _FakeTree:
    def __init__(self):
        self.items: dict[str, tuple] = {}
        self.selected: str | None = None
        self.focused: str | None = None
        self.seen: str | None = None

    def get_children(self):
        return tuple(self.items.keys())

    def delete(self, item):
        self.items.pop(str(item), None)

    def insert(self, _parent, _index, iid, values):
        self.items[str(iid)] = tuple(values)

    def selection_set(self, iid):
        self.selected = str(iid)

    def focus(self, iid):
        self.focused = str(iid)

    def see(self, iid):
        self.seen = str(iid)


class _FakeNotebook:
    def __init__(self):
        self._selected = ""

    def select(self, value=None):
        if value is None:
            return self._selected
        self._selected = value
        return self._selected


class _Token:
    def __init__(self, token: str):
        self.token = token

    def __str__(self):
        return self.token


class _FakeFilterTab(_Token):
    def __init__(self, token: str):
        super().__init__(token)
        self.activated_trip_ids: list[int] = []
        self.idle_updates = 0
        self.load_calls = 0

    def activate_trip_filter(self, trip_id: int):
        self.activated_trip_ids.append(trip_id)

    def update_idletasks(self):
        self.idle_updates += 1

    def load_collection_events(self):
        self.load_calls += 1

    def load_finds(self):
        self.load_calls += 1


class _FakeLoadTab(_Token):
    def __init__(self, token: str):
        super().__init__(token)
        self.load_calls = 0

    def load_locations(self):
        self.load_calls += 1

    def load_geology(self):
        self.load_calls += 1

    def load_users(self):
        self.load_calls += 1


class _FakeTabsController:
    def __init__(self, _parent, _repo, _on_tab_changed):
        self.tabs = _FakeNotebook()
        self.trips_tab = _Token("trips")
        self.location_tab = _FakeLoadTab("location")
        self.geology_tab = _FakeLoadTab("geology")
        self.collection_events_tab = _FakeFilterTab("collection_events")
        self.finds_tab = _FakeFilterTab("finds")
        self.collection_plan_tab = _Token("collection_plan")
        self.users_tab = _FakeLoadTab("users")

    def build_collection_plan_placeholder(self):
        return None

    def load_initial_tab_data(self, load_trips):
        load_trips()
        self.location_tab.load_locations()
        self.geology_tab.load_geology()
        self.collection_events_tab.load_collection_events()
        self.finds_tab.load_finds()
        self.users_tab.load_users()


class _FakeDialogController:
    def __init__(self, **_kwargs):
        return

    def new_trip(self):
        return None

    def edit_selected(self):
        return None


class _FakeDialog:
    def __init__(self):
        self.deiconify_calls = 0
        self.lift_calls = 0
        self.focus_calls = 0

    def winfo_exists(self):
        return True

    def deiconify(self):
        self.deiconify_calls += 1

    def lift(self):
        self.lift_calls += 1

    def focus_force(self):
        self.focus_calls += 1


class TestUiHandoffSmoke(unittest.TestCase):
    def test_trip_handoff_to_collection_events_and_finds_then_restore_selection(self):
        fake_repo = _FakeRepo()

        def _fake_build_trips_tab(self):
            self.trips_tree = _FakeTree()

        with mock.patch.object(ppw.tk.Tk, "__init__", lambda self: None), \
            mock.patch.object(ppw.tk.Tk, "title", lambda self, *_: None), \
            mock.patch.object(ppw.tk.Tk, "geometry", lambda self, *_: None), \
            mock.patch.object(ppw.PlanningPhaseWindow, "_apply_palette", lambda self: None), \
            mock.patch.object(ppw.PlanningPhaseWindow, "_build_trips_tab", _fake_build_trips_tab), \
            mock.patch("ui.planning_phase_window.TripRepository", return_value=fake_repo), \
            mock.patch("ui.planning_phase_window.PlanningTabsController", side_effect=lambda *a, **k: _FakeTabsController(*a, **k)), \
            mock.patch("ui.planning_phase_window.TripDialogController", side_effect=lambda **k: _FakeDialogController(**k)):
            window = ppw.PlanningPhaseWindow("test.db")

        ce_dialog = _FakeDialog()
        window.navigation.open_collection_events_for_trip(1, ce_dialog)
        self.assertEqual(window.tabs.select(), str(window.collection_events_tab))
        self.assertEqual(window.collection_events_tab.activated_trip_ids[-1], 1)
        self.assertEqual(window.collection_events_tab.idle_updates, 1)

        window.tabs.select(str(window.trips_tab))
        window._on_tab_changed(None)
        self.assertEqual(window.trips_tree.selected, "1")
        self.assertEqual(window.trips_tree.focused, "1")
        self.assertEqual(window.trips_tree.seen, "1")
        self.assertEqual(ce_dialog.deiconify_calls, 1)
        self.assertEqual(ce_dialog.lift_calls, 1)
        self.assertEqual(ce_dialog.focus_calls, 1)

        finds_dialog = _FakeDialog()
        window.navigation.open_finds_for_trip(1, finds_dialog)
        self.assertEqual(window.tabs.select(), str(window.finds_tab))
        self.assertEqual(window.finds_tab.activated_trip_ids[-1], 1)
        self.assertEqual(window.finds_tab.idle_updates, 1)

        window.tabs.select(str(window.trips_tab))
        window._on_tab_changed(None)
        self.assertEqual(window.trips_tree.selected, "1")
        self.assertEqual(finds_dialog.deiconify_calls, 1)
        self.assertEqual(finds_dialog.lift_calls, 1)
        self.assertEqual(finds_dialog.focus_calls, 1)


if __name__ == "__main__":
    unittest.main()
