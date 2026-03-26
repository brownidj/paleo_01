from __future__ import annotations

import json
from pathlib import Path


class PlanningPhaseWindowSelectionMixin:
    _last_selected_trip_id: int | None
    _last_selected_trip_name: str | None
    _trip_toast_last_iid: str | None
    _trip_toast_hide_after_id: str | None
    _suspend_trip_selection_persist: bool
    _trip_toast_shown_count: int

    def _get_selected_trip_id(self) -> int | None:
        selected = self.trips_tree.selection()
        if selected:
            try:
                return int(selected[0])
            except (TypeError, ValueError):
                return None
        return self._last_selected_trip_id

    def _restore_trip_selection(self) -> None:
        children = tuple(self.trips_tree.get_children())
        if not children:
            self._last_selected_trip_id = None
            self._last_selected_trip_name = None
            self._save_last_selected_trip_state(None, None)
            return
        target_iid = None
        if self._last_selected_trip_id is not None:
            candidate = str(self._last_selected_trip_id)
            if candidate in children:
                target_iid = candidate
        if target_iid is None and self._last_selected_trip_name:
            for iid in children:
                values = self.trips_tree.item(iid, "values")
                trip_name = str(values[0]) if values else ""
                if trip_name == self._last_selected_trip_name:
                    target_iid = str(iid)
                    break
        if target_iid is None:
            target_iid = children[0]
        self.trips_tree.selection_set(target_iid)
        self.trips_tree.focus(target_iid)
        self.trips_tree.see(target_iid)
        self._maybe_show_trip_edit_toast()
        self._persist_trip_selection_from_iid(target_iid, force=True)
        self._suspend_trip_selection_persist = False

    def _on_trip_selected(self, _event) -> None:
        if self._suspend_trip_selection_persist:
            return
        selected = self.trips_tree.selection()
        if not selected:
            return
        self._maybe_show_trip_edit_toast()
        self._persist_trip_selection_from_iid(str(selected[0]))

    def _persist_trip_selection_from_iid(self, iid: str, force: bool = False) -> None:
        if self._suspend_trip_selection_persist and not force:
            return
        try:
            trip_id = int(iid)
        except (TypeError, ValueError):
            return
        values = self.trips_tree.item(iid, "values")
        trip_name = str(values[0]) if values else None
        self._last_selected_trip_id = trip_id
        self._last_selected_trip_name = trip_name
        self._save_last_selected_trip_state(trip_id, trip_name)

    def _load_last_selected_trip_state(self) -> tuple[int | None, str | None]:
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, None
        raw = data.get("last_selected_trip_id")
        trip_name_raw = data.get("last_selected_trip_name")
        trip_name = str(trip_name_raw) if isinstance(trip_name_raw, str) and trip_name_raw.strip() else None
        try:
            trip_id = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            trip_id = None
        return trip_id, trip_name

    def _save_last_selected_trip_state(self, trip_id: int | None, trip_name: str | None) -> None:
        payload = {"last_selected_trip_id": trip_id, "last_selected_trip_name": trip_name}
        try:
            self._state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            return

    def _on_close(self) -> None:
        selected = self.trips_tree.selection()
        if selected:
            self._persist_trip_selection_from_iid(str(selected[0]), force=True)
        self.destroy()

    def _maybe_show_trip_edit_toast(self, duration_ms: int = 1400) -> None:
        trips_tree = self.__dict__.get("trips_tree")
        if trips_tree is None:
            return
        selected = trips_tree.selection()
        if not selected:
            return
        selected_iid = str(selected[0])
        last_iid = self.__dict__.get("_trip_toast_last_iid")
        if isinstance(last_iid, str) and last_iid == selected_iid:
            return
        shown_count = int(self.__dict__.get("_trip_toast_shown_count", 0))
        if shown_count >= 2:
            return
        toast = self.__dict__.get("_trip_toast")
        if toast is None:
            return
        self._trip_toast_shown_count = shown_count + 1
        self._trip_toast_last_iid = selected_iid
        toast.configure(text="Double-click to edit.")
        toast.place(in_=trips_tree, relx=0.5, rely=1.0, anchor="s", y=-18)
        hide_after_id = self.__dict__.get("_trip_toast_hide_after_id")
        if hide_after_id is not None:
            self.after_cancel(hide_after_id)
        self._trip_toast_hide_after_id = self.after(duration_ms, self._hide_trip_toast)

    def _hide_trip_toast(self) -> None:
        toast = self.__dict__.get("_trip_toast")
        if toast is None:
            return
        toast.place_forget()
        self._trip_toast_hide_after_id = None

    @staticmethod
    def _resolve_db_path(db_path: str) -> Path:
        path = Path(db_path)
        if path.is_absolute():
            return path.resolve()
        project_root = Path(__file__).resolve().parent.parent
        return (project_root / path).resolve()
