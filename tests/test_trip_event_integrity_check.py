import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.check_trip_event_integrity import collect_integrity_metrics, enable_foreign_keys, has_violations


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE Trips (id INTEGER PRIMARY KEY, trip_name TEXT)")
    conn.execute(
        """
        CREATE TABLE CollectionEvents (
            id INTEGER PRIMARY KEY,
            trip_id INTEGER,
            location_id INTEGER,
            event_year INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE Finds (
            id INTEGER PRIMARY KEY,
            trip_id INTEGER,
            collection_event_id INTEGER
        )
        """
    )


class TestTripEventIntegrityCheck(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        Path(path).unlink(missing_ok=True)
        self.db_path = path

    def tearDown(self):
        Path(self.db_path).unlink(missing_ok=True)

    def test_collect_integrity_metrics_clean(self):
        conn = sqlite3.connect(self.db_path)
        try:
            _init_schema(conn)
            conn.execute("INSERT INTO Trips (id, trip_name) VALUES (1, 'Trip 1')")
            conn.execute(
                "INSERT INTO CollectionEvents (id, trip_id, location_id, event_year) VALUES (10, 1, 100, 2001)"
            )
            conn.execute("INSERT INTO Finds (id, trip_id, collection_event_id) VALUES (1000, 1, 10)")
            conn.commit()

            fk_on = enable_foreign_keys(conn)
            metrics = collect_integrity_metrics(conn)
        finally:
            conn.close()

        self.assertTrue(fk_on)
        self.assertEqual(
            metrics,
            {
                "finds_without_event": 0,
                "events_without_trip": 0,
                "find_event_trip_mismatch": 0,
                "mixed_trip_events": 0,
            },
        )
        self.assertFalse(has_violations(metrics))

    def test_collect_integrity_metrics_detects_all_violation_types(self):
        conn = sqlite3.connect(self.db_path)
        try:
            _init_schema(conn)
            conn.executemany(
                "INSERT INTO Trips (id, trip_name) VALUES (?, ?)",
                [(1, "Trip 1"), (2, "Trip 2")],
            )
            # One event without trip.
            conn.execute("INSERT INTO CollectionEvents (id, trip_id, location_id, event_year) VALUES (10, NULL, 100, 2001)")
            # One event with trip, used by mixed-trip/mismatch finds.
            conn.execute("INSERT INTO CollectionEvents (id, trip_id, location_id, event_year) VALUES (20, 1, 101, 2002)")
            # Find without event.
            conn.execute("INSERT INTO Finds (id, trip_id, collection_event_id) VALUES (1000, 1, NULL)")
            # Mismatch + mixed-trip event: same collection_event_id with different trip_ids.
            conn.execute("INSERT INTO Finds (id, trip_id, collection_event_id) VALUES (1001, 1, 20)")
            conn.execute("INSERT INTO Finds (id, trip_id, collection_event_id) VALUES (1002, 2, 20)")
            conn.commit()

            metrics = collect_integrity_metrics(conn)
        finally:
            conn.close()

        self.assertEqual(metrics["finds_without_event"], 1)
        self.assertEqual(metrics["events_without_trip"], 1)
        self.assertEqual(metrics["find_event_trip_mismatch"], 1)
        self.assertEqual(metrics["mixed_trip_events"], 1)
        self.assertTrue(has_violations(metrics))


if __name__ == "__main__":
    unittest.main()
