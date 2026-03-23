#!/usr/bin/env python3
import argparse
import random
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from faker import Faker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from repository import DEFAULT_DB_PATH
from scripts.db_bootstrap import create_locations_table, resolve_db_path


AU_STATES = ["NSW", "QLD", "VIC", "TAS", "SA", "WA", "NT", "ACT"]
CARDINAL_POINTS = ["North", "South", "East", "West"]


def _build_location_record(fake: Faker) -> dict[str, str]:
    city = fake.city()
    if fake.pybool(truth_probability=40):
        direction = fake.random_element(CARDINAL_POINTS)
        location_name = f"{city} {direction} Site"
    else:
        location_name = f"{city} Site"
    return {
        "name": location_name,
        "latitude": f"{fake.latitude():.6f}",
        "longitude": f"{fake.longitude():.6f}",
        "altitude_value": str(fake.random_int(min=0, max=2000)),
        "altitude_unit": "m",
        "country_code": "AU",
        "state": fake.random_element(AU_STATES),
        "lga": f"{city} LGA",
        "basin": fake.word().title(),
        "geogscale": fake.random_element(["local", "regional", "site"]),
        "geography_comments": fake.sentence(nb_words=8),
    }


def _extract_cardinal(name: str) -> str | None:
    for direction in CARDINAL_POINTS:
        if re.search(rf"\b{direction}\b", name):
            return direction
    return None


def _with_replaced_cardinal(name: str, source: str, target: str) -> str:
    return re.sub(rf"\b{source}\b", target, name, count=1)


def _build_seed_records(fake: Faker, count: int) -> list[dict[str, str]]:
    base_records = [_build_location_record(fake) for _ in range(count)]
    extra_records: list[dict[str, str]] = []

    for record in base_records:
        source_direction = _extract_cardinal(record["name"])
        if not source_direction:
            continue
        target_direction = random.choice([d for d in CARDINAL_POINTS if d != source_direction])
        duplicate = dict(record)
        duplicate["name"] = _with_replaced_cardinal(record["name"], source_direction, target_direction)
        extra_records.append(duplicate)

    return base_records + extra_records


def seed_locations(db_path: Path, count: int, truncate: bool = False) -> int:
    fake = Faker("en_AU")
    inserted = 0
    fields = [
        "name",
        "latitude",
        "longitude",
        "altitude_value",
        "altitude_unit",
        "country_code",
        "state",
        "lga",
        "basin",
        "geogscale",
        "geography_comments",
    ]
    placeholders = ", ".join(["?"] * len(fields))
    col_sql = ", ".join([f'"{name}"' for name in fields])

    with closing(sqlite3.connect(db_path)) as conn:
        create_locations_table(conn)
        if truncate:
            conn.execute("DELETE FROM TripLocations")
            conn.execute("DELETE FROM CollectionEvents")
            conn.execute("DELETE FROM Locations")
        records = _build_seed_records(fake, count)
        for record in records:
            values = [record[field] for field in fields]
            conn.execute(f"INSERT INTO Locations ({col_sql}) VALUES ({placeholders})", values)
            inserted += 1
        conn.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Seed fake Locations into {DEFAULT_DB_PATH}")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite database path")
    parser.add_argument("--count", type=int, default=15, help="Number of locations to insert")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing TripLocations, CollectionEvents, and Locations before seeding",
    )
    args = parser.parse_args()

    db_path = resolve_db_path(args.db)
    inserted = seed_locations(db_path, args.count, truncate=args.truncate)
    print(f"Inserted {inserted} locations into {db_path}")


if __name__ == "__main__":
    main()
