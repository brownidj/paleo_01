import sqlite3
import tkinter as tk
import tkinter.font as tkfont
import json
from collections.abc import Mapping
from pathlib import Path
from tkinter import messagebox, ttk

from repository import DEFAULT_DB_PATH
from repository.trip_repository import TripRepository
from ui.auto_hide_scrollbars import attach_auto_hiding_scrollbars
from ui.planning_tabs_controller import PlanningTabsController
from ui.trip_dialog_controller import TripDialogController
from ui.trip_navigation_coordinator import TripNavigationCoordinator


class PlanningPhaseWindow(tk.Tk):
    PALETTE = {
        "earth": {
            "dusty_ochre": "#D9B37A",
            "clay_blush": "#D9A8A1",
            "soft_ironstone": "#C98F7A",
        },
        "vegetation": {
            "eucalypt_sage": "#9DB8A7",
            "spinifex_mint": "#C7D8B6",
            "pale_wattle_green": "#AFC8A2",
        },
        "water_sky": {
            "creek_blue": "#A9C7CF",
        },
        "fossil_bone": {
            "fossil_sand": "#F5EEDF",
            "bone_white": "#FBF8F2",
            "chalk_beige": "#E9DFCF",
            "weathered_stone": "#C8BBAA",
        },
        "text": {
            "deep_gumleaf": "#4A5A52",
            "dust_bark": "#7A746B",
        },
        "status": {
            "muted_rust": "#B97A6A",
            "pale_wattle_green": "#AFC8A2",
        },
    }

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        super().__init__()
        self.title("Planning Phase")
        self.geometry("980x560")
        self._apply_palette()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._db_path = self._resolve_db_path(db_path)
        self._state_path = self._db_path.with_suffix(self._db_path.suffix + ".ui_state.json")
        self._last_selected_trip_id, self._last_selected_trip_name = self._load_last_selected_trip_state()
        self._suspend_trip_selection_persist = True
        self._trip_toast_shown_count = 0
        self._trip_toast_hide_after_id: str | None = None
        self._trip_toast_last_iid: str | None = None

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
            anchor = "center" if field in {"collection_events_count", "finds_count"} else "w"
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

    def _get_selected_trip_id(self) -> int | None:
        selected = self.trips_tree.selection()
        if selected:
            try:
                return int(selected[0])
            except (TypeError, ValueError):
                return None
        return self._last_selected_trip_id

    def _restore_trip_selection(self) -> None:
        children = tuple(self.trips_tree.get_children())
        if not children:
            self._last_selected_trip_id = None
            self._last_selected_trip_name = None
            self._save_last_selected_trip_state(None, None)
            return
        target_iid = None
        if self._last_selected_trip_id is not None:
            candidate = str(self._last_selected_trip_id)
            if candidate in children:
                target_iid = candidate
        if target_iid is None and self._last_selected_trip_name:
            for iid in children:
                values = self.trips_tree.item(iid, "values")
                trip_name = str(values[0]) if values else ""
                if trip_name == self._last_selected_trip_name:
                    target_iid = str(iid)
                    break
        if target_iid is None:
            target_iid = children[0]
        self.trips_tree.selection_set(target_iid)
        self.trips_tree.focus(target_iid)
        self.trips_tree.see(target_iid)
        self._maybe_show_trip_edit_toast()
        self._persist_trip_selection_from_iid(target_iid, force=True)
        self._suspend_trip_selection_persist = False

    def _on_trip_selected(self, _event) -> None:
        if self._suspend_trip_selection_persist:
            return
        selected = self.trips_tree.selection()
        if not selected:
            return
        self._maybe_show_trip_edit_toast()
        self._persist_trip_selection_from_iid(str(selected[0]))

    def _persist_trip_selection_from_iid(self, iid: str, force: bool = False) -> None:
        if self._suspend_trip_selection_persist and not force:
            return
        try:
            trip_id = int(iid)
        except (TypeError, ValueError):
            return
        values = self.trips_tree.item(iid, "values")
        trip_name = str(values[0]) if values else None
        self._last_selected_trip_id = trip_id
        self._last_selected_trip_name = trip_name
        self._save_last_selected_trip_state(trip_id, trip_name)

    def _load_last_selected_trip_state(self) -> tuple[int | None, str | None]:
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, None
        raw = data.get("last_selected_trip_id")
        trip_name_raw = data.get("last_selected_trip_name")
        trip_name = str(trip_name_raw) if isinstance(trip_name_raw, str) and trip_name_raw.strip() else None
        try:
            trip_id = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            trip_id = None
        return trip_id, trip_name

    def _save_last_selected_trip_state(self, trip_id: int | None, trip_name: str | None) -> None:
        payload = {"last_selected_trip_id": trip_id, "last_selected_trip_name": trip_name}
        try:
            self._state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            # Non-fatal: selection persistence should not block UI behavior.
            return

    def _on_close(self) -> None:
        selected = self.trips_tree.selection()
        if selected:
            self._persist_trip_selection_from_iid(str(selected[0]), force=True)
        self.destroy()

    def _maybe_show_trip_edit_toast(self, duration_ms: int = 1400) -> None:
        trips_tree = self.__dict__.get("trips_tree")
        if trips_tree is None:
            return
        selected = trips_tree.selection()
        if not selected:
            return
        selected_iid = str(selected[0])
        last_iid = self.__dict__.get("_trip_toast_last_iid")
        if isinstance(last_iid, str) and last_iid == selected_iid:
            return
        shown_count = int(self.__dict__.get("_trip_toast_shown_count", 0))
        if shown_count >= 2:
            return
        toast = self.__dict__.get("_trip_toast")
        if toast is None:
            return
        self._trip_toast_shown_count = shown_count + 1
        self._trip_toast_last_iid = selected_iid
        toast.configure(text="Double-click to edit.")
        toast.place(in_=trips_tree, relx=0.5, rely=1.0, anchor="s", y=-18)
        hide_after_id = self.__dict__.get("_trip_toast_hide_after_id")
        if hide_after_id is not None:
            self.after_cancel(hide_after_id)
        self._trip_toast_hide_after_id = self.after(duration_ms, self._hide_trip_toast)

    def _hide_trip_toast(self) -> None:
        toast = self.__dict__.get("_trip_toast")
        if toast is None:
            return
        toast.place_forget()
        self._trip_toast_hide_after_id = None

    @staticmethod
    def _resolve_db_path(db_path: str) -> Path:
        path = Path(db_path)
        if path.is_absolute():
            return path.resolve()
        # Anchor relative DB paths to project root, not process CWD.
        project_root = Path(__file__).resolve().parent.parent
        return (project_root / path).resolve()

    def _apply_palette(self) -> None:
        p = self.PALETTE
        bg = p["fossil_bone"]["fossil_sand"]
        surface = p["fossil_bone"]["bone_white"]
        surface_alt = p["fossil_bone"]["chalk_beige"]
        border = p["fossil_bone"]["weathered_stone"]
        text_primary = p["text"]["deep_gumleaf"]
        text_secondary = p["text"]["dust_bark"]
        primary = p["vegetation"]["eucalypt_sage"]
        secondary = p["earth"]["dusty_ochre"]
        selected = p["earth"]["clay_blush"]

        self.configure(bg=bg)
        self.option_add("*Background", bg)
        self.option_add("*Foreground", text_primary)
        self.option_add("*Listbox.background", surface)
        self.option_add("*Listbox.foreground", text_primary)
        self.option_add("*Listbox.selectBackground", secondary)
        self.option_add("*Listbox.selectForeground", text_primary)
        self.option_add("*Text.background", surface)
        self.option_add("*Text.foreground", text_primary)
        self.option_add("*Text.insertBackground", text_primary)

        style = ttk.Style(self)
        self._tab_font_normal = tkfont.Font(self, family="Helvetica", size=10, weight="normal")
        self._tab_font_selected = tkfont.Font(self, family="Helvetica", size=11, weight="bold")
        available_themes = set(style.theme_names())
        if "clam" in available_themes:
            style.theme_use("clam")

        style.configure(".", background=bg, foreground=text_primary)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=text_primary)

        style.configure(
            "TButton",
            background=primary,
            foreground=text_primary,
            borderwidth=1,
            padding=(10, 5),
        )
        style.map(
            "TButton",
            background=[("active", secondary), ("pressed", p["earth"]["clay_blush"])],
            foreground=[("disabled", text_secondary)],
        )

        style.configure(
            "TNotebook",
            background=bg,
            borderwidth=0,
            tabmargins=(6, 6, 6, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background=surface_alt,
            foreground=text_secondary,
            padding=(14, 6),
            font=self._tab_font_normal,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", primary), ("active", secondary)],
            foreground=[("selected", text_primary), ("active", text_primary)],
            padding=[("selected", (14, 10)), ("active", (14, 8))],
            font=[("selected", self._tab_font_selected), ("!selected", self._tab_font_normal)],
        )

        style.configure(
            "Treeview",
            background=surface,
            fieldbackground=surface,
            foreground=text_primary,
            rowheight=24,
        )
        style.map(
            "Treeview",
            background=[("selected", selected)],
            foreground=[("selected", text_primary)],
        )
        style.configure(
            "Treeview.Heading",
            background=surface_alt,
            foreground=text_primary,
            relief="flat",
        )
        style.configure(
            "Trips.Treeview",
            background=surface,
            fieldbackground=surface,
            foreground=text_primary,
            rowheight=24,
        )
        style.map(
            "Trips.Treeview",
            background=[("selected", selected)],
            foreground=[("selected", text_primary)],
        )
        style.configure(
            "Trips.Treeview.Heading",
            background=surface_alt,
            foreground=text_primary,
            relief="flat",
            font=("Helvetica", 10, "bold"),
        )

        style.configure(
            "TEntry",
            fieldbackground=surface,
            foreground=text_primary,
        )
        style.map("TEntry", fieldbackground=[("readonly", surface_alt)])
        style.configure(
            "TCheckbutton",
            background=bg,
            foreground=text_primary,
        )
