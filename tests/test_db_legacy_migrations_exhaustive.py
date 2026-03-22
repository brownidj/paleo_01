import csv
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from scripts.db_bootstrap import SCHEMA_VERSION, initialize_database
class TestDbLegacyMigrationsExhaustive(unittest.TestCase):
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
    def test_exhaustive_trip_schema_permutations_upgrade(self):
        bools = [False, True]
        for has_id in bools:
            for has_trip_code in bools:
                for has_region in bools:
                    for has_location in bools:
                        with self.subTest(
                            has_id=has_id,
                            has_trip_code=has_trip_code,
                            has_region=has_region,
                            has_location=has_location,
                        ):
                            db_path, csv_path = self._new_db_and_csv()
                            try:
                                with closing(sqlite3.connect(db_path)) as conn:
                                    columns: list[str] = []
                                    if has_id:
                                        columns.append("id INTEGER PRIMARY KEY AUTOINCREMENT")
                                    if has_trip_code:
                                        columns.append("trip_code TEXT")
                                    columns.append("trip_name TEXT")
                                    if has_region:
                                        columns.append("region TEXT")
                                    if has_location:
                                        columns.append("location TEXT")
                                    columns.append("notes TEXT")
                                    conn.execute(f"CREATE TABLE Trips ({', '.join(columns)})")

                                    insert_cols = ["trip_name", "notes"]
                                    insert_vals: list[str | None] = ["Legacy", "n1"]
                                    if has_trip_code:
                                        insert_cols.append("trip_code")
                                        insert_vals.append("T001")
                                    if has_region:
                                        insert_cols.append("region")
                                        insert_vals.append("Region A")
                                    if has_location:
                                        insert_cols.append("location")
                                        insert_vals.append("")
                                    placeholders = ", ".join(["?"] * len(insert_cols))
                                    conn.execute(
                                        f"INSERT INTO Trips ({', '.join(insert_cols)}) VALUES ({placeholders})",
                                        tuple(insert_vals),
                                    )
                                    conn.execute("PRAGMA user_version = 0")
                                    conn.commit()

                                initialize_database(db_path, csv_path)
                                initialize_database(db_path, csv_path)

                                with closing(sqlite3.connect(db_path)) as conn:
                                    version = conn.execute("PRAGMA user_version").fetchone()[0]
                                    cols = {row[1] for row in conn.execute("PRAGMA table_info(Trips)").fetchall()}
                                    row = conn.execute("SELECT trip_name, location, notes FROM Trips").fetchone()
                                    self.assertEqual(version, SCHEMA_VERSION)
                                    self.assertIn("id", cols)
                                    self.assertIn("trip_name", cols)
                                    self.assertIn("location", cols)
                                    self.assertNotIn("trip_code", cols)
                                    self.assertNotIn("region", cols)
                                    self.assertEqual(row[0], "Legacy")
                                    self.assertEqual(row[2], "n1")
                                    if has_region:
                                        self.assertEqual(row[1], "Region A")
                                    elif has_location:
                                        self.assertEqual(row[1], "")
                                    else:
                                        self.assertIsNone(row[1])
                            finally:
                                self._cleanup(db_path, csv_path)
    def test_exhaustive_trip_locations_legacy_modes(self):
        modes = ("legacy_mappable", "legacy_unmappable", "modern_existing", "absent_table")
        for mode in modes:
            with self.subTest(mode=mode):
                db_path, csv_path = self._new_db_and_csv()
                try:
                    with closing(sqlite3.connect(db_path)) as conn:
                        conn.execute("CREATE TABLE Locations (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")
                        conn.execute("INSERT INTO Locations (name) VALUES ('L1')")
                        conn.execute("INSERT INTO Locations (name) VALUES ('L2')")

                        if mode == "legacy_mappable":
                            conn.execute(
                                """
                                CREATE TABLE Trips (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    trip_code TEXT,
                                    trip_name TEXT,
                                    location TEXT
                                )
                                """
                            )
                            conn.execute("INSERT INTO Trips (trip_code, trip_name, location) VALUES ('T001', 'A', 'L1')")
                            conn.execute("INSERT INTO Trips (trip_code, trip_name, location) VALUES ('T002', 'B', 'L2')")
                            conn.execute(
                                "CREATE TABLE TripLocations (trip_code TEXT NOT NULL, location_id INTEGER NOT NULL)"
                            )
                            conn.execute("INSERT INTO TripLocations (trip_code, location_id) VALUES ('T001', 1)")
                            conn.execute("INSERT INTO TripLocations (trip_code, location_id) VALUES ('T002', 2)")
                        elif mode == "legacy_unmappable":
                            conn.execute(
                                """
                                CREATE TABLE Trips (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    trip_name TEXT,
                                    location TEXT
                                )
                                """
                            )
                            conn.execute("INSERT INTO Trips (trip_name, location) VALUES ('A', 'L1')")
                            conn.execute("INSERT INTO Trips (trip_name, location) VALUES ('B', 'L2')")
                            conn.execute(
                                "CREATE TABLE TripLocations (trip_code TEXT NOT NULL, location_id INTEGER NOT NULL)"
                            )
                            conn.execute("INSERT INTO TripLocations (trip_code, location_id) VALUES ('T001', 1)")
                        elif mode == "modern_existing":
                            conn.execute(
                                """
                                CREATE TABLE Trips (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    trip_name TEXT,
                                    location TEXT
                                )
                                """
                            )
                            conn.execute("INSERT INTO Trips (trip_name, location) VALUES ('A', 'L1')")
                            conn.execute(
                                "CREATE TABLE TripLocations (id INTEGER NOT NULL, location_id INTEGER NOT NULL)"
                            )
                            conn.execute("INSERT INTO TripLocations (id, location_id) VALUES (1, 1)")
                        else:
                            conn.execute(
                                """
                                CREATE TABLE Trips (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    trip_name TEXT,
                                    location TEXT
                                )
                                """
                            )
                            conn.execute("INSERT INTO Trips (trip_name, location) VALUES ('A', 'L1')")

                        conn.execute("PRAGMA user_version = 1")
                        conn.commit()

                    initialize_database(db_path, csv_path)
                    initialize_database(db_path, csv_path)

                    with closing(sqlite3.connect(db_path)) as conn:
                        version = conn.execute("PRAGMA user_version").fetchone()[0]
                        cols = [row[1] for row in conn.execute("PRAGMA table_info(TripLocations)").fetchall()]
                        rows = conn.execute("SELECT id, location_id FROM TripLocations ORDER BY id, location_id").fetchall()
                        self.assertEqual(version, SCHEMA_VERSION)
                        self.assertIn("id", cols)
                        self.assertIn("location_id", cols)
                        self.assertNotIn("trip_code", cols)
                        if mode == "legacy_mappable":
                            self.assertEqual(rows, [(1, 1), (2, 2)])
                        elif mode == "modern_existing":
                            self.assertEqual(rows, [(1, 1)])
                        else:
                            self.assertEqual(rows, [])
                finally:
                    self._cleanup(db_path, csv_path)
    def test_exhaustive_location_legacy_column_permutations(self):
        bools = [False, True]
        for has_county in bools:
            for has_collection_name in bools:
                for has_collection_subset in bools:
                    for has_collection_aka in bools:
                        for preset_lga in bools:
                            with self.subTest(
                                has_county=has_county,
                                has_collection_name=has_collection_name,
                                has_collection_subset=has_collection_subset,
                                has_collection_aka=has_collection_aka,
                                preset_lga=preset_lga,
                            ):
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
                                        location_cols = ["id INTEGER PRIMARY KEY AUTOINCREMENT", "name TEXT"]
                                        if has_county:
                                            location_cols.append("county TEXT")
                                        if preset_lga:
                                            location_cols.append("lga TEXT")
                                        if has_collection_name:
                                            location_cols.append("collection_name TEXT")
                                        if has_collection_subset:
                                            location_cols.append("collection_subset TEXT")
                                        if has_collection_aka:
                                            location_cols.append("collection_aka TEXT")
                                        conn.execute(f"CREATE TABLE Locations ({', '.join(location_cols)})")

                                        cols = ["name"]
                                        vals: list[str | None] = ["Legacy Site"]
                                        if has_county:
                                            cols.append("county")
                                            vals.append("County X")
                                        if preset_lga:
                                            cols.append("lga")
                                            vals.append("Preset LGA")
                                        if has_collection_name:
                                            cols.append("collection_name")
                                            vals.append("Collection X")
                                        if has_collection_subset:
                                            cols.append("collection_subset")
                                            vals.append("Subset Y")
                                        if has_collection_aka:
                                            cols.append("collection_aka")
                                            vals.append("AKA Z")
                                        placeholders = ", ".join(["?"] * len(cols))
                                        conn.execute(
                                            f"INSERT INTO Locations ({', '.join(cols)}) VALUES ({placeholders})",
                                            tuple(vals),
                                        )
                                        conn.execute("PRAGMA user_version = 1")
                                        conn.commit()

                                    initialize_database(db_path, csv_path)
                                    initialize_database(db_path, csv_path)

                                    with closing(sqlite3.connect(db_path)) as conn:
                                        version = conn.execute("PRAGMA user_version").fetchone()[0]
                                        cols = {row[1] for row in conn.execute("PRAGMA table_info(Locations)").fetchall()}
                                        lga = conn.execute("SELECT lga FROM Locations WHERE id = 1").fetchone()[0]
                                        events = conn.execute(
                                            """
                                            SELECT collection_name, collection_subset
                                            FROM CollectionEvents
                                            WHERE location_id = 1
                                            ORDER BY id
                                            """
                                        ).fetchall()

                                        self.assertEqual(version, SCHEMA_VERSION)
                                        self.assertNotIn("county", cols)
                                        self.assertNotIn("collection_name", cols)
                                        self.assertNotIn("collection_subset", cols)
                                        self.assertNotIn("collection_aka", cols)
                                        if preset_lga:
                                            self.assertEqual(lga, "Preset LGA")
                                        elif has_county:
                                            self.assertEqual(lga, "County X")
                                        else:
                                            self.assertIsNone(lga)

                                        if has_collection_name:
                                            expected_subset = "Subset Y" if has_collection_subset else None
                                            self.assertEqual(events, [("Collection X", expected_subset)])
                                        else:
                                            self.assertEqual(events, [])
                                finally:
                                    self._cleanup(db_path, csv_path)
if __name__ == "__main__":
    unittest.main()
