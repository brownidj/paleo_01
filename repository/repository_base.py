import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = "data/paleo_trips_01.db"


DEFAULT_TRIP_FIELDS = [
    "trip_name",
    "start_date",
    "end_date",
    "team",
    "location",
    "notes",
]

LOCATION_FIELDS = [
    "name",
    "latitude",
    "longitude",
    "altitude_value",
    "altitude_unit",
    "country_code",
    "state",
    "lga",
    "basin",
    "proterozoic_province",
    "orogen",
    "geogscale",
    "geography_comments",
]


class RepositoryBase:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path).resolve()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
