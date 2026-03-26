#!/usr/bin/env python3
import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from faker import Faker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from repository import DEFAULT_DB_PATH
from scripts.db.bootstrap import create_team_members_table, resolve_db_path


def seed_users(db_path: Path, count: int) -> int:
    fake = Faker()
    fixed_phone = "0061-412-345-678"
    active_quota = 8
    inserted = 0
    with closing(sqlite3.connect(db_path)) as conn:
        create_team_members_table(conn)
        for i in range(count):
            is_active = 1 if i < min(active_quota, count) else 0
            conn.execute(
                "INSERT INTO Team_members (name, phone_number, active) VALUES (?, ?, ?)",
                (fake.name(), fixed_phone, is_active),
            )
            inserted += 1
        conn.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Seed dummy team members into {DEFAULT_DB_PATH}")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite database path")
    parser.add_argument("--count", type=int, default=20, help="Number of team members to insert")
    args = parser.parse_args()

    db_path = resolve_db_path(args.db)
    inserted = seed_users(db_path, args.count)
    print(f"Inserted {inserted} team members into {db_path}")


if __name__ == "__main__":
    main()
