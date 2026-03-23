import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from repository.trip_repository import TripRepository
from ui.auto_hide_scrollbars import attach_auto_hiding_scrollbars
from ui.geology_form_dialog import GeologyFormDialog
from ui.location_form_dialog import LocationFormDialog


class LocationTab(ttk.Frame):
    LIST_COLUMNS = ("name", "lga", "state", "country_code", "latitude", "longitude")

    def __init__(self, parent, repo: TripRepository):
        super().__init__(parent)
        self.repo = repo
        self._toast_shown_count = 0
        self._toast_hide_after_id: str | None = None

        self.tree = ttk.Treeview(
            self,
            columns=self.LIST_COLUMNS,
            show="headings",
        )
        column_widths = {
            "name": 220,
            "lga": 170,
            "state": 55,
            "country_code": 45,
            "latitude": 95,
            "longitude": 95,
        }
        for col in self.LIST_COLUMNS:
            heading = "LGA" if col == "lga" else col.replace("_", " ")
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=column_widths.get(col, 120), anchor="w")
        attach_auto_hiding_scrollbars(self, self.tree, padx=10, pady=6)

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="New Location", command=self.new_location).pack(side="left", padx=4)
        self.tree.bind("<Double-1>", lambda _: self.edit_location())
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        self._toast = tk.Label(
            self,
            text="",
            bg="#2B6E59",
            fg="#FFFFFF",
            font=("Helvetica", 12, "bold"),
            bd=2,
            relief="solid",
            padx=14,
            pady=8,
        )
        self._toast.place_forget()

    def load_locations(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            locations = self.repo.list_locations()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        for loc in locations:
            self.tree.insert(
                "",
                "end",
                iid=str(loc["id"]),
                values=tuple((loc.get(col, "") or "") for col in self.LIST_COLUMNS),
            )

    def new_location(self) -> None:
        geology_choices = self._list_geology_choices()

        def save_location(payload: dict[str, object]) -> bool:
            normalized = self._normalize_payload(payload)
            create_new_geology = bool(payload.get("new_geology"))
            try:
                location_id = self.repo.create_location(normalized)
                if create_new_geology:
                    geology_id = self.repo.create_geology_record(location_id, {})
                    self.repo.update_location(location_id, {"geology_id": geology_id})
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_locations()
            return True

        LocationFormDialog(self, None, save_location, geology_choices=geology_choices, is_new=True)

    def edit_location(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Edit Location", "Select a Location first.")
            return
        location_id = int(selected[0])
        try:
            location = self.repo.get_location(location_id)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        if not location:
            messagebox.showerror("Edit Location", "Selected Location no longer exists.")
            self.load_locations()
            return

        geology_choices = self._list_geology_choices()
        geology_by_id = {gid: label for gid, label in geology_choices}
        geology_id_raw = location.get("geology_id")
        geology_id = int(geology_id_raw) if geology_id_raw is not None else None
        location["geology_name"] = geology_by_id.get(geology_id, "") if geology_id is not None else ""

        def save_location(payload: dict[str, object]) -> bool:
            normalized = self._normalize_payload(payload)
            try:
                self.repo.update_location(location_id, normalized)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_locations()
            return True

        def edit_geology(geology_id_to_edit: int) -> None:
            try:
                record = self.repo.get_geology_record(geology_id_to_edit)
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", str(e))
                return
            if not record:
                messagebox.showerror("Edit Geology", "Selected geology record no longer exists.")
                return

            def save_geology(payload: dict[str, object]) -> bool:
                try:
                    self.repo.update_geology_record(geology_id_to_edit, payload)
                except (sqlite3.Error, ValueError) as e:
                    messagebox.showerror("Save Error", str(e))
                    return False
                return True

            GeologyFormDialog(self, record, save_geology, title="Edit Geology")

        LocationFormDialog(
            self,
            location,
            save_location,
            geology_choices=geology_choices,
            is_new=False,
            on_edit_geology=edit_geology,
        )

    def _list_geology_choices(self) -> list[tuple[int, str]]:
        try:
            rows = self.repo.list_geology_records()
        except sqlite3.Error:
            return []
        choices: list[tuple[int, str]] = []
        for row in rows:
            geology_id_raw = row.get("geology_id")
            if geology_id_raw is None:
                continue
            geology_id = int(geology_id_raw)
            location_name = str(row.get("location_name") or "").strip() or "n/a"
            formation = str(row.get("formation") or "").strip()
            if formation:
                label = f"{location_name} | {formation}"
            else:
                label = location_name
            choices.append((geology_id, label))
        choices.sort(key=lambda item: item[1].lower())
        return choices

    @staticmethod
    def _normalize_payload(payload: dict[str, object]) -> dict[str, object]:
        normalized: dict[str, object] = {}
        for key, value in payload.items():
            if key == "new_geology":
                continue
            if key == "geology_id":
                if value is None or value == "":
                    normalized[key] = None
                else:
                    normalized[key] = int(value)
                continue
            normalized[key] = value if value else None
        return normalized

    def maybe_show_edit_toast(self) -> None:
        if self.tree.selection():
            self._show_toast_if_available("Double-click to edit.")

    def _on_tree_select(self, _event) -> None:
        self._show_toast_if_available("Double-click to edit.")

    def _show_toast_if_available(self, message: str, duration_ms: int = 1400) -> None:
        if self._toast_shown_count >= 2:
            return
        self._toast_shown_count += 1
        self._toast.configure(text=message)
        self._toast.place(in_=self.tree, relx=0.5, rely=1.0, anchor="s", y=-18)
        if self._toast_hide_after_id is not None:
            self.after_cancel(self._toast_hide_after_id)
        self._toast_hide_after_id = self.after(duration_ms, self._hide_toast)

    def _hide_toast(self) -> None:
        self._toast.place_forget()
        self._toast_hide_after_id = None
