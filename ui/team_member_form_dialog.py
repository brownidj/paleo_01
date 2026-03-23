import tkinter as tk
from tkinter import ttk


class TeamMemberFormDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, initial_data: dict[str, str] | None, on_save):
        super().__init__(parent)
        self.title("Team member")
        self.on_save = on_save
        self.resizable(False, False)

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="name").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.name_entry = ttk.Entry(frame, width=40)
        self.name_entry.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frame, text="phone_number").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.phone_entry = ttk.Entry(frame, width=40)
        self.phone_entry.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frame, text="institution").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        self.institution_entry = ttk.Entry(frame, width=40)
        self.institution_entry.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frame, text="active").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        self.active_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, variable=self.active_var).grid(row=3, column=1, sticky="w", padx=4, pady=4)

        if initial_data:
            self.name_entry.insert(0, str(initial_data.get("name", "")))
            self.phone_entry.insert(0, str(initial_data.get("phone_number", "")))
            self.institution_entry.insert(0, str(initial_data.get("institution", "")))
            self.active_var.set(bool(initial_data.get("active", 0)))

        btns = ttk.Frame(frame)
        btns.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)

        self.transient(parent)
        self.grab_set()

    def _save(self) -> None:
        payload = {
            "name": self.name_entry.get().strip(),
            "phone_number": self.phone_entry.get().strip(),
            "institution": self.institution_entry.get().strip(),
            "active": self.active_var.get(),
        }
        should_close = self.on_save(payload)
        if should_close is False:
            return
        self.destroy()
