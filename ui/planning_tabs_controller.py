import sqlite3
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Callable

from repository.trip_repository import TripRepository
from ui.auto_hide_scrollbars import attach_auto_hiding_scrollbars
from ui.collection_events_tab import CollectionEventsTab
from ui.finds_tab import FindsTab
from ui.geology_tab import GeologyTab
from ui.location_tab import LocationTab
from ui.team_members_tab import TeamMembersTab


class PlanningTabsController:
    def __init__(self, parent, repo: TripRepository, on_tab_changed: Callable):
        self.repo = repo
        self.tabs = ttk.Notebook(parent)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)

        self.trips_tab = ttk.Frame(self.tabs)
        self.location_tab = LocationTab(self.tabs, repo)
        self.geology_tab = GeologyTab(self.tabs, repo)
        self.collection_events_tab = CollectionEventsTab(self.tabs, repo)
        self.finds_tab = FindsTab(self.tabs, repo)
        self.collection_plan_tab = ttk.Frame(self.tabs)
        self.team_members_tab = TeamMembersTab(self.tabs, repo)

        self.tabs.add(self.trips_tab, text="Trips")
        self.tabs.add(self.collection_plan_tab, text="Collection Plan")
        self.tabs.add(self.location_tab, text="Location")
        self.tabs.add(self.collection_events_tab, text="Collection Events")
        self.tabs.add(self.finds_tab, text="Finds")
        self.tabs.add(self.team_members_tab, text="Team Members")
        self.tabs.add(self.geology_tab, text="Geology")
        self.tabs.bind("<<NotebookTabChanged>>", on_tab_changed)
        self.collection_plan_tree: ttk.Treeview | None = None
        self.collection_plan_new_button: ttk.Button | None = None
        self._collection_plan_event_by_trip: dict[int, int | None] = {}

    def build_collection_plan_placeholder(self) -> None:
        self.collection_plan_tree = ttk.Treeview(
            self.collection_plan_tab,
            columns=("trip_name", "start_date", "collection_event_name"),
            show="headings",
        )
        self.collection_plan_tree.heading("trip_name", text="Trip")
        self.collection_plan_tree.heading("start_date", text="Start")
        self.collection_plan_tree.heading("collection_event_name", text="Collection Event")
        self.collection_plan_tree.column("trip_name", width=320, anchor="w", stretch=True)
        self.collection_plan_tree.column("start_date", width=120, anchor="w", stretch=False)
        self.collection_plan_tree.column("collection_event_name", width=240, anchor="w", stretch=True)
        self.collection_plan_tree.bind("<<TreeviewSelect>>", self._on_collection_plan_selected)
        self.collection_plan_tree.bind("<Double-1>", self._on_collection_plan_double_click)
        attach_auto_hiding_scrollbars(self.collection_plan_tab, self.collection_plan_tree, padx=10, pady=(10, 6))
        buttons = ttk.Frame(self.collection_plan_tab)
        buttons.pack(fill="x", padx=10, pady=8)
        self.collection_plan_new_button = ttk.Button(
            buttons,
            text="New Plan",
            command=self._on_new_plan,
            state="disabled",
        )
        self.collection_plan_new_button.pack(side="left", padx=4)
        self.load_collection_plan_trips()

    def _on_new_plan(self) -> None:
        if self.collection_plan_tree is None:
            return
        selected = self.collection_plan_tree.selection()
        if not selected:
            return
        self._open_collection_plan_modal(int(selected[0]), edit_existing=False)

    def _on_collection_plan_double_click(self, _event) -> None:
        if self.collection_plan_tree is None:
            return
        selected = self.collection_plan_tree.selection()
        if not selected:
            return
        self._open_collection_plan_modal(int(selected[0]), edit_existing=True)

    def _open_collection_plan_modal(self, trip_id: int, edit_existing: bool) -> None:
        try:
            trip_id = int(trip_id)
        except (TypeError, ValueError):
            return
        trip = self.repo.get_trip(trip_id) or {}
        trip_name = str(trip.get("trip_name") or "")
        start_date = str(trip.get("start_date") or "")
        location = str(trip.get("location") or "")
        existing_event_id = self._collection_plan_event_by_trip.get(trip_id)
        existing_event_name = ""
        if existing_event_id is not None:
            events = self.repo.list_collection_events(trip_id)
            for event in events:
                if int(event.get("id") or 0) == existing_event_id:
                    existing_event_name = str(event.get("collection_name") or "")
                    break

        dialog = tk.Toplevel(self.collection_plan_tab)
        dialog.title("Edit Plan" if edit_existing else "New Plan")
        dialog.resizable(False, False)
        dialog.transient(self.collection_plan_tab.winfo_toplevel())
        dialog.grab_set()

        body = ttk.Frame(dialog, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Trip").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        ttk.Label(body, text=trip_name).grid(row=0, column=1, sticky="w", pady=(0, 6))
        ttk.Label(body, text="Start").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        ttk.Label(body, text=start_date).grid(row=1, column=1, sticky="w", pady=(0, 6))
        ttk.Label(body, text="Location").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=(0, 10))
        ttk.Label(body, text=location).grid(row=2, column=1, sticky="w", pady=(0, 10))
        ttk.Label(body, text="Collection Event").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        all_events = self.repo.list_collection_events(None)
        historical_names = sorted(
            {
                str(event.get("collection_name") or "").strip()
                for event in all_events
                if str(event.get("collection_name") or "").strip()
            },
            key=str.lower,
        )
        create_new_option = "[+]"
        initial_selection = existing_event_name if (edit_existing and existing_event_name) else create_new_option
        ce_name_var = tk.StringVar(value=initial_selection)
        ce_name_combo = ttk.Combobox(
            body,
            textvariable=ce_name_var,
            values=[create_new_option, *historical_names],
            state="readonly",
            width=33,
        )
        ce_name_combo.grid(row=3, column=1, sticky="ew", pady=(0, 6))

        ttk.Label(body, text="New name").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        ce_name_entry = ttk.Entry(body, width=36)
        ce_name_entry.grid(row=4, column=1, sticky="ew", pady=(0, 6))
        ce_name_entry.focus_set()

        def _sync_new_name_state() -> None:
            use_new_name = ce_name_var.get() == create_new_option
            ce_name_entry.configure(state="normal" if use_new_name else "disabled")
            if not use_new_name:
                ce_name_entry.delete(0, "end")

        ce_name_combo.bind("<<ComboboxSelected>>", lambda _event: _sync_new_name_state())
        _sync_new_name_state()

        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(6, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")

        def _save_plan() -> None:
            selected_name = ce_name_var.get().strip()
            creating_new_name = selected_name == create_new_option
            if creating_new_name:
                collection_event_name = ce_name_entry.get().strip()
            else:
                collection_event_name = selected_name
            if not collection_event_name:
                messagebox.showerror("New Plan", "Collection Event name is required.", parent=dialog)
                return
            try:
                if creating_new_name:
                    self.repo.create_collection_event_for_trip(trip_id, collection_event_name)
                elif edit_existing and existing_event_id is not None:
                    self.repo.update_collection_event_name(existing_event_id, collection_event_name)
                else:
                    self.repo.create_collection_event_for_trip(trip_id, collection_event_name)
            except (sqlite3.Error, ValueError) as exc:
                messagebox.showerror("Plan", str(exc), parent=dialog)
                return
            dialog.destroy()
            self.load_collection_plan_trips()

        ttk.Button(buttons, text="Save" if edit_existing else "Create", command=_save_plan).pack(side="right", padx=(0, 6))

    def load_initial_tab_data(self, load_trips: Callable[[], None]) -> None:
        load_trips()
        self.load_collection_plan_trips()
        self.location_tab.load_locations()
        self.geology_tab.load_geology()
        self.collection_events_tab.load_collection_events()
        self.finds_tab.load_finds()
        self.team_members_tab.load_team_members()

    def load_collection_plan_trips(self) -> None:
        if self.collection_plan_tree is None:
            return
        tree = self.collection_plan_tree
        for item in tree.get_children():
            tree.delete(item)
        self._collection_plan_event_by_trip.clear()
        records = self.repo.list_trips()
        records = [trip for trip in records if self._include_collection_plan_trip(trip.get("end_date"))]
        records.sort(key=lambda trip: (str(trip.get("trip_name") or "").lower(), str(trip.get("start_date") or "")))
        for trip in records:
            trip_id = int(trip["id"])
            events = self.repo.list_collection_events(trip_id)
            latest_event = max(events, key=lambda row: int(row.get("id") or 0)) if events else None
            collection_event_name = str(latest_event.get("collection_name") or "") if latest_event else ""
            self._collection_plan_event_by_trip[trip_id] = int(latest_event["id"]) if latest_event else None
            tree.insert(
                "",
                "end",
                iid=str(trip_id),
                values=((trip.get("trip_name") or ""), (trip.get("start_date") or ""), collection_event_name),
            )
        self._set_collection_plan_button_state(False)

    def _on_collection_plan_selected(self, _event) -> None:
        if self.collection_plan_tree is None:
            return
        self._set_collection_plan_button_state(bool(self.collection_plan_tree.selection()))

    def _set_collection_plan_button_state(self, enabled: bool) -> None:
        if self.collection_plan_new_button is None:
            return
        self.collection_plan_new_button.configure(state="normal" if enabled else "disabled")

    @staticmethod
    def _include_collection_plan_trip(end_date_value: object) -> bool:
        raw = str(end_date_value or "").strip()
        if not raw:
            return True
        candidate = raw.split("T", 1)[0]
        try:
            end_date = date.fromisoformat(candidate)
        except ValueError:
            return True
        return end_date > date.today()
