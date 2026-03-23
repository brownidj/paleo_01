import tkinter as tk
from tkinter import ttk


class LocationFormDialog(tk.Toplevel):
    FIELDS = [
        "name",
        "latitude",
        "longitude",
        "altitude_value",
        "altitude_unit",
        "country_code",
        "state",
        "lga",
        "basin",
        "geogscale",
        "geography_comments",
    ]

    NONE_OPTION = "(None)"
    NEW_GEOLOGY_OPTION = "New geology"

    def __init__(
        self,
        parent: tk.Widget,
        initial_data: dict[str, object] | None,
        on_save,
        geology_choices: list[tuple[int, str]] | None = None,
        is_new: bool = False,
        on_edit_geology=None,
    ):
        super().__init__(parent)
        self.title("Location")
        self.on_save = on_save
        self.resizable(False, False)
        self.entries: dict[str, ttk.Entry] = {}
        self._is_new = is_new
        self._on_edit_geology = on_edit_geology
        self._geology_label_to_id: dict[str, int] = {}
        self._geology_id: int | None = int(initial_data.get("geology_id")) if initial_data and initial_data.get("geology_id") else None

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)

        for i, field in enumerate(self.FIELDS):
            ttk.Label(frame, text=field).grid(row=i, column=0, sticky="e", padx=4, pady=4)
            entry = ttk.Entry(frame, width=42)
            entry.grid(row=i, column=1, sticky="w", padx=4, pady=4)
            if initial_data and initial_data.get(field) is not None:
                entry.insert(0, str(initial_data.get(field, "")))
            self.entries[field] = entry

        geology_row = len(self.FIELDS)
        ttk.Label(frame, text="geology").grid(row=geology_row, column=0, sticky="e", padx=4, pady=4)
        self.geology_var = tk.StringVar(value=self.NONE_OPTION)
        self.geology_combo: ttk.Combobox | None = None
        self.geology_display: ttk.Entry | None = None
        self.geology_edit_button: ttk.Button | None = None
        if self._is_new:
            options = [self.NONE_OPTION]
            for geology_id, geology_label in geology_choices or []:
                label = str(geology_label).strip()
                if not label:
                    continue
                if label in self._geology_label_to_id:
                    label = f"{label} (#{geology_id})"
                self._geology_label_to_id[label] = int(geology_id)
                options.append(label)
            options.append(self.NEW_GEOLOGY_OPTION)
            self.geology_combo = ttk.Combobox(
                frame,
                textvariable=self.geology_var,
                values=options,
                state="readonly",
                width=40,
            )
            self.geology_combo.grid(row=geology_row, column=1, sticky="w", padx=4, pady=4)
            if self._geology_id is not None:
                for label, geology_id in self._geology_label_to_id.items():
                    if geology_id == self._geology_id:
                        self.geology_var.set(label)
                        break
                else:
                    self.geology_var.set(self.NONE_OPTION)
        else:
            geology_frame = ttk.Frame(frame)
            geology_frame.grid(row=geology_row, column=1, sticky="w", padx=4, pady=4)
            geology_name = str(initial_data.get("geology_name") or "").strip() if initial_data else ""
            if not geology_name:
                geology_name = self.NONE_OPTION
            self.geology_display = ttk.Entry(geology_frame, width=38)
            self.geology_display.pack(side="left", fill="x", expand=True)
            self.geology_display.insert(0, geology_name)
            self.geology_display.configure(state="readonly")
            self.geology_edit_button = ttk.Button(
                geology_frame,
                text="✎",
                width=2,
                command=self._edit_geology,
                state="normal" if callable(self._on_edit_geology) and self._geology_id is not None else "disabled",
            )
            self.geology_edit_button.pack(side="left", padx=(4, 0))

        btns = ttk.Frame(frame)
        btns.grid(row=geology_row + 1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)

        self.transient(parent)
        self.grab_set()

    def _save(self) -> None:
        payload: dict[str, object] = {field: entry.get().strip() for field, entry in self.entries.items()}
        if self._is_new:
            selected = self.geology_var.get().strip()
            if selected == self.NEW_GEOLOGY_OPTION:
                payload["new_geology"] = True
                payload["geology_id"] = None
            elif selected and selected != self.NONE_OPTION:
                payload["geology_id"] = self._geology_label_to_id.get(selected)
            else:
                payload["geology_id"] = None
        else:
            payload["geology_id"] = self._geology_id
        should_close = self.on_save(payload)
        if should_close is False:
            return
        self.destroy()

    def _edit_geology(self) -> None:
        if not callable(self._on_edit_geology) or self._geology_id is None:
            return
        self._on_edit_geology(self._geology_id)
