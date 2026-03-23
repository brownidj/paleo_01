from typing import Any, Callable


class TripNavigationCoordinator:
    def __init__(
        self,
        tabs: Any,
        trips_tab: Any,
        location_tab: Any,
        geology_tab: Any,
        collection_events_tab: Any,
        finds_tab: Any,
        team_members_tab: Any,
        load_trips: Callable[[], None],
        select_trip_row: Callable[[int], None],
        get_trip_team_names: Callable[[int], list[str]],
    ):
        self.tabs = tabs
        self.trips_tab = trips_tab
        self.location_tab = location_tab
        self.geology_tab = geology_tab
        self.collection_events_tab = collection_events_tab
        self.finds_tab = finds_tab
        self.team_members_tab = team_members_tab
        self.load_trips = load_trips
        self.select_trip_row = select_trip_row
        self.get_trip_team_names = get_trip_team_names
        self.hidden_trip_dialog: Any | None = None
        self.hidden_trip_dialog_trip_id: int | None = None

    def open_collection_events_for_trip(self, trip_id: int, dialog: Any) -> None:
        self.hidden_trip_dialog = dialog
        self.hidden_trip_dialog_trip_id = trip_id
        self.tabs.select(str(self.collection_events_tab))
        self.collection_events_tab.activate_trip_filter(trip_id)
        self.collection_events_tab.update_idletasks()

    def open_finds_for_trip(self, trip_id: int, dialog: Any) -> None:
        self.hidden_trip_dialog = dialog
        self.hidden_trip_dialog_trip_id = trip_id
        self.tabs.select(str(self.finds_tab))
        self.finds_tab.activate_trip_filter(trip_id)
        self.finds_tab.update_idletasks()

    def open_team_members_for_trip(self, trip_id: int, dialog: Any) -> None:
        self.hidden_trip_dialog = dialog
        self.hidden_trip_dialog_trip_id = trip_id
        self.tabs.select(str(self.team_members_tab))
        team_names = self.get_trip_team_names(trip_id)
        self.team_members_tab.activate_trip_filter(team_names)
        self.team_members_tab.update_idletasks()

    def on_edit_dialog_closed(self, row_id: int) -> None:
        if self.hidden_trip_dialog_trip_id == row_id:
            self.hidden_trip_dialog = None
            self.hidden_trip_dialog_trip_id = None

    def on_tab_changed(self) -> None:
        current_tab = self.tabs.select()
        if current_tab == str(self.trips_tab):
            self.load_trips()
            self._restore_hidden_trip_dialog()
            return
        if current_tab == str(self.location_tab):
            self.location_tab.load_locations()
        if current_tab == str(self.geology_tab):
            self.geology_tab.load_geology()
        if current_tab == str(self.collection_events_tab):
            self.collection_events_tab.load_collection_events()
        if current_tab == str(self.finds_tab):
            self.finds_tab.load_finds()
        if current_tab == str(self.team_members_tab):
            self.team_members_tab.load_team_members()

    def _restore_hidden_trip_dialog(self) -> None:
        if self.hidden_trip_dialog and self.hidden_trip_dialog.winfo_exists():
            trip_id = self.hidden_trip_dialog_trip_id
            if isinstance(trip_id, int):
                self.select_trip_row(trip_id)
            self.hidden_trip_dialog.deiconify()
            self.hidden_trip_dialog.lift()
            self.hidden_trip_dialog.focus_force()
            self.hidden_trip_dialog = None
            self.hidden_trip_dialog_trip_id = None
            return
        if self.hidden_trip_dialog:
            self.hidden_trip_dialog = None
            self.hidden_trip_dialog_trip_id = None
