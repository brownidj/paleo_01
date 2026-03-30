import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from repository.trip_repository import TripRepository
from ui.auto_hide_scrollbars import attach_auto_hiding_scrollbars
from ui.geology_form_dialog import GeologyFormDialog
from ui.location_form_dialog import LocationFormDialog


class LocationTab(ttk.Frame):
    LIST_COLUMNS = ("name", "basin", "proterozoic_province", "orogen", "state", "country_code", "latitude", "longitude")

    def __init__(self, parent, repo: TripRepository):
        super().__init__(parent)
        self.repo = repo
        self.trip_filter_var = tk.IntVar(value=1)
        self._trip_filter_trip_id: int | None = None
        self._current_trip_id_provider = None
        self._toast_shown_count = 0
        self._toast_hide_after_id: str | None = None

        trip_filter_radio = ttk.Radiobutton(self, text="Trip filter", variable=self.trip_filter_var, value=1)
        trip_filter_radio.pack(anchor="w", padx=10, pady=(10, 4))
        trip_filter_radio.bind("<Button-1>", self._on_trip_filter_click, add="+")

        self.tree = ttk.Treeview(
            self,
            columns=self.LIST_COLUMNS,
            show="headings",
            style="Location.Treeview",
        )
        style = ttk.Style(self)
        style.configure("Location.Treeview.Heading", font=("Helvetica", 10, "bold"))
        column_widths = {
            "name": 220,
            "basin": 86,
            "proterozoic_province": 170,
            "orogen": 150,
            "state": 44,
            "country_code": 56,
            "latitude": 82,
            "longitude": 86,
        }
        heading_labels = {
            "name": "Name",
            "basin": "Basin",
            "proterozoic_province": "Province",
            "orogen": "Orogen",
            "state": "State",
            "country_code": "Country",
            "latitude": "Latitude",
            "longitude": "Longitude",
        }
        for col in self.LIST_COLUMNS:
            self.tree.heading(col, text=heading_labels.get(col, col))
            width = column_widths.get(col, 120)
            self.tree.column(col, width=width, minwidth=width, stretch=False, anchor="w")
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
        allowed_location_names = self._active_trip_location_names()
        use_trip_filter = self.trip_filter_var.get() == 1 and allowed_location_names is not None
        for loc in locations:
            if use_trip_filter and str(loc.get("name") or "").strip().lower() not in allowed_location_names:
                continue
            self.tree.insert(
                "",
                "end",
                iid=str(loc["id"]),
                values=tuple((loc.get(col, "") or "") for col in self.LIST_COLUMNS),
            )

    def set_current_trip_provider(self, provider) -> None:
        self._current_trip_id_provider = provider

    def activate_trip_filter(self, trip_id: int) -> None:
        self._trip_filter_trip_id = trip_id
        self.trip_filter_var.set(1)
        self.load_locations()

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

    def _on_trip_filter_click(self, _event) -> str:
        currently_on = self.trip_filter_var.get() == 1
        if currently_on:
            self.trip_filter_var.set(0)
        else:
            provider_trip_id = self._get_provider_trip_id()
            if provider_trip_id is not None:
                self._trip_filter_trip_id = provider_trip_id
            self.trip_filter_var.set(1)
        self.load_locations()
        return "break"

    def _get_provider_trip_id(self) -> int | None:
        if not callable(self._current_trip_id_provider):
            return None
        trip_id = self._current_trip_id_provider()
        if trip_id is None:
            return None
        try:
            return int(trip_id)
        except (TypeError, ValueError):
            return None

    def _active_trip_filter_trip_id(self) -> int | None:
        provider_trip_id = self._get_provider_trip_id()
        if provider_trip_id is not None:
            self._trip_filter_trip_id = provider_trip_id
        return self._trip_filter_trip_id

    def _active_trip_location_names(self) -> set[str] | None:
        trip_id = self._active_trip_filter_trip_id()
        if trip_id is None:
            return None
        trip = self.repo.get_trip(trip_id)
        if not trip:
            return None
        raw_location = str(trip.get("location") or "")
        names = {part.strip().lower() for part in raw_location.split(";") if part.strip()}
        return names or None

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
