from tkinter import ttk

from repository.trip_repository import TripRepository
from ui.trip_filter_tree_tab import TripFilterTreeTab


class CollectionEventsTab(TripFilterTreeTab):
    LIST_COLUMNS = ("collection_name", "location_name", "find_count")

    def __init__(self, parent, repo: TripRepository):
        widths = {
            "collection_name": 260,
            "location_name": 260,
            "find_count": 80,
        }
        super().__init__(parent, repo, self.LIST_COLUMNS, widths, repo.list_collection_events)
        style = ttk.Style(self)
        style.configure("CollectionEvents.Treeview.Heading", font=("Helvetica", 10, "bold"))
        self.tree.configure(style="CollectionEvents.Treeview")
        self.tree.heading("collection_name", text="Name")
        self.tree.heading("location_name", text="Location")
        self.tree.heading("find_count", text="Finds")
        self.tree.column("find_count", anchor="center")

    def load_collection_events(self) -> None:
        self.load_rows()
