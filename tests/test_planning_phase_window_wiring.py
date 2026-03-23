import unittest
from unittest import mock

import ui.planning_phase_window as ppw


class _FakeRepo:
    def ensure_trips_table(self):
        return None

    def get_fields(self):
        return ["id", "trip_name", "start_date", "end_date", "location", "team", "notes"]

    def list_trips(self):
        return []


class _FakeTabsController:
    def __init__(self, parent, repo, on_tab_changed):
        self.parent = parent
        self.repo = repo
        self.on_tab_changed = on_tab_changed
        self.tabs = object()
        self.trips_tab = object()
        self.location_tab = object()
        self.geology_tab = object()
        self.collection_events_tab = object()
        self.finds_tab = object()
        self.collection_plan_tab = object()
        self.team_members_tab = object()
        self.placeholder_built = False
        self.initial_loaded = False

    def build_collection_plan_placeholder(self):
        self.placeholder_built = True

    def load_initial_tab_data(self, _load_trips):
        self.initial_loaded = True


class _FakeNavigationCoordinator:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def open_collection_events_for_trip(self, *_):
        return None

    def open_finds_for_trip(self, *_):
        return None

    def open_team_members_for_trip(self, *_):
        return None

    def on_edit_dialog_closed(self, *_):
        return None

    def on_tab_changed(self):
        return None


class _FakeDialogController:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.new_calls = 0
        self.edit_calls = 0

    def new_trip(self):
        self.new_calls += 1

    def edit_selected(self):
        self.edit_calls += 1


class TestPlanningPhaseWindowWiring(unittest.TestCase):
    def test_window_wires_tabs_navigation_and_dialog_controller(self):
        fake_repo = _FakeRepo()

        def _fake_build_trips_tab(self):
            self.trips_tree = object()

        with mock.patch.object(ppw.tk.Tk, "__init__", lambda self: None), \
            mock.patch.object(ppw.tk.Tk, "title", lambda self, *_: None), \
            mock.patch.object(ppw.tk.Tk, "geometry", lambda self, *_: None), \
            mock.patch.object(ppw.tk.Tk, "protocol", lambda self, *_: None), \
            mock.patch.object(ppw.tk.Tk, "after_idle", lambda self, _cb: None), \
            mock.patch.object(ppw.PlanningPhaseWindow, "_apply_palette", lambda self: None), \
            mock.patch.object(ppw.PlanningPhaseWindow, "_build_trips_tab", _fake_build_trips_tab), \
            mock.patch("ui.planning_phase_window.TripRepository", return_value=fake_repo), \
            mock.patch("ui.planning_phase_window.PlanningTabsController", side_effect=lambda *a, **k: _FakeTabsController(*a, **k)) as tabs_cls, \
            mock.patch("ui.planning_phase_window.TripNavigationCoordinator", side_effect=lambda **k: _FakeNavigationCoordinator(**k)) as nav_cls, \
            mock.patch("ui.planning_phase_window.TripDialogController", side_effect=lambda **k: _FakeDialogController(**k)) as dialog_cls:
            window = ppw.PlanningPhaseWindow("test.db")

        self.assertIsNotNone(window.tabs_controller)
        self.assertTrue(window.tabs_controller.placeholder_built)
        self.assertTrue(window.tabs_controller.initial_loaded)

        nav_kwargs = nav_cls.call_args.kwargs
        self.assertIs(nav_kwargs["load_trips"].__self__, window)
        self.assertEqual(nav_kwargs["load_trips"].__name__, "load_trips")
        self.assertIs(nav_kwargs["select_trip_row"].__self__, window)
        self.assertEqual(nav_kwargs["select_trip_row"].__name__, "_select_trip_row")

        dialog_kwargs = dialog_cls.call_args.kwargs
        self.assertIs(dialog_kwargs["parent"], window)
        self.assertIs(dialog_kwargs["repo"], fake_repo)
        self.assertIs(dialog_kwargs["trips_tree"], window.trips_tree)
        self.assertEqual(dialog_kwargs["on_open_collection_events"], window.navigation.open_collection_events_for_trip)
        self.assertEqual(dialog_kwargs["on_open_finds"], window.navigation.open_finds_for_trip)
        self.assertEqual(dialog_kwargs["on_open_team"], window.navigation.open_team_members_for_trip)

        window.new_trip()
        window.edit_selected()
        self.assertEqual(window.dialog_controller.new_calls, 1)
        self.assertEqual(window.dialog_controller.edit_calls, 1)

        self.assertEqual(tabs_cls.call_count, 1)


if __name__ == "__main__":
    unittest.main()
