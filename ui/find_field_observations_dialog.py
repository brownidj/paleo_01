import tkinter as tk
from tkinter import ttk
from typing import Callable, cast


class FindFieldObservationsDialog(tk.Toplevel):
    TEXT_FIELDS = ("notes", "occurrence_comments")
    EDITABLE_FIELDS = (
        "provisional_identification",
        "abund_value",
        "abund_unit",
        "research_group",
        "notes",
        "occurrence_comments",
    )

    def __init__(
        self,
        parent: tk.Widget,
        find_id: int,
        initial_data: dict[str, object] | None,
        on_save: Callable[[dict[str, object]], bool | None],
    ):
        super().__init__(parent)
        self.title(f"Find Field Observations #{find_id}")
        self.resizable(True, True)
        self.minsize(620, 420)
        self._on_save = on_save
        self._inputs: dict[str, tk.Text | ttk.Entry] = {}

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="find_id").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        find_id_entry = ttk.Entry(frame, width=48)
        find_id_entry.insert(0, str(find_id))
        find_id_entry.configure(state="readonly")
        find_id_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        row = 1
        for field in self.EDITABLE_FIELDS:
            ttk.Label(frame, text=field).grid(row=row, column=0, sticky="ne", padx=4, pady=4)
            value = ""
            if initial_data and initial_data.get(field) is not None:
                value = str(initial_data.get(field))
            if field in self.TEXT_FIELDS:
                widget: tk.Text | ttk.Entry = tk.Text(
                    frame,
                    width=56,
                    height=4,
                    wrap="word",
                    bd=1,
                    relief="solid",
                    highlightthickness=0,
                )
                if value:
                    widget.insert("1.0", value)
            else:
                widget = ttk.Entry(frame, width=58)
                if value:
                    widget.insert(0, value)
            widget.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            self._inputs[field] = widget
            row += 1

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="left", padx=4)

        self.transient(cast(tk.Wm, parent))
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _collect_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        for field, widget in self._inputs.items():
            if isinstance(widget, tk.Text):
                payload[field] = widget.get("1.0", "end").strip()
            else:
                payload[field] = widget.get().strip()
        return payload

    def _save(self) -> None:
        should_close = self._on_save(self._collect_payload())
        if should_close is False:
            return
        self.destroy()
