import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from ui.photo_viewer import PhotoViewer
from ui.ui_services import UIServiceError

class LocalityListView(ttk.Frame):
    def __init__(self, parent, controller, mission_id):
        super().__init__(parent)
        self.controller = controller
        self.ui_service = controller.ui_service
        self.mission_id = mission_id

        ttk.Label(self, text="Localities", style="Header.TLabel").pack(pady=10)

        # Listbox for localities
        self.tree = ttk.Treeview(self, columns=("Name", "Created At"), show="headings")
        self.tree.heading("Name", text="Name")
        self.tree.heading("Created At", text="Created At")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tree.bind("<Double-1>", self.on_double_click)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=10)
        
        ttk.Button(btn_frame, text="Back to Missions", command=self.controller.show_mission_list).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="New Locality", command=lambda: self.controller.show_locality_detail(self.mission_id)).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.load_data).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Edit Selected", command=self.edit_selected).pack(side="left", padx=5)

        self.load_data()

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            localities = self.ui_service.get_localities_for_mission(self.mission_id)
        except UIServiceError as e:
            messagebox.showerror("Error", str(e))
            return
        for loc in localities:
            self.tree.insert("", "end", iid=loc["id"], values=(loc["name"], loc["created_at"]))

    def on_double_click(self, event):
        self.edit_selected()

    def edit_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        loc_id = selected[0]
        try:
            locality = self.ui_service.get_locality(loc_id)
        except UIServiceError as e:
            messagebox.showerror("Error", str(e))
            return
        self.controller.show_locality_detail(self.mission_id, locality)

class LocalityDetailView(ttk.Frame):
    def __init__(self, parent, controller, mission_id, locality=None):
        super().__init__(parent)
        self.controller = controller
        self.ui_service = controller.ui_service
        self.mission_id = mission_id
        self.locality = locality

        title = "Edit Locality" if locality else "New Locality"
        ttk.Label(self, text=title, style="Header.TLabel").grid(row=0, column=0, columnspan=2, pady=10)

        # Form fields
        self.fields = {}
        row = 1
        labels = [("Name", "name"), ("Latitude", "latitude"), ("Longitude", "longitude"), 
                  ("Altitude", "altitude"), ("Lithology", "lithology_text"), 
                  ("Dip", "measured_dip"), ("Dip Direction", "dip_direction")]

        for label_text, field_name in labels:
            ttk.Label(self, text=label_text).grid(row=row, column=0, sticky="e", padx=5, pady=2)
            entry = ttk.Entry(self)
            entry.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            if locality and locality.get(field_name) is not None:
                entry.insert(0, str(locality[field_name]))
            self.fields[field_name] = entry
            row += 1

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Save", command=self.save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=lambda: self.controller.show_locality_list(self.mission_id)).pack(side="left", padx=5)
        
        if locality:
            ttk.Button(btn_frame, text="Delete", command=self.delete_locality).pack(side="left", padx=5)
            
            # Specimens Section
            row += 1
            ttk.Separator(self, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
            row += 1
            ttk.Label(self, text="Specimens", style="Header.TLabel").grid(row=row, column=0, columnspan=2)
            row += 1
            self.spec_tree = ttk.Treeview(self, columns=("Name",), show="headings", height=5)
            self.spec_tree.heading("Name", text="Specimen Name")
            self.spec_tree.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5)
            self.spec_tree.bind("<Double-1>", self.on_specimen_click)
            
            row += 1
            ttk.Button(self, text="Add Specimen", 
                       command=lambda: self.controller.show_specimen_detail(self.locality["id"])).grid(row=row, column=0, columnspan=2, pady=5)
            
            self.load_specimens()

            # Photos Section
            row += 1
            ttk.Separator(self, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
            row += 1
            ttk.Label(self, text="Photos", style="Header.TLabel").grid(row=row, column=0, columnspan=2)
            row += 1
            self.photo_list = tk.Listbox(self, height=5)
            self.photo_list.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5)
            self.photo_list.bind("<Double-1>", self.on_photo_double_click)
            
            row += 1
            btn_photo_frame = ttk.Frame(self)
            btn_photo_frame.grid(row=row, column=0, columnspan=2, pady=5)
            
            ttk.Button(btn_photo_frame, text="Add Photo", command=self.add_photo).pack(side="left", padx=2)
            ttk.Button(btn_photo_frame, text="View Photo", command=self.on_photo_double_click).pack(side="left", padx=2)
            
            self.load_photos()

    def load_specimens(self):
        if not self.locality: return
        for item in self.spec_tree.get_children():
            self.spec_tree.delete(item)
        try:
            specs = self.ui_service.get_specimens_for_locality(self.locality["id"])
        except UIServiceError as e:
            messagebox.showerror("Error", str(e))
            return
        for spec in specs:
            self.spec_tree.insert("", "end", iid=spec["id"], values=(spec["name"],))

    def on_specimen_click(self, event):
        selected = self.spec_tree.selection()
        if not selected: return
        spec_id = selected[0]
        try:
            specimen = self.ui_service.get_specimen(spec_id)
        except UIServiceError as e:
            messagebox.showerror("Error", str(e))
            return
        self.controller.show_specimen_detail(self.locality["id"], specimen)

    def load_photos(self):
        if not self.locality: return
        self.photo_list.delete(0, tk.END)
        try:
            self.photos = self.ui_service.get_photos(self.locality["id"])
        except UIServiceError as e:
            messagebox.showerror("Error", str(e))
            return
        for p in self.photos:
            self.photo_list.insert(tk.END, f"{os.path.basename(p['file_path'])} - {p['caption']}")

    def on_photo_double_click(self, event=None):
        selected = self.photo_list.curselection()
        if not selected:
            return
        photo = self.photos[selected[0]]
        file_path = photo["file_path"]
        
        # Handle cases where path starts with / but is meant to be relative to project root
        if file_path.startswith("/images/"):
            file_path = file_path.lstrip("/")
        
        # Check if it's relative to project root
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.getcwd(), file_path)

        if os.path.exists(file_path):
            PhotoViewer(self, file_path, photo.get("caption", ""))
        else:
            messagebox.showerror("Error", f"File not found: {file_path}")

    def add_photo(self):
        file_path = filedialog.askopenfilename(title="Select Photo", filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if file_path:
            # In a real app we might copy the file to an 'assets' folder
            try:
                self.ui_service.add_photo(self.locality["id"], "locality", file_path, "Locality photo")
            except (UIServiceError, ValueError) as e:
                messagebox.showerror("Error", str(e))
                return
            self.load_photos()

    def save(self):
        data = {}
        try:
            for field, entry in self.fields.items():
                val = entry.get()
                if field in ["latitude", "longitude", "altitude", "measured_dip", "dip_direction"]:
                    data[field] = float(val) if val else 0.0
                else:
                    data[field] = val
        except ValueError:
            messagebox.showerror("Error", "Invalid numeric value")
            return

        if self.locality:
            try:
                self.ui_service.update_locality(self.locality["id"], data)
            except (UIServiceError, ValueError) as e:
                messagebox.showerror("Error", str(e))
                return
        else:
            try:
                self.ui_service.create_locality(mission_id=self.mission_id, **data)
            except UIServiceError as e:
                messagebox.showerror("Error", str(e))
                return
        
        self.controller.show_locality_list(self.mission_id)

    def delete_locality(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this locality?"):
            try:
                self.ui_service.delete_locality(self.locality["id"])
            except UIServiceError as e:
                messagebox.showerror("Error", str(e))
                return
            self.controller.show_locality_list(self.mission_id)
