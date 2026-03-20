import tkinter as tk
from tkinter import ttk

from ui.location_picker_dialog import LocationPickerDialog
from ui.team_editor_dialog import TeamEditorDialog


class TripFormDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        fields: list[str],
        initial_data: dict[str, str] | None,
        on_save,
        on_duplicate=None,
        readonly_fields: set[str] | None = None,
        active_users: list[str] | None = None,
        location_names: list[str] | None = None,
        modal: bool = True,
        on_close=None,
    ):
        super().__init__(parent)
        self.title("Trip Record")
        self.fields = fields
        self.on_save = on_save
        self.on_duplicate = on_duplicate
        self.readonly_fields = readonly_fields or set()
        self.active_users = active_users or []
        self.location_names = location_names or []
        self.modal = modal
        self.on_close = on_close
        self.inputs: dict[str, tk.Widget] = {}
        self.resizable(False, False)

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)

        for i, field in enumerate(fields):
            ttk.Label(body, text=field).grid(row=i, column=0, sticky="e", padx=4, pady=4)
            if field == "notes":
                notes_frame = ttk.Frame(body)
                notes_frame.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                widget = tk.Text(
                    notes_frame,
                    width=40,
                    height=6,
                    wrap="word",
                    bd=1,
                    relief="solid",
                    highlightthickness=0,
                )
                scrollbar = ttk.Scrollbar(notes_frame, orient="vertical", command=widget.yview)
                widget.configure(yscrollcommand=scrollbar.set)
                widget.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")
                if initial_data and initial_data.get(field):
                    widget.insert("1.0", str(initial_data[field]))
            else:
                if field in {"team", "location"}:
                    team_frame = ttk.Frame(body)
                    team_frame.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                    widget = ttk.Entry(team_frame, width=38)
                    widget.pack(side="left", fill="x", expand=True)
                    if field == "team":
                        edit_cmd = self._edit_team
                    else:
                        edit_cmd = self._edit_location
                    ttk.Button(team_frame, text="✎", width=3, command=edit_cmd).pack(side="left", padx=(4, 0))
                else:
                    widget = ttk.Entry(body, width=42)
                    widget.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                if initial_data and initial_data.get(field):
                    widget.insert(0, str(initial_data[field]))
                if field in self.readonly_fields:
                    widget.configure(state="readonly")
            self.inputs[field] = widget

        btns = ttk.Frame(body)
        btns.grid(row=len(fields), column=0, columnspan=3, sticky="ew", pady=8)
        btns.columnconfigure(2, weight=1)
        ttk.Button(btns, text="Save", command=self._save).grid(row=0, column=0, padx=4, sticky="w")
        if callable(self.on_duplicate):
            ttk.Button(btns, text="Duplicate", command=self._duplicate).grid(row=0, column=1, padx=4, sticky="w")
        ttk.Button(btns, text="Cancel", command=self._close).grid(row=0, column=3, padx=4, sticky="e")

        self.transient(parent)
        if self.modal:
            self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _edit_team(self) -> None:
        team_widget = self.inputs.get("team")
        if not isinstance(team_widget, ttk.Entry):
            return
        trip_name_widget = self.inputs.get("trip_name")
        trip_name = ""
        if isinstance(trip_name_widget, ttk.Entry):
            trip_name = trip_name_widget.get().strip()
        current_value = team_widget.get().strip()
        existing_names = [v.strip() for v in current_value.split(";") if v.strip()]

        def save_team(selected_names: list[str]) -> None:
            lines = [line.strip() for line in selected_names if line.strip()]
            team_widget.configure(state="normal")
            team_widget.delete(0, "end")
            team_widget.insert(0, "; ".join(lines))
            if "team" in self.readonly_fields:
                team_widget.configure(state="readonly")

        TeamEditorDialog(self, self.active_users, existing_names, trip_name, save_team)

    def _edit_location(self) -> None:
        location_widget = self.inputs.get("location")
        if not isinstance(location_widget, ttk.Entry):
            return
        trip_name_widget = self.inputs.get("trip_name")
        trip_name = ""
        if isinstance(trip_name_widget, ttk.Entry):
            trip_name = trip_name_widget.get().strip()
        current_value = location_widget.get().strip()
        existing_names = [v.strip() for v in current_value.split(";") if v.strip()]

        def save_locations(selected_names: list[str]) -> None:
            lines = [line.strip() for line in selected_names if line.strip()]
            location_widget.configure(state="normal")
            location_widget.delete(0, "end")
            location_widget.insert(0, "; ".join(lines))
            if "location" in self.readonly_fields:
                location_widget.configure(state="readonly")

        LocationPickerDialog(self, self.location_names, existing_names, trip_name, save_locations)

    def _save(self) -> None:
        payload = self._collect_payload()
        should_close = self.on_save(payload)
        if should_close is False:
            return
        self._close()

    def _duplicate(self) -> None:
        if not callable(self.on_duplicate):
            return
        payload = self._collect_payload()
        self.on_duplicate(payload)

    def _collect_payload(self) -> dict[str, str]:
        payload: dict[str, str] = {}
        for field, widget in self.inputs.items():
            if isinstance(widget, tk.Text):
                payload[field] = widget.get("1.0", "end").strip()
            else:
                payload[field] = widget.get().strip()
        return payload

    def _close(self) -> None:
        if callable(self.on_close):
            self.on_close()
        self.destroy()
