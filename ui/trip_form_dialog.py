import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from ui.location_picker_dialog import LocationPickerDialog
from ui.team_editor_dialog import TeamEditorDialog


class TripFormDialog(tk.Toplevel):
    @staticmethod
    def _count_label(count: int, singular: str, plural: str) -> str:
        return f"{count} {singular if count == 1 else plural}"

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
        trip_id: int | None = None,
        on_open_collection_events=None,
        on_open_finds=None,
        on_open_team=None,
        collection_events_count: int = 0,
        finds_count: int = 0,
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
        self.trip_id = trip_id
        self.on_open_collection_events = on_open_collection_events
        self.on_open_finds = on_open_finds
        self.on_open_team = on_open_team
        self.collection_events_count = collection_events_count
        self.finds_count = finds_count
        self.inputs: dict[str, tk.Widget] = {}
        self._icon_buttons: dict[str, ttk.Button] = {}
        self._edit_var = tk.IntVar(value=0)
        self._last_saved_payload: dict[str, str] = {}
        self.resizable(False, False)

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        style = ttk.Style(self)
        self._chip_icon_font = tkfont.Font(self, family="Helvetica", size=13, weight="bold")
        style.configure(
            "IconChip.TButton",
            padding=1,
            foreground="#FFFFFF",
            background="#4A5A52",
            font=self._chip_icon_font,
        )
        style.map(
            "IconChip.TButton",
            foreground=[("disabled", "#C4CCC8"), ("!disabled", "#FFFFFF")],
            background=[("disabled", "#7A807B"), ("active", "#60726A"), ("!disabled", "#4A5A52")],
        )
        style.configure(
            "FieldChip.TButton",
            padding=1,
            foreground="#FFFFFF",
            background="#4A5A52",
            font=self._chip_icon_font,
        )
        style.map(
            "FieldChip.TButton",
            foreground=[("disabled", "#C4CCC8"), ("!disabled", "#FFFFFF")],
            background=[("disabled", "#7A807B"), ("active", "#60726A"), ("!disabled", "#4A5A52")],
        )

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
                    icon_btn = ttk.Button(team_frame, text="✎", width=2, style="FieldChip.TButton", command=edit_cmd)
                    icon_btn.pack(side="left", padx=(4, 0))
                    self._icon_buttons[field] = icon_btn
                else:
                    widget = ttk.Entry(body, width=42)
                    widget.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                if initial_data and initial_data.get(field):
                    widget.insert(0, str(initial_data[field]))
                if field in self.readonly_fields:
                    widget.configure(state="readonly")
            self.inputs[field] = widget

        actions = ttk.Frame(body)
        actions.grid(row=len(fields), column=0, columnspan=3, sticky="ew", pady=(6, 4))
        collection_events_state = (
            "normal" if callable(self.on_open_collection_events) and isinstance(self.trip_id, int) else "disabled"
        )
        ttk.Button(
            actions,
            text=self._count_label(self.collection_events_count, "Collection Event", "Collection Events"),
            style="FieldChip.TButton",
            state=collection_events_state,
            command=self._open_collection_events,
        ).grid(
            row=0, column=0, padx=2, sticky="w"
        )
        finds_state = "normal" if callable(self.on_open_finds) and isinstance(self.trip_id, int) else "disabled"
        ttk.Button(
            actions,
            text=self._count_label(self.finds_count, "Find", "Finds"),
            style="FieldChip.TButton",
            state=finds_state,
            command=self._open_finds,
        ).grid(row=0, column=1, padx=2, sticky="w")
        team_state = "normal" if callable(self.on_open_team) and isinstance(self.trip_id, int) else "disabled"
        ttk.Button(
            actions,
            text="Team",
            style="FieldChip.TButton",
            state=team_state,
            command=self._open_team,
        ).grid(row=0, column=2, padx=2, sticky="w")
        actions.columnconfigure(3, weight=1)
        edit_radio = ttk.Radiobutton(actions, text="Edit", variable=self._edit_var, value=1)
        edit_radio.grid(row=0, column=4, padx=(8, 4), sticky="e")
        edit_radio.bind("<Button-1>", self._on_edit_radio_click, add="+")
        if callable(self.on_duplicate):
            ttk.Button(actions, text="⧉", style="IconChip.TButton", width=2, command=self._duplicate).grid(
                row=0, column=5, padx=2, sticky="e"
            )

        self._last_saved_payload = self._collect_payload()
        self._set_edit_mode(False)
        self.transient(parent)
        if self.modal:
            self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

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
        if self._edit_var.get() != 1:
            return
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

    def _duplicate(self) -> None:
        if not callable(self.on_duplicate):
            return
        payload = self._collect_payload()
        self.on_duplicate(payload)

    def _open_collection_events(self) -> None:
        if not callable(self.on_open_collection_events) or not isinstance(self.trip_id, int):
            return
        if not self._save_if_changed():
            return
        self.withdraw()
        self.on_open_collection_events(self.trip_id, self)

    def _open_finds(self) -> None:
        if not callable(self.on_open_finds) or not isinstance(self.trip_id, int):
            return
        if not self._save_if_changed():
            return
        self.withdraw()
        self.on_open_finds(self.trip_id, self)

    def _open_team(self) -> None:
        if not callable(self.on_open_team) or not isinstance(self.trip_id, int):
            return
        if not self._save_if_changed():
            return
        self.withdraw()
        self.on_open_team(self.trip_id, self)

    def _collect_payload(self) -> dict[str, str]:
        payload: dict[str, str] = {}
        for field, widget in self.inputs.items():
            if isinstance(widget, tk.Text):
                payload[field] = widget.get("1.0", "end").strip()
            else:
                payload[field] = widget.get().strip()
        return payload

    def _close(self, skip_save: bool = False) -> None:
        if not skip_save and not self._save_if_changed():
            return
        if callable(self.on_close):
            self.on_close()
        self.destroy()

    def _save_if_changed(self) -> bool:
        payload = self._collect_payload()
        if payload == self._last_saved_payload:
            return True
        should_close = self.on_save(payload)
        if should_close is False:
            return False
        self._last_saved_payload = payload
        return True

    def _set_edit_mode(self, editable: bool) -> None:
        for field, widget in self.inputs.items():
            if isinstance(widget, tk.Text):
                widget.configure(state="normal" if editable else "disabled")
                continue
            if field == "trip_name":
                widget.configure(state="readonly")
            else:
                widget.configure(state="normal" if editable else "readonly")
        for button in self._icon_buttons.values():
            button.configure(state="normal" if editable else "disabled")

    def _on_edit_radio_click(self, _event) -> str:
        # Toggle behavior on a single radio control.
        currently_on = self._edit_var.get() == 1
        if currently_on:
            if not self._save_if_changed():
                return "break"
            self._edit_var.set(0)
            self._set_edit_mode(False)
            return "break"
        self._edit_var.set(1)
        self._set_edit_mode(True)
        return "break"
