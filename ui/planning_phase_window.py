import sqlite3
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from repository import DEFAULT_DB_PATH
from repository.trip_repository import TripRepository
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

        self.repo = TripRepository(db_path)
        self.repo.ensure_trips_table()
        self.fields = self.repo.get_fields()
        self.list_fields = ["trip_name", "start_date", "end_date", "location"]
        self.edit_fields = ["trip_name", "start_date", "end_date", "location", "team", "notes"]
        self.list_fields = [f for f in self.list_fields if f in self.fields]
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
            on_edit_dialog_closed=self.navigation.on_edit_dialog_closed,
        )
        self.tabs_controller.build_collection_plan_placeholder()
        self.tabs_controller.load_initial_tab_data(self.load_trips)

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
        self.dialog_controller.new_trip()

    def edit_selected(self) -> None:
        self.dialog_controller.edit_selected()

    def _on_tab_changed(self, _event) -> None:
        self.navigation.on_tab_changed()

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
