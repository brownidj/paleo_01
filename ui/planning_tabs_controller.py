from tkinter import ttk
from typing import Callable

from repository.trip_repository import TripRepository
from ui.collection_events_tab import CollectionEventsTab
from ui.finds_tab import FindsTab
from ui.geology_tab import GeologyTab
from ui.location_tab import LocationTab
from ui.team_members_tab import TeamMembersTab


class PlanningTabsController:
    def __init__(self, parent, repo: TripRepository, on_tab_changed: Callable):
        self.tabs = ttk.Notebook(parent)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)

        self.trips_tab = ttk.Frame(self.tabs)
        self.location_tab = LocationTab(self.tabs, repo)
        self.geology_tab = GeologyTab(self.tabs, repo)
        self.collection_events_tab = CollectionEventsTab(self.tabs, repo)
        self.finds_tab = FindsTab(self.tabs, repo)
        self.collection_plan_tab = ttk.Frame(self.tabs)
        self.team_members_tab = TeamMembersTab(self.tabs, repo)

        self.tabs.add(self.trips_tab, text="Trips")
        self.tabs.add(self.location_tab, text="Location")
        self.tabs.add(self.collection_plan_tab, text="Collection Plan")
        self.tabs.add(self.collection_events_tab, text="Collection Events")
        self.tabs.add(self.finds_tab, text="Finds")
        self.tabs.add(self.team_members_tab, text="Team Members")
        self.tabs.add(self.geology_tab, text="Geology")
        self.tabs.bind("<<NotebookTabChanged>>", on_tab_changed)

    def build_collection_plan_placeholder(self) -> None:
        ttk.Label(self.collection_plan_tab, text="Scaffolded tab. Data form coming next.").pack(pady=(16, 0))

    def load_initial_tab_data(self, load_trips: Callable[[], None]) -> None:
        load_trips()
        self.location_tab.load_locations()
        self.geology_tab.load_geology()
        self.collection_events_tab.load_collection_events()
        self.finds_tab.load_finds()
        self.team_members_tab.load_team_members()
