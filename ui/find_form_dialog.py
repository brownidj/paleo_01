import json
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

from ui.location_form_dialog import LocationFormDialog

try:
    import tkintermapview
except ModuleNotFoundError:
    tkintermapview = None


class FindFormDialog(tk.Toplevel):
    READONLY_FIELDS = ("location_name",)
    TEXT_FIELDS: tuple[str, ...] = ()
    EDITABLE_FIELDS = (
        "find_date",
        "find_time",
        "latitude",
        "longitude",
        "source_system",
        "source_occurrence_no",
    )

    def __init__(
        self,
        parent: tk.Widget,
        collection_event_choices: list[tuple[int, str]],
        collection_event_locations: dict[int, str] | None,
        team_member_choices_by_event: dict[int, list[tuple[int, str]]] | None,
        on_save,
        on_saved=None,
        on_open_field_observations=None,
        on_open_taxonomy=None,
        initial_data: dict[str, object] | None = None,
        title: str = "Find",
        is_new: bool = False,
        collection_event_map_data: dict[int, dict[str, object]] | None = None,
    ):
        super().__init__(parent)
        self.title(title)
        self.resizable(True, True)
        self.minsize(640, 520)
        self.on_save = on_save
        self.on_saved = on_saved
        self._is_new = is_new
        self._on_open_field_observations = on_open_field_observations
        self._find_id = int(initial_data["id"]) if initial_data and initial_data.get("id") not in (None, "") else None
        self._choice_map: dict[str, int] = {label: ce_id for ce_id, label in collection_event_choices}
        self._collection_event_locations = dict(collection_event_locations or {})
        self._team_member_choices_by_event = {
            int(event_id): list(choices)
            for event_id, choices in (team_member_choices_by_event or {}).items()
        }
        self._collection_event_map_data = dict(collection_event_map_data or {})
        self._selected_collection_event_id = (
            int(initial_data["collection_event_id"]) if initial_data and initial_data.get("collection_event_id") else None
        )
        self._initial_team_member_id = (
            int(initial_data["team_member_id"]) if initial_data and initial_data.get("team_member_id") not in (None, "") else None
        )
        self._team_member_var = tk.StringVar(value="")
        self._team_member_choice_map: dict[str, int] = {}
        self._team_member_combo: ttk.Combobox | None = None
        self._edit_var = tk.IntVar(value=1 if self._is_new else 0)
        self._last_saved_payload: dict[str, object] = {}
        self._on_open_taxonomy = on_open_taxonomy
        self._picker_buttons: dict[str, ttk.Button] = {}
        self._map_widget = None
        self._map_polygon = None
        self._find_marker = None
        self._map_center_by_event_id: dict[int, tuple[float, float]] = {}
        self._boundary_by_event_id: dict[int, list[tuple[float, float]]] = {}
        self._map_default_zoom = LocationFormDialog.DEFAULT_MAP_ZOOM

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, highlightthickness=0)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")

        form = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=form, anchor="nw")

        def _sync_scroll_region(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _sync_form_width(event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        form.bind("<Configure>", _sync_scroll_region)
        canvas.bind("<Configure>", _sync_form_width)

        self._inputs: dict[str, tk.Widget] = {}
        now = datetime.now()
        default_values: dict[str, str] = {}
        if self._is_new:
            default_values = {
                "find_date": now.strftime("%Y-%m-%d"),
                "find_time": now.strftime("%H:%M"),
            }

        row = 0
        for field in self.READONLY_FIELDS:
            label_text = "Location" if field == "location_name" else field
            ttk.Label(form, text=label_text).grid(row=row, column=0, sticky="e", padx=4, pady=4)
            entry = ttk.Entry(form, width=64)
            value = ""
            if initial_data and initial_data.get(field) is not None:
                value = str(initial_data.get(field))
            entry.insert(0, value)
            entry.configure(state="readonly")
            entry.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            self._inputs[field] = entry
            row += 1

        ttk.Label(form, text="CE").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        self.collection_event_var = tk.StringVar(value=collection_event_choices[0][1] if collection_event_choices else "")
        self.collection_event_combo = ttk.Combobox(
            form,
            textvariable=self.collection_event_var,
            values=[label for _, label in collection_event_choices],
            state="readonly",
            width=62,
        )
        self.collection_event_combo.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        if self._selected_collection_event_id is not None:
            for ce_id, label in collection_event_choices:
                if ce_id == self._selected_collection_event_id:
                    self.collection_event_var.set(label)
                    break
        self.collection_event_combo.bind("<<ComboboxSelected>>", self._on_collection_event_changed, add="+")
        self._sync_location_name_from_collection_event()
        row += 1

        ttk.Label(form, text="Team member").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        self._team_member_combo = ttk.Combobox(
            form,
            textvariable=self._team_member_var,
            values=[],
            state="readonly",
            width=62,
        )
        self._team_member_combo.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        self._sync_team_member_choices_from_collection_event()
        row += 1

        ttk.Label(form, text="Date").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        date_time_row = ttk.Frame(form)
        date_time_row.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        date_time_row.columnconfigure(0, weight=1)
        date_widget = ttk.Entry(date_time_row, width=22)
        date_value = ""
        if initial_data and initial_data.get("find_date") is not None:
            date_value = str(initial_data.get("find_date"))
        if not date_value:
            date_value = default_values.get("find_date", "")
        date_widget.insert(0, date_value)
        date_widget.grid(row=0, column=0, sticky="ew")
        date_picker = ttk.Button(date_time_row, text="📅", width=3, command=self._open_date_picker)
        date_picker.grid(row=0, column=1, padx=(6, 12), sticky="w")
        ttk.Label(date_time_row, text="Time").grid(row=0, column=2, padx=(0, 6), sticky="e")
        time_widget = ttk.Entry(date_time_row, width=18)
        time_value = ""
        if initial_data and initial_data.get("find_time") is not None:
            time_value = str(initial_data.get("find_time"))
        if not time_value:
            time_value = default_values.get("find_time", "")
        time_widget.insert(0, time_value)
        time_widget.grid(row=0, column=3, sticky="w")
        time_picker = ttk.Button(date_time_row, text="🕒", width=3, command=self._open_time_picker)
        time_picker.grid(row=0, column=4, padx=(6, 0), sticky="w")
        self._inputs["find_date"] = date_widget
        self._inputs["find_time"] = time_widget
        self._picker_buttons["find_date"] = date_picker
        self._picker_buttons["find_time"] = time_picker
        row += 1

        ttk.Label(form, text="Lat").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        lat_lon_row = ttk.Frame(form)
        lat_lon_row.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        lat_widget = ttk.Entry(lat_lon_row, width=26)
        lat_value = ""
        if initial_data and initial_data.get("latitude") is not None:
            lat_value = str(initial_data.get("latitude"))
        if lat_value:
            lat_widget.insert(0, lat_value)
        lat_widget.grid(row=0, column=0, sticky="w")
        ttk.Label(lat_lon_row, text="Lon").grid(row=0, column=1, padx=(12, 6), sticky="e")
        lon_widget = ttk.Entry(lat_lon_row, width=26)
        lon_value = ""
        if initial_data and initial_data.get("longitude") is not None:
            lon_value = str(initial_data.get("longitude"))
        if lon_value:
            lon_widget.insert(0, lon_value)
        lon_widget.grid(row=0, column=2, sticky="w")
        self._inputs["latitude"] = lat_widget
        self._inputs["longitude"] = lon_widget
        row += 1

        ttk.Label(form, text="Source").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        source_row = ttk.Frame(form)
        source_row.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        source_row.columnconfigure(1, weight=1)
        source_widget = ttk.Entry(source_row, width=24)
        source_value = ""
        if initial_data and initial_data.get("source_system") is not None:
            source_value = str(initial_data.get("source_system"))
        source_widget.insert(0, source_value)
        source_widget.grid(row=0, column=1, sticky="ew")
        ttk.Label(source_row, text="#").grid(row=0, column=2, padx=(12, 6), sticky="e")
        source_occ_widget = ttk.Entry(source_row, width=22)
        source_occ_value = ""
        if initial_data and initial_data.get("source_occurrence_no") is not None:
            source_occ_value = str(initial_data.get("source_occurrence_no"))
        source_occ_widget.insert(0, source_occ_value)
        source_occ_widget.grid(row=0, column=3, sticky="w")
        self._inputs["source_system"] = source_widget
        self._inputs["source_occurrence_no"] = source_occ_widget
        row += 1

        if self._is_new:
            ttk.Label(form, text="CE Area").grid(row=row, column=0, sticky="ne", padx=4, pady=(8, 4))
            map_frame = ttk.Frame(form, height=340)
            map_frame.grid(row=row, column=1, sticky="nsew", padx=4, pady=(8, 4))
            map_frame.grid_propagate(False)
            map_frame.columnconfigure(0, weight=1)
            map_frame.rowconfigure(0, weight=1)
            self._build_collection_event_map(map_frame)
            row += 1

        form.columnconfigure(1, weight=1)

        controls = ttk.Frame(outer)
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        controls.columnconfigure(0, weight=1)
        edit_radio = ttk.Radiobutton(controls, text="Edit", variable=self._edit_var, value=1)
        edit_radio.grid(row=0, column=1, padx=(6, 4), sticky="e")
        edit_radio.bind("<Button-1>", self._on_edit_radio_click, add="+")
        button_col = 2
        if callable(self._on_open_field_observations) and isinstance(self._find_id, int):
            ttk.Button(
                controls,
                text="Observations",
                command=self._open_field_observations,
            ).grid(row=0, column=button_col, padx=4, sticky="e")
            button_col += 1
        if callable(self._on_open_taxonomy) and isinstance(self._find_id, int):
            ttk.Button(
                controls,
                text="Taxonomy",
                command=self._open_taxonomy,
            ).grid(row=0, column=button_col, padx=4, sticky="e")
            button_col += 1
        if self._is_new:
            ttk.Button(controls, text="Save", command=self._save_and_close).grid(row=0, column=button_col, padx=4, sticky="e")
        else:
            ttk.Button(controls, text="Close", command=self._close).grid(row=0, column=button_col, padx=4, sticky="e")

        self._last_saved_payload = self._collect_payload()
        self._set_edit_mode(self._edit_var.get() == 1)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy if self._is_new else self._close)

    def _collect_payload(self) -> dict[str, object]:
        selected_label = self.collection_event_var.get().strip()
        payload: dict[str, object] = {
            "collection_event_id": self._choice_map.get(selected_label),
            "team_member_id": self._team_member_choice_map.get(self._team_member_var.get().strip()),
        }
        for field in self.EDITABLE_FIELDS:
            widget = self._inputs[field]
            if isinstance(widget, tk.Text):
                payload[field] = widget.get("1.0", "end").strip()
            else:
                payload[field] = widget.get().strip()
        return payload

    def _save_if_changed(self, force: bool = False) -> bool:
        payload = self._collect_payload()
        if not force and payload == self._last_saved_payload:
            return True
        should_close = self.on_save(payload)
        if should_close is False:
            return False
        self._last_saved_payload = payload
        if callable(self.on_saved):
            self.on_saved()
        return True

    def _sync_location_name_from_collection_event(self) -> None:
        widget = self._inputs.get("location_name")
        if not isinstance(widget, ttk.Entry):
            return
        selected_label = self.collection_event_var.get().strip()
        selected_ce_id = self._choice_map.get(selected_label)
        location_name = str(self._collection_event_locations.get(int(selected_ce_id), "")) if selected_ce_id is not None else ""
        widget.configure(state="normal")
        widget.delete(0, "end")
        widget.insert(0, location_name)
        widget.configure(state="readonly")
        self._clear_find_marker(clear_fields=True)
        self._refresh_collection_event_map(selected_ce_id)

    def _sync_team_member_choices_from_collection_event(self) -> None:
        if self._team_member_combo is None:
            return
        selected_label = self.collection_event_var.get().strip()
        selected_ce_id = self._choice_map.get(selected_label)
        team_choices = list(self._team_member_choices_by_event.get(int(selected_ce_id), [])) if selected_ce_id is not None else []
        if self._initial_team_member_id is not None and self._initial_team_member_id > 0:
            known_ids = {member_id for member_id, _ in team_choices}
            if self._initial_team_member_id not in known_ids:
                fallback_label = f"#{self._initial_team_member_id}"
                team_choices.append((self._initial_team_member_id, fallback_label))
        labels = [name for _, name in team_choices]
        self._team_member_choice_map = {name: member_id for member_id, name in team_choices}
        self._team_member_combo.configure(values=labels)
        if not labels:
            self._team_member_var.set("")
            return
        if self._initial_team_member_id is not None:
            for member_id, name in team_choices:
                if member_id == self._initial_team_member_id:
                    self._team_member_var.set(name)
                    return
        current = self._team_member_var.get().strip()
        if current in self._team_member_choice_map:
            return
        self._team_member_var.set(labels[0])

    def _on_collection_event_changed(self, _event=None) -> None:
        self._sync_location_name_from_collection_event()
        self._sync_team_member_choices_from_collection_event()

    def _close(self) -> None:
        if not self._save_if_changed():
            return
        self.destroy()

    def _save_and_close(self) -> None:
        if not self._save_if_changed(force=True):
            return
        self.destroy()

    def _set_edit_mode(self, editable: bool) -> None:
        self.collection_event_combo.configure(state="readonly" if editable else "disabled")
        if self._team_member_combo is not None:
            has_choices = bool(self._team_member_combo.cget("values"))
            self._team_member_combo.configure(state="readonly" if editable and has_choices else "disabled")
        for field in self.READONLY_FIELDS:
            widget = self._inputs.get(field)
            if widget is None:
                continue
            widget.configure(state="readonly")
        for field in self.EDITABLE_FIELDS:
            widget = self._inputs[field]
            if isinstance(widget, tk.Text):
                widget.configure(state="normal" if editable else "disabled")
            else:
                widget.configure(state="normal" if editable else "readonly")
            picker = self._picker_buttons.get(field)
            if picker is not None:
                picker.configure(state="normal" if editable else "disabled")

    def _on_edit_radio_click(self, _event) -> str:
        currently_on = self._edit_var.get() == 1
        if currently_on:
            if not self._save_if_changed():
                return "break"
            self._edit_var.set(0)
            self._set_edit_mode(False)
            return "break"
        self._edit_var.set(1)
        self._set_edit_mode(True)
        return "break"

    def _open_field_observations(self) -> None:
        if not callable(self._on_open_field_observations) or not isinstance(self._find_id, int):
            return
        if not self._save_if_changed():
            return
        self._on_open_field_observations(self._find_id)

    def _open_taxonomy(self) -> None:
        if not callable(self._on_open_taxonomy) or not isinstance(self._find_id, int):
            return
        if not self._save_if_changed():
            return
        self._on_open_taxonomy(self._find_id)

    def _open_date_picker(self) -> None:
        entry = self._inputs.get("find_date")
        if not isinstance(entry, ttk.Entry):
            return
        value = entry.get().strip()
        now = datetime.now()
        try:
            selected = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            selected = now
        picker = tk.Toplevel(self)
        picker.title("Select Date")
        picker.transient(self)
        picker.grab_set()
        ttk.Label(picker, text="Year").grid(row=0, column=0, padx=4, pady=(8, 4))
        ttk.Label(picker, text="Month").grid(row=0, column=1, padx=4, pady=(8, 4))
        ttk.Label(picker, text="Day").grid(row=0, column=2, padx=4, pady=(8, 4))
        year_var = tk.StringVar(value=str(selected.year))
        month_var = tk.StringVar(value=f"{selected.month:02d}")
        day_var = tk.StringVar(value=f"{selected.day:02d}")
        ttk.Spinbox(picker, from_=1900, to=2200, width=6, textvariable=year_var).grid(row=1, column=0, padx=4, pady=4)
        ttk.Spinbox(picker, from_=1, to=12, width=4, format="%02.0f", textvariable=month_var).grid(
            row=1, column=1, padx=4, pady=4
        )
        ttk.Spinbox(picker, from_=1, to=31, width=4, format="%02.0f", textvariable=day_var).grid(
            row=1, column=2, padx=4, pady=4
        )

        def _apply() -> None:
            try:
                picked = datetime(int(year_var.get()), int(month_var.get()), int(day_var.get()))
            except ValueError:
                messagebox.showerror("Invalid Date", "Please select a valid date (YYYY-MM-DD).")
                return
            entry.delete(0, "end")
            entry.insert(0, picked.strftime("%Y-%m-%d"))
            picker.destroy()

        buttons = ttk.Frame(picker, padding=(4, 8))
        buttons.grid(row=2, column=0, columnspan=3, sticky="e")
        ttk.Button(buttons, text="OK", command=_apply).pack(side="right", padx=(4, 0))
        ttk.Button(buttons, text="Cancel", command=picker.destroy).pack(side="right")

    def _open_time_picker(self) -> None:
        entry = self._inputs.get("find_time")
        if not isinstance(entry, ttk.Entry):
            return
        value = entry.get().strip()
        now = datetime.now()
        try:
            selected = datetime.strptime(value, "%H:%M")
        except ValueError:
            selected = now
        picker = tk.Toplevel(self)
        picker.title("Select Time")
        picker.transient(self)
        picker.grab_set()
        ttk.Label(picker, text="Hour").grid(row=0, column=0, padx=4, pady=(8, 4))
        ttk.Label(picker, text="Minute").grid(row=0, column=1, padx=4, pady=(8, 4))
        hour_var = tk.StringVar(value=f"{selected.hour:02d}")
        minute_var = tk.StringVar(value=f"{selected.minute:02d}")
        ttk.Spinbox(picker, from_=0, to=23, width=4, format="%02.0f", textvariable=hour_var).grid(
            row=1, column=0, padx=4, pady=4
        )
        ttk.Spinbox(picker, from_=0, to=59, width=4, format="%02.0f", textvariable=minute_var).grid(
            row=1, column=1, padx=4, pady=4
        )

        def _apply() -> None:
            try:
                hour = int(hour_var.get())
                minute = int(minute_var.get())
                if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid Time", "Please select a valid time (HH:MM).")
                return
            entry.delete(0, "end")
            entry.insert(0, f"{hour:02d}:{minute:02d}")
            picker.destroy()

        buttons = ttk.Frame(picker, padding=(4, 8))
        buttons.grid(row=2, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="OK", command=_apply).pack(side="right", padx=(4, 0))
        ttk.Button(buttons, text="Cancel", command=picker.destroy).pack(side="right")

    def _build_collection_event_map(self, host: ttk.Frame) -> None:
        if tkintermapview is None:
            ttk.Label(host, text="Map preview unavailable. Install tkintermapview.", justify="left").grid(
                row=0, column=0, sticky="nw"
            )
            return
        selected_map_type, saved_zoom = LocationFormDialog._load_map_preferences()
        if selected_map_type not in LocationFormDialog.MAP_TILE_TYPES:
            selected_map_type = LocationFormDialog.DEFAULT_MAP_TYPE
        zoom_min = 5
        zoom_max = int(LocationFormDialog.MAP_TILE_TYPES[selected_map_type][2])
        zoom = min(max(int(saved_zoom), zoom_min), zoom_max)
        if selected_map_type == "OpenTopoMap" and zoom < 10:
            zoom = 10
        self._map_default_zoom = zoom
        self._prepare_collection_event_map_metadata()
        map_widget = tkintermapview.TkinterMapView(host, corner_radius=0)
        map_widget.grid(row=0, column=0, sticky="nsew")
        map_widget.set_tile_server(*LocationFormDialog.MAP_TILE_TYPES[selected_map_type])
        initial_center = self._initial_map_center()
        map_widget.set_position(initial_center[0], initial_center[1])
        map_widget.set_zoom(zoom)
        map_widget.canvas.delete("button")
        LocationFormDialog._start_map_loading_indicator(
            self,
            map_widget,
            selected_map_type,
            initial_center[0],
            initial_center[1],
            zoom,
        )
        self._map_widget = map_widget
        map_widget.add_left_click_map_command(self._on_map_left_click)
        selected_label = self.collection_event_var.get().strip()
        self._refresh_collection_event_map(self._choice_map.get(selected_label))

    def _prepare_collection_event_map_metadata(self) -> None:
        self._map_center_by_event_id.clear()
        self._boundary_by_event_id.clear()
        for event_id, payload in self._collection_event_map_data.items():
            boundary = self._parse_boundary_geojson(str(payload.get("boundary_geojson") or ""))
            if boundary:
                self._boundary_by_event_id[event_id] = boundary
                self._map_center_by_event_id[event_id] = self._boundary_center(boundary)
                continue
            lat = self._to_float(payload.get("latitude"))
            lon = self._to_float(payload.get("longitude"))
            if lat is not None and lon is not None:
                self._map_center_by_event_id[event_id] = (lat, lon)

    def _initial_map_center(self) -> tuple[float, float]:
        selected_label = self.collection_event_var.get().strip()
        selected_id = self._choice_map.get(selected_label)
        if selected_id is not None and selected_id in self._map_center_by_event_id:
            return self._map_center_by_event_id[selected_id]
        if self._map_center_by_event_id:
            return next(iter(self._map_center_by_event_id.values()))
        return (-22.0, 133.0)

    def _refresh_collection_event_map(self, selected_ce_id: int | None) -> None:
        map_widget = self._map_widget
        if map_widget is None:
            return
        try:
            map_widget.delete_all_polygon()
        except Exception:
            if self._map_polygon is not None:
                try:
                    self._map_polygon.delete()
                except Exception:
                    pass
        self._map_polygon = None
        if selected_ce_id is None:
            return
        center = self._map_center_by_event_id.get(selected_ce_id)
        if center is not None:
            try:
                map_widget.set_position(center[0], center[1])
                map_widget.set_zoom(self._map_default_zoom)
            except Exception:
                pass
        boundary = self._boundary_by_event_id.get(selected_ce_id, [])
        if len(boundary) >= 3:
            try:
                self._map_polygon = map_widget.set_polygon(
                    boundary,
                    outline_color=LocationFormDialog.GOLD_LIGHT,
                    fill_color=None,
                    border_width=2,
                )
            except Exception:
                self._map_polygon = None

    def _on_map_left_click(self, coords: tuple[float, float] | list[float]) -> None:
        if not self._is_new or self._edit_var.get() != 1:
            return
        lat: float | None = None
        lon: float | None = None
        if isinstance(coords, (tuple, list)) and len(coords) >= 2:
            try:
                lat = float(coords[0])
                lon = float(coords[1])
            except (TypeError, ValueError):
                lat = None
                lon = None
        if lat is None or lon is None:
            return
        self._set_find_marker(lat, lon, update_fields=True)

    def _set_find_marker(self, lat: float, lon: float, update_fields: bool) -> None:
        map_widget = self._map_widget
        if map_widget is None:
            return
        self._clear_find_marker(clear_fields=False)
        try:
            self._find_marker = map_widget.set_marker(lat, lon, text=None)
        except Exception:
            self._find_marker = None
            return
        if update_fields:
            lat_widget = self._inputs.get("latitude")
            lon_widget = self._inputs.get("longitude")
            if isinstance(lat_widget, ttk.Entry):
                lat_widget.delete(0, "end")
                lat_widget.insert(0, f"{lat:.6f}")
            if isinstance(lon_widget, ttk.Entry):
                lon_widget.delete(0, "end")
                lon_widget.insert(0, f"{lon:.6f}")

    def _clear_find_marker(self, clear_fields: bool) -> None:
        if self._find_marker is not None:
            try:
                self._find_marker.delete()
            except Exception:
                pass
        self._find_marker = None
        if not clear_fields:
            return
        lat_widget = self._inputs.get("latitude")
        lon_widget = self._inputs.get("longitude")
        if isinstance(lat_widget, ttk.Entry):
            lat_widget.delete(0, "end")
        if isinstance(lon_widget, ttk.Entry):
            lon_widget.delete(0, "end")

    @staticmethod
    def _to_float(value: object) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _boundary_center(points: list[tuple[float, float]]) -> tuple[float, float]:
        if not points:
            return (-22.0, 133.0)
        lat_sum = 0.0
        lon_sum = 0.0
        for lat, lon in points:
            lat_sum += lat
            lon_sum += lon
        size = float(len(points))
        return lat_sum / size, lon_sum / size

    @staticmethod
    def _parse_boundary_geojson(boundary_geojson: str) -> list[tuple[float, float]]:
        raw = str(boundary_geojson or "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if not isinstance(parsed, dict):
            return []
        geometry = parsed
        if parsed.get("type") == "Feature":
            geometry = parsed.get("geometry")
        if not isinstance(geometry, dict):
            return []
        if str(geometry.get("type")) != "Polygon":
            return []
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or not coordinates:
            return []
        outer_ring = coordinates[0]
        if not isinstance(outer_ring, list):
            return []
        points: list[tuple[float, float]] = []
        for point in outer_ring:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                lon = float(point[0])
                lat = float(point[1])
            except (TypeError, ValueError):
                continue
            points.append((lat, lon))
        if len(points) >= 2 and points[0] == points[-1]:
            points.pop()
        return points
