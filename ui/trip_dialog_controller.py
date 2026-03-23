import sqlite3

from tkinter import messagebox

from repository.domain_types import TripPayloadMap, TripRecord
from repository.trip_repository import TripRepository
from ui.trip_form_dialog import TripFormDialog


class TripDialogController:
    def __init__(
        self,
        parent,
        repo: TripRepository,
        edit_fields: list[str],
        trips_tree,
        load_trips,
        on_open_collection_events,
        on_open_finds,
        on_open_team,
        on_edit_dialog_closed,
    ):
        self.parent = parent
        self.repo = repo
        self.edit_fields = edit_fields
        self.trips_tree = trips_tree
        self.load_trips = load_trips
        self.on_open_collection_events = on_open_collection_events
        self.on_open_finds = on_open_finds
        self.on_open_team = on_open_team
        self.on_edit_dialog_closed = on_edit_dialog_closed
        self.open_edit_dialogs: dict[int, TripFormDialog] = {}

    def new_trip(self) -> None:
        def save_new(payload: TripPayloadMap) -> bool:
            if not payload.get("trip_name"):
                messagebox.showerror("Validation Error", "trip_name is required.")
                return False
            normalized = self._normalize_payload(payload)
            try:
                self.repo.create_trip(normalized)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_trips()
            return True

        TripFormDialog(
            self.parent,
            self.edit_fields,
            {},
            save_new,
            readonly_fields=set(),
            active_users=self.repo.list_active_team_members(),
            location_names=self.repo.list_location_names(),
            modal=True,
            trip_id=None,
            on_open_collection_events=None,
            on_open_finds=None,
            on_open_team=None,
            collection_events_count=0,
            finds_count=0,
        )

    def edit_selected(self) -> None:
        selected = self.trips_tree.selection()
        if not selected:
            messagebox.showinfo("Edit Trip", "Select a Trip first.")
            return
        trip_id = int(selected[0])
        try:
            trip = self.repo.get_trip(trip_id)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        if not trip:
            messagebox.showerror("Edit Trip", "Selected Trip no longer exists.")
            self.load_trips()
            return

        def save_edit(payload: TripPayloadMap) -> bool:
            if not payload.get("trip_name"):
                messagebox.showerror("Validation Error", "trip_name is required.")
                return False
            normalized = self._normalize_payload(payload)
            try:
                self.repo.update_trip(trip_id, normalized)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_trips()
            return True

        def duplicate_trip(payload: TripPayloadMap) -> bool:
            if not payload.get("trip_name"):
                messagebox.showerror("Validation Error", "trip_name is required.")
                return False
            payload["start_date"] = ""
            payload["end_date"] = ""
            normalized = self._normalize_payload(payload)
            try:
                new_trip_id = self.repo.create_trip(normalized)
                new_trip = self.repo.get_trip(new_trip_id)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Duplicate Error", str(e))
                return False
            self.load_trips()
            existing_dialog = self.open_edit_dialogs.get(trip_id)
            if existing_dialog and existing_dialog.winfo_exists():
                existing_dialog.destroy()
            if new_trip:
                self._open_edit_dialog(new_trip_id, new_trip)
            return True

        self._open_edit_dialog(trip_id, trip, save_edit, duplicate_trip)

    def _open_edit_dialog(
        self,
        trip_id: int,
        trip: TripRecord,
        save_edit=None,
        duplicate_trip=None,
    ) -> None:
        existing = self.open_edit_dialogs.get(trip_id)
        if existing and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        if len(self._active_edit_dialogs()) >= 2:
            messagebox.showinfo("Trip Comparison", "You can open up to 2 Trip edit windows at a time.")
            return

        def _default_save(payload: TripPayloadMap) -> bool:
            if not payload.get("trip_name"):
                messagebox.showerror("Validation Error", "trip_name is required.")
                return False
            normalized = self._normalize_payload(payload)
            try:
                self.repo.update_trip(trip_id, normalized)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_trips()
            return True

        dialog = TripFormDialog(
            self.parent,
            self.edit_fields,
            {k: "" if v is None else str(v) for k, v in trip.items()},
            save_edit or _default_save,
            on_duplicate=duplicate_trip,
            readonly_fields=set(),
            active_users=self.repo.list_active_team_members(),
            location_names=self.repo.list_location_names(),
            modal=False,
            on_close=lambda rid=trip_id: self._on_edit_dialog_closed(rid),
            trip_id=trip_id,
            on_open_collection_events=self.on_open_collection_events,
            on_open_finds=self.on_open_finds,
            on_open_team=self.on_open_team,
            collection_events_count=self.repo.count_collection_events_for_trip(trip_id),
            finds_count=self.repo.count_finds_for_trip(trip_id),
        )
        self.open_edit_dialogs[trip_id] = dialog

    def _on_edit_dialog_closed(self, row_id: int) -> None:
        self.open_edit_dialogs.pop(row_id, None)
        self.on_edit_dialog_closed(row_id)

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

    @staticmethod
    def _normalize_payload(payload: TripPayloadMap) -> TripPayloadMap:
        normalized: TripPayloadMap = {}
        for key, value in payload.items():
            if key in {"trip_name"}:
                normalized[key] = value
            elif key == "id":
                continue
            else:
                normalized[key] = value if value else None
        return normalized
