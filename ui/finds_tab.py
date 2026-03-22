from repository.trip_repository import TripRepository
from ui.trip_filter_tree_tab import TripFilterTreeTab


class FindsTab(TripFilterTreeTab):
    LIST_COLUMNS = (
        "location_name",
        "collection_subset",
        "trip_name",
        "source_occurrence_no",
        "accepted_name",
    )

    def __init__(self, parent, repo: TripRepository):
        widths = {
            "location_name": 220,
            "collection_subset": 130,
            "trip_name": 220,
            "source_occurrence_no": 120,
            "accepted_name": 220,
        }
        super().__init__(parent, repo, self.LIST_COLUMNS, widths, repo.list_finds)

    def load_finds(self) -> None:
        self.load_rows()
