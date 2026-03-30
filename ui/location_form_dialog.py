import json
import tkinter as tk
import webbrowser
import threading
from io import BytesIO
from pathlib import Path
from tkinter import messagebox, ttk

import requests
from PIL import Image, ImageStat, ImageTk

try:
    import tkintermapview
except ModuleNotFoundError:
    tkintermapview = None


class LocationFormDialog(tk.Toplevel):
    DEFAULT_MAP_TYPE = "OpenStreetMap"
    DEFAULT_MAP_ZOOM = 8
    MAP_PREF_PATH = Path(__file__).resolve().parents[1] / "data" / "ui_map_preferences.json"
    MAP_TILE_TYPES: dict[str, tuple[str, int, int]] = {
        "OpenStreetMap": ("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", 256, 19),
        "Geoscience Australia": (
            "https://services.ga.gov.au/gis/rest/services/GA_Surface_Geology/MapServer/tile/{z}/{y}/{x}",
            256,
            11,
        ),
        "Macrostrat Geology": ("https://tiles.macrostrat.org/carto/{z}/{x}/{y}.png", 256, 20),
        "OpenTopoMap": ("https://a.tile.opentopomap.org/{z}/{x}/{y}.png", 256, 17),
        "Google Hybrid": ("https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}", 256, 22),
    }

    FIELDS = [
        "name",
        "latitude",
        "longitude",
        "altitude_value",
        "altitude_unit",
        "country_code",
        "state",
        "lga",
        "basin",
        "proterozoic_province",
        "orogen",
        "geogscale",
        "geography_comments",
    ]

    NONE_OPTION = "(None)"
    NEW_GEOLOGY_OPTION = "New geology"
    _ga_legend_cache: list[tuple[str, str, str, str]] | None = None

    def __init__(
        self,
        parent: tk.Widget,
        initial_data: dict[str, object] | None,
        on_save,
        geology_choices: list[tuple[int, str]] | None = None,
        is_new: bool = False,
        on_edit_geology=None,
    ):
        super().__init__(parent)
        self.title("Location")
        self.on_save = on_save
        self.resizable(False, False)
        self.entries: dict[str, ttk.Entry] = {}
        self._is_new = is_new
        self._on_edit_geology = on_edit_geology
        self._geology_label_to_id: dict[str, int] = {}
        self._geology_id: int | None = int(initial_data.get("geology_id")) if initial_data and initial_data.get("geology_id") else None
        self._map_icon_image: ImageTk.PhotoImage | None = None

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)
        style = ttk.Style(frame)
        style.configure("LocationMapIcon.TButton", font=("Helvetica", 15), padding=0)

        map_compact_fields = {"latitude", "longitude"}
        for i, field in enumerate(self.FIELDS):
            ttk.Label(frame, text=field).grid(row=i, column=0, sticky="e", padx=4, pady=4)
            entry_width = 31 if field in map_compact_fields else 42
            entry = ttk.Entry(frame, width=entry_width)
            entry.grid(row=i, column=1, sticky="w", padx=4, pady=4)
            if initial_data and initial_data.get(field) is not None:
                entry.insert(0, str(initial_data.get(field, "")))
            self.entries[field] = entry

        latitude_row = self.FIELDS.index("latitude")
        self.map_button = ttk.Button(
            frame,
            text="🗺",
            width=2,
            style="LocationMapIcon.TButton",
            state="disabled",
        )
        self.map_button.grid(
            row=latitude_row,
            column=1,
            rowspan=2,
            sticky="e",
            padx=4,
            pady=0,
        )
        self._configure_map_button_icon()
        self._bind_map_coordinate_events()
        self._update_map_button_state()

        geology_row = len(self.FIELDS)
        ttk.Label(frame, text="geology").grid(row=geology_row, column=0, sticky="e", padx=4, pady=4)
        self.geology_var = tk.StringVar(value=self.NONE_OPTION)
        self.geology_combo: ttk.Combobox | None = None
        self.geology_display: ttk.Entry | None = None
        self.geology_edit_button: ttk.Button | None = None
        if self._is_new:
            options = [self.NONE_OPTION]
            for geology_id, geology_label in geology_choices or []:
                label = str(geology_label).strip()
                if not label:
                    continue
                if label in self._geology_label_to_id:
                    label = f"{label} (#{geology_id})"
                self._geology_label_to_id[label] = int(geology_id)
                options.append(label)
            options.append(self.NEW_GEOLOGY_OPTION)
            self.geology_combo = ttk.Combobox(
                frame,
                textvariable=self.geology_var,
                values=options,
                state="readonly",
                width=40,
            )
            self.geology_combo.grid(row=geology_row, column=1, sticky="w", padx=4, pady=4)
            if self._geology_id is not None:
                for label, geology_id in self._geology_label_to_id.items():
                    if geology_id == self._geology_id:
                        self.geology_var.set(label)
                        break
                else:
                    self.geology_var.set(self.NONE_OPTION)
        else:
            geology_name = str(initial_data.get("geology_name") or "").strip() if initial_data else ""
            if not geology_name:
                geology_name = self.NONE_OPTION
            self.geology_display = ttk.Entry(frame, width=42)
            self.geology_display.grid(row=geology_row, column=1, sticky="w", padx=4, pady=4)
            self.geology_display.insert(0, geology_name)
            self.geology_display.configure(state="readonly")
            self.geology_edit_button = ttk.Button(
                frame,
                text="✎",
                width=2,
                command=self._edit_geology,
                state="normal" if callable(self._on_edit_geology) and self._geology_id is not None else "disabled",
            )
            self.geology_edit_button.grid(row=geology_row, column=2, sticky="w", padx=(0, 4), pady=4)

        btns = ttk.Frame(frame)
        btns.grid(row=geology_row + 1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)

        self.transient(parent)
        self.grab_set()

    def _configure_map_button_icon(self) -> None:
        icon_path = Path(__file__).resolve().parents[1] / "assets" / "images" / "icons" / "map-icon-1.png"
        if not icon_path.exists():
            return
        latitude_entry = self.entries.get("latitude")
        if latitude_entry is None:
            return
        self.update_idletasks()
        side = max(int(latitude_entry.winfo_reqheight()) * 2 + 8, 24)
        try:
            image = Image.open(icon_path).resize((side, side), Image.Resampling.LANCZOS)
            self._map_icon_image = ImageTk.PhotoImage(image)
        except Exception:
            return
        self.map_button.configure(image=self._map_icon_image, text="")

    def _bind_map_coordinate_events(self) -> None:
        for field in ("latitude", "longitude"):
            entry = self.entries.get(field)
            if entry is None:
                continue
            entry.bind("<KeyRelease>", lambda _event: self._update_map_button_state(), add="+")
            entry.bind("<FocusOut>", lambda _event: self._update_map_button_state(), add="+")
        self.map_button.configure(command=self._open_map_modal)

    def _parse_lat_lon(self) -> tuple[float, float] | None:
        lat_text = str(self.entries.get("latitude").get() if self.entries.get("latitude") else "").strip()
        lon_text = str(self.entries.get("longitude").get() if self.entries.get("longitude") else "").strip()
        if not lat_text or not lon_text:
            return None
        try:
            lat = float(lat_text)
            lon = float(lon_text)
        except ValueError:
            return None
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return None
        return lat, lon

    def _update_map_button_state(self) -> None:
        self.map_button.configure(state="normal")

    def _open_map_modal(self) -> None:
        coords = self._parse_lat_lon()
        if coords is None:
            messagebox.showinfo(
                "Map Preview",
                "Latitude and Longitude unknown. Edit this location to add that information.",
            )
            return
        if tkintermapview is None:
            messagebox.showerror(
                "Map Preview",
                "Interactive map dependency is missing. Install with:\n\n"
                ".venv/bin/pip install tkintermapview",
            )
            return
        lat, lon = coords

        modal = tk.Toplevel(self)
        modal.title("Map Preview")
        modal.transient(self)
        modal.grab_set()
        modal.geometry("1140x840")
        modal.minsize(780, 630)

        selected_map_type, saved_zoom_level = self._load_map_preferences()
        if selected_map_type not in self.MAP_TILE_TYPES:
            selected_map_type = self.DEFAULT_MAP_TYPE

        zoom_min = 5
        zoom_max = self.MAP_TILE_TYPES[selected_map_type][2]
        initial_zoom = min(max(saved_zoom_level, zoom_min), zoom_max)
        if selected_map_type == "OpenTopoMap" and initial_zoom < 10:
            initial_zoom = 10

        map_widget = tkintermapview.TkinterMapView(modal, corner_radius=0)
        map_widget.pack(fill="both", expand=True)
        map_widget.set_tile_server(*self.MAP_TILE_TYPES[selected_map_type])
        map_widget.set_position(lat, lon)
        map_widget.set_zoom(initial_zoom)
        map_widget.canvas.delete("button")
        location_name = str(self.entries.get("name").get() if self.entries.get("name") else "").strip()
        marker_text = f"{location_name}\n{lat:.6f}, {lon:.6f}" if location_name else f"{lat:.6f}, {lon:.6f}"
        marker = map_widget.set_marker(
            lat,
            lon,
            text=marker_text,
            marker_color_circle="#FF2D2D",
            marker_color_outside="#FF0000",
        )
        self._apply_half_size_marker(map_widget, marker)
        marker_text_bg_id: int | None = None

        def _sync_marker_text_background() -> None:
            nonlocal marker_text_bg_id
            if not modal.winfo_exists():
                return
            text_id = getattr(marker, "canvas_text", None)
            if text_id:
                bbox = map_widget.canvas.bbox(text_id)
                if bbox:
                    x1, y1, x2, y2 = bbox
                    pad = 4  # >= 3 px requested
                    rect_coords = (x1 - pad, y1 - pad, x2 + pad, y2 + pad)
                    if marker_text_bg_id is None:
                        marker_text_bg_id = map_widget.canvas.create_rectangle(
                            *rect_coords,
                            fill="#F7FAFD",
                            outline="#DCE8F1",
                            width=1,
                            tags=("marker", "marker_text_bg"),
                        )
                    else:
                        map_widget.canvas.coords(marker_text_bg_id, *rect_coords)
                    map_widget.canvas.tag_lower(marker_text_bg_id, text_id)
            modal.after(100, _sync_marker_text_background)

        # Keep the marker centered whenever user zooms in.
        def _center_marker() -> None:
            map_widget.set_position(lat, lon)

        zoom_level_var = tk.IntVar(value=int(round(float(map_widget.zoom))))

        def _mouse_zoom_and_center(event) -> None:
            previous_zoom = float(map_widget.zoom)
            map_widget.mouse_zoom(event)
            if float(map_widget.zoom) > previous_zoom:
                _center_marker()
            _sync_zoom_controls()

        map_widget.canvas.bind("<MouseWheel>", _mouse_zoom_and_center)
        map_widget.canvas.bind("<Button-4>", _mouse_zoom_and_center)
        map_widget.canvas.bind("<Button-5>", _mouse_zoom_and_center)
        map_widget.canvas.bind("<ButtonRelease-1>", lambda _event: _schedule_macrostrat_data_check(), add="+")
        _sync_marker_text_background()

        controls = ttk.Frame(modal, padding=(8, 8, 8, 8))
        controls.pack(fill="x")
        ttk.Label(controls, text="Map type").pack(side="left")
        map_type_var = tk.StringVar(value=selected_map_type)
        map_type_combo = ttk.Combobox(
            controls,
            textvariable=map_type_var,
            values=list(self.MAP_TILE_TYPES.keys()),
            state="readonly",
            width=22,
        )
        map_type_combo.pack(side="left", padx=(8, 0))
        legend_button = ttk.Button(
            controls,
            text="Legend",
            command=self._show_ga_legend,
        )

        zoom_overlay = ttk.Frame(modal, padding=(6, 4, 6, 4))
        zoom_overlay.place(relx=1.0, y=10, x=-10, anchor="ne")
        zoom_min_label = ttk.Label(zoom_overlay, text=str(zoom_min), width=2, anchor="e")
        zoom_min_label.pack(side="left", padx=(0, 2))
        zoom_scale = tk.Scale(
            zoom_overlay,
            from_=zoom_min,
            to=zoom_max,
            orient=tk.HORIZONTAL,
            length=180,
            resolution=1,
            showvalue=0,
            highlightthickness=0,
            bd=0,
            sliderlength=2,
            width=8,
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
        syncing_zoom_ui = False
        macrostrat_check_state: dict[str, object] = {
            "job_id": 0,
            "cache": {},
            "last_warning_key": None,
        }

        def _set_zoom_from_control(raw_value: str) -> None:
            nonlocal syncing_zoom_ui
            if syncing_zoom_ui:
                return
            target_zoom = int(round(float(raw_value)))
            previous_zoom = float(map_widget.zoom)
            map_widget.set_zoom(target_zoom)
            if target_zoom > previous_zoom:
                _center_marker()
            _sync_zoom_controls()

        def _sync_zoom_controls() -> None:
            nonlocal syncing_zoom_ui
            syncing_zoom_ui = True
            current_zoom = int(round(float(map_widget.zoom)))
            if current_zoom < zoom_min:
                current_zoom = zoom_min
            if current_zoom > zoom_max:
                current_zoom = zoom_max
            zoom_level_var.set(current_zoom)
            zoom_scale.set(current_zoom)
            zoom_max_label.configure(text=str(zoom_max))

            # Superimpose current zoom directly over the slider thumb area.
            zoom_overlay.update_idletasks()
            scale_x = zoom_scale.winfo_x()
            scale_y = zoom_scale.winfo_y()
            scale_w = max(zoom_scale.winfo_width(), 1)
            frac = (current_zoom - zoom_min) / max((zoom_max - zoom_min), 1)
            thumb_x = int(scale_x + frac * scale_w)
            thumb_y = scale_y + max(zoom_scale.winfo_height() // 2 - 8, 0)
            zoom_value_overlay.configure(text=str(current_zoom))
            zoom_value_overlay.place(x=thumb_x, y=thumb_y, anchor="center")
            syncing_zoom_ui = False
            self._save_map_preferences(map_type_var.get(), current_zoom)
            _schedule_macrostrat_data_check()

        def _schedule_macrostrat_data_check() -> None:
            if map_type_var.get() != "Macrostrat Geology":
                return
            current_zoom = int(round(float(map_widget.zoom)))
            center_lat, center_lon = map_widget.get_position()
            x_tile, y_tile = self._lat_lon_to_xyz(center_lat, center_lon, current_zoom)
            tile_key = (current_zoom, x_tile, y_tile)
            cache = macrostrat_check_state["cache"]
            if tile_key in cache:
                has_data = cache[tile_key]
                if has_data is False and macrostrat_check_state["last_warning_key"] != tile_key:
                    macrostrat_check_state["last_warning_key"] = tile_key
                    messagebox.showwarning(
                        "Macrostrat Geology",
                        "No data available at that zoom level for the current area.",
                    )
                return
            macrostrat_check_state["job_id"] = int(macrostrat_check_state["job_id"]) + 1
            current_job_id = int(macrostrat_check_state["job_id"])

            def _worker() -> None:
                has_data = self._macrostrat_tile_has_data(current_zoom, x_tile, y_tile)
                cache[tile_key] = has_data

                def _apply_result() -> None:
                    if not modal.winfo_exists():
                        return
                    if map_type_var.get() != "Macrostrat Geology":
                        return
                    if int(macrostrat_check_state["job_id"]) != current_job_id:
                        return
                    if has_data is False and macrostrat_check_state["last_warning_key"] != tile_key:
                        macrostrat_check_state["last_warning_key"] = tile_key
                        messagebox.showwarning(
                            "Macrostrat Geology",
                            "No data available at that zoom level for the current area.",
                        )

                modal.after(0, _apply_result)

            threading.Thread(target=_worker, daemon=True).start()

        zoom_scale.configure(command=_set_zoom_from_control)
        _sync_zoom_controls()

        def _update_legend_button_visibility() -> None:
            selected_map = map_type_var.get()
            if selected_map == "Geoscience Australia":
                legend_button.configure(text="Legend", command=self._show_ga_legend)
                if legend_button.winfo_manager() != "pack":
                    legend_button.pack(side="right")
            elif selected_map == "Macrostrat Geology":
                legend_button.configure(text="Macrostrat legend", command=self._show_macrostrat_legend)
                if legend_button.winfo_manager() != "pack":
                    legend_button.pack(side="right")
            elif legend_button.winfo_manager():
                legend_button.pack_forget()

        def _switch_map_type(_event=None) -> None:
            nonlocal marker, marker_text_bg_id, zoom_max
            selection = map_type_var.get()
            tile_settings = self.MAP_TILE_TYPES.get(selection)
            if not tile_settings:
                return
            _update_legend_button_visibility()
            current_zoom = int(self._load_zoom_for_map_type(selection))
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
            marker.delete()
            if marker_text_bg_id is not None:
                map_widget.canvas.delete(marker_text_bg_id)
                marker_text_bg_id = None
            marker = map_widget.set_marker(
                lat,
                lon,
                text=marker_text,
                marker_color_circle="#FF2D2D",
                marker_color_outside="#FF0000",
            )
            self._apply_half_size_marker(map_widget, marker)
            _sync_zoom_controls()

        _update_legend_button_visibility()
        map_type_combo.bind("<<ComboboxSelected>>", _switch_map_type)

    def _show_ga_legend(self) -> None:
        entries = self._get_ga_legend_entries()
        modal = tk.Toplevel(self)
        modal.title("Geoscience Australia Legend")
        modal.transient(self)
        modal.grab_set()
        modal.geometry("760x520")
        modal.minsize(620, 400)

        frame = ttk.Frame(modal, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=(
                "Lithostratigraphy symbols from GA Surface Geology.\n"
                "Format: symbol - unit name (lithology; age)."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        body = tk.Text(frame, wrap="word", font=("Menlo", 11))
        body.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=body.yview)
        scroll.pack(side="right", fill="y")
        body.configure(yscrollcommand=scroll.set)

        if not entries:
            body.insert("1.0", "Legend data unavailable.")
        else:
            for symbol, name, lithology, age in entries:
                body.insert("end", f"{symbol:<5}  {name}\n")
                body.insert("end", f"       {lithology}; {age}\n\n")
        body.configure(state="disabled")

    @classmethod
    def _get_ga_legend_entries(cls) -> list[tuple[str, str, str, str]]:
        if cls._ga_legend_cache is not None:
            return cls._ga_legend_cache
        url = "https://services.ga.gov.au/gis/rest/services/GA_Surface_Geology/MapServer/3/query"
        params = {
            "where": "1=1",
            "outFields": "plotsymbol,name,lithology,geolhist",
            "returnGeometry": "false",
            "returnDistinctValues": "true",
            "f": "json",
        }
        try:
            response = requests.get(url, params=params, timeout=12)
            payload = response.json()
        except Exception:
            cls._ga_legend_cache = []
            return cls._ga_legend_cache

        entries: dict[str, tuple[str, str, str, str]] = {}
        for feature in payload.get("features", []):
            attrs = feature.get("attributes") or {}
            symbol = str(attrs.get("plotsymbol") or "").strip()
            if not symbol:
                continue
            name = str(attrs.get("name") or "Unknown unit").strip()
            lithology = str(attrs.get("lithology") or "lithology n/a").strip()
            age = str(attrs.get("geolhist") or "age n/a").strip()
            if symbol not in entries:
                entries[symbol] = (symbol, name, lithology, age)
        cls._ga_legend_cache = [entries[key] for key in sorted(entries.keys())]
        return cls._ga_legend_cache

    @staticmethod
    def _show_macrostrat_legend() -> None:
        webbrowser.open("https://www.gaiagps.com/maps/source/macrostrat-bedrock/legend/")

    @classmethod
    def _load_map_preferences(cls) -> tuple[str, int]:
        try:
            payload = json.loads(cls.MAP_PREF_PATH.read_text(encoding="utf-8"))
            selected = str(payload.get("selected_map_type") or "").strip()
            if not selected:
                selected = cls.DEFAULT_MAP_TYPE
            zoom_levels_raw = payload.get("zoom_levels")
            zoom_levels: dict[str, int] = {}
            if isinstance(zoom_levels_raw, dict):
                for map_name, zoom_raw in zoom_levels_raw.items():
                    try:
                        zoom_levels[str(map_name)] = int(zoom_raw)
                    except (TypeError, ValueError):
                        continue
            legacy_zoom_raw = payload.get("zoom_level")
            if selected not in zoom_levels and legacy_zoom_raw is not None:
                try:
                    zoom_levels[selected] = int(legacy_zoom_raw)
                except (TypeError, ValueError):
                    pass
            zoom_level = int(zoom_levels.get(selected, cls.DEFAULT_MAP_ZOOM))
            return selected, zoom_level
        except Exception:
            pass
        return cls.DEFAULT_MAP_TYPE, cls.DEFAULT_MAP_ZOOM

    @classmethod
    def _save_map_preferences(cls, map_type: str, zoom_level: int) -> None:
        try:
            payload: dict[str, object] = {}
            if cls.MAP_PREF_PATH.exists():
                try:
                    payload = json.loads(cls.MAP_PREF_PATH.read_text(encoding="utf-8"))
                except Exception:
                    payload = {}
            zoom_levels_raw = payload.get("zoom_levels")
            zoom_levels: dict[str, int] = {}
            if isinstance(zoom_levels_raw, dict):
                for map_name, raw_zoom in zoom_levels_raw.items():
                    try:
                        zoom_levels[str(map_name)] = int(raw_zoom)
                    except (TypeError, ValueError):
                        continue
            zoom_levels[str(map_type)] = int(zoom_level)
            cls.MAP_PREF_PATH.parent.mkdir(parents=True, exist_ok=True)
            cls.MAP_PREF_PATH.write_text(
                json.dumps(
                    {
                        "selected_map_type": str(map_type),
                        "zoom_level": int(zoom_level),
                        "zoom_levels": zoom_levels,
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    @classmethod
    def _load_zoom_for_map_type(cls, map_type: str) -> int:
        selected_map_type, selected_zoom = cls._load_map_preferences()
        if selected_map_type == map_type:
            return selected_zoom
        try:
            payload = json.loads(cls.MAP_PREF_PATH.read_text(encoding="utf-8"))
            zoom_levels_raw = payload.get("zoom_levels")
            if isinstance(zoom_levels_raw, dict) and map_type in zoom_levels_raw:
                return int(zoom_levels_raw.get(map_type))
        except Exception:
            pass
        return cls.DEFAULT_MAP_ZOOM

    @staticmethod
    def _lat_lon_to_xyz(lat: float, lon: float, zoom: int) -> tuple[int, int]:
        import math

        n = 2**zoom
        x = int((lon + 180.0) / 360.0 * n)
        lat_rad = math.radians(lat)
        y = int((1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
        return x, y

    @staticmethod
    def _macrostrat_tile_has_data(zoom: int, x_tile: int, y_tile: int) -> bool | None:
        url = f"https://tiles.macrostrat.org/carto/{zoom}/{x_tile}/{y_tile}.png"
        try:
            response = requests.get(url, timeout=8)
        except requests.RequestException:
            return None
        if response.status_code != 200:
            return None
        content_type = str(response.headers.get("content-type", "")).lower()
        if "image" not in content_type:
            return None
        try:
            image = Image.open(BytesIO(response.content)).convert("RGB")
        except Exception:
            return None
        variance = sum(ImageStat.Stat(image).var) / 3.0
        # Macrostrat blank placeholders are nearly uniform and small.
        if variance <= 1.0 and len(response.content) <= 2600:
            return False
        return True

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


    def _save(self) -> None:
        payload: dict[str, object] = {field: entry.get().strip() for field, entry in self.entries.items()}
        if self._is_new:
            selected = self.geology_var.get().strip()
            if selected == self.NEW_GEOLOGY_OPTION:
                payload["new_geology"] = True
                payload["geology_id"] = None
            elif selected and selected != self.NONE_OPTION:
                payload["geology_id"] = self._geology_label_to_id.get(selected)
            else:
                payload["geology_id"] = None
        else:
            payload["geology_id"] = self._geology_id
        should_close = self.on_save(payload)
        if should_close is False:
            return
        self.destroy()

    def _edit_geology(self) -> None:
        if not callable(self._on_edit_geology) or self._geology_id is None:
            return
        self._on_edit_geology(self._geology_id)
