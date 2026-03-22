import os
import sqlite3
import tempfile
import unittest
from contextlib import closing

from scripts.db_bootstrap import create_locations_table, create_users_table
from trip_repository import TripRepository


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_path = path
        self.repo = TripRepository(self.db_path)
        self.repo.ensure_trips_table()
        with closing(sqlite3.connect(self.db_path)) as conn:
            create_users_table(conn)
            create_locations_table(conn)
            conn.executemany(
                "INSERT INTO Users (name, phone_number, active) VALUES (?, ?, ?)",
                [
                    ("Alice", "0061-412-345-678", 1),
                    ("Bob", "0061-412-345-678", 0),
                    ("Carol", "0061-412-345-678", 1),
                ],
            )
            conn.commit()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
