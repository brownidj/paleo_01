import sqlite3
from tkinter import messagebox, ttk

from trip_repository import TripRepository
from ui.location_form_dialog import LocationFormDialog


class LocationTab(ttk.Frame):
    LIST_COLUMNS = ("name", "lga", "state", "country_code", "latitude", "longitude")

    def __init__(self, parent, repo: TripRepository):
        super().__init__(parent)
        self.repo = repo

        ttk.Label(self, text="Location", font=("Helvetica", 15, "bold")).pack(pady=10)
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
        self.tree.pack(fill="both", expand=True, padx=10, pady=6)

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="New Location", command=self.new_location).pack(side="left", padx=4)
        self.tree.bind("<Double-1>", lambda _: self.edit_location())

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
        def save_location(payload: dict[str, object]) -> bool:
            normalized = self._normalize_payload(payload)
            try:
                self.repo.create_location(normalized)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_locations()
            return True

        LocationFormDialog(self, None, save_location)

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

        def save_location(payload: dict[str, object]) -> bool:
            normalized = self._normalize_payload(payload)
            try:
                self.repo.update_location(location_id, normalized)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_locations()
            return True

        LocationFormDialog(self, location, save_location)

    @staticmethod
    def _normalize_payload(payload: dict[str, object]) -> dict[str, object]:
        normalized: dict[str, object] = {}
        for key, value in payload.items():
            if key == "collection_events":
                events = []
                raw_events = value if isinstance(value, list) else []
                for event in raw_events:
                    if not isinstance(event, dict):
                        continue
                    name = str(event.get("collection_name") or "").strip()
                    if not name:
                        continue
                    subset = str(event.get("collection_subset") or "").strip()
                    events.append(
                        {
                            "collection_name": name,
                            "collection_subset": subset or None,
                        }
                    )
                normalized[key] = events
                continue
            normalized[key] = value if value else None
        return normalized
