import sqlite3
from tkinter import messagebox, ttk

from repository.trip_repository import TripRepository
from ui.find_form_dialog import FindFormDialog
from ui.trip_filter_tree_tab import TripFilterTreeTab


class FindsTab(TripFilterTreeTab):
    LIST_COLUMNS = (
        "trip_name",
        "collection_name",
        "source_occurrence_no",
        "accepted_name",
    )

    def __init__(self, parent, repo: TripRepository):
        widths = {
            "trip_name": 220,
            "collection_name": 240,
            "source_occurrence_no": 80,
            "accepted_name": 220,
        }
        super().__init__(parent, repo, self.LIST_COLUMNS, widths, repo.list_finds)
        style = ttk.Style(self)
        style.configure("Finds.Treeview.Heading", font=("Helvetica", 10, "bold"))
        self.tree.configure(style="Finds.Treeview")
        self.tree.heading("trip_name", text="Trip")
        self.tree.heading("collection_name", text="CE")
        self.tree.heading("source_occurrence_no", text="Source")
        self.tree.heading("accepted_name", text="Accepted")
        self.tree.column("source_occurrence_no", width=80, minwidth=80, stretch=False, anchor="w")
        self._current_trip_id_provider = None
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="New Find", command=self.new_find).pack(side="left", padx=4)
        self.tree.bind("<Double-1>", lambda _: self.edit_find())

    def load_finds(self) -> None:
        self.load_rows()

    def set_current_trip_provider(self, provider) -> None:
        self._current_trip_id_provider = provider

    def new_find(self) -> None:
        trip_id = None
        if callable(self._current_trip_id_provider):
            trip_id = self._current_trip_id_provider()
        if trip_id is None:
            trip_id = self._trip_filter_trip_id
        try:
            events = self.repo.list_collection_events(trip_id)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        if not events:
            messagebox.showinfo("New Find", "Create at least one Collection Event before adding a Find.")
            return

        choices: list[tuple[int, str]] = []
        for event in events:
            event_id = int(event["id"])
            collection_name = str(event.get("collection_name") or "").strip() or "n/a"
            location_name = str(event.get("location_name") or "").strip() or "n/a"
            label = f"#{event_id} | {collection_name} | {location_name}"
            choices.append((event_id, label))

        def save_find(payload: dict[str, object]) -> bool:
            try:
                self.repo.create_find(payload)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_finds()
            return True

        FindFormDialog(self, choices, save_find, initial_data=None, title="New Find", is_new=True)

    def edit_find(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Edit Find", "Select a Find first.")
            return
        try:
            find_id = int(selected[0])
        except (TypeError, ValueError):
            messagebox.showerror("Edit Find", "Invalid Find selection.")
            return
        try:
            record = self.repo.get_find(find_id)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        if not record:
            messagebox.showerror("Edit Find", "Selected Find no longer exists.")
            self.load_finds()
            return

        trip_id = None
        if callable(self._current_trip_id_provider):
            trip_id = self._current_trip_id_provider()
        if trip_id is None:
            trip_id = self._trip_filter_trip_id
        try:
            events = self.repo.list_collection_events(trip_id)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        choices: list[tuple[int, str]] = []
        for event in events:
            event_id = int(event["id"])
            collection_name = str(event.get("collection_name") or "").strip() or "n/a"
            location_name = str(event.get("location_name") or "").strip() or "n/a"
            label = f"#{event_id} | {collection_name} | {location_name}"
            choices.append((event_id, label))
        current_ce_id_raw = record.get("collection_event_id")
        current_ce_id = int(current_ce_id_raw) if current_ce_id_raw is not None else None
        if current_ce_id is not None and current_ce_id not in {c[0] for c in choices}:
            all_events = self.repo.list_collection_events(None)
            for event in all_events:
                event_id = int(event["id"])
                if event_id != current_ce_id:
                    continue
                collection_name = str(event.get("collection_name") or "").strip() or "n/a"
                location_name = str(event.get("location_name") or "").strip() or "n/a"
                choices.append((event_id, f"#{event_id} | {collection_name} | {location_name}"))
                break
        if not choices:
            messagebox.showinfo("Edit Find", "No Collection Events are available for this Find.")
            return

        initial = dict(record)

        def save_find(payload: dict[str, object]) -> bool:
            try:
                self.repo.update_find(find_id, payload)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_finds()
            return True

        FindFormDialog(self, choices, save_find, initial_data=initial, title="Edit Find", is_new=False)
