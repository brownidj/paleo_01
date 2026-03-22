import unittest

from ui.trip_navigation_coordinator import TripNavigationCoordinator


class FakeNotebook:
    def __init__(self):
        self._selected = ""

    def select(self, value=None):
        if value is None:
            return self._selected
        self._selected = value
        return self._selected


class FakeTab:
    def __init__(self, token: str):
        self.token = token
        self.load_calls = 0

    def __str__(self) -> str:
        return self.token

    def load_locations(self):
        self.load_calls += 1

    def load_geology(self):
        self.load_calls += 1

    def load_collection_events(self):
        self.load_calls += 1

    def load_finds(self):
        self.load_calls += 1

    def load_users(self):
        self.load_calls += 1


class FakeFilterTab(FakeTab):
    def __init__(self, token: str):
        super().__init__(token)
        self.activated_trip_ids: list[int] = []
        self.idle_updates = 0

    def activate_trip_filter(self, trip_id: int):
        self.activated_trip_ids.append(trip_id)

    def update_idletasks(self):
        self.idle_updates += 1


class FakeDialog:
    def __init__(self, exists: bool = True):
        self.exists = exists
        self.deiconify_calls = 0
        self.lift_calls = 0
        self.focus_calls = 0

    def winfo_exists(self):
        return self.exists

    def deiconify(self):
        self.deiconify_calls += 1

    def lift(self):
        self.lift_calls += 1

    def focus_force(self):
        self.focus_calls += 1


class TestTripNavigationCoordinator(unittest.TestCase):
    def setUp(self):
        self.tabs = FakeNotebook()
        self.trips_tab = FakeTab("trips")
        self.location_tab = FakeTab("location")
        self.geology_tab = FakeTab("geology")
        self.collection_events_tab = FakeFilterTab("collection")
        self.finds_tab = FakeFilterTab("finds")
        self.users_tab = FakeTab("users")
        self.load_trips_calls = 0
        self.selected_trip_ids: list[int] = []

        def load_trips():
            self.load_trips_calls += 1

        def select_trip_row(trip_id: int):
            self.selected_trip_ids.append(trip_id)

        self.coordinator = TripNavigationCoordinator(
            tabs=self.tabs,
            trips_tab=self.trips_tab,
            location_tab=self.location_tab,
            geology_tab=self.geology_tab,
            collection_events_tab=self.collection_events_tab,
            finds_tab=self.finds_tab,
            users_tab=self.users_tab,
            load_trips=load_trips,
            select_trip_row=select_trip_row,
        )

    def test_open_collection_events_for_trip_activates_filter_and_selects_tab(self):
        dialog = FakeDialog()
        self.coordinator.open_collection_events_for_trip(42, dialog)

        self.assertEqual(self.tabs.select(), str(self.collection_events_tab))
        self.assertEqual(self.collection_events_tab.activated_trip_ids, [42])
        self.assertEqual(self.collection_events_tab.idle_updates, 1)
        self.assertIs(self.coordinator.hidden_trip_dialog, dialog)
        self.assertEqual(self.coordinator.hidden_trip_dialog_trip_id, 42)

    def test_open_finds_for_trip_activates_filter_and_selects_tab(self):
        dialog = FakeDialog()
        self.coordinator.open_finds_for_trip(7, dialog)

        self.assertEqual(self.tabs.select(), str(self.finds_tab))
        self.assertEqual(self.finds_tab.activated_trip_ids, [7])
        self.assertEqual(self.finds_tab.idle_updates, 1)
        self.assertIs(self.coordinator.hidden_trip_dialog, dialog)
        self.assertEqual(self.coordinator.hidden_trip_dialog_trip_id, 7)

    def test_on_tab_changed_trips_restores_hidden_dialog(self):
        dialog = FakeDialog(exists=True)
        self.coordinator.hidden_trip_dialog = dialog
        self.coordinator.hidden_trip_dialog_trip_id = 99
        self.tabs.select(str(self.trips_tab))

        self.coordinator.on_tab_changed()

        self.assertEqual(self.load_trips_calls, 1)
        self.assertEqual(self.selected_trip_ids, [99])
        self.assertEqual(dialog.deiconify_calls, 1)
        self.assertEqual(dialog.lift_calls, 1)
        self.assertEqual(dialog.focus_calls, 1)
        self.assertIsNone(self.coordinator.hidden_trip_dialog)
        self.assertIsNone(self.coordinator.hidden_trip_dialog_trip_id)

    def test_on_tab_changed_trips_clears_stale_hidden_dialog(self):
        dialog = FakeDialog(exists=False)
        self.coordinator.hidden_trip_dialog = dialog
        self.coordinator.hidden_trip_dialog_trip_id = 5
        self.tabs.select(str(self.trips_tab))

        self.coordinator.on_tab_changed()

        self.assertEqual(self.load_trips_calls, 1)
        self.assertEqual(self.selected_trip_ids, [])
        self.assertIsNone(self.coordinator.hidden_trip_dialog)
        self.assertIsNone(self.coordinator.hidden_trip_dialog_trip_id)

    def test_on_tab_changed_loads_current_non_trip_tab(self):
        self.tabs.select(str(self.location_tab))
        self.coordinator.on_tab_changed()
        self.tabs.select(str(self.geology_tab))
        self.coordinator.on_tab_changed()
        self.tabs.select(str(self.collection_events_tab))
        self.coordinator.on_tab_changed()
        self.tabs.select(str(self.finds_tab))
        self.coordinator.on_tab_changed()
        self.tabs.select(str(self.users_tab))
        self.coordinator.on_tab_changed()

        self.assertEqual(self.location_tab.load_calls, 1)
        self.assertEqual(self.geology_tab.load_calls, 1)
        self.assertEqual(self.collection_events_tab.load_calls, 1)
        self.assertEqual(self.finds_tab.load_calls, 1)
        self.assertEqual(self.users_tab.load_calls, 1)


if __name__ == "__main__":
    unittest.main()
