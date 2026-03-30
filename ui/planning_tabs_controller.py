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
from ui.location_form_dialog import LocationFormDialog
from ui.team_members_tab import TeamMembersTab

try:
    import tkintermapview
except ModuleNotFoundError:
    tkintermapview = None


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
        self.tabs.add(self.location_tab, text="Location")
        self.tabs.add(self.collection_plan_tab, text="Collection Plan")
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
        attach_auto_hiding_scrollbars(self.collection_plan_tab, self.collection_plan_tree, padx=10, pady=10)
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
        body.columnconfigure(1, weight=1)
        body.rowconfigure(4, weight=1)
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
        initial_selection = existing_event_name if (edit_existing and existing_event_name) else ""
        ce_name_var = tk.StringVar(value=initial_selection)
        ce_name_combo = ttk.Combobox(
            body,
            textvariable=ce_name_var,
            values=historical_names,
            state="normal",
            width=33,
        )
        ce_name_combo.grid(row=3, column=1, sticky="ew", pady=(0, 6))
        ce_name_combo.focus_set()

        map_frame = ttk.LabelFrame(body, text="Location Map", padding=(6, 6, 6, 6))
        map_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=1)
        coords = self._resolve_trip_location_coords(location)
        if tkintermapview is None:
            ttk.Label(
                map_frame,
                text="Map preview unavailable. Install tkintermapview.",
                justify="left",
            ).grid(row=0, column=0, sticky="nw")
        elif coords is None:
            ttk.Label(
                map_frame,
                text="No map coordinates found for this trip location.",
                justify="left",
            ).grid(row=0, column=0, sticky="nw")
        else:
            lat, lon = coords
            selected_map_type, saved_zoom = LocationFormDialog._load_map_preferences()
            if selected_map_type not in LocationFormDialog.MAP_TILE_TYPES:
                selected_map_type = LocationFormDialog.DEFAULT_MAP_TYPE
            zoom_min = 5
            zoom_max = LocationFormDialog.MAP_TILE_TYPES[selected_map_type][2]
            zoom = min(max(saved_zoom, zoom_min), zoom_max)
            if selected_map_type == "OpenTopoMap" and zoom < 10:
                zoom = 10
            map_widget = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
            map_widget.pack(fill="both", expand=True)
            map_widget.set_tile_server(*LocationFormDialog.MAP_TILE_TYPES[selected_map_type])
            map_widget.set_position(lat, lon)
            map_widget.set_zoom(zoom)
            marker = map_widget.set_marker(
                lat,
                lon,
                text=str(location).strip() or f"{lat:.6f}, {lon:.6f}",
                marker_color_circle="#FF2D2D",
                marker_color_outside="#FF0000",
            )
            self._apply_half_size_marker(map_widget, marker)
            zoom_level_var = tk.IntVar(value=int(round(float(map_widget.zoom))))
            zoom_controls = ttk.Frame(map_frame, padding=(4, 6, 4, 2))
            zoom_controls.pack(fill="x")
            ttk.Label(zoom_controls, text="Zoom").pack(side="left")
            zoom_value_label = ttk.Label(zoom_controls, text=str(zoom_level_var.get()), width=3, anchor="e")
            zoom_value_label.pack(side="right")
            zoom_scale = tk.Scale(
                zoom_controls,
                from_=zoom_min,
                to=zoom_max,
                orient=tk.HORIZONTAL,
                resolution=1,
                showvalue=0,
                highlightthickness=0,
                bd=0,
                sliderlength=8,
                width=10,
            )
            zoom_scale.pack(side="left", fill="x", expand=True, padx=(8, 8))

            syncing_zoom = False

            def _sync_zoom_controls() -> None:
                nonlocal syncing_zoom
                syncing_zoom = True
                current_zoom = int(round(float(map_widget.zoom)))
                current_zoom = min(max(current_zoom, zoom_min), zoom_max)
                zoom_level_var.set(current_zoom)
                zoom_scale.set(current_zoom)
                zoom_value_label.configure(text=str(current_zoom))
                LocationFormDialog._save_map_preferences(selected_map_type, current_zoom)
                syncing_zoom = False

            def _set_zoom_from_scale(raw_value: str) -> None:
                nonlocal syncing_zoom
                if syncing_zoom:
                    return
                target_zoom = int(round(float(raw_value)))
                map_widget.set_zoom(target_zoom)
                map_widget.set_position(lat, lon)
                _sync_zoom_controls()

            def _mouse_zoom_and_sync(event) -> None:
                map_widget.mouse_zoom(event)
                map_widget.set_position(lat, lon)
                _sync_zoom_controls()

            zoom_scale.configure(command=_set_zoom_from_scale)
            map_widget.canvas.bind("<MouseWheel>", _mouse_zoom_and_sync)
            map_widget.canvas.bind("<Button-4>", _mouse_zoom_and_sync)
            map_widget.canvas.bind("<Button-5>", _mouse_zoom_and_sync)
            _sync_zoom_controls()

        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")

        def _save_plan() -> None:
            collection_event_name = ce_name_var.get().strip()
            if not collection_event_name:
                messagebox.showerror("New Plan", "Collection Event name is required.", parent=dialog)
                return
            try:
                if edit_existing and existing_event_id is not None:
                    self.repo.update_collection_event_name(existing_event_id, collection_event_name)
                else:
                    self.repo.create_collection_event_for_trip(trip_id, collection_event_name)
            except (sqlite3.Error, ValueError) as exc:
                messagebox.showerror("Plan", str(exc), parent=dialog)
                return
            dialog.destroy()
            self.load_collection_plan_trips()

        ttk.Button(buttons, text="Save" if edit_existing else "Create", command=_save_plan).pack(side="right", padx=(0, 6))
        dialog.update_idletasks()
        target_width = int(round(dialog.winfo_reqwidth() * 1.5))
        target_height = int(round(dialog.winfo_reqheight() * 2.0))
        dialog.geometry(f"{target_width}x{target_height}")

    def load_initial_tab_data(self, load_trips: Callable[[], None]) -> None:
        load_trips()
        current_tab = self.tabs.select()
        if current_tab == str(self.collection_plan_tab):
            self.load_collection_plan_trips()
        elif current_tab == str(self.location_tab):
            self.location_tab.load_locations()
        elif current_tab == str(self.geology_tab):
            self.geology_tab.load_geology()
        elif current_tab == str(self.collection_events_tab):
            self.collection_events_tab.load_collection_events()
        elif current_tab == str(self.finds_tab):
            self.finds_tab.load_finds()
        elif current_tab == str(self.team_members_tab):
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
        latest_by_trip: dict[int, dict[str, object]] = {}
        list_latest = getattr(self.repo, "list_latest_collection_events_by_trip", None)
        if callable(list_latest):
            try:
                latest_by_trip = dict(list_latest())
            except Exception:
                latest_by_trip = {}
        for trip in records:
            trip_id = int(trip["id"])
            latest_event = latest_by_trip.get(trip_id)
            if latest_event is None:
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

    def _resolve_trip_location_coords(self, location_name: str) -> tuple[float, float] | None:
        name_key = str(location_name or "").strip().lower()
        if not name_key:
            return None
        try:
            locations = self.repo.list_locations()
        except Exception:
            return None
        for row in locations:
            candidate = str(row.get("name") or "").strip().lower()
            if candidate != name_key:
                continue
            lat = self._parse_coordinate(row.get("latitude"))
            lon = self._parse_coordinate(row.get("longitude"))
            if lat is None or lon is None:
                continue
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue
            return lat, lon
        return None

    @staticmethod
    def _parse_coordinate(value: object) -> float | None:
        try:
            return float(str(value or "").strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _apply_half_size_marker(map_widget, marker) -> None:
        canvas = getattr(map_widget, "canvas", None)
        if canvas is None:
            return
        for item_name in ("canvas_marker", "canvas_icon", "canvas_text"):
            item_id = getattr(marker, item_name, None)
            if not item_id:
                continue
            try:
                bbox = canvas.bbox(item_id)
                if not bbox:
                    continue
                center_x = (bbox[0] + bbox[2]) / 2.0
                center_y = (bbox[1] + bbox[3]) / 2.0
                canvas.scale(item_id, center_x, center_y, 0.5, 0.5)
            except Exception:
                continue
