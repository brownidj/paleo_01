import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from repository.trip_repository import TripRepository
from ui.trip_filter_tree_tab import TripFilterTreeTab


class CollectionEventsTab(TripFilterTreeTab):
    LIST_COLUMNS = ("collection_name", "location_name", "find_count")

    def __init__(self, parent, repo: TripRepository):
        widths = {
            "collection_name": 260,
            "location_name": 260,
            "find_count": 80,
        }
        super().__init__(parent, repo, self.LIST_COLUMNS, widths, repo.list_collection_events)
        style = ttk.Style(self)
        style.configure("CollectionEvents.Treeview.Heading", font=("Helvetica", 10, "bold"))
        self.tree.configure(style="CollectionEvents.Treeview")
        self.tree.heading("collection_name", text="Name")
        self.tree.heading("location_name", text="Location")
        self.tree.heading("find_count", text="Finds")
        self.tree.column("find_count", anchor="center")

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=(4, 10))
        self.new_event_button = ttk.Button(
            buttons,
            text="New Collection Event",
            command=self._open_new_collection_event_dialog,
            state="disabled",
        )
        self.new_event_button.pack(side="left")
        self._sync_new_event_button_state()

    def load_collection_events(self) -> None:
        self.load_rows()
        self._sync_new_event_button_state()

    def activate_trip_filter(self, trip_id: int) -> None:
        super().activate_trip_filter(trip_id)
        self._sync_new_event_button_state()

    def _on_trip_filter_click(self, event) -> str:
        result = super()._on_trip_filter_click(event)
        self._sync_new_event_button_state()
        return result

    def _sync_new_event_button_state(self) -> None:
        enabled = self.trip_filter_var.get() == 1 and self._trip_filter_trip_id is not None
        self.new_event_button.configure(state="normal" if enabled else "disabled")

    def _selected_trip_id(self) -> int:
        if self.trip_filter_var.get() != 1 or self._trip_filter_trip_id is None:
            raise ValueError("Select a trip filter first.")
        return int(self._trip_filter_trip_id)

    def create_collection_event_for_active_trip(self, collection_name: str, event_year: int | None = None) -> int:
        trip_id = self._selected_trip_id()
        cleaned_name = str(collection_name or "").strip()
        if not cleaned_name:
            raise ValueError("Collection Event name is required.")
        return int(self.repo.create_collection_event_for_trip(trip_id, cleaned_name, event_year))

    def _open_new_collection_event_dialog(self) -> None:
        try:
            trip_id = self._selected_trip_id()
        except ValueError as exc:
            messagebox.showerror("New Collection Event", str(exc), parent=self)
            return
        trip = self.repo.get_trip(trip_id) or {}
        trip_name = str(trip.get("trip_name") or "")
        start_date = str(trip.get("start_date") or "")
        location = str(trip.get("location") or "")

        dialog = tk.Toplevel(self)
        dialog.title("New Collection Event")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        body = ttk.Frame(dialog, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="Trip").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        ttk.Label(body, text=trip_name).grid(row=0, column=1, sticky="w", pady=(0, 6))
        ttk.Label(body, text="Start").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        ttk.Label(body, text=start_date).grid(row=1, column=1, sticky="w", pady=(0, 6))
        ttk.Label(body, text="Location").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        ttk.Label(body, text=location).grid(row=2, column=1, sticky="w", pady=(0, 6))

        ttk.Label(body, text="Collection Event name").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        name_entry = ttk.Entry(body, width=36)
        name_entry.grid(row=3, column=1, sticky="ew", pady=(0, 6))

        ttk.Label(body, text="Event year (optional)").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        year_entry = ttk.Entry(body, width=36)
        year_entry.grid(row=4, column=1, sticky="ew", pady=(0, 6))
        name_entry.focus_set()

        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(6, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")

        def _save() -> None:
            name = name_entry.get().strip()
            year_text = year_entry.get().strip()
            if not name:
                messagebox.showerror(
                    "New Collection Event",
                    "Collection Event name is required.",
                    parent=dialog,
                )
                return
            event_year: int | None = None
            if year_text:
                try:
                    event_year = int(year_text)
                except ValueError:
                    messagebox.showerror(
                        "New Collection Event",
                        "Event year must be an integer.",
                        parent=dialog,
                    )
                    return
            try:
                event_id = self.create_collection_event_for_active_trip(name, event_year)
            except (sqlite3.Error, ValueError) as exc:
                messagebox.showerror("New Collection Event", str(exc), parent=dialog)
                return
            dialog.destroy()
            self.load_collection_events()
            iid = str(event_id)
            if iid in self.tree.get_children():
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self.tree.see(iid)

        ttk.Button(buttons, text="Create", command=_save).pack(side="right", padx=(0, 6))
