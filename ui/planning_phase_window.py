import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from trip_repository import TripRepository
from ui.location_tab import LocationTab
from ui.trip_form_dialog import TripFormDialog
from ui.users_tab import UsersTab


class PlanningPhaseWindow(tk.Tk):
    def __init__(self, db_path: str = "paleo_trips_01.db"):
        super().__init__()
        self.title("Planning Phase")
        self.geometry("980x560")

        self.repo = TripRepository(db_path)
        self.open_edit_dialogs: dict[int, TripFormDialog] = {}
        self.repo.ensure_trips_table()
        self.fields = self.repo.get_fields()
        self.list_fields = ["trip_name", "trip_code", "start_date", "end_date", "region"]
        self.edit_fields = ["trip_name", "trip_code", "start_date", "end_date", "region", "team", "notes"]
        self.list_fields = [f for f in self.list_fields if f in self.fields]
        self.edit_fields = [f for f in self.edit_fields if f in self.fields]

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)

        self.trips_tab = ttk.Frame(self.tabs)
        self.location_tab = LocationTab(self.tabs, self.repo)
        self.geology_tab = ttk.Frame(self.tabs)
        self.collection_plan_tab = ttk.Frame(self.tabs)
        self.users_tab = UsersTab(self.tabs, self.repo)
        self.tabs.add(self.trips_tab, text="Trips")
        self.tabs.add(self.location_tab, text="Location")
        self.tabs.add(self.geology_tab, text="Geology")
        self.tabs.add(self.collection_plan_tab, text="Collection Plan")
        self.tabs.add(self.users_tab, text="Team Members")
        self.tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._build_trips_tab()
        self._build_placeholder_tab(self.geology_tab, "Geology")
        self._build_placeholder_tab(self.collection_plan_tab, "Collection Plan")
        self.load_trips()
        self.location_tab.load_locations()
        self.users_tab.load_users()

    def _build_trips_tab(self) -> None:
        ttk.Label(self.trips_tab, text="Trips", font=("Helvetica", 15, "bold")).pack(pady=10)
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
        ttk.Label(tab, text=title, font=("Helvetica", 15, "bold")).pack(pady=(40, 10))
        ttk.Label(tab, text="Scaffolded tab. Data form coming next.").pack()

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
            self.trips_tree.insert("", "end", iid=str(record["rowid"]), values=values)

    def new_trip(self) -> None:
        def save_new(payload: dict[str, str]) -> bool:
            if not payload.get("trip_name"):
                messagebox.showerror("Validation Error", "trip_name is required.")
                return False
            payload["trip_code"] = self.repo.next_trip_code()
            normalized = self._normalize_payload(payload)
            try:
                self.repo.create_trip(normalized)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_trips()
            return True

        initial_data = {"trip_code": self.repo.next_trip_code()}
        TripFormDialog(
            self,
            self.edit_fields,
            initial_data,
            save_new,
            readonly_fields={"trip_code"},
            active_users=self.repo.list_active_users(),
            modal=True,
        )

    def edit_selected(self) -> None:
        selected = self.trips_tree.selection()
        if not selected:
            messagebox.showinfo("Edit Trip", "Select a Trip first.")
            return
        row_id = int(selected[0])
        try:
            trip = self.repo.get_trip(row_id)
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
                self.repo.update_trip(row_id, normalized)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_trips()
            return True

        def duplicate_trip(payload: dict[str, str]) -> bool:
            if not payload.get("trip_name"):
                messagebox.showerror("Validation Error", "trip_name is required.")
                return False
            payload["trip_code"] = self.repo.next_trip_code()
            payload["start_date"] = ""
            payload["end_date"] = ""
            normalized = self._normalize_payload(payload)
            try:
                new_row_id = self.repo.create_trip(normalized)
                new_trip = self.repo.get_trip(new_row_id)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Duplicate Error", str(e))
                return False
            self.load_trips()
            existing_dialog = self.open_edit_dialogs.get(row_id)
            if existing_dialog and existing_dialog.winfo_exists():
                existing_dialog.destroy()
            if new_trip:
                self._open_edit_dialog(new_row_id, new_trip)
            return True

        self._open_edit_dialog(row_id, trip, save_edit, duplicate_trip)

    def _open_edit_dialog(
        self,
        row_id: int,
        trip: dict[str, str],
        save_edit=None,
        duplicate_trip=None,
    ) -> None:
        existing = self.open_edit_dialogs.get(row_id)
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
                self.repo.update_trip(row_id, normalized)
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
            readonly_fields={"trip_code"},
            active_users=self.repo.list_active_users(),
            modal=False,
            on_close=lambda rid=row_id: self._on_edit_dialog_closed(rid),
        )
        self.open_edit_dialogs[row_id] = dialog

    @staticmethod
    def _normalize_payload(payload: dict[str, str]) -> dict[str, str | None]:
        normalized: dict[str, str | None] = {}
        for key, value in payload.items():
            if key in {"trip_name", "trip_code"}:
                normalized[key] = value
            else:
                normalized[key] = value if value else None
        return normalized

    def _on_edit_dialog_closed(self, row_id: int) -> None:
        self.open_edit_dialogs.pop(row_id, None)

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
        if current_tab == str(self.location_tab):
            self.location_tab.load_locations()
        if current_tab == str(self.users_tab):
            self.users_tab.load_users()
