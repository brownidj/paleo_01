import tkinter as tk
from tkinter import ttk


class FindFormDialog(tk.Toplevel):
    READONLY_FIELDS = ("location_name",)
    TEXT_FIELDS: tuple[str, ...] = ()
    EDITABLE_FIELDS = (
        "find_date",
        "find_time",
        "latitude",
        "longitude",
        "source_system",
        "source_occurrence_no",
    )

    def __init__(
        self,
        parent: tk.Widget,
        collection_event_choices: list[tuple[int, str]],
        on_save,
        on_saved=None,
        on_open_field_observations=None,
        on_open_taxonomy=None,
        initial_data: dict[str, object] | None = None,
        title: str = "Find",
        is_new: bool = False,
    ):
        super().__init__(parent)
        self.title(title)
        self.resizable(True, True)
        self.minsize(640, 520)
        self.on_save = on_save
        self.on_saved = on_saved
        self._on_open_field_observations = on_open_field_observations
        self._find_id = int(initial_data["id"]) if initial_data and initial_data.get("id") not in (None, "") else None
        self._choice_map: dict[str, int] = {label: ce_id for ce_id, label in collection_event_choices}
        self._selected_collection_event_id = (
            int(initial_data["collection_event_id"]) if initial_data and initial_data.get("collection_event_id") else None
        )
        self._edit_var = tk.IntVar(value=0)
        self._last_saved_payload: dict[str, object] = {}
        self._on_open_taxonomy = on_open_taxonomy

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, highlightthickness=0)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")

        form = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=form, anchor="nw")

        def _sync_scroll_region(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _sync_form_width(event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        form.bind("<Configure>", _sync_scroll_region)
        canvas.bind("<Configure>", _sync_form_width)

        self._inputs: dict[str, tk.Widget] = {}

        row = 0
        for field in self.READONLY_FIELDS:
            ttk.Label(form, text=field).grid(row=row, column=0, sticky="e", padx=4, pady=4)
            entry = ttk.Entry(form, width=64)
            value = ""
            if initial_data and initial_data.get(field) is not None:
                value = str(initial_data.get(field))
            entry.insert(0, value)
            entry.configure(state="readonly")
            entry.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            self._inputs[field] = entry
            row += 1

        ttk.Label(form, text="Collection Event").grid(row=row, column=0, sticky="e", padx=4, pady=4)
        self.collection_event_var = tk.StringVar(value=collection_event_choices[0][1] if collection_event_choices else "")
        self.collection_event_combo = ttk.Combobox(
            form,
            textvariable=self.collection_event_var,
            values=[label for _, label in collection_event_choices],
            state="readonly",
            width=62,
        )
        self.collection_event_combo.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        if self._selected_collection_event_id is not None:
            for ce_id, label in collection_event_choices:
                if ce_id == self._selected_collection_event_id:
                    self.collection_event_var.set(label)
                    break
        row += 1

        for field in self.EDITABLE_FIELDS:
            ttk.Label(form, text=field).grid(row=row, column=0, sticky="ne", padx=4, pady=4)
            if field in self.TEXT_FIELDS:
                widget = tk.Text(form, width=62, height=4, wrap="word", bd=1, relief="solid", highlightthickness=0)
                if initial_data and initial_data.get(field) is not None:
                    widget.insert("1.0", str(initial_data.get(field)))
                widget.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            else:
                widget = ttk.Entry(form, width=64)
                if initial_data and initial_data.get(field) is not None:
                    widget.insert(0, str(initial_data.get(field)))
                widget.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            self._inputs[field] = widget
            row += 1

        form.columnconfigure(1, weight=1)

        controls = ttk.Frame(outer)
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        controls.columnconfigure(0, weight=1)
        edit_radio = ttk.Radiobutton(controls, text="Edit", variable=self._edit_var, value=1)
        edit_radio.grid(row=0, column=1, padx=(6, 4), sticky="e")
        edit_radio.bind("<Button-1>", self._on_edit_radio_click, add="+")
        button_col = 2
        if callable(self._on_open_field_observations) and isinstance(self._find_id, int):
            ttk.Button(
                controls,
                text="Observations",
                command=self._open_field_observations,
            ).grid(row=0, column=button_col, padx=4, sticky="e")
            button_col += 1
        if callable(self._on_open_taxonomy) and isinstance(self._find_id, int):
            ttk.Button(
                controls,
                text="Taxonomy",
                command=self._open_taxonomy,
            ).grid(row=0, column=button_col, padx=4, sticky="e")
            button_col += 1
        ttk.Button(controls, text="Close", command=self._close).grid(row=0, column=button_col, padx=4, sticky="e")

        self._last_saved_payload = self._collect_payload()
        self._set_edit_mode(self._edit_var.get() == 1)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _collect_payload(self) -> dict[str, object]:
        selected_label = self.collection_event_var.get().strip()
        payload: dict[str, object] = {
            "collection_event_id": self._choice_map.get(selected_label),
        }
        for field in self.EDITABLE_FIELDS:
            widget = self._inputs[field]
            if isinstance(widget, tk.Text):
                payload[field] = widget.get("1.0", "end").strip()
            else:
                payload[field] = widget.get().strip()
        return payload

    def _save_if_changed(self) -> bool:
        payload = self._collect_payload()
        if payload == self._last_saved_payload:
            return True
        should_close = self.on_save(payload)
        if should_close is False:
            return False
        self._last_saved_payload = payload
        if callable(self.on_saved):
            self.on_saved()
        return True

    def _close(self) -> None:
        if not self._save_if_changed():
            return
        self.destroy()

    def _set_edit_mode(self, editable: bool) -> None:
        self.collection_event_combo.configure(state="readonly" if editable else "disabled")
        for field in self.READONLY_FIELDS:
            widget = self._inputs.get(field)
            if widget is None:
                continue
            widget.configure(state="readonly")
        for field in self.EDITABLE_FIELDS:
            widget = self._inputs[field]
            if isinstance(widget, tk.Text):
                widget.configure(state="normal" if editable else "disabled")
            else:
                widget.configure(state="normal" if editable else "readonly")

    def _on_edit_radio_click(self, _event) -> str:
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

    def _open_field_observations(self) -> None:
        if not callable(self._on_open_field_observations) or not isinstance(self._find_id, int):
            return
        if not self._save_if_changed():
            return
        self._on_open_field_observations(self._find_id)

    def _open_taxonomy(self) -> None:
        if not callable(self._on_open_taxonomy) or not isinstance(self._find_id, int):
            return
        if not self._save_if_changed():
            return
        self._on_open_taxonomy(self._find_id)
