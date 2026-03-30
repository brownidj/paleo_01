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
        self._trip_filter_trip_name_label = ttk.Label(
            self._trip_filter_header,
            text="",
            anchor="center",
            font=("Helvetica", 10, "bold"),
        )
        self._trip_filter_trip_name_label.pack(side="left", fill="x", expand=True, padx=(10, 10))
        self.set_trip_filter_hint(
            "[Double-click to edit. Turn the Trip filter 'off' to see all Collection Events.]",
            font=("Helvetica", 10, "italic"),
        )
        self.tree.bind("<Double-1>", self._on_double_click)
        self.trip_filter_var.set(1)
        self._update_trip_filter_trip_name()

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=(4, 10))
        self.new_event_button = ttk.Button(
            buttons,
            text="New Collection Event",
            command=self._open_new_collection_event_dialog,
            state="disabled",
        )
        self.new_event_button.pack(side="left")
        self.duplicate_event_button = ttk.Button(
            buttons,
            text="Duplicate Event",
            command=self._open_duplicate_collection_event_dialog,
            state="disabled",
        )
        self.duplicate_event_button.pack(side="left", padx=(8, 0))
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select, add="+")
        self._sync_new_event_button_state()
        self._sync_duplicate_event_button_state()

    def load_collection_events(self) -> None:
        self.trip_filter_var.set(1)
        self.load_rows()
        self._sync_new_event_button_state()
        self._sync_duplicate_event_button_state()
        self._update_trip_filter_trip_name()

    def activate_trip_filter(self, trip_id: int) -> None:
        super().activate_trip_filter(trip_id)
        self._sync_new_event_button_state()
        self._sync_duplicate_event_button_state()
        self._update_trip_filter_trip_name()

    def _on_trip_filter_click(self, event) -> str:
        result = super()._on_trip_filter_click(event)
        self._sync_new_event_button_state()
        self._sync_duplicate_event_button_state()
        self._update_trip_filter_trip_name()
        return result

    def _sync_new_event_button_state(self) -> None:
        enabled = self.trip_filter_var.get() == 1 and self._trip_filter_trip_id is not None
        self.new_event_button.configure(state="normal" if enabled else "disabled")

    def _sync_duplicate_event_button_state(self) -> None:
        filter_on = self.trip_filter_var.get() == 1 and self._trip_filter_trip_id is not None
        if filter_on:
            if self.duplicate_event_button.winfo_manager() != "pack":
                self.duplicate_event_button.pack(side="left", padx=(8, 0))
        else:
            if self.duplicate_event_button.winfo_manager():
                self.duplicate_event_button.pack_forget()
            self.duplicate_event_button.configure(state="disabled")
            return
        selected = self.tree.selection()
        enabled = False
        if selected:
            try:
                int(selected[0])
                enabled = True
            except (TypeError, ValueError):
                enabled = False
        self.duplicate_event_button.configure(state="normal" if enabled else "disabled")

    def _update_trip_filter_trip_name(self) -> None:
        if self.trip_filter_var.get() != 1:
            self._trip_filter_trip_name_label.configure(text="")
            return
        trip_id = self._active_trip_filter_trip_id()
        if trip_id is None:
            self._trip_filter_trip_name_label.configure(text="")
            return
        try:
            trip = self.repo.get_trip(int(trip_id)) or {}
        except sqlite3.Error:
            self._trip_filter_trip_name_label.configure(text="")
            return
        trip_name = str(trip.get("trip_name") or "").strip()
        self._trip_filter_trip_name_label.configure(text=trip_name)

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

    def _on_double_click(self, event) -> None:
        row_iid = self.tree.identify_row(event.y)
        if row_iid:
            self.tree.selection_set(row_iid)
            self.tree.focus(row_iid)
        selected = self.tree.selection()
        if not selected:
            return
        try:
            collection_event_id = int(selected[0])
        except (TypeError, ValueError):
            return
        values = self.tree.item(selected[0], "values")
        current_name = str(values[0]) if values else ""
        self._open_edit_collection_event_dialog(collection_event_id, current_name)

    def _open_edit_collection_event_dialog(self, collection_event_id: int, current_name: str) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Edit Collection Event")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        body = ttk.Frame(dialog, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="Collection Event name").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        name_entry = ttk.Entry(body, width=36)
        name_entry.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        name_entry.insert(0, current_name)
        name_entry.focus_set()
        name_entry.select_range(0, "end")

        buttons = ttk.Frame(body)
        buttons.grid(row=1, column=0, columnspan=2, sticky="e", pady=(6, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")

        def _save() -> None:
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror(
                    "Edit Collection Event",
                    "Collection Event name is required.",
                    parent=dialog,
                )
                return
            try:
                self.edit_collection_event_by_id(collection_event_id, name)
            except (sqlite3.Error, ValueError) as exc:
                messagebox.showerror("Edit Collection Event", str(exc), parent=dialog)
                return
            dialog.destroy()

        ttk.Button(buttons, text="Save", command=_save).pack(side="right", padx=(0, 6))

    def _on_tree_select(self, _event) -> None:
        self._sync_duplicate_event_button_state()

    def _open_duplicate_collection_event_dialog(self) -> None:
        if self.trip_filter_var.get() != 1 or self._trip_filter_trip_id is None:
            return
        selected = self.tree.selection()
        if not selected:
            return
        try:
            source_event_id = int(selected[0])
        except (TypeError, ValueError):
            return
        values = self.tree.item(selected[0], "values")
        current_name = str(values[0]).strip() if values else ""
        source_event = self.repo.get_collection_event(source_event_id) or {}
        location_name = str(source_event.get("location_name") or "").strip()
        event_year_raw = source_event.get("event_year")
        event_year_text = str(event_year_raw).strip() if event_year_raw is not None else ""
        try:
            trip_id = int(source_event.get("trip_id")) if source_event.get("trip_id") is not None else None
        except (TypeError, ValueError):
            trip_id = None
        trip = self.repo.get_trip(trip_id) if trip_id is not None else None
        trip_name = str((trip or {}).get("trip_name") or "").strip()
        start_date = str((trip or {}).get("start_date") or "").strip()

        dialog = tk.Toplevel(self)
        dialog.title("Duplicate Collection Event")
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
        ttk.Label(body, text=location_name).grid(row=2, column=1, sticky="w", pady=(0, 6))
        ttk.Label(body, text="Event year").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        ttk.Label(body, text=event_year_text).grid(row=3, column=1, sticky="w", pady=(0, 6))

        ttk.Label(body, text="Collection Event name").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=(0, 6))
        name_entry = ttk.Entry(body, width=36)
        name_entry.grid(row=4, column=1, sticky="ew", pady=(0, 6))
        name_entry.insert(0, current_name)
        name_entry.focus_set()
        name_entry.select_range(0, "end")

        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(6, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        save_button = ttk.Button(buttons, text="Save", state="disabled")
        save_button.pack(side="right", padx=(0, 6))

        def _sync_save_state(_event=None) -> None:
            candidate = name_entry.get().strip()
            changed = candidate != current_name
            save_button.configure(state="normal" if (candidate and changed) else "disabled")

        def _save_duplicate() -> None:
            duplicate_name = name_entry.get().strip()
            if not duplicate_name:
                messagebox.showerror(
                    "Duplicate Collection Event",
                    "Collection Event name is required.",
                    parent=dialog,
                )
                return
            if duplicate_name == current_name:
                messagebox.showerror(
                    "Duplicate Collection Event",
                    "Change the Collection Event name before saving.",
                    parent=dialog,
                )
                return
            try:
                duplicated_event_id = self.duplicate_collection_event_by_id(source_event_id, duplicate_name)
            except (sqlite3.Error, ValueError) as exc:
                messagebox.showerror("Duplicate Collection Event", str(exc), parent=dialog)
                return
            dialog.destroy()
            iid = str(duplicated_event_id)
            if iid in self.tree.get_children():
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self.tree.see(iid)

        save_button.configure(command=_save_duplicate)
        name_entry.bind("<KeyRelease>", _sync_save_state, add="+")
        name_entry.bind("<FocusOut>", _sync_save_state, add="+")
        _sync_save_state()

    def duplicate_collection_event_by_id(self, source_collection_event_id: int, collection_name: str) -> int:
        duplicate_fn = getattr(self.repo, "duplicate_collection_event", None)
        if not callable(duplicate_fn):
            raise ValueError("Collection Event duplication is not available.")
        cleaned_name = str(collection_name or "").strip()
        if not cleaned_name:
            raise ValueError("Collection Event name is required.")
        duplicated_event_id = int(duplicate_fn(source_collection_event_id, cleaned_name))
        self.load_collection_events()
        return duplicated_event_id

    def edit_collection_event_by_id(self, collection_event_id: int, collection_name: str) -> None:
        cleaned_name = str(collection_name or "").strip()
        if not cleaned_name:
            raise ValueError("Collection Event name is required.")
        self.repo.update_collection_event_name(collection_event_id, cleaned_name)
        self.load_collection_events()
        iid = str(collection_event_id)
        if iid in self.tree.get_children():
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
