import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Mapping, cast

from repository.domain_types import CollectionEventRecord
from repository.trip_repository import TripRepository
from ui.find_field_observations_dialog import FindFieldObservationsDialog
from ui.find_form_dialog import FindFormDialog
from ui.find_taxonomy_dialog import FindTaxonomyDialog
from ui.trip_filter_tree_tab import TripFilterTreeTab


class FindsTab(TripFilterTreeTab):
    LIST_COLUMNS = (
        "id",
        "trip_name",
        "collection_name",
        "find_date",
        "find_time",
        "latitude",
        "longitude",
        "source_occurrence_no",
        "accepted_name",
    )

    def __init__(self, parent, repo: TripRepository):
        widths = {
            "id": 72,
            "trip_name": 180,
            "collection_name": 200,
            "find_date": 92,
            "find_time": 78,
            "latitude": 96,
            "longitude": 102,
            "source_occurrence_no": 96,
            "accepted_name": 180,
        }
        super().__init__(
            parent,
            repo,
            self.LIST_COLUMNS,
            widths,
            cast(Callable[[int | None], list[Mapping[str, object]]], repo.list_finds),
        )
        style = ttk.Style(self)
        style.configure("Finds.Treeview.Heading", font=("Helvetica", 10, "bold"))
        self.tree.configure(style="Finds.Treeview")
        self.tree.heading("id", text="ID")
        self.tree.heading("trip_name", text="Trip")
        self.tree.heading("collection_name", text="CE")
        self.tree.heading("find_date", text="Date")
        self.tree.heading("find_time", text="Time")
        self.tree.heading("latitude", text="Latitude")
        self.tree.heading("longitude", text="Longitude")
        self.tree.heading("source_occurrence_no", text="Source")
        self.tree.heading("accepted_name", text="Accepted")
        self.tree.column("id", width=72, minwidth=72, stretch=False, anchor="center")
        self.tree.column("find_date", width=92, minwidth=92, stretch=False, anchor="center")
        self.tree.column("find_time", width=78, minwidth=78, stretch=False, anchor="center")
        self.tree.column("latitude", width=96, minwidth=96, stretch=False, anchor="w")
        self.tree.column("longitude", width=102, minwidth=102, stretch=False, anchor="w")
        self.tree.column("source_occurrence_no", width=96, minwidth=96, stretch=False, anchor="w")
        self.set_trip_filter_hint(
            "[Double-click to edit. Turn the Trip filter 'off' to see all Finds.]",
            font=("Helvetica", 10, "italic"),
        )
        self._save_toast_hide_after_id: str | None = None
        self._save_toast = tk.Label(
            self,
            text="Record saved",
            bg="#2B6E59",
            fg="#FFFFFF",
            font=("Helvetica", 11, "bold"),
            bd=2,
            relief="solid",
            padx=10,
            pady=5,
        )
        self._save_toast.place_forget()
        self._current_trip_id_provider = None
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="New Find", command=self.new_find).pack(side="left", padx=4)
        ttk.Button(buttons, text="Duplicate", command=self.duplicate_find).pack(side="left", padx=4)
        self.tree.bind("<Double-1>", lambda _: self.edit_find())

    def load_finds(self) -> None:
        self.trip_filter_var.set(1)
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

        choices = self._collection_event_choices(events)

        def save_find(payload: dict[str, object]) -> bool:
            try:
                new_find_id = int(self.repo.create_find(payload))
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_finds()
            self._focus_find(new_find_id)
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
        choices = self._collection_event_choices(events)
        current_ce_id_raw = record.get("collection_event_id")
        current_ce_id = int(current_ce_id_raw) if current_ce_id_raw is not None else None
        if current_ce_id is not None and current_ce_id not in {c[0] for c in choices}:
            all_events = self.repo.list_collection_events(None)
            for event in all_events:
                event_id = int(event["id"])
                if event_id != current_ce_id:
                    continue
                choices.extend(self._collection_event_choices([event]))
                break
        if not choices:
            messagebox.showinfo("Edit Find", "No Collection Events are available for this Find.")
            return

        initial = dict(record)

        def save_find(payload: dict[str, object]) -> bool:
            try:
                merged_payload = dict(initial)
                merged_payload.update(payload)
                self.repo.update_find(find_id, merged_payload)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_finds()
            self._focus_find(find_id)
            return True

        FindFormDialog(
            self,
            choices,
            save_find,
            on_saved=self._show_record_saved_toast,
            on_open_field_observations=self._open_field_observations_form,
            on_open_taxonomy=self._open_taxonomy_form,
            initial_data=initial,
            title="Edit Find",
            is_new=False,
        )

    def duplicate_find(self) -> None:
        source_find_id: int | None = None
        selected = self.tree.selection()
        if selected:
            try:
                source_find_id = int(selected[0])
            except (TypeError, ValueError):
                source_find_id = None
        if source_find_id is None:
            source_find_id = self._latest_visible_find_id()
        if source_find_id is None:
            messagebox.showinfo("Duplicate Find", "Select a Find first.")
            return
        try:
            source_find = self.repo.get_find(source_find_id)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        if not source_find:
            messagebox.showerror("Duplicate Find", "Selected Find no longer exists.")
            self.load_finds()
            return
        duplicate_payload = dict(source_find)
        duplicate_payload.pop("id", None)
        duplicate_payload.pop("created_at", None)
        duplicate_payload.pop("updated_at", None)
        duplicate_payload.pop("location_name", None)
        try:
            new_find_id = int(self.repo.create_find(duplicate_payload))
            get_observations = getattr(self.repo, "get_find_field_observations", None)
            update_observations = getattr(self.repo, "update_find_field_observations", None)
            if callable(get_observations) and callable(update_observations):
                observations = get_observations(source_find_id) or {}
                if observations:
                    update_observations(new_find_id, dict(observations))
            get_taxonomy = getattr(self.repo, "get_find_taxonomy", None)
            update_taxonomy = getattr(self.repo, "update_find_taxonomy", None)
            if callable(get_taxonomy) and callable(update_taxonomy):
                taxonomy = get_taxonomy(source_find_id) or {}
                if taxonomy:
                    update_taxonomy(new_find_id, dict(taxonomy))
        except (sqlite3.Error, ValueError) as e:
            messagebox.showerror("Duplicate Error", str(e))
            return
        self.load_finds()
        self._focus_find(new_find_id)
        self._show_record_saved_toast()

    def _open_field_observations_form(self, find_id: int) -> None:
        try:
            existing = self.repo.get_find_field_observations(find_id) or {}
        except (sqlite3.Error, ValueError) as e:
            messagebox.showerror("Database Error", str(e))
            return

        def save_observations(payload: dict[str, object]) -> bool:
            try:
                self.repo.update_find_field_observations(find_id, payload)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self._show_record_saved_toast()
            return True

        FindFieldObservationsDialog(self, find_id=find_id, initial_data=existing, on_save=save_observations)

    def _open_taxonomy_form(self, find_id: int) -> None:
        try:
            existing = self.repo.get_find_taxonomy(find_id) or {}
        except (sqlite3.Error, ValueError) as e:
            messagebox.showerror("Database Error", str(e))
            return

        def save_taxonomy(payload: dict[str, object]) -> bool:
            try:
                self.repo.update_find_taxonomy(find_id, payload)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_finds()
            self._focus_find(find_id)
            self._show_record_saved_toast()
            return True

        FindTaxonomyDialog(self, find_id=find_id, initial_data=existing, on_save=save_taxonomy)

    def _focus_find(self, find_id: int) -> None:
        iid = str(find_id)
        if iid in self.tree.get_children():
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
            return
        if self.trip_filter_var.get() == 1:
            messagebox.showinfo(
                "Find Saved",
                f"Find #{find_id} was saved, but it is hidden by the active Trip filter.",
            )

    def _show_record_saved_toast(self, duration_ms: int = 3000) -> None:
        self._save_toast.configure(text="Record saved")
        self._save_toast.place(in_=self, relx=0.5, rely=1.0, anchor="s", y=-12)
        self._save_toast.lift()
        if self._save_toast_hide_after_id is not None:
            self.after_cancel(self._save_toast_hide_after_id)
        self._save_toast_hide_after_id = self.after(duration_ms, self._hide_record_saved_toast)

    def _latest_visible_find_id(self) -> int | None:
        max_find_id: int | None = None
        for iid in self.tree.get_children():
            try:
                value = int(iid)
            except (TypeError, ValueError):
                continue
            if max_find_id is None or value > max_find_id:
                max_find_id = value
        return max_find_id

    def _hide_record_saved_toast(self) -> None:
        self._save_toast.place_forget()
        self._save_toast_hide_after_id = None

    @staticmethod
    def _event_id(event: CollectionEventRecord) -> int | None:
        raw = event.get("id")
        try:
            if raw is None:
                return None
            return int(raw)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _collection_event_choices(cls, events: list[CollectionEventRecord]) -> list[tuple[int, str]]:
        base_labels: dict[int, tuple[str, str]] = {}
        counts: dict[str, int] = {}
        for event in events:
            event_id = cls._event_id(event)
            if event_id is None:
                continue
            collection_name = str(event.get("collection_name") or "").strip() or "n/a"
            location_name = str(event.get("location_name") or "").strip() or "n/a"
            base_labels[event_id] = (collection_name, location_name)
            counts[collection_name] = counts.get(collection_name, 0) + 1
        choices: list[tuple[int, str]] = []
        for event in events:
            event_id = cls._event_id(event)
            if event_id is None or event_id not in base_labels:
                continue
            collection_name, location_name = base_labels[event_id]
            if counts.get(collection_name, 0) == 1:
                label = collection_name
            else:
                label = f"{collection_name} | {location_name} (CE #{event_id})"
            choices.append((event_id, label))
        return choices
