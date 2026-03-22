#!/usr/bin/env python3
import argparse
import sys

from repository import DEFAULT_DB_PATH
from db_bootstrap import initialize_database, resolve_classification_csv, resolve_db_path


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Initialize {DEFAULT_DB_PATH} with required tables.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite database path")
    parser.add_argument(
        "--classification-csv",
        default="data/paleo_field_research_classification.csv",
        help="Path to classification CSV",
    )
    args = parser.parse_args()

    db_path = resolve_db_path(args.db)
    classification_csv = resolve_classification_csv(args.classification_csv)
    if not classification_csv.exists():
        print(f"Classification CSV not found: {classification_csv}", file=sys.stderr)
        raise SystemExit(1)

    fields = initialize_database(db_path, classification_csv)
    print(f"Initialized database: {db_path}")
    print("Created/verified tables: Users, Trips, Locations, TripLocations, CollectionEvents")
    print("Trips fields:")
    for field in fields:
        print(f"- {field}")


if __name__ == "__main__":
    main()
