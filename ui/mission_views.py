import tkinter as tk
from tkinter import ttk, messagebox

class MissionListView(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.ui_service = controller.ui_service

        ttk.Label(self, text="Missions", style="Header.TLabel").pack(pady=10)

        # Listbox for missions
        self.tree = ttk.Treeview(self, columns=("Name", "Date"), show="headings")
        self.tree.heading("Name", text="Name")
        self.tree.heading("Date", text="Date")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tree.bind("<Double-1>", self.on_double_click)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=10)
        
        ttk.Button(btn_frame, text="New Mission", command=lambda: self.controller.show_mission_detail()).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.load_data).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Edit Selected", command=self.edit_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="View Localities", command=self.view_localities).pack(side="left", padx=5)

        self.load_data()

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        missions = self.ui_service.get_all_missions()
        for m in missions:
            self.tree.insert("", "end", iid=m["id"], values=(m["name"], m["date"]))

    def on_double_click(self, event):
        self.view_localities()

    def edit_selected(self):
        selected = self.tree.selection()
        if not selected: return
        mission_id = selected[0]
        mission = self.ui_service.get_mission(mission_id)
        self.controller.show_mission_detail(mission)

    def view_localities(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a mission first")
            return
        mission_id = selected[0]
        self.controller.show_locality_list(mission_id)

class MissionDetailView(ttk.Frame):
    def __init__(self, parent, controller, mission=None):
        super().__init__(parent)
        self.controller = controller
        self.ui_service = controller.ui_service
        self.mission = mission

        title = "Edit Mission" if mission else "New Mission"
        ttk.Label(self, text=title, style="Header.TLabel").grid(row=0, column=0, columnspan=2, pady=10)

        # Form fields
        self.fields = {}
        row = 1
        labels = [("Name", "name"), ("Date (YYYY-MM-DD)", "date")]

        for label_text, field_name in labels:
            ttk.Label(self, text=label_text).grid(row=row, column=0, sticky="e", padx=5, pady=2)
            entry = ttk.Entry(self)
            entry.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            if mission and mission.get(field_name) is not None:
                entry.insert(0, str(mission[field_name]))
            self.fields[field_name] = entry
            row += 1

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Save", command=self.save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.controller.show_mission_list).pack(side="left", padx=5)
        
        if mission:
            ttk.Button(btn_frame, text="Delete", command=self.delete_mission).pack(side="left", padx=5)

    def save(self):
        data = {f: e.get() for f, e in self.fields.items()}
        if not data["name"] or not data["date"]:
            messagebox.showerror("Error", "Name and Date are required")
            return

        if self.mission:
            self.ui_service.update_mission(self.mission["id"], data)
        else:
            self.ui_service.create_mission(**data)
        
        self.controller.show_mission_list()

    def delete_mission(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this mission?"):
            self.ui_service.delete_mission(self.mission["id"])
            self.controller.show_mission_list()
