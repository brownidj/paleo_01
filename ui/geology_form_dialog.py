import tkinter as tk
from tkinter import ttk


class GeologyFormDialog(tk.Toplevel):
    FIELDS = [
        "source_reference_no",
        "early_interval",
        "late_interval",
        "max_ma",
        "min_ma",
        "environment",
        "geogscale",
        "formation",
        "stratigraphy_group",
        "member",
        "stratscale",
        "stratigraphy_comments",
        "geology_comments",
        "geoplate",
        "paleomodel",
        "paleolat",
        "paleolng",
    ]

    def __init__(self, parent: tk.Widget, initial_data: dict[str, object], on_save):
        super().__init__(parent)
        self.title("Edit Geology")
        self.on_save = on_save
        self.resizable(False, False)
        self.entries: dict[str, ttk.Entry] = {}
        self.lith_entries: dict[tuple[int, str], ttk.Entry] = {}

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=f"location: {initial_data.get('location_name') or 'n/a'}").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 8)
        )

        row_i = 1
        for field in self.FIELDS:
            ttk.Label(frame, text=field).grid(row=row_i, column=0, sticky="e", padx=4, pady=3)
            entry = ttk.Entry(frame, width=40)
            entry.grid(row=row_i, column=1, sticky="w", padx=4, pady=3)
            value = initial_data.get(field)
            if value is not None:
                entry.insert(0, str(value))
            self.entries[field] = entry
            row_i += 1

        lith_by_slot: dict[int, dict[str, object]] = {}
        for row in initial_data.get("lithology_rows", []) or []:
            if isinstance(row, dict) and row.get("slot") in {1, 2}:
                lith_by_slot[int(row["slot"])] = row

        for slot in (1, 2):
            ttk.Label(frame, text=f"lithology slot {slot}", font=("Helvetica", 10, "bold")).grid(
                row=row_i, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 2)
            )
            row_i += 1
            for field in ("lithology", "lithification", "minor_lithology", "lithology_adjectives", "fossils_from"):
                ttk.Label(frame, text=field).grid(row=row_i, column=0, sticky="e", padx=4, pady=3)
                entry = ttk.Entry(frame, width=40)
                entry.grid(row=row_i, column=1, sticky="w", padx=4, pady=3)
                value = (lith_by_slot.get(slot) or {}).get(field)
                if value is not None:
                    entry.insert(0, str(value))
                self.lith_entries[(slot, field)] = entry
                row_i += 1

        btns = ttk.Frame(frame)
        btns.grid(row=row_i, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)

        self.transient(parent)
        self.grab_set()

    def _save(self) -> None:
        payload: dict[str, object] = {field: self.entries[field].get().strip() or None for field in self.FIELDS}
        lith_rows: list[dict[str, object]] = []
        for slot in (1, 2):
            row: dict[str, object] = {"slot": slot}
            for field in ("lithology", "lithification", "minor_lithology", "lithology_adjectives", "fossils_from"):
                row[field] = self.lith_entries[(slot, field)].get().strip() or None
            lith_rows.append(row)
        payload["lithology_rows"] = lith_rows
        should_close = self.on_save(payload)
        if should_close is False:
            return
        self.destroy()
