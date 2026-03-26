from __future__ import annotations

from tkinter import ttk

from ui.location_picker_dialog import LocationPickerDialog
from ui.team_editor_dialog import TeamEditorDialog


class TripFormDialogPickersMixin:
    def _split_list(self, raw: str) -> list[str]:
        return [v.strip() for v in raw.split(";") if v.strip()]

    def _join_list(self, selected_names: list[str]) -> str:
        return "; ".join(line.strip() for line in selected_names if line.strip())

    def _edit_team(self) -> None:
        if self._edit_var.get() != 1:
            return
        team_widget = self.inputs.get("team")
        if not isinstance(team_widget, ttk.Entry):
            return
        trip_name_widget = self.inputs.get("trip_name")
        trip_name = ""
        if isinstance(trip_name_widget, ttk.Entry):
            trip_name = trip_name_widget.get().strip()
        existing_names = self._split_list(team_widget.get().strip())

        def save_team(selected_names: list[str]) -> None:
            team_widget.configure(state="normal")
            team_widget.delete(0, "end")
            team_widget.insert(0, self._join_list(selected_names))
            if "team" in self.readonly_fields:
                team_widget.configure(state="readonly")

        TeamEditorDialog(self, self.active_users, existing_names, trip_name, save_team)

    def _edit_location(self) -> None:
        if self._edit_var.get() != 1:
            return
        location_widget = self.inputs.get("location")
        if not isinstance(location_widget, ttk.Entry):
            return
        trip_name_widget = self.inputs.get("trip_name")
        trip_name = ""
        if isinstance(trip_name_widget, ttk.Entry):
            trip_name = trip_name_widget.get().strip()
        existing_names = self._split_list(location_widget.get().strip())

        def save_locations(selected_names: list[str]) -> None:
            location_widget.configure(state="normal")
            location_widget.delete(0, "end")
            location_widget.insert(0, self._join_list(selected_names))
            if "location" in self.readonly_fields:
                location_widget.configure(state="readonly")

        LocationPickerDialog(self, self.location_names, existing_names, trip_name, save_locations)
