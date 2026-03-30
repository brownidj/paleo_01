import json
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
        self.collection_plan_trip_filter_var = tk.IntVar(value=1)
        self._collection_plan_trip_filter_trip_id: int | None = None
        self._collection_plan_current_trip_id_provider = None
        self._collection_plan_event_by_trip: dict[int, int | None] = {}
        self._collection_plan_row_trip_by_iid: dict[str, int] = {}
        self._collection_plan_row_event_by_iid: dict[str, int | None] = {}

    def build_collection_plan_placeholder(self) -> None:
        trip_filter_radio = ttk.Radiobutton(
            self.collection_plan_tab,
            text="Trip filter",
            variable=self.collection_plan_trip_filter_var,
            value=1,
        )
        trip_filter_radio.pack(anchor="w", padx=10, pady=(10, 4))
        trip_filter_radio.bind("<Button-1>", self._on_collection_plan_trip_filter_click, add="+")
        self.collection_plan_tree = ttk.Treeview(
            self.collection_plan_tab,
            columns=("trip_name", "start_date", "collection_event_name", "team"),
            show="headings",
        )
        self.collection_plan_tree.heading("trip_name", text="Trip")
        self.collection_plan_tree.heading("start_date", text="Start")
        self.collection_plan_tree.heading("collection_event_name", text="Collection Event")
        self.collection_plan_tree.heading("team", text="Team")
        self.collection_plan_tree.column("trip_name", width=260, anchor="w", stretch=True)
        self.collection_plan_tree.column("start_date", width=120, anchor="w", stretch=False)
        self.collection_plan_tree.column("collection_event_name", width=260, anchor="w", stretch=True)
        self.collection_plan_tree.column("team", width=240, anchor="w", stretch=True)
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
        trip_id = self._selected_collection_plan_trip_id(str(selected[0]))
        if trip_id is None:
            return
        self._open_collection_plan_modal(trip_id, edit_existing=False, selected_event_id=None)

    def _on_collection_plan_double_click(self, _event) -> None:
        if self.collection_plan_tree is None:
            return
        selected = self.collection_plan_tree.selection()
        if not selected:
            return
        selected_iid = str(selected[0])
        trip_id = self._selected_collection_plan_trip_id(selected_iid)
        if trip_id is None:
            return
        selected_event_id = self._selected_collection_plan_event_id(selected_iid)
        self._open_collection_plan_modal(
            trip_id,
            edit_existing=selected_event_id is not None,
            selected_event_id=selected_event_id,
        )

    def _open_collection_plan_modal(
        self,
        trip_id: int,
        edit_existing: bool,
        selected_event_id: int | None = None,
    ) -> None:
        try:
            trip_id = int(trip_id)
        except (TypeError, ValueError):
            return
        trip = self.repo.get_trip(trip_id) or {}
        trip_name = str(trip.get("trip_name") or "")
        start_date = str(trip.get("start_date") or "")
        location = str(trip.get("location") or "")
        existing_event_id = (
            selected_event_id
            if selected_event_id is not None
            else (self._collection_plan_event_by_trip.get(trip_id) if edit_existing else None)
        )
        trip_events = [dict(event) for event in self.repo.list_collection_events(trip_id)]
        trip_events.sort(key=lambda row: int(row.get("id") or 0))
        trip_event_by_id: dict[int, dict[str, object]] = {}
        trip_event_name_by_id: dict[int, str] = {}
        trip_event_id_by_name: dict[str, int] = {}
        for event in trip_events:
            event_id_raw = event.get("id")
            try:
                event_id = int(event_id_raw) if event_id_raw is not None else None
            except (TypeError, ValueError):
                event_id = None
            if event_id is None:
                continue
            event_name = str(event.get("collection_name") or "").strip()
            if not event_name:
                continue
            trip_event_by_id[event_id] = event
            trip_event_name_by_id[event_id] = event_name
            trip_event_id_by_name[event_name] = event_id
        active_event_id: int | None = existing_event_id
        existing_event_name = ""
        existing_boundary_geojson = ""
        if existing_event_id is not None and existing_event_id in trip_event_by_id:
            event = trip_event_by_id[existing_event_id]
            existing_event_name = str(event.get("collection_name") or "")
            existing_boundary_geojson = str(event.get("boundary_geojson") or "")

        dialog = tk.Toplevel(self.collection_plan_tab)
        dialog.title("Edit Plan" if edit_existing else "New Plan")
        dialog.resizable(False, False)
        dialog.transient(self.collection_plan_tab.winfo_toplevel())
        dialog.grab_set()

        body = ttk.Frame(dialog, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(3, weight=1)
        body.rowconfigure(2, weight=1)
        ttk.Label(body, text="Trip").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        ttk.Label(body, text=trip_name).grid(row=0, column=1, sticky="w", pady=(0, 6))
        ttk.Label(body, text="Location").grid(row=0, column=2, sticky="w", padx=(16, 10), pady=(0, 6))
        ttk.Label(body, text=location).grid(row=0, column=3, sticky="w", pady=(0, 6))
        ttk.Label(body, text="Collection Event").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(0, 10))
        all_events = self.repo.list_collection_events(None)
        historical_names = sorted(
            {
                str(event.get("collection_name") or "").strip()
                for event in all_events
                if str(event.get("collection_name") or "").strip()
            },
            key=str.lower,
        )
        trip_event_names = [trip_event_name_by_id[event_id] for event_id in sorted(trip_event_name_by_id)]
        initial_selection = existing_event_name if (edit_existing and existing_event_name) else ""
        ce_name_var = tk.StringVar(value=initial_selection)
        active_event_boundary_loader = None

        def _on_collection_event_name_changed(_event=None) -> None:
            nonlocal active_event_id
            selected_name = ce_name_var.get().strip()
            matched_event_id = trip_event_id_by_name.get(selected_name)
            if matched_event_id is None:
                return
            active_event_id = matched_event_id
            if callable(active_event_boundary_loader):
                active_event_boundary_loader(matched_event_id)

        ce_name_combo = ttk.Combobox(
            body,
            textvariable=ce_name_var,
            values=(trip_event_names if edit_existing else historical_names),
            state=("readonly" if edit_existing else "normal"),
            width=33,
        )
        ce_name_combo.grid(row=1, column=1, sticky="ew", pady=(0, 10))
        ce_name_combo.bind("<<ComboboxSelected>>", _on_collection_event_name_changed, add="+")
        ttk.Label(body, text="Start").grid(row=1, column=2, sticky="w", padx=(16, 10), pady=(0, 10))
        ttk.Label(body, text=start_date).grid(row=1, column=3, sticky="w", pady=(0, 10))
        ce_name_combo.focus_set()

        map_frame = ttk.Frame(body)
        map_frame.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(4, 0))
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
            LocationFormDialog._start_map_loading_indicator(dialog, map_widget, selected_map_type, lat, lon, zoom)
            boundary_points = self._parse_boundary_geojson(existing_boundary_geojson)
            vertex_markers: list[object] = []
            boundary_polygon = None
            selected_vertex_index: int | None = None
            draw_press_moved = False
            suppress_next_add = False
            ctrl_drag_vertex_index: int | None = None
            ctrl_drag_active = False

            def _load_boundary_for_event(event_id: int) -> None:
                nonlocal boundary_points, selected_vertex_index, ctrl_drag_vertex_index, ctrl_drag_active, draw_press_moved
                event = trip_event_by_id.get(event_id)
                if event is None:
                    return
                boundary_points = self._parse_boundary_geojson(str(event.get("boundary_geojson") or ""))
                selected_vertex_index = None
                ctrl_drag_vertex_index = None
                ctrl_drag_active = False
                draw_press_moved = False
                _redraw_boundary()

            def _is_map_alive() -> bool:
                try:
                    return bool(
                        dialog.winfo_exists()
                        and map_widget.winfo_exists()
                        and map_widget.canvas.winfo_exists()
                    )
                except Exception:
                    return False

            def _redraw_boundary() -> None:
                nonlocal boundary_polygon
                if not _is_map_alive():
                    return
                for marker in vertex_markers:
                    try:
                        marker.delete()
                    except Exception:
                        pass
                vertex_markers.clear()
                if boundary_polygon is not None:
                    try:
                        boundary_polygon.delete()
                    except Exception:
                        pass
                    boundary_polygon = None
                for pt_lat, pt_lon in boundary_points:
                    marker_idx = len(vertex_markers)
                    try:
                        vertex_markers.append(
                            map_widget.set_marker(
                                pt_lat,
                                pt_lon,
                                text=None,
                                icon=(
                                    LocationFormDialog._get_boundary_vertex_selected_icon(dialog)
                                    if selected_vertex_index == marker_idx
                                    else LocationFormDialog._get_boundary_vertex_icon(dialog)
                                ),
                                icon_anchor="s",
                            )
                        )
                    except tk.TclError:
                        return
                if len(boundary_points) >= 3:
                    try:
                        boundary_polygon = map_widget.set_polygon(
                            [(pt_lat, pt_lon) for pt_lat, pt_lon in boundary_points],
                            outline_color="#E0A800",
                            fill_color=None,
                            border_width=2,
                        )
                    except tk.TclError:
                        boundary_polygon = None

            zoom_level_var = tk.IntVar(value=int(round(float(map_widget.zoom))))
            map_controls = ttk.Frame(map_frame, padding=(8, 6, 8, 6))
            map_controls.place(relx=0.0, rely=1.0, x=10, y=-10, anchor="sw")
            ttk.Label(map_controls, text="Map type").pack(side="left")
            map_type_var = tk.StringVar(value=selected_map_type)
            map_type_combo = ttk.Combobox(
                map_controls,
                textvariable=map_type_var,
                values=list(LocationFormDialog.MAP_TILE_TYPES.keys()),
                state="readonly",
                width=22,
            )
            map_type_combo.pack(side="left", padx=(8, 0))
            draw_var = tk.IntVar(value=0)
            ttk.Checkbutton(map_controls, text="Draw boundary", variable=draw_var).pack(side="left", padx=(12, 0))
            ttk.Label(map_controls, text="(click point to select, Ctrl+drag to move)").pack(side="left", padx=(8, 0))
            ttk.Button(
                map_controls,
                text="Undo",
                command=lambda: _undo_boundary_point(),
                width=6,
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                map_controls,
                text="Clear",
                command=lambda: _clear_boundary_points(),
                width=6,
            ).pack(side="left", padx=(6, 0))
            zoom_overlay = ttk.Frame(map_frame, padding=(6, 4, 6, 4))
            zoom_overlay.place(relx=1.0, y=10, x=-10, anchor="ne")
            zoom_min_label = ttk.Label(zoom_overlay, text=str(zoom_min), width=2, anchor="e")
            zoom_min_label.pack(side="left", padx=(0, 2))
            zoom_scale = tk.Scale(
                zoom_overlay,
                from_=zoom_min,
                to=zoom_max,
                orient=tk.HORIZONTAL,
                resolution=1,
                showvalue=0,
                highlightthickness=0,
                bd=0,
                sliderlength=2,
                width=8,
                length=180,
                troughcolor="#CFD7DF",
            )
            zoom_scale.pack(side="left")
            zoom_max_label = ttk.Label(zoom_overlay, text=str(zoom_max), width=2, anchor="w")
            zoom_max_label.pack(side="left", padx=(2, 0))
            zoom_value_overlay = tk.Label(
                zoom_overlay,
                text=str(zoom_level_var.get()),
                bg="#EEF3F8",
                fg="#20262C",
                padx=3,
                pady=1,
                font=("Helvetica", 9, "bold"),
                relief="raised",
                bd=1,
            )

            syncing_zoom = False

            def _sync_zoom_controls() -> None:
                nonlocal syncing_zoom
                if not _is_map_alive():
                    return
                syncing_zoom = True
                current_zoom = int(round(float(map_widget.zoom)))
                current_zoom = min(max(current_zoom, zoom_min), zoom_max)
                zoom_level_var.set(current_zoom)
                zoom_scale.set(current_zoom)
                zoom_max_label.configure(text=str(zoom_max))
                zoom_overlay.update_idletasks()
                scale_x = zoom_scale.winfo_x()
                scale_y = zoom_scale.winfo_y()
                scale_w = max(zoom_scale.winfo_width(), 1)
                frac = (current_zoom - zoom_min) / max((zoom_max - zoom_min), 1)
                thumb_x = int(scale_x + frac * scale_w)
                thumb_y = scale_y + max(zoom_scale.winfo_height() // 2 - 8, 0)
                zoom_value_overlay.configure(text=str(current_zoom))
                zoom_value_overlay.place(x=thumb_x, y=thumb_y, anchor="center")
                LocationFormDialog._save_map_preferences(map_type_var.get(), current_zoom)
                syncing_zoom = False

            def _set_zoom_from_scale(raw_value: str) -> None:
                nonlocal syncing_zoom
                if syncing_zoom:
                    return
                if not _is_map_alive():
                    return
                target_zoom = int(round(float(raw_value)))
                map_widget.set_zoom(target_zoom)
                map_widget.set_position(lat, lon)
                _sync_zoom_controls()

            def _mouse_zoom_and_sync(event) -> None:
                if not _is_map_alive():
                    return
                map_widget.mouse_zoom(event)
                map_widget.set_position(lat, lon)
                _sync_zoom_controls()

            def _undo_boundary_point() -> None:
                if not boundary_points:
                    return
                boundary_points.pop()
                _redraw_boundary()

            def _clear_boundary_points() -> None:
                boundary_points.clear()
                _redraw_boundary()

            def _on_map_left_click(position: tuple[float, float]) -> None:
                nonlocal suppress_next_add, ctrl_drag_active
                if draw_var.get() != 1:
                    return
                if ctrl_drag_active:
                    return
                if suppress_next_add:
                    suppress_next_add = False
                    return
                if draw_press_moved:
                    return
                if not isinstance(position, tuple) or len(position) != 2:
                    return
                pt_lat = float(position[0])
                pt_lon = float(position[1])
                if not (-90.0 <= pt_lat <= 90.0 and -180.0 <= pt_lon <= 180.0):
                    return
                boundary_points.append((pt_lat, pt_lon))
                _redraw_boundary()

            def _nearest_vertex_index(canvas_x: int, canvas_y: int, threshold_px: float = 16.0) -> int | None:
                if not vertex_markers:
                    return None
                best_idx: int | None = None
                best_dist2 = threshold_px * threshold_px
                for idx, marker in enumerate(vertex_markers):
                    try:
                        px, py = marker.get_canvas_pos(marker.position)
                    except Exception:
                        continue
                    dx = float(px) - float(canvas_x)
                    dy = float(py) - float(canvas_y)
                    dist2 = dx * dx + dy * dy
                    if dist2 <= best_dist2:
                        best_dist2 = dist2
                        best_idx = idx
                return best_idx

            def _on_draw_press(event) -> str | None:
                nonlocal draw_press_moved, selected_vertex_index, suppress_next_add
                draw_press_moved = False
                if draw_var.get() != 1:
                    selected_vertex_index = None
                    suppress_next_add = False
                    _redraw_boundary()
                    return None
                hit_index = _nearest_vertex_index(int(event.x), int(event.y))
                if hit_index is not None:
                    selected_vertex_index = hit_index
                    suppress_next_add = True
                    _redraw_boundary()
                    return "break"
                selected_vertex_index = None
                suppress_next_add = False
                _redraw_boundary()
                return None

            def _on_ctrl_draw_press(event) -> str | None:
                nonlocal ctrl_drag_vertex_index, ctrl_drag_active, selected_vertex_index, suppress_next_add
                if draw_var.get() != 1:
                    return None
                hit_index = _nearest_vertex_index(int(event.x), int(event.y))
                if hit_index is None:
                    return None
                ctrl_drag_vertex_index = hit_index
                selected_vertex_index = hit_index
                ctrl_drag_active = True
                suppress_next_add = True
                _redraw_boundary()
                return "break"

            def _on_ctrl_draw_drag(event) -> str | None:
                nonlocal draw_press_moved
                if not _is_map_alive():
                    return "break"
                if draw_var.get() != 1 or ctrl_drag_vertex_index is None:
                    return None
                draw_press_moved = True
                try:
                    dlat, dlon = map_widget.convert_canvas_coords_to_decimal_coords(int(event.x), int(event.y))
                    dlat = float(dlat)
                    dlon = float(dlon)
                except Exception:
                    return "break"
                if not (-90.0 <= dlat <= 90.0 and -180.0 <= dlon <= 180.0):
                    return "break"
                boundary_points[ctrl_drag_vertex_index] = (dlat, dlon)
                _redraw_boundary()
                return "break"

            def _on_ctrl_draw_release(_event) -> str | None:
                nonlocal ctrl_drag_vertex_index, ctrl_drag_active
                if draw_var.get() != 1:
                    ctrl_drag_vertex_index = None
                    ctrl_drag_active = False
                    return None
                if ctrl_drag_vertex_index is not None:
                    ctrl_drag_vertex_index = None
                    ctrl_drag_active = False
                    return "break"
                return None

            def _delete_selected_vertex(_event=None) -> str | None:
                nonlocal selected_vertex_index, ctrl_drag_vertex_index, ctrl_drag_active
                if draw_var.get() != 1 or selected_vertex_index is None:
                    return None
                if 0 <= selected_vertex_index < len(boundary_points):
                    boundary_points.pop(selected_vertex_index)
                selected_vertex_index = None
                ctrl_drag_vertex_index = None
                ctrl_drag_active = False
                _redraw_boundary()
                return "break"

            def _switch_map_type(_event=None) -> None:
                nonlocal zoom_max
                if not _is_map_alive():
                    return
                selection = map_type_var.get()
                tile_settings = LocationFormDialog.MAP_TILE_TYPES.get(selection)
                if not tile_settings:
                    return
                current_zoom = int(LocationFormDialog._load_zoom_for_map_type(selection))
                if current_zoom < zoom_min:
                    current_zoom = zoom_min
                if current_zoom > tile_settings[2]:
                    current_zoom = tile_settings[2]
                if selection == "OpenTopoMap" and current_zoom < 10:
                    current_zoom = 10
                map_widget.set_tile_server(*tile_settings)
                zoom_max = tile_settings[2]
                zoom_scale.configure(to=zoom_max)
                map_widget.set_position(lat, lon)
                map_widget.set_zoom(current_zoom)
                LocationFormDialog._start_map_loading_indicator(dialog, map_widget, selection, lat, lon, current_zoom)
                LocationFormDialog._save_map_preferences(selection, current_zoom)
                _sync_zoom_controls()
                _redraw_boundary()

            zoom_scale.configure(command=_set_zoom_from_scale)
            map_widget.canvas.bind("<MouseWheel>", _mouse_zoom_and_sync)
            map_widget.canvas.bind("<Button-4>", _mouse_zoom_and_sync)
            map_widget.canvas.bind("<Button-5>", _mouse_zoom_and_sync)
            map_widget.canvas.bind("<ButtonPress-1>", _on_draw_press, add="+")
            map_widget.canvas.bind("<Control-ButtonPress-1>", _on_ctrl_draw_press, add="+")
            map_widget.canvas.bind("<Control-B1-Motion>", _on_ctrl_draw_drag, add="+")
            map_widget.canvas.bind("<Control-ButtonRelease-1>", _on_ctrl_draw_release, add="+")
            map_widget.add_left_click_map_command(_on_map_left_click)
            dialog.bind("<Delete>", _delete_selected_vertex, add="+")
            map_type_combo.bind("<<ComboboxSelected>>", _switch_map_type)
            active_event_boundary_loader = _load_boundary_for_event
            _redraw_boundary()
            _sync_zoom_controls()

            def _close_dialog_safe() -> None:
                try:
                    map_widget.delete_all_marker()
                except Exception:
                    pass
                try:
                    map_widget.delete_all_path()
                except Exception:
                    pass
                try:
                    map_widget.delete_all_polygon()
                except Exception:
                    pass
                try:
                    if dialog.winfo_exists():
                        dialog.destroy()
                except Exception:
                    pass

        buttons = ttk.Frame(body)
        buttons.grid(row=3, column=0, columnspan=4, sticky="e", pady=(10, 0))
        close_dialog = locals().get("_close_dialog_safe", dialog.destroy)
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)

        def _save_plan() -> None:
            collection_event_name = ce_name_var.get().strip()
            if not collection_event_name:
                messagebox.showerror("New Plan", "Collection Event name is required.", parent=dialog)
                return
            try:
                collection_event_id_to_update: int
                if edit_existing and active_event_id is not None:
                    self.repo.update_collection_event_name(active_event_id, collection_event_name)
                    collection_event_id_to_update = int(active_event_id)
                elif edit_existing:
                    raise ValueError("No Collection Event is selected for editing.")
                else:
                    collection_event_id_to_update = int(self.repo.create_collection_event_for_trip(trip_id, collection_event_name))
                boundary_json = None
                if 'boundary_points' in locals():
                    boundary_json = self._boundary_points_to_geojson(boundary_points)
                update_boundary = getattr(self.repo, "update_collection_event_boundary", None)
                if callable(update_boundary):
                    update_boundary(collection_event_id_to_update, boundary_json)
            except (sqlite3.Error, ValueError) as exc:
                messagebox.showerror("Plan", str(exc), parent=dialog)
                return
            close_dialog()
            self.load_collection_plan_trips()

        ttk.Button(buttons, text="Save" if edit_existing else "Create", command=_save_plan).pack(side="right", padx=(0, 6))
        dialog.update_idletasks()
        target_width = int(round(dialog.winfo_reqwidth() * 1.5))
        target_height = int(round(dialog.winfo_reqheight() * 3.0))
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
        self._collection_plan_row_trip_by_iid.clear()
        self._collection_plan_row_event_by_iid.clear()
        records = self.repo.list_trips()
        active_trip_id = self._active_collection_plan_filter_trip_id()
        use_trip_filter = self.collection_plan_trip_filter_var.get() == 1 and active_trip_id is not None
        if use_trip_filter:
            records = [trip for trip in records if int(trip.get("id") or 0) == active_trip_id]
        records = [trip for trip in records if self._include_collection_plan_trip(trip.get("end_date"))]
        records.sort(key=lambda trip: (str(trip.get("trip_name") or "").lower(), str(trip.get("start_date") or "")))
        events_by_trip: dict[int, list[dict[str, object]]] = {}
        try:
            all_events = self.repo.list_collection_events(None)
        except Exception:
            all_events = []
        for event in all_events:
            trip_id_raw = event.get("trip_id")
            try:
                event_trip_id = int(trip_id_raw) if trip_id_raw is not None else None
            except (TypeError, ValueError):
                event_trip_id = None
            if event_trip_id is None:
                continue
            events_by_trip.setdefault(event_trip_id, []).append(dict(event))
        for trip in records:
            trip_id = int(trip["id"])
            trip_events = events_by_trip.get(trip_id, [])
            trip_events.sort(key=lambda row: int(row.get("id") or 0))
            if trip_events:
                latest_event = max(trip_events, key=lambda row: int(row.get("id") or 0))
                self._collection_plan_event_by_trip[trip_id] = int(latest_event["id"])
                for idx, event in enumerate(trip_events):
                    event_id = int(event.get("id") or 0)
                    row_iid = f"trip:{trip_id}:event:{event_id}"
                    self._collection_plan_row_trip_by_iid[row_iid] = trip_id
                    self._collection_plan_row_event_by_iid[row_iid] = event_id
                    tree.insert(
                        "",
                        "end",
                        iid=row_iid,
                        values=(
                            (trip.get("trip_name") or "") if idx == 0 else "",
                            (trip.get("start_date") or "") if idx == 0 else "",
                            str(event.get("collection_name") or ""),
                            (trip.get("team") or "") if idx == 0 else "",
                        ),
                    )
            else:
                self._collection_plan_event_by_trip[trip_id] = None
                row_iid = f"trip:{trip_id}:event:none"
                self._collection_plan_row_trip_by_iid[row_iid] = trip_id
                self._collection_plan_row_event_by_iid[row_iid] = None
                tree.insert(
                    "",
                    "end",
                    iid=row_iid,
                    values=((trip.get("trip_name") or ""), (trip.get("start_date") or ""), "", (trip.get("team") or "")),
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

    def _selected_collection_plan_trip_id(self, row_iid: str) -> int | None:
        if row_iid in self._collection_plan_row_trip_by_iid:
            return self._collection_plan_row_trip_by_iid[row_iid]
        try:
            return int(row_iid)
        except (TypeError, ValueError):
            return None

    def _selected_collection_plan_event_id(self, row_iid: str) -> int | None:
        if row_iid in self._collection_plan_row_event_by_iid:
            return self._collection_plan_row_event_by_iid[row_iid]
        return None

    def set_current_trip_provider(self, provider) -> None:
        self._collection_plan_current_trip_id_provider = provider

    def _on_collection_plan_trip_filter_click(self, _event) -> str:
        currently_on = self.collection_plan_trip_filter_var.get() == 1
        if currently_on:
            self.collection_plan_trip_filter_var.set(0)
        else:
            provider_trip_id = self._get_collection_plan_provider_trip_id()
            if provider_trip_id is not None:
                self._collection_plan_trip_filter_trip_id = provider_trip_id
            self.collection_plan_trip_filter_var.set(1)
        self.load_collection_plan_trips()
        return "break"

    def _get_collection_plan_provider_trip_id(self) -> int | None:
        if not callable(self._collection_plan_current_trip_id_provider):
            return None
        trip_id = self._collection_plan_current_trip_id_provider()
        if trip_id is None:
            return None
        try:
            return int(trip_id)
        except (TypeError, ValueError):
            return None

    def _active_collection_plan_filter_trip_id(self) -> int | None:
        provider_trip_id = self._get_collection_plan_provider_trip_id()
        if provider_trip_id is not None:
            self._collection_plan_trip_filter_trip_id = provider_trip_id
        return self._collection_plan_trip_filter_trip_id

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
    def _parse_boundary_geojson(boundary_geojson: str) -> list[tuple[float, float]]:
        raw = str(boundary_geojson or "").strip()
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except Exception:
            return []
        if not isinstance(payload, dict) or str(payload.get("type")) != "Polygon":
            return []
        coords = payload.get("coordinates")
        if not isinstance(coords, list) or not coords:
            return []
        ring = coords[0]
        if not isinstance(ring, list):
            return []
        points: list[tuple[float, float]] = []
        for pair in ring:
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            try:
                lon = float(pair[0])
                lat = float(pair[1])
            except (TypeError, ValueError):
                continue
            points.append((lat, lon))
        if len(points) >= 2 and points[0] == points[-1]:
            points = points[:-1]
        return points

    @staticmethod
    def _boundary_points_to_geojson(points: list[tuple[float, float]]) -> str | None:
        if len(points) < 3:
            return None
        ring = [[float(lon), float(lat)] for lat, lon in points]
        if ring[0] != ring[-1]:
            ring.append([ring[0][0], ring[0][1]])
        payload = {"type": "Polygon", "coordinates": [ring]}
        return json.dumps(payload, ensure_ascii=True)
