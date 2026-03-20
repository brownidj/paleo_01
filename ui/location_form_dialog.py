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

    def __init__(self, parent: tk.Widget, initial_data: dict[str, object] | None, on_save):
        super().__init__(parent)
        self.title("Location")
        self.on_save = on_save
        self.resizable(False, False)
        self.entries: dict[str, ttk.Entry] = {}
        self.collection_events: list[dict[str, str]] = []

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)

        for i, field in enumerate(self.FIELDS):
            ttk.Label(frame, text=field).grid(row=i, column=0, sticky="e", padx=4, pady=4)
            entry = ttk.Entry(frame, width=42)
            entry.grid(row=i, column=1, sticky="w", padx=4, pady=4)
            if initial_data and initial_data.get(field) is not None:
                entry.insert(0, str(initial_data.get(field, "")))
            self.entries[field] = entry

        events_row = len(self.FIELDS)
        ttk.Label(frame, text="collection_events").grid(row=events_row, column=0, sticky="ne", padx=4, pady=4)
        events_container = ttk.Frame(frame)
        events_container.grid(row=events_row, column=1, sticky="w", padx=4, pady=4)

        self.events_list = tk.Listbox(events_container, width=48, height=5)
        self.events_list.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))

        ttk.Label(events_container, text="name").grid(row=1, column=0, sticky="w")
        self.collection_name_entry = ttk.Entry(events_container, width=22)
        self.collection_name_entry.grid(row=2, column=0, sticky="w", padx=(0, 6))

        ttk.Label(events_container, text="subset").grid(row=1, column=1, sticky="w")
        self.collection_subset_entry = ttk.Entry(events_container, width=22)
        self.collection_subset_entry.grid(row=2, column=1, sticky="w", padx=(0, 6))

        ttk.Button(events_container, text="Add Event", command=self._add_event).grid(row=2, column=2, sticky="w")
        ttk.Button(events_container, text="Remove Selected", command=self._remove_selected_event).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )

        if initial_data:
            for event in initial_data.get("collection_events", []):
                name = str(event.get("collection_name") or "").strip()
                if not name:
                    continue
                subset = str(event.get("collection_subset") or "").strip()
                self.collection_events.append({"collection_name": name, "collection_subset": subset})
            self._render_events()

        btns = ttk.Frame(frame)
        btns.grid(row=events_row + 1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)

        self.transient(parent)
        self.grab_set()

    def _save(self) -> None:
        payload = {field: entry.get().strip() for field, entry in self.entries.items()}
        payload["collection_events"] = self.collection_events.copy()
        should_close = self.on_save(payload)
        if should_close is False:
            return
        self.destroy()

    def _add_event(self) -> None:
        collection_name = self.collection_name_entry.get().strip()
        if not collection_name:
            return
        collection_subset = self.collection_subset_entry.get().strip()
        self.collection_events.append(
            {
                "collection_name": collection_name,
                "collection_subset": collection_subset,
            }
        )
        self.collection_name_entry.delete(0, tk.END)
        self.collection_subset_entry.delete(0, tk.END)
        self._render_events()

    def _remove_selected_event(self) -> None:
        selected = self.events_list.curselection()
        if not selected:
            return
        index = int(selected[0])
        del self.collection_events[index]
        self._render_events()

    def _render_events(self) -> None:
        self.events_list.delete(0, tk.END)
        for event in self.collection_events:
            name = event.get("collection_name", "")
            subset = event.get("collection_subset", "")
            label = f"{name} | {subset}" if subset else name
            self.events_list.insert(tk.END, label)
