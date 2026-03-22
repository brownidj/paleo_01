#!/usr/bin/env python3
import argparse
import sqlite3
import sys
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from random import choice

from faker import Faker

from db_bootstrap import (
    create_locations_table,
    create_trips_table,
    get_trip_fields,
    resolve_classification_csv,
    resolve_db_path,
)


def _build_trip_record(fake: Faker) -> dict[str, str]:
    start_date = fake.date_between(start_date="-2y", end_date="today")
    end_date = fake.date_between(start_date=start_date, end_date=start_date + timedelta(days=21))
    team_size = fake.random_int(min=2, max=5)
    team = "; ".join(fake.name() for _ in range(team_size))
    return {
        "trip_name": f"{fake.city()} Survey",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "team": team,
        "location": "n/a",
        "notes": fake.sentence(nb_words=10),
    }


def _location_similarity_key(location: sqlite3.Row) -> tuple[str, ...]:
    # Similarity is based on all location attributes except id and name.
    attrs = [
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
    return tuple(str(location[attr] or "") for attr in attrs)


def _insert_trip(
    conn: sqlite3.Connection,
    fields: list[str],
    trip_record: dict[str, str],
    location_ids: list[int],
) -> int:
    insert_fields = [field for field in fields if field != "id"]
    values = [trip_record.get(field, "n/a") for field in insert_fields]
    placeholders = ", ".join(["?"] * len(insert_fields))
    col_sql = ", ".join([f'"{name}"' for name in insert_fields])
    cur = conn.execute(
        f"INSERT INTO Trips ({col_sql}) VALUES ({placeholders})",
        values,
    )
    trip_id = int(cur.lastrowid)
    for location_id in location_ids:
        conn.execute(
            "INSERT OR IGNORE INTO TripLocations (id, location_id) VALUES (?, ?)",
            (trip_id, location_id),
        )
    return trip_id


def seed_trips(db_path: Path, fields: list[str], count: int) -> tuple[int, int]:
    fake = Faker("en_AU")
    first_pass_inserted = 0
    second_pass_inserted = 0
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        create_trips_table(conn, fields)
        create_locations_table(conn)

        locations = conn.execute(
            """
            SELECT id, name, latitude, longitude, altitude_value, altitude_unit,
                   country_code, state, lga, basin, geogscale, geography_comments
            FROM Locations
            """
        ).fetchall()
        if not locations:
            raise ValueError("No locations found. Seed locations before seeding trips.")

        grouped: dict[tuple[str, ...], list[sqlite3.Row]] = {}
        for loc in locations:
            grouped.setdefault(_location_similarity_key(loc), []).append(loc)

        second_pass_pairs: list[tuple[sqlite3.Row, sqlite3.Row]] = []

        for _ in range(count):
            primary = choice(locations)
            trip_record = _build_trip_record(fake)
            trip_record["location"] = str(primary["name"] or "n/a")
            _insert_trip(conn, fields, trip_record, [int(primary["id"])])
            first_pass_inserted += 1

            similars = [loc for loc in grouped[_location_similarity_key(primary)] if loc["id"] != primary["id"]]
            if similars and fake.pybool():
                secondary = choice(similars)
                second_pass_pairs.append((primary, secondary))

        for primary, secondary in second_pass_pairs:
            trip_record = _build_trip_record(fake)
            primary_name = str(primary["name"] or "").strip()
            secondary_name = str(secondary["name"] or "").strip()
            trip_record["location"] = "; ".join([name for name in [primary_name, secondary_name] if name]) or "n/a"
            _insert_trip(
                conn,
                fields,
                trip_record,
                [int(primary["id"]), int(secondary["id"])],
            )
            second_pass_inserted += 1

        conn.commit()
    return first_pass_inserted, second_pass_inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed fake data into Trips table.")
    parser.add_argument("--db", default="paleo_trips_01.db", help="SQLite database path")
    parser.add_argument(
        "--classification-csv",
        default="data/paleo_field_research_classification.csv",
        help="Path to classification CSV",
    )
    parser.add_argument("--count", type=int, default=20, help="Number of fake Trips records to insert")
    args = parser.parse_args()

    db_path = resolve_db_path(args.db)
    classification_csv = resolve_classification_csv(args.classification_csv)
    if not classification_csv.exists():
        print(f"Classification CSV not found: {classification_csv}", file=sys.stderr)
        raise SystemExit(1)

    fields = get_trip_fields(classification_csv)
    first_pass, second_pass = seed_trips(db_path, fields, args.count)
    print(f"Created/verified Trips table in {db_path}")
    print(f"Inserted {first_pass + second_pass} fake Trips records")
    print(f"- first pass trips: {first_pass}")
    print(f"- second pass trips: {second_pass}")
    print("Fields:")
    for field in fields:
        print(f"- {field}")


if __name__ == "__main__":
    main()
