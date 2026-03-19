import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ui.ui_services import UIService

class MainWindow(tk.Tk):
    def __init__(self, ui_service: UIService):
        super().__init__()
        self.ui_service = ui_service
        self.title("Paleo_01 Field Recorder")
        self.geometry("800x600")
        
        # Style
        self.style = ttk.Style()
        self.style.configure("TButton", padding=10, font=('Helvetica', 12))
        self.style.configure("TLabel", font=('Helvetica', 11))
        self.style.configure("Header.TLabel", font=('Helvetica', 14, 'bold'))

        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True, padx=10, pady=10)

        self.current_view = None
        self.show_mission_list()

    def clear_view(self):
        if self.current_view:
            self.current_view.destroy()

    def show_mission_list(self):
        self.clear_view()
        from ui.mission_views import MissionListView
        self.current_view = MissionListView(self.container, self)
        self.current_view.pack(fill="both", expand=True)

    def show_mission_detail(self, mission=None):
        self.clear_view()
        from ui.mission_views import MissionDetailView
        self.current_view = MissionDetailView(self.container, self, mission)
        self.current_view.pack(fill="both", expand=True)

    def show_locality_list(self, mission_id):
        self.clear_view()
        from ui.locality_views import LocalityListView
        self.current_view = LocalityListView(self.container, self, mission_id)
        self.current_view.pack(fill="both", expand=True)

    def show_locality_detail(self, mission_id, locality=None):
        self.clear_view()
        from ui.locality_views import LocalityDetailView
        self.current_view = LocalityDetailView(self.container, self, mission_id, locality)
        self.current_view.pack(fill="both", expand=True)

    def show_specimen_detail(self, locality_id, specimen=None):
        self.clear_view()
        from ui.specimen_views import SpecimenDetailView
        self.current_view = SpecimenDetailView(self.container, self, locality_id, specimen)
        self.current_view.pack(fill="both", expand=True)
