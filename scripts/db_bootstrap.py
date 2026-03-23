#!/usr/bin/env python3
import csv
import sqlite3
from contextlib import closing
from pathlib import Path

try:
    from .db_schema_helpers import (
        create_team_members_table,
        create_locations_table,
        create_trips_table,
        normalize_trip_fields,
    )
except ImportError:
    from db_schema_helpers import (
        create_team_members_table,
        create_locations_table,
        create_trips_table,
        normalize_trip_fields,
    )


SCHEMA_VERSION = 3


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
    return normalize_trip_fields(unique_fields)


def initialize_database(db_path: Path, classification_csv: Path) -> list[str]:
    trip_fields = get_trip_fields(classification_csv)
    with closing(sqlite3.connect(db_path)) as conn:
        migrate_database(conn, trip_fields)
        conn.commit()
    return trip_fields


def migrate_database(conn: sqlite3.Connection, trip_fields: list[str], target_version: int = SCHEMA_VERSION) -> int:
    current_version = _get_user_version(conn)
    if current_version > target_version:
        raise ValueError(
            f"Database user_version {current_version} is newer than supported version {target_version}."
        )
    while current_version < target_version:
        next_version = current_version + 1
        _apply_migration_step(conn, next_version, trip_fields)
        _set_user_version(conn, next_version)
        current_version = next_version
    return current_version


def _apply_migration_step(conn: sqlite3.Connection, step_version: int, trip_fields: list[str]) -> None:
    if step_version == 1:
        create_team_members_table(conn)
        create_trips_table(conn, trip_fields)
        return
    if step_version == 2:
        create_locations_table(conn)
        return
    if step_version == 3:
        # Normalize Finds schema to derive trip through CollectionEvents only.
        create_locations_table(conn)
        return
    raise ValueError(f"Unsupported migration step: {step_version}")


def _get_user_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    if not row:
        return 0
    return int(row[0])


def _set_user_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {int(version)}")


__all__ = [
    "SCHEMA_VERSION",
    "project_root",
    "resolve_db_path",
    "resolve_classification_csv",
    "get_trip_fields",
    "initialize_database",
    "migrate_database",
    "create_team_members_table",
    "create_trips_table",
    "create_locations_table",
    "normalize_trip_fields",
]
