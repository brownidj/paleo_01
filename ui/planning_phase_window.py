import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from trip_repository import TripRepository
from ui.team_editor_dialog import TeamEditorDialog


class TripFormDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        fields: list[str],
        initial_data: dict[str, str] | None,
        on_save,
        on_duplicate=None,
        readonly_fields: set[str] | None = None,
        active_users: list[str] | None = None,
        modal: bool = True,
        on_close=None,
    ):
        super().__init__(parent)
        self.title("Trip Record")
        self.fields = fields
        self.on_save = on_save
        self.on_duplicate = on_duplicate
        self.readonly_fields = readonly_fields or set()
        self.active_users = active_users or []
        self.modal = modal
        self.on_close = on_close
        self.inputs: dict[str, tk.Widget] = {}
        self.resizable(False, False)

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)

        for i, field in enumerate(fields):
            ttk.Label(body, text=field).grid(row=i, column=0, sticky="e", padx=4, pady=4)
            if field == "notes":
                notes_frame = ttk.Frame(body)
                notes_frame.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                widget = tk.Text(
                    notes_frame,
                    width=40,
                    height=6,
                    wrap="word",
                    bd=1,
                    relief="solid",
                    highlightthickness=0,
                )
                scrollbar = ttk.Scrollbar(notes_frame, orient="vertical", command=widget.yview)
                widget.configure(yscrollcommand=scrollbar.set)
                widget.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")
                if initial_data and initial_data.get(field):
                    widget.insert("1.0", str(initial_data[field]))
            else:
                widget = ttk.Entry(body, width=42)
                widget.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                if initial_data and initial_data.get(field):
                    widget.insert(0, str(initial_data[field]))
                if field in self.readonly_fields:
                    widget.configure(state="readonly")
                if field == "team":
                    ttk.Button(body, text="Edit team", command=self._edit_team).grid(
                        row=i, column=2, sticky="w", padx=4, pady=4
                    )
            self.inputs[field] = widget

        btns = ttk.Frame(body)
        btns.grid(row=len(fields), column=0, columnspan=3, sticky="ew", pady=8)
        btns.columnconfigure(2, weight=1)
        ttk.Button(btns, text="Save", command=self._save).grid(row=0, column=0, padx=4, sticky="w")
        if callable(self.on_duplicate):
            ttk.Button(btns, text="Duplicate", command=self._duplicate).grid(row=0, column=1, padx=4, sticky="w")
        ttk.Button(btns, text="Cancel", command=self._close).grid(row=0, column=3, padx=4, sticky="e")

        self.transient(parent)
        if self.modal:
            self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _edit_team(self) -> None:
        team_widget = self.inputs.get("team")
        if not isinstance(team_widget, ttk.Entry):
            return
        trip_name_widget = self.inputs.get("trip_name")
        trip_name = ""
        if isinstance(trip_name_widget, ttk.Entry):
            trip_name = trip_name_widget.get().strip()
        current_value = team_widget.get().strip()
        existing_names = [v.strip() for v in current_value.split(",") if v.strip()]

        def save_team(selected_names: list[str]) -> None:
            lines = [line.strip() for line in selected_names if line.strip()]
            team_widget.configure(state="normal")
            team_widget.delete(0, "end")
            team_widget.insert(0, ", ".join(lines))
            if "team" in self.readonly_fields:
                team_widget.configure(state="readonly")

        TeamEditorDialog(self, self.active_users, existing_names, trip_name, save_team)

    def _save(self) -> None:
        payload = self._collect_payload()
        should_close = self.on_save(payload)
        if should_close is False:
            return
        self._close()

    def _duplicate(self) -> None:
        if not callable(self.on_duplicate):
            return
        payload = self._collect_payload()
        self.on_duplicate(payload)

    def _collect_payload(self) -> dict[str, str]:
        payload: dict[str, str] = {}
        for field, widget in self.inputs.items():
            if isinstance(widget, tk.Text):
                payload[field] = widget.get("1.0", "end").strip()
            else:
                payload[field] = widget.get().strip()
        return payload

    def _close(self) -> None:
        if callable(self.on_close):
            self.on_close()
        self.destroy()


class PlanningPhaseWindow(tk.Tk):
    def __init__(self, db_path: str = "paleo_trips_01.db"):
        super().__init__()
        self.title("Planning Phase - Trips")
        self.geometry("980x560")

        self.repo = TripRepository(db_path)
        self.open_edit_dialogs: dict[int, TripFormDialog] = {}
        self.repo.ensure_trips_table()
        self.fields = self.repo.get_fields()
        self.list_fields = ["trip_name", "trip_code", "start_date", "end_date", "region"]
        self.edit_fields = ["trip_name", "trip_code", "start_date", "end_date", "region", "team", "notes"]
        self.list_fields = [f for f in self.list_fields if f in self.fields]
        self.edit_fields = [f for f in self.edit_fields if f in self.fields]

        ttk.Label(self, text="Trips", font=("Helvetica", 15, "bold")).pack(pady=10)

        self.tree = ttk.Treeview(
            self,
            columns=self.list_fields,
            show="headings",
        )
        for field in self.list_fields:
            self.tree.heading(field, text=field)
            self.tree.column(field, width=160, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=6)

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="New Trip", command=self.new_trip).pack(side="left", padx=4)
        ttk.Button(buttons, text="Edit Selected", command=self.edit_selected).pack(side="left", padx=4)
        ttk.Button(buttons, text="Refresh", command=self.load_trips).pack(side="left", padx=4)

        self.tree.bind("<Double-1>", lambda _: self.edit_selected())
        self.load_trips()

    def load_trips(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            records = self.repo.list_trips()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        for record in records:
            values = [record.get(field, "") for field in self.list_fields]
            self.tree.insert("", "end", iid=str(record["rowid"]), values=values)

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
        selected = self.tree.selection()
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
