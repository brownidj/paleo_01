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
    ):
        super().__init__(parent)
        self.title("Location")
        self.on_save = on_save
        self.resizable(False, False)
        self.entries: dict[str, ttk.Entry] = {}
        self._is_new = is_new
        self._geology_label_to_id: dict[str, int] = {}

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
        options = [self.NONE_OPTION]
        for geology_id, geology_label in geology_choices or []:
            label = str(geology_label).strip()
            if not label:
                continue
            if label in self._geology_label_to_id:
                label = f"{label} (#{geology_id})"
            self._geology_label_to_id[label] = int(geology_id)
            options.append(label)
        if self._is_new:
            options.append(self.NEW_GEOLOGY_OPTION)
        self.geology_combo = ttk.Combobox(frame, textvariable=self.geology_var, values=options, state="readonly", width=40)
        self.geology_combo.grid(row=geology_row, column=1, sticky="w", padx=4, pady=4)

        current_geology_id = int(initial_data.get("geology_id")) if initial_data and initial_data.get("geology_id") else None
        if current_geology_id is not None:
            for label, geology_id in self._geology_label_to_id.items():
                if geology_id == current_geology_id:
                    self.geology_var.set(label)
                    break
            else:
                self.geology_var.set(self.NONE_OPTION)

        btns = ttk.Frame(frame)
        btns.grid(row=geology_row + 1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)

        self.transient(parent)
        self.grab_set()

    def _save(self) -> None:
        payload: dict[str, object] = {field: entry.get().strip() for field, entry in self.entries.items()}
        selected = self.geology_var.get().strip()
        if selected == self.NEW_GEOLOGY_OPTION:
            payload["new_geology"] = True
            payload["geology_id"] = None
        elif selected and selected != self.NONE_OPTION:
            payload["geology_id"] = self._geology_label_to_id.get(selected)
        else:
            payload["geology_id"] = None
        should_close = self.on_save(payload)
        if should_close is False:
            return
        self.destroy()
