from repository.trip_repository import TripRepository
from ui.trip_filter_tree_tab import TripFilterTreeTab


class CollectionEventsTab(TripFilterTreeTab):
    LIST_COLUMNS = ("location_name", "collection_name", "find_count")

    def __init__(self, parent, repo: TripRepository):
        widths = {
            "location_name": 260,
            "collection_name": 260,
            "find_count": 80,
        }
        super().__init__(parent, repo, self.LIST_COLUMNS, widths, repo.list_collection_events)

    def load_collection_events(self) -> None:
        self.load_rows()
