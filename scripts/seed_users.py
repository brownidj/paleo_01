#!/usr/bin/env python3
import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from faker import Faker

from db_bootstrap import create_users_table, resolve_db_path


def seed_users(db_path: Path, count: int) -> int:
    fake = Faker()
    fixed_phone = "0061-412-345-678"
    active_quota = 8
    inserted = 0
    with closing(sqlite3.connect(db_path)) as conn:
        create_users_table(conn)
        for i in range(count):
            is_active = 1 if i < min(active_quota, count) else 0
            conn.execute(
                "INSERT INTO Users (name, phone_number, active) VALUES (?, ?, ?)",
                (fake.name(), fixed_phone, is_active),
            )
            inserted += 1
        conn.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed dummy users into paleo_trips_01.db")
    parser.add_argument("--db", default="paleo_trips_01.db", help="SQLite database path")
    parser.add_argument("--count", type=int, default=20, help="Number of users to insert")
    args = parser.parse_args()

    db_path = resolve_db_path(args.db)
    inserted = seed_users(db_path, args.count)
    print(f"Inserted {inserted} users into {db_path}")


if __name__ == "__main__":
    main()
