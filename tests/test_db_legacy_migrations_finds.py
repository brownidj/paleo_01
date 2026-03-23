import csv
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.db_bootstrap import SCHEMA_VERSION, initialize_database


class TestDbLegacyMigrationsFinds(unittest.TestCase):
    def _new_db_and_csv(self) -> tuple[Path, Path]:
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        csv_fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(csv_fd)
        db_file = Path(db_path)
        csv_file = Path(csv_path)
        with csv_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["section", "field"])
            writer.writeheader()
            writer.writerow({"section": "Trip", "field": "trip_name"})
            writer.writerow({"section": "Trip", "field": "region"})
            writer.writerow({"section": "Trip", "field": "start_date"})
            writer.writerow({"section": "Trip", "field": "end_date"})
            writer.writerow({"section": "Trip", "field": "notes"})
        return db_file, csv_file

    @staticmethod
    def _cleanup(*paths: Path) -> None:
        for path in paths:
            if path.exists():
                path.unlink()

    def test_exhaustive_finds_trip_id_removal_permutations(self):
        bools = [False, True]
        for has_trip_id in bools:
            for has_collection_year in bools:
                with self.subTest(has_trip_id=has_trip_id, has_collection_year=has_collection_year):
                    db_path, csv_path = self._new_db_and_csv()
                    try:
                        with closing(sqlite3.connect(db_path)) as conn:
                            conn.execute(
                                """
                                CREATE TABLE Trips (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    trip_name TEXT,
                                    location TEXT
                                )
                                """
                            )
                            conn.execute(
                                """
                                CREATE TABLE Locations (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT,
                                    latitude TEXT,
                                    longitude TEXT,
                                    altitude_value TEXT,
                                    altitude_unit TEXT,
                                    country_code TEXT,
                                    state TEXT,
                                    lga TEXT,
                                    basin TEXT,
                                    geogscale TEXT,
                                    geography_comments TEXT
                                )
                                """
                            )
                            conn.execute(
                                """
                                CREATE TABLE CollectionEvents (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    trip_id INTEGER,
                                    location_id INTEGER NOT NULL,
                                    collection_name TEXT NOT NULL,
                                    collection_subset TEXT,
                                    event_year INTEGER
                                )
                                """
                            )
                            find_cols = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
                            if has_trip_id:
                                find_cols.append("trip_id INTEGER")
                            find_cols.extend(
                                [
                                    "location_id INTEGER",
                                    "collection_event_id INTEGER",
                                    "source_occurrence_no TEXT",
                                    "accepted_name TEXT",
                                ]
                            )
                            if has_collection_year:
                                find_cols.append("collection_year_latest_estimate INTEGER")
                            find_cols.extend(
                                [
                                    "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                                    "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                                ]
                            )
                            conn.execute(f"CREATE TABLE Finds ({', '.join(find_cols)})")
                            conn.execute("INSERT INTO Trips (id, trip_name, location) VALUES (1, 'T1', 'L1')")
                            conn.execute(
                                "INSERT INTO Locations (id, name, latitude, longitude, country_code, state) VALUES (1, 'L1', '-20', '140', 'AU', 'QLD')"
                            )
                            conn.execute(
                                """
                                INSERT INTO CollectionEvents (id, trip_id, location_id, collection_name, collection_subset, event_year)
                                VALUES (1, 1, 1, 'L1', 'CE1', 2000)
                                """
                            )
                            if has_trip_id and has_collection_year:
                                conn.execute(
                                    """
                                    INSERT INTO Finds (id, trip_id, location_id, collection_event_id, source_occurrence_no, accepted_name, collection_year_latest_estimate)
                                    VALUES (1, 1, 1, 1, 'occ-1', 'Taxon A', 2001)
                                    """
                                )
                            elif has_trip_id:
                                conn.execute(
                                    """
                                    INSERT INTO Finds (id, trip_id, location_id, collection_event_id, source_occurrence_no, accepted_name)
                                    VALUES (1, 1, 1, 1, 'occ-1', 'Taxon A')
                                    """
                                )
                            elif has_collection_year:
                                conn.execute(
                                    """
                                    INSERT INTO Finds (id, location_id, collection_event_id, source_occurrence_no, accepted_name, collection_year_latest_estimate)
                                    VALUES (1, 1, 1, 'occ-1', 'Taxon A', 2001)
                                    """
                                )
                            else:
                                conn.execute(
                                    """
                                    INSERT INTO Finds (id, location_id, collection_event_id, source_occurrence_no, accepted_name)
                                    VALUES (1, 1, 1, 'occ-1', 'Taxon A')
                                    """
                                )
                            conn.execute("PRAGMA user_version = 2")
                            conn.commit()

                        initialize_database(db_path, csv_path)
                        initialize_database(db_path, csv_path)

                        with closing(sqlite3.connect(db_path)) as conn:
                            version = conn.execute("PRAGMA user_version").fetchone()[0]
                            cols = {row[1] for row in conn.execute("PRAGMA table_info(Finds)").fetchall()}
                            row = conn.execute(
                                "SELECT id, location_id, collection_event_id, source_occurrence_no, accepted_name FROM Finds WHERE id = 1"
                            ).fetchone()
                            self.assertEqual(version, SCHEMA_VERSION)
                            self.assertNotIn("trip_id", cols)
                            self.assertIn("collection_year_latest_estimate", cols)
                            self.assertEqual(row, (1, 1, 1, "occ-1", "Taxon A"))
                    finally:
                        self._cleanup(db_path, csv_path)


if __name__ == "__main__":
    unittest.main()
