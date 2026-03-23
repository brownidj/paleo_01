import tkinter as tk
from tkinter import ttk


class TeamEditorDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        active_users: list[str],
        initial_team: list[str],
        trip_name: str,
        on_save,
    ):
        super().__init__(parent)
        self.title("Edit Team")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.on_save = on_save

        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)
        lists = ttk.Frame(container)
        lists.pack(fill="both", expand=True)

        source_frame = ttk.Frame(lists)
        source_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ttk.Label(source_frame, text="Active team members").pack(anchor="w", pady=(0, 2))
        ttk.Label(
            source_frame,
            text=f"Trip: {trip_name}",
        ).pack(anchor="w", pady=(0, 4))
        self.source_list = tk.Listbox(source_frame, selectmode=tk.EXTENDED, height=10)
        self.source_list.pack(fill="both", expand=True)
        for name in active_users:
            self.source_list.insert(tk.END, name)

        target_frame = ttk.Frame(lists)
        target_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(target_frame, text="Team").pack(anchor="w", pady=(0, 4))
        self.target_list = tk.Listbox(target_frame, selectmode=tk.EXTENDED, height=10)
        self.target_list.pack(fill="both", expand=True)
        for name in initial_team:
            self.target_list.insert(tk.END, name)

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(8, 0))
        ttk.Button(controls, text="Add selected", command=self._add_selected).pack(side="left", padx=4)
        ttk.Button(controls, text="Remove selected", command=self._remove_selected).pack(side="left", padx=4)

        btns = ttk.Frame(container)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left", padx=4)

        # Position this modal directly below the parent Trip modal.
        parent.update_idletasks()
        self.update_idletasks()
        x = parent.winfo_rootx()
        y = parent.winfo_rooty() + parent.winfo_height() + 8
        self.geometry(f"+{x}+{y}")

    def _add_selected(self) -> None:
        selected_names = [self.source_list.get(i) for i in self.source_list.curselection()]
        existing = set(self.target_list.get(0, tk.END))
        for name in selected_names:
            if name not in existing:
                self.target_list.insert(tk.END, name)
                existing.add(name)

    def _remove_selected(self) -> None:
        for idx in reversed(self.target_list.curselection()):
            self.target_list.delete(idx)

    def _save(self) -> None:
        names = [line.strip() for line in self.target_list.get(0, tk.END) if line.strip()]
        self.on_save(names)
        self.destroy()
