#!/usr/bin/env python3
import csv
import sqlite3
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_db_path(db_arg: str) -> Path:
    path = Path(db_arg)
    if path.is_absolute():
        return path
    return project_root() / path


def resolve_classification_csv(path_arg: str) -> Path:
    path = Path(path_arg)
    if path.is_absolute():
        return path
    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate
    return project_root() / path


def get_trip_fields(classification_csv: Path) -> list[str]:
    fields: list[str] = []
    with classification_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("section") == "Trip":
                field_name = (row.get("field") or "").strip()
                if field_name:
                    fields.append(field_name)

    seen: set[str] = set()
    unique_fields: list[str] = []
    for field in fields:
        if field not in seen:
            unique_fields.append(field)
            seen.add(field)
    return unique_fields


def create_users_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))
        )
        """
    )
    columns = [row[1] for row in conn.execute("PRAGMA table_info(Users)").fetchall()]
    if "active" not in columns:
        conn.execute(
            "ALTER TABLE Users ADD COLUMN active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))"
        )


def create_trips_table(conn: sqlite3.Connection, fields: list[str]) -> None:
    if not fields:
        raise ValueError("No Trip fields found in classification CSV.")
    column_sql = ",\n            ".join(f'"{name}" TEXT' for name in fields)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS Trips (
            {column_sql}
        )
        """
    )


def initialize_database(db_path: Path, classification_csv: Path) -> list[str]:
    trip_fields = get_trip_fields(classification_csv)
    with sqlite3.connect(db_path) as conn:
        create_users_table(conn)
        create_trips_table(conn, trip_fields)
        conn.commit()
    return trip_fields
