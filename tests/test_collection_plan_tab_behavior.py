from datetime import date, timedelta
import tkinter as tk
import unittest
from tkinter import ttk

from ui.planning_tabs_controller import PlanningTabsController


class _FakeRepo:
    def __init__(self):
        self.events_by_trip: dict[int, list[dict[str, object]]] = {
            1: [{"id": 101, "collection_name": "CE Zulu"}],
            2: [],
            3: [{"id": 301, "collection_name": "CE Beta"}],
            4: [],
            5: [],
        }

    def list_trips(self):
        today = date.today()
        tomorrow = (today + timedelta(days=1)).isoformat()
        yesterday = (today - timedelta(days=1)).isoformat()
        return [
            {"id": 1, "trip_name": "Zulu", "start_date": "2024-01-01", "end_date": tomorrow},
            {"id": 2, "trip_name": "Alpha", "start_date": "2025-04-10", "end_date": ""},
            {"id": 3, "trip_name": "Beta", "start_date": "2025-04-10", "end_date": None},
            {"id": 4, "trip_name": "No Date", "start_date": None, "end_date": tomorrow},
            {"id": 5, "trip_name": "Finished", "start_date": "2026-01-01", "end_date": yesterday},
        ]

    def list_collection_events(self, _trip_id=None):
        if _trip_id is None:
            merged: list[dict[str, object]] = []
            for rows in self.events_by_trip.values():
                merged.extend(rows)
            return merged
        return list(self.events_by_trip.get(int(_trip_id), []))

    def list_finds(self, _trip_id=None):
        return []

    def get_trip(self, trip_id: int):
        for row in self.list_trips():
            if int(row["id"]) == trip_id:
                return {
                    "id": row["id"],
                    "trip_name": row["trip_name"],
                    "start_date": row["start_date"],
                    "location": f"Location for {row['trip_name']}",
                }
        return None

    def create_collection_event_for_trip(self, trip_id: int, collection_name: str):
        trip_key = int(trip_id)
        events = self.events_by_trip.setdefault(trip_key, [])
        new_id = len(events) + 1000 + trip_key
        events.insert(0, {"id": new_id, "collection_name": collection_name})
        return new_id

    def update_collection_event_name(self, collection_event_id: int, collection_name: str):
        target_id = int(collection_event_id)
        for events in self.events_by_trip.values():
            for event in events:
                if int(event["id"]) == target_id:
                    event["collection_name"] = collection_name
                    return
        raise ValueError("Collection Event does not exist.")


class _FakeRepoDuplicateTripNames(_FakeRepo):
    def list_trips(self):
        today = date.today()
        tomorrow = (today + timedelta(days=1)).isoformat()
        return [
            {"id": 10, "trip_name": "Alpha", "start_date": "2025-05-01", "end_date": tomorrow},
            {"id": 11, "trip_name": "Alpha", "start_date": "2024-01-01", "end_date": tomorrow},
            {"id": 12, "trip_name": "Alpha", "start_date": "2026-02-20", "end_date": tomorrow},
            {"id": 13, "trip_name": "Beta", "start_date": "2025-07-07", "end_date": tomorrow},
        ]


class TestCollectionPlanTabBehavior(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable in test environment: {exc}")

    def tearDown(self):
        if hasattr(self, "root"):
            try:
                self.root.destroy()
            except tk.TclError:
                pass

    def test_trips_sorted_by_trip_name_then_start_and_new_plan_requires_selection(self):
        controller = PlanningTabsController(self.root, _FakeRepo(), lambda _event: None)
        controller.build_collection_plan_placeholder()
        assert controller.collection_plan_tree is not None
        assert controller.collection_plan_new_button is not None

        self.assertEqual(str(controller.collection_plan_new_button.cget("state")), "disabled")

        rows = [controller.collection_plan_tree.item(iid, "values") for iid in controller.collection_plan_tree.get_children()]
        self.assertEqual(
            rows,
            [
                ("Alpha", "2025-04-10", ""),
                ("Beta", "2025-04-10", "CE Beta"),
                ("No Date", "", ""),
                ("Zulu", "2024-01-01", "CE Zulu"),
            ],
        )

        first_iid = controller.collection_plan_tree.get_children()[0]
        controller.collection_plan_tree.selection_set(first_iid)
        controller._on_collection_plan_selected(None)
        self.assertEqual(str(controller.collection_plan_new_button.cget("state")), "normal")

    def test_new_plan_modal_shows_trip_start_and_location(self):
        controller = PlanningTabsController(self.root, _FakeRepo(), lambda _event: None)
        controller.build_collection_plan_placeholder()
        assert controller.collection_plan_tree is not None

        first_iid = controller.collection_plan_tree.get_children()[0]
        controller.collection_plan_tree.selection_set(first_iid)
        controller._on_collection_plan_selected(None)

        controller._on_new_plan()
        dialog = self.root.grab_current()
        self.assertIsNotNone(dialog)
        assert dialog is not None
        self.assertIsInstance(dialog, tk.Toplevel)
        self.assertEqual(dialog.title(), "New Plan")

        label_texts: list[str] = []

        def _collect_labels(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Label):
                    label_texts.append(str(child.cget("text")))
                _collect_labels(child)

        _collect_labels(dialog)
        self.assertIn("Trip", label_texts)
        self.assertIn("Start", label_texts)
        self.assertIn("Location", label_texts)
        self.assertIn("Collection Event", label_texts)
        self.assertIn("New name", label_texts)
        self.assertIn("Alpha", label_texts)
        self.assertIn("2025-04-10", label_texts)
        self.assertIn("Location for Alpha", label_texts)

        combo_widgets: list[ttk.Combobox] = []

        def _collect_comboboxes(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Combobox):
                    combo_widgets.append(child)
                _collect_comboboxes(child)

        _collect_comboboxes(dialog)
        self.assertEqual(len(combo_widgets), 1)
        combo_values = tuple(str(v) for v in combo_widgets[0].cget("values"))
        self.assertEqual(combo_values[0], "[+]")
        dialog.destroy()

    def test_create_collection_event_from_modal_updates_collection_plan_row(self):
        controller = PlanningTabsController(self.root, _FakeRepo(), lambda _event: None)
        controller.build_collection_plan_placeholder()
        assert controller.collection_plan_tree is not None

        first_iid = controller.collection_plan_tree.get_children()[0]
        controller.collection_plan_tree.selection_set(first_iid)
        controller._on_collection_plan_selected(None)
        controller._on_new_plan()
        dialog = self.root.grab_current()
        self.assertIsNotNone(dialog)
        assert dialog is not None

        entry_widgets: list[ttk.Entry] = []

        def _collect_entries(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Entry) and not isinstance(child, ttk.Combobox):
                    entry_widgets.append(child)
                _collect_entries(child)

        _collect_entries(dialog)
        self.assertEqual(len(entry_widgets), 1)
        entry = entry_widgets[0]
        entry.insert(0, "CE Alpha New")

        create_buttons: list[ttk.Button] = []

        def _collect_buttons(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button) and str(child.cget("text")) == "Create":
                    create_buttons.append(child)
                _collect_buttons(child)

        _collect_buttons(dialog)
        self.assertEqual(len(create_buttons), 1)
        create_buttons[0].invoke()

        rows = [controller.collection_plan_tree.item(iid, "values") for iid in controller.collection_plan_tree.get_children()]
        self.assertEqual(rows[0], ("Alpha", "2025-04-10", "CE Alpha New"))

    def test_create_collection_event_from_existing_dropdown_value(self):
        controller = PlanningTabsController(self.root, _FakeRepo(), lambda _event: None)
        controller.build_collection_plan_placeholder()
        assert controller.collection_plan_tree is not None

        first_iid = controller.collection_plan_tree.get_children()[0]
        controller.collection_plan_tree.selection_set(first_iid)
        controller._on_collection_plan_selected(None)
        controller._on_new_plan()
        dialog = self.root.grab_current()
        self.assertIsNotNone(dialog)
        assert dialog is not None

        combo_widgets: list[ttk.Combobox] = []

        def _collect_comboboxes(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Combobox):
                    combo_widgets.append(child)
                _collect_comboboxes(child)

        _collect_comboboxes(dialog)
        self.assertEqual(len(combo_widgets), 1)
        combo = combo_widgets[0]
        combo.set("CE Beta")
        combo.event_generate("<<ComboboxSelected>>")

        create_buttons: list[ttk.Button] = []

        def _collect_buttons(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button) and str(child.cget("text")) == "Create":
                    create_buttons.append(child)
                _collect_buttons(child)

        _collect_buttons(dialog)
        self.assertEqual(len(create_buttons), 1)
        create_buttons[0].invoke()

        rows = [controller.collection_plan_tree.item(iid, "values") for iid in controller.collection_plan_tree.get_children()]
        self.assertEqual(rows[0], ("Alpha", "2025-04-10", "CE Beta"))

    def test_double_click_collection_plan_item_allows_edit(self):
        controller = PlanningTabsController(self.root, _FakeRepo(), lambda _event: None)
        controller.build_collection_plan_placeholder()
        assert controller.collection_plan_tree is not None

        beta_iid = next(
            iid
            for iid in controller.collection_plan_tree.get_children()
            if controller.collection_plan_tree.item(iid, "values")[0] == "Beta"
        )
        controller.collection_plan_tree.selection_set(beta_iid)
        controller._on_collection_plan_double_click(None)
        dialog = self.root.grab_current()
        self.assertIsNotNone(dialog)
        assert dialog is not None
        self.assertEqual(dialog.title(), "Edit Plan")

        combo_widgets: list[ttk.Combobox] = []

        def _collect_comboboxes(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Combobox):
                    combo_widgets.append(child)
                _collect_comboboxes(child)

        _collect_comboboxes(dialog)
        self.assertEqual(len(combo_widgets), 1)
        combo = combo_widgets[0]
        combo.set("[+]")
        combo.event_generate("<<ComboboxSelected>>")

        entry_widgets: list[ttk.Entry] = []

        def _collect_entries(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Entry) and not isinstance(child, ttk.Combobox):
                    entry_widgets.append(child)
                _collect_entries(child)

        _collect_entries(dialog)
        self.assertEqual(len(entry_widgets), 1)
        entry = entry_widgets[0]
        entry.insert(0, "CE Beta Edited")

        save_buttons: list[ttk.Button] = []

        def _collect_buttons(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button) and str(child.cget("text")) == "Save":
                    save_buttons.append(child)
                _collect_buttons(child)

        _collect_buttons(dialog)
        self.assertEqual(len(save_buttons), 1)
        save_buttons[0].invoke()

        rows = [controller.collection_plan_tree.item(iid, "values") for iid in controller.collection_plan_tree.get_children()]
        beta_row = next(row for row in rows if row[0] == "Beta")
        self.assertEqual(beta_row, ("Beta", "2025-04-10", "CE Beta Edited"))

    def test_duplicate_trip_names_order_by_start_date_as_tiebreaker(self):
        controller = PlanningTabsController(self.root, _FakeRepoDuplicateTripNames(), lambda _event: None)
        controller.build_collection_plan_placeholder()
        assert controller.collection_plan_tree is not None

        rows = [controller.collection_plan_tree.item(iid, "values") for iid in controller.collection_plan_tree.get_children()]
        self.assertEqual(
            rows,
            [
                ("Alpha", "2024-01-01", ""),
                ("Alpha", "2025-05-01", ""),
                ("Alpha", "2026-02-20", ""),
                ("Beta", "2025-07-07", ""),
            ],
        )


if __name__ == "__main__":
    unittest.main()
