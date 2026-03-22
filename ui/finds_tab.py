import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from trip_repository import TripRepository


class FindsTab(ttk.Frame):
    LIST_COLUMNS = (
        "location_name",
        "collection_subset",
        "trip_name",
        "source_occurrence_no",
        "accepted_name",
    )

    def __init__(self, parent, repo: TripRepository):
        super().__init__(parent)
        self.repo = repo
        self._trip_filter_trip_id: int | None = None

        self.trip_filter_var = tk.IntVar(value=0)
        trip_filter_radio = ttk.Radiobutton(self, text="Trip filter", variable=self.trip_filter_var, value=1)
        trip_filter_radio.pack(anchor="w", padx=10, pady=(10, 4))
        trip_filter_radio.bind("<Button-1>", self._on_trip_filter_click, add="+")
        self.tree = ttk.Treeview(self, columns=self.LIST_COLUMNS, show="headings")
        widths = {
            "location_name": 220,
            "collection_subset": 130,
            "trip_name": 220,
            "source_occurrence_no": 120,
            "accepted_name": 220,
        }
        for col in self.LIST_COLUMNS:
            self.tree.heading(col, text=col.replace("_", " "))
            self.tree.column(col, width=widths.get(col, 120), anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=6)

    def load_finds(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            use_trip_filter = self.trip_filter_var.get() == 1 and self._trip_filter_trip_id is not None
            rows = self.repo.list_finds(self._trip_filter_trip_id if use_trip_filter else None)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        for row in rows:
            self.tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=tuple((row.get(col) or "") for col in self.LIST_COLUMNS),
            )

    def activate_trip_filter(self, trip_id: int) -> None:
        self._trip_filter_trip_id = trip_id
        self.trip_filter_var.set(1)
        self.load_finds()

    def _on_trip_filter_click(self, _event) -> str:
        currently_on = self.trip_filter_var.get() == 1
        if currently_on:
            self.trip_filter_var.set(0)
        else:
            self.trip_filter_var.set(1)
        self.load_finds()
        return "break"
