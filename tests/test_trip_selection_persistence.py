import tempfile
import unittest
from pathlib import Path

from ui.planning_phase_window import PlanningPhaseWindow


class _FakeTree:
    def __init__(self, children: list[str], names: dict[str, str] | None = None):
        self._children = tuple(children)
        self._selection: tuple[str, ...] = ()
        self.focus_iid: str | None = None
        self.seen_iid: str | None = None
        self._names = names or {str(iid): f"Trip {iid}" for iid in children}

    def get_children(self):
        return self._children

    def selection_set(self, iid):
        self._selection = (str(iid),)

    def selection(self):
        return self._selection

    def focus(self, iid):
        self.focus_iid = str(iid)

    def see(self, iid):
        self.seen_iid = str(iid)

    def item(self, iid, option=None):
        if option == "values":
            return (self._names.get(str(iid), ""),)
        return {"values": (self._names.get(str(iid), ""),)}


class TestTripSelectionPersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "app_state.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_window(self) -> PlanningPhaseWindow:
        window = PlanningPhaseWindow.__new__(PlanningPhaseWindow)
        window._state_path = self.state_path
        window._last_selected_trip_id = None
        window._last_selected_trip_name = None
        window._suspend_trip_selection_persist = False
        return window

    def test_save_and_load_last_selected_trip_id(self):
        window = self._make_window()
        window._save_last_selected_trip_state(42, "Trip 42")
        self.assertEqual(window._load_last_selected_trip_state(), (42, "Trip 42"))

        window._save_last_selected_trip_state(None, None)
        self.assertEqual(window._load_last_selected_trip_state(), (None, None))

    def test_restore_selects_persisted_trip_when_present(self):
        window = self._make_window()
        window.trips_tree = _FakeTree(["1", "2", "3"])
        window._last_selected_trip_id = 2

        window._restore_trip_selection()

        self.assertEqual(window.trips_tree.selection(), ("2",))
        self.assertEqual(window.trips_tree.focus_iid, "2")
        self.assertEqual(window.trips_tree.seen_iid, "2")
        self.assertEqual(window._load_last_selected_trip_state()[0], 2)

    def test_restore_falls_back_to_first_trip_when_missing(self):
        window = self._make_window()
        window.trips_tree = _FakeTree(["10", "20"])
        window._last_selected_trip_id = 999

        window._restore_trip_selection()

        self.assertEqual(window.trips_tree.selection(), ("10",))
        self.assertEqual(window._load_last_selected_trip_state()[0], 10)

    def test_restore_uses_trip_name_fallback_when_id_missing(self):
        window = self._make_window()
        window.trips_tree = _FakeTree(["10", "20"], names={"10": "Alpha", "20": "Beta"})
        window._last_selected_trip_id = 999
        window._last_selected_trip_name = "Beta"

        window._restore_trip_selection()

        self.assertEqual(window.trips_tree.selection(), ("20",))

    def test_on_trip_selected_persists_current_selection(self):
        window = self._make_window()
        tree = _FakeTree(["7"])
        tree.selection_set("7")
        window.trips_tree = tree

        window._on_trip_selected(None)

        self.assertEqual(window._last_selected_trip_id, 7)
        self.assertEqual(window._load_last_selected_trip_state()[0], 7)

    def test_on_close_persists_selection_before_destroy(self):
        window = self._make_window()
        tree = _FakeTree(["12"])
        tree.selection_set("12")
        window.trips_tree = tree
        destroyed = {"called": False}
        window.destroy = lambda: destroyed.__setitem__("called", True)  # type: ignore[method-assign]

        window._on_close()

        self.assertTrue(destroyed["called"])
        self.assertEqual(window._load_last_selected_trip_state()[0], 12)


if __name__ == "__main__":
    unittest.main()
