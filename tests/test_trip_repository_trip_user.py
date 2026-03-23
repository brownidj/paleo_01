import sqlite3
import unittest
from contextlib import closing

from tests._repo_test_base import RepoTestCase


class TestTripRepositoryTripUser(RepoTestCase):
    def test_create_and_fetch_trip(self):
        row_id = self.repo.create_trip(
            {
                "trip_name": "Test Trip",
                "location": "Queensland, AU",
            }
        )
        trip = self.repo.get_trip(row_id)
        self.assertIsNotNone(trip)
        self.assertEqual(trip["trip_name"], "Test Trip")
        self.assertEqual(trip["id"], row_id)

    def test_list_active_team_members(self):
        active = self.repo.list_active_team_members()
        self.assertEqual(active, ["Alice", "Carol"])

    def test_list_users_active_group_and_last_name_order(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO Team_members (name, phone_number, active) VALUES (?, ?, ?)",
                ("Zoe Adams", "0061-412-345-678", 1),
            )
            conn.execute(
                "INSERT INTO Team_members (name, phone_number, active) VALUES (?, ?, ?)",
                ("Aaron Brown", "0061-412-345-678", 1),
            )
            conn.execute(
                "INSERT INTO Team_members (name, phone_number, active) VALUES (?, ?, ?)",
                ("Ivy Aaron", "0061-412-345-678", 0),
            )
            conn.commit()

        team_members = self.repo.list_team_members()
        names = [tm["name"] for tm in team_members]
        actives = [tm["active"] for tm in team_members]

        first_inactive_idx = next((i for i, v in enumerate(actives) if v == 0), len(actives))
        self.assertTrue(all(v == 1 for v in actives[:first_inactive_idx]))
        self.assertTrue(all(v == 0 for v in actives[first_inactive_idx:]))

        active_names = names[:first_inactive_idx]
        self.assertEqual(active_names, ["Zoe Adams", "Alice", "Aaron Brown", "Carol"])


if __name__ == "__main__":
    unittest.main()
