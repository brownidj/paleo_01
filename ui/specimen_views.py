import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from ui.photo_viewer import PhotoViewer

class SpecimenDetailView(ttk.Frame):
    def __init__(self, parent, controller, locality_id, specimen=None):
        super().__init__(parent)
        self.controller = controller
        self.ui_service = controller.ui_service
        self.locality_id = locality_id
        self.specimen = specimen

        title = "Edit Specimen" if specimen else "New Specimen"
        ttk.Label(self, text=title, style="Header.TLabel").grid(row=0, column=0, columnspan=2, pady=10)

        # Form fields
        self.fields = {}
        row = 1
        labels = [("Name", "name"), ("Description", "description"), 
                  ("Latitude", "latitude"), ("Longitude", "longitude"), ("Altitude", "altitude")]

        for label_text, field_name in labels:
            ttk.Label(self, text=label_text).grid(row=row, column=0, sticky="e", padx=5, pady=2)
            entry = ttk.Entry(self)
            entry.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            if specimen and specimen.get(field_name) is not None:
                entry.insert(0, str(specimen[field_name]))
            self.fields[field_name] = entry
            row += 1

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Save", command=self.save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.back_to_locality).pack(side="left", padx=5)
        
        if specimen:
            ttk.Button(btn_frame, text="Delete", command=self.delete_specimen).pack(side="left", padx=5)

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

    def back_to_locality(self):
        locality = self.ui_service.get_locality(self.locality_id)
        if not locality:
            messagebox.showerror("Error", "Locality not found")
            return
        self.controller.show_locality_detail(locality["mission_id"], locality)

    def load_photos(self):
        if not self.specimen: return
        self.photo_list.delete(0, tk.END)
        self.photos = self.ui_service.get_photos(self.specimen["id"])
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
            self.ui_service.add_photo(self.specimen["id"], "specimen", file_path, "Field photo")
            self.load_photos()

    def save(self):
        data = {}
        try:
            for field, entry in self.fields.items():
                val = entry.get()
                if field in ["latitude", "longitude", "altitude"]:
                    data[field] = float(val) if val else 0.0
                else:
                    data[field] = val
        except ValueError:
            messagebox.showerror("Error", "Invalid numeric value")
            return

        if self.specimen:
            self.ui_service.update_specimen(self.specimen["id"], data)
        else:
            data["locality_id"] = self.locality_id
            self.ui_service.create_specimen(**data)
        
        self.back_to_locality()

    def delete_specimen(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this specimen?"):
            self.ui_service.delete_specimen(self.specimen["id"])
            self.back_to_locality()
