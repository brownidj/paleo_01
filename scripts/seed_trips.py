#!/usr/bin/env python3
import argparse
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path

from faker import Faker

from db_bootstrap import (
    create_trips_table,
    get_trip_fields,
    resolve_classification_csv,
    resolve_db_path,
)


def _build_trip_record(fake: Faker, index: int) -> dict[str, str]:
    start_date = fake.date_between(start_date="-2y", end_date="today")
    end_date = fake.date_between(start_date=start_date, end_date=start_date + timedelta(days=21))
    team_size = fake.random_int(min=2, max=5)
    team = ", ".join(fake.name() for _ in range(team_size))
    return {
        "trip_code": f"TRIP-{index:04d}",
        "trip_name": f"{fake.city()} Survey",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "team": team,
        "region": f"{fake.state()}, AU",
        "notes": fake.sentence(nb_words=10),
    }


def seed_trips(db_path: Path, fields: list[str], count: int) -> int:
    fake = Faker("en_AU")
    inserted = 0
    with sqlite3.connect(db_path) as conn:
        create_trips_table(conn, fields)
        # noinspection SqlResolve
        existing_count = conn.execute("SELECT COUNT(*) FROM Trips").fetchone()[0]
        for i in range(1, count + 1):
            record = _build_trip_record(fake, existing_count + i)
            values = [record.get(field, "n/a") for field in fields]
            placeholders = ", ".join(["?"] * len(fields))
            col_sql = ", ".join([f'"{name}"' for name in fields])
            # noinspection SqlResolve
            conn.execute(
                f"INSERT INTO Trips ({col_sql}) VALUES ({placeholders})",
                values,
            )
            inserted += 1
        conn.commit()
    return inserted


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
    inserted = seed_trips(db_path, fields, args.count)
    print(f"Created/verified Trips table in {db_path}")
    print(f"Inserted {inserted} fake Trips records")
    print("Fields:")
    for field in fields:
        print(f"- {field}")


if __name__ == "__main__":
    main()
