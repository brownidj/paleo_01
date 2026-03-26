import sqlite3
import tkinter as tk
from collections.abc import Mapping
from tkinter import messagebox, ttk
from typing import Any, Literal

from app.api_auth import ApiAuthClient
from repository import DEFAULT_DB_PATH
from repository.trip_repository import TripRepository
from ui.auto_hide_scrollbars import attach_auto_hiding_scrollbars
from ui.planning_tabs_controller import PlanningTabsController
from ui.planning_phase_window_palette import PlanningPhaseWindowPaletteMixin
from ui.planning_phase_window_selection import PlanningPhaseWindowSelectionMixin
from ui.trip_dialog_controller import TripDialogController
from ui.trip_navigation_coordinator import TripNavigationCoordinator


class PlanningPhaseWindow(PlanningPhaseWindowSelectionMixin, PlanningPhaseWindowPaletteMixin, tk.Tk):

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        auth_client: ApiAuthClient | None = None,
        db_backend: str = "sqlite",
    ):
        super().__init__()
        self.title("Planning Phase")
        self.geometry("980x560")
        self._apply_palette()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._db_path = self._resolve_db_path(db_path)
        self._state_path = self._db_path.with_suffix(self._db_path.suffix + ".ui_state.json")
        self._last_selected_trip_id: int | None
        self._last_selected_trip_name: str | None
        self._last_selected_trip_id, self._last_selected_trip_name = self._load_last_selected_trip_state()
        self._suspend_trip_selection_persist = True
        self._trip_toast_shown_count = 0
        self._trip_toast_hide_after_id: str | None = None
        self._trip_toast_last_iid: str | None = None
        self.auth_client = auth_client
        self.repo: Any

        backend = db_backend.strip().lower()
        if backend == "postgres":
            try:
                from repository.postgres_trip_repository import PostgresTripRepository
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "Postgres backend requires optional dependency 'psycopg'. "
                    "Install backend requirements or run with PALEO_DESKTOP_DB_BACKEND=sqlite."
                ) from exc
            self.repo = PostgresTripRepository(str(self._db_path))
        else:
            self.repo = TripRepository(str(self._db_path))
        self.repo.ensure_trips_table()
        self.fields = self.repo.get_fields()
        self.list_fields = ["trip_name", "start_date", "collection_events_count", "finds_count", "team", "location"]
        self.edit_fields = ["trip_name", "start_date", "end_date", "location", "team", "notes"]
        static_list_fields = ["collection_events_count", "finds_count"]
        self.list_fields = [f for f in self.list_fields if f in self.fields or f in static_list_fields]
        self.edit_fields = [f for f in self.edit_fields if f in self.fields]

        self.tabs_controller = PlanningTabsController(self, self.repo, self._on_tab_changed)
        self.tabs = self.tabs_controller.tabs
        self.trips_tab = self.tabs_controller.trips_tab
        self.location_tab = self.tabs_controller.location_tab
        self.geology_tab = self.tabs_controller.geology_tab
        self.collection_events_tab = self.tabs_controller.collection_events_tab
        self.finds_tab = self.tabs_controller.finds_tab
        self.collection_plan_tab = self.tabs_controller.collection_plan_tab
        self.team_members_tab = self.tabs_controller.team_members_tab
        set_provider = getattr(self.finds_tab, "set_current_trip_provider", None)
        if callable(set_provider):
            set_provider(self._get_selected_trip_id)
        self.navigation = TripNavigationCoordinator(
            tabs=self.tabs,
            trips_tab=self.trips_tab,
            location_tab=self.location_tab,
            geology_tab=self.geology_tab,
            collection_events_tab=self.collection_events_tab,
            finds_tab=self.finds_tab,
            team_members_tab=self.team_members_tab,
            load_trips=self.load_trips,
            select_trip_row=self._select_trip_row,
            get_trip_team_names=self._trip_team_names,
        )

        self._build_trips_tab()
        self.dialog_controller = TripDialogController(
            parent=self,
            repo=self.repo,
            edit_fields=self.edit_fields,
            trips_tree=self.trips_tree,
            load_trips=self.load_trips,
            on_open_collection_events=self.navigation.open_collection_events_for_trip,
            on_open_finds=self.navigation.open_finds_for_trip,
            on_open_team=self.navigation.open_team_members_for_trip,
            on_edit_dialog_closed=self.navigation.on_edit_dialog_closed,
        )
        self.tabs_controller.build_collection_plan_placeholder()
        self.tabs_controller.load_initial_tab_data(self.load_trips)
        self.after_idle(self._restore_trip_selection)

    def _build_trips_tab(self) -> None:
        heading_labels = {
            "trip_name": "Name",
            "start_date": "Start",
            "collection_events_count": "CEs",
            "finds_count": "Finds",
            "team": "Team",
            "location": "Location",
        }
        self.trips_tree = ttk.Treeview(
            self.trips_tab,
            columns=self.list_fields,
            show="headings",
            style="Trips.Treeview",
        )
        for field in self.list_fields:
            self.trips_tree.heading(field, text=heading_labels.get(field, field))
            anchor: Literal["center", "w"] = "center" if field in {"collection_events_count", "finds_count"} else "w"
            width = 160
            stretch = field in {"trip_name", "team", "location"}
            if field == "start_date":
                width = 74
            elif field == "collection_events_count":
                width = 48
            elif field == "finds_count":
                width = 52
            minwidth = 140 if field in {"trip_name", "team", "location"} else width
            self.trips_tree.column(field, width=width, minwidth=minwidth, stretch=stretch, anchor=anchor)
        attach_auto_hiding_scrollbars(self.trips_tab, self.trips_tree, padx=10, pady=6)
        buttons = ttk.Frame(self.trips_tab)
        buttons.pack(fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="New Trip", command=self.new_trip).pack(side="left", padx=4)
        self.trips_tree.bind("<Double-1>", lambda _: self.edit_selected())
        self.trips_tree.bind("<<TreeviewSelect>>", self._on_trip_selected)
        self._trip_toast = tk.Label(
            self.trips_tab,
            text="",
            bg="#2B6E59",
            fg="#FFFFFF",
            font=("Helvetica", 12, "bold"),
            bd=2,
            relief="solid",
            padx=14,
            pady=8,
        )
        self._trip_toast.place_forget()

    def load_trips(self) -> None:
        for item in self.trips_tree.get_children():
            self.trips_tree.delete(item)
        try:
            records = self.repo.list_trips()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        for record in records:
            values = [self._trip_list_value(record, field) for field in self.list_fields]
            self.trips_tree.insert("", "end", iid=str(record["id"]), values=values)
        load_collection_plan = getattr(self.tabs_controller, "load_collection_plan_trips", None)
        if callable(load_collection_plan):
            load_collection_plan()
        self._restore_trip_selection()

    def _trip_list_value(self, record: Mapping[str, object], field: str):
        trip_id_raw = record.get("id")
        try:
            trip_id = int(trip_id_raw) if isinstance(trip_id_raw, (int, str)) else None
        except (TypeError, ValueError):
            trip_id = None
        if field == "collection_events_count":
            count_fn = getattr(self.repo, "count_collection_events_for_trip", None)
            if callable(count_fn) and trip_id is not None:
                try:
                    return int(count_fn(trip_id))
                except Exception:
                    return 0
            return 0
        if field == "finds_count":
            count_fn = getattr(self.repo, "count_finds_for_trip", None)
            if callable(count_fn) and trip_id is not None:
                try:
                    return int(count_fn(trip_id))
                except Exception:
                    return 0
            return 0
        return record.get(field, "")

    def new_trip(self) -> None:
        self.dialog_controller.new_trip()

    def edit_selected(self) -> None:
        self.dialog_controller.edit_selected()

    def _on_tab_changed(self, _event) -> None:
        self.navigation.on_tab_changed()
        current_tab = self.tabs.select()
        if current_tab == str(self.trips_tab):
            self._maybe_show_trip_edit_toast()
        elif current_tab == str(self.location_tab):
            maybe = getattr(self.location_tab, "maybe_show_edit_toast", None)
            if callable(maybe):
                maybe()
        elif current_tab == str(self.team_members_tab):
            maybe = getattr(self.team_members_tab, "maybe_show_edit_toast", None)
            if callable(maybe):
                maybe()

    def _select_trip_row(self, trip_id: int) -> None:
        iid = str(trip_id)
        if iid not in self.trips_tree.get_children():
            return
        self.trips_tree.selection_set(iid)
        self.trips_tree.focus(iid)
        self.trips_tree.see(iid)
        self._persist_trip_selection_from_iid(iid)

    def _trip_team_names(self, trip_id: int) -> list[str]:
        trip = self.repo.get_trip(trip_id)
        if not trip:
            return []
        team_value = str(trip.get("team") or "").strip()
        if not team_value:
            return []
        return [name.strip() for name in team_value.split(";") if name.strip()]
