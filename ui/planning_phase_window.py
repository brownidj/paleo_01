import sqlite3
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from ui.collection_events_tab import CollectionEventsTab
from ui.finds_tab import FindsTab
from trip_repository import TripRepository
from ui.geology_tab import GeologyTab
from ui.location_tab import LocationTab
from ui.trip_form_dialog import TripFormDialog
from ui.users_tab import UsersTab


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

    def __init__(self, db_path: str = "paleo_trips_01.db"):
        super().__init__()
        self.title("Planning Phase")
        self.geometry("980x560")
        self._apply_palette()

        self.repo = TripRepository(db_path)
        self.open_edit_dialogs: dict[int, TripFormDialog] = {}
        self.hidden_trip_dialog: TripFormDialog | None = None
        self.hidden_trip_dialog_trip_id: int | None = None
        self.repo.ensure_trips_table()
        self.fields = self.repo.get_fields()
        self.list_fields = ["trip_name", "start_date", "end_date", "location"]
        self.edit_fields = ["trip_name", "start_date", "end_date", "location", "team", "notes"]
        self.list_fields = [f for f in self.list_fields if f in self.fields]
        self.edit_fields = [f for f in self.edit_fields if f in self.fields]

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)

        self.trips_tab = ttk.Frame(self.tabs)
        self.location_tab = LocationTab(self.tabs, self.repo)
        self.geology_tab = GeologyTab(self.tabs, self.repo)
        self.collection_events_tab = CollectionEventsTab(self.tabs, self.repo)
        self.finds_tab = FindsTab(self.tabs, self.repo)
        self.collection_plan_tab = ttk.Frame(self.tabs)
        self.users_tab = UsersTab(self.tabs, self.repo)
        self.tabs.add(self.trips_tab, text="Trips")
        self.tabs.add(self.location_tab, text="Location")
        self.tabs.add(self.geology_tab, text="Geology")
        self.tabs.add(self.collection_events_tab, text="Collection Events")
        self.tabs.add(self.finds_tab, text="Finds")
        self.tabs.add(self.collection_plan_tab, text="Collection Plan")
        self.tabs.add(self.users_tab, text="Team Members")
        self.tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._build_trips_tab()
        self._build_placeholder_tab(self.collection_plan_tab, "Collection Plan")
        self.load_trips()
        self.location_tab.load_locations()
        self.geology_tab.load_geology()
        self.collection_events_tab.load_collection_events()
        self.finds_tab.load_finds()
        self.users_tab.load_users()

    def _build_trips_tab(self) -> None:
        self.trips_tree = ttk.Treeview(
            self.trips_tab,
            columns=self.list_fields,
            show="headings",
        )
        for field in self.list_fields:
            self.trips_tree.heading(field, text=field)
            self.trips_tree.column(field, width=160, anchor="w")
        self.trips_tree.pack(fill="both", expand=True, padx=10, pady=6)
        buttons = ttk.Frame(self.trips_tab)
        buttons.pack(fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="New Trip", command=self.new_trip).pack(side="left", padx=4)
        ttk.Button(buttons, text="Edit Selected", command=self.edit_selected).pack(side="left", padx=4)
        ttk.Button(buttons, text="Refresh", command=self.load_trips).pack(side="left", padx=4)
        self.trips_tree.bind("<Double-1>", lambda _: self.edit_selected())

    @staticmethod
    def _build_placeholder_tab(tab: ttk.Frame, title: str) -> None:
        ttk.Label(tab, text="Scaffolded tab. Data form coming next.").pack(pady=(16, 0))

    def load_trips(self) -> None:
        for item in self.trips_tree.get_children():
            self.trips_tree.delete(item)
        try:
            records = self.repo.list_trips()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        for record in records:
            values = [record.get(field, "") for field in self.list_fields]
            self.trips_tree.insert("", "end", iid=str(record["id"]), values=values)

    def new_trip(self) -> None:
        def save_new(payload: dict[str, str]) -> bool:
            if not payload.get("trip_name"):
                messagebox.showerror("Validation Error", "trip_name is required.")
                return False
            normalized = self._normalize_payload(payload)
            try:
                self.repo.create_trip(normalized)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_trips()
            return True

        initial_data = {}
        TripFormDialog(
            self,
            self.edit_fields,
            initial_data,
            save_new,
            readonly_fields=set(),
            active_users=self.repo.list_active_users(),
            location_names=self.repo.list_location_names(),
            modal=True,
            trip_id=None,
            on_open_collection_events=None,
            on_open_finds=None,
            collection_events_count=0,
            finds_count=0,
        )

    def edit_selected(self) -> None:
        selected = self.trips_tree.selection()
        if not selected:
            messagebox.showinfo("Edit Trip", "Select a Trip first.")
            return
        trip_id = int(selected[0])
        try:
            trip = self.repo.get_trip(trip_id)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        if not trip:
            messagebox.showerror("Edit Trip", "Selected Trip no longer exists.")
            self.load_trips()
            return

        def save_edit(payload: dict[str, str]) -> bool:
            if not payload.get("trip_name"):
                messagebox.showerror("Validation Error", "trip_name is required.")
                return False
            normalized = self._normalize_payload(payload)
            try:
                self.repo.update_trip(trip_id, normalized)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_trips()
            return True

        def duplicate_trip(payload: dict[str, str]) -> bool:
            if not payload.get("trip_name"):
                messagebox.showerror("Validation Error", "trip_name is required.")
                return False
            payload["start_date"] = ""
            payload["end_date"] = ""
            normalized = self._normalize_payload(payload)
            try:
                new_trip_id = self.repo.create_trip(normalized)
                new_trip = self.repo.get_trip(new_trip_id)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Duplicate Error", str(e))
                return False
            self.load_trips()
            existing_dialog = self.open_edit_dialogs.get(trip_id)
            if existing_dialog and existing_dialog.winfo_exists():
                existing_dialog.destroy()
            if new_trip:
                self._open_edit_dialog(new_trip_id, new_trip)
            return True

        self._open_edit_dialog(trip_id, trip, save_edit, duplicate_trip)

    def _open_edit_dialog(
        self,
        trip_id: int,
        trip: dict[str, str],
        save_edit=None,
        duplicate_trip=None,
    ) -> None:
        existing = self.open_edit_dialogs.get(trip_id)
        if existing and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        if len(self._active_edit_dialogs()) >= 2:
            messagebox.showinfo("Trip Comparison", "You can open up to 2 Trip edit windows at a time.")
            return

        def _default_save(payload: dict[str, str]) -> bool:
            if not payload.get("trip_name"):
                messagebox.showerror("Validation Error", "trip_name is required.")
                return False
            normalized = self._normalize_payload(payload)
            try:
                self.repo.update_trip(trip_id, normalized)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_trips()
            return True

        dialog = TripFormDialog(
            self,
            self.edit_fields,
            trip,
            save_edit or _default_save,
            on_duplicate=duplicate_trip,
            readonly_fields=set(),
            active_users=self.repo.list_active_users(),
            location_names=self.repo.list_location_names(),
            modal=False,
            on_close=lambda rid=trip_id: self._on_edit_dialog_closed(rid),
            trip_id=trip_id,
            on_open_collection_events=self.open_collection_events_for_trip,
            on_open_finds=self.open_finds_for_trip,
            collection_events_count=self.repo.count_collection_events_for_trip(trip_id),
            finds_count=self.repo.count_finds_for_trip(trip_id),
        )
        self.open_edit_dialogs[trip_id] = dialog

    def open_collection_events_for_trip(self, trip_id: int, dialog: TripFormDialog) -> None:
        self.hidden_trip_dialog = dialog
        self.hidden_trip_dialog_trip_id = trip_id
        self.tabs.select(str(self.collection_events_tab))
        self.collection_events_tab.activate_trip_filter(trip_id)
        self.collection_events_tab.update_idletasks()

    def open_finds_for_trip(self, trip_id: int, dialog: TripFormDialog) -> None:
        self.hidden_trip_dialog = dialog
        self.hidden_trip_dialog_trip_id = trip_id
        self.tabs.select(str(self.finds_tab))
        self.finds_tab.activate_trip_filter(trip_id)
        self.finds_tab.update_idletasks()

    @staticmethod
    def _normalize_payload(payload: dict[str, str]) -> dict[str, str | None]:
        normalized: dict[str, str | None] = {}
        for key, value in payload.items():
            if key in {"trip_name"}:
                normalized[key] = value
            elif key == "id":
                continue
            else:
                normalized[key] = value if value else None
        return normalized

    def _on_edit_dialog_closed(self, row_id: int) -> None:
        self.open_edit_dialogs.pop(row_id, None)
        if self.hidden_trip_dialog_trip_id == row_id:
            self.hidden_trip_dialog = None
            self.hidden_trip_dialog_trip_id = None

    def _active_edit_dialogs(self) -> list[TripFormDialog]:
        active: list[TripFormDialog] = []
        stale_ids: list[int] = []
        for rid, dialog in self.open_edit_dialogs.items():
            if dialog.winfo_exists():
                active.append(dialog)
            else:
                stale_ids.append(rid)
        for rid in stale_ids:
            self.open_edit_dialogs.pop(rid, None)
        return active

    def _on_tab_changed(self, _event) -> None:
        current_tab = self.tabs.select()
        if current_tab == str(self.trips_tab):
            self.load_trips()
            if self.hidden_trip_dialog and self.hidden_trip_dialog.winfo_exists():
                trip_id = self.hidden_trip_dialog_trip_id
                if isinstance(trip_id, int):
                    self._select_trip_row(trip_id)
                self.hidden_trip_dialog.deiconify()
                self.hidden_trip_dialog.lift()
                self.hidden_trip_dialog.focus_force()
                self.hidden_trip_dialog = None
                self.hidden_trip_dialog_trip_id = None
            elif self.hidden_trip_dialog:
                self.hidden_trip_dialog = None
                self.hidden_trip_dialog_trip_id = None
            return
        if current_tab == str(self.location_tab):
            self.location_tab.load_locations()
        if current_tab == str(self.geology_tab):
            self.geology_tab.load_geology()
        if current_tab == str(self.collection_events_tab):
            self.collection_events_tab.load_collection_events()
        if current_tab == str(self.finds_tab):
            self.finds_tab.load_finds()
        if current_tab == str(self.users_tab):
            self.users_tab.load_users()

    def _select_trip_row(self, trip_id: int) -> None:
        iid = str(trip_id)
        if iid not in self.trips_tree.get_children():
            return
        self.trips_tree.selection_set(iid)
        self.trips_tree.focus(iid)
        self.trips_tree.see(iid)

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
