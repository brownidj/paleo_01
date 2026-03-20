import unittest
import sqlite3

from ui.ui_services import UIService, UIServiceError


class FakeDb:
    def get_mission(self, mission_id):
        return {"id": mission_id, "name": "M"}

    def get_locality(self, locality_id):
        return {"id": locality_id, "mission_id": "mission-1"}

    def get_specimen(self, spec_id):
        return {"id": spec_id, "name": "S"}


class FailingDb:
    def list_missions(self):
        raise sqlite3.OperationalError("boom")


class TestUIService(unittest.TestCase):
    def setUp(self):
        self.service = UIService(FakeDb())

    def test_get_mission_passthrough(self):
        mission = self.service.get_mission("mission-1")
        self.assertEqual(mission["id"], "mission-1")

    def test_get_locality_passthrough(self):
        locality = self.service.get_locality("locality-1")
        self.assertEqual(locality["mission_id"], "mission-1")

    def test_get_specimen_passthrough(self):
        specimen = self.service.get_specimen("specimen-1")
        self.assertEqual(specimen["id"], "specimen-1")

    def test_wraps_sqlite_errors(self):
        service = UIService(FailingDb())
        with self.assertRaises(UIServiceError):
            service.get_all_missions()


if __name__ == "__main__":
    unittest.main()
