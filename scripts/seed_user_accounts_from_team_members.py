#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

from backend.app.passwords import hash_password

DEFAULT_DB_PATH = "data/paleo_trips_01.db"
DEFAULT_PASSWORD = "qwer1234"
ADMIN_NAME = "D. Browning"


def _normalize_username(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", ".", name.lower()).strip(".")
    base = re.sub(r"\.+", ".", base)
    return base or "team.member"


def seed_user_accounts(db_path: Path, password: str) -> tuple[int, int]:
    created = 0
    updated = 0

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        members = conn.execute(
            """
            SELECT id, name, active
            FROM Team_members
            ORDER BY id
            """
        ).fetchall()

        used_usernames: set[str] = set()
        existing_rows = conn.execute("SELECT username FROM User_Accounts").fetchall()
        for row in existing_rows:
            used_usernames.add(str(row["username"]).lower())

        for member in members:
            member_id = int(member["id"])
            name = str(member["name"] or "").strip()
            role = "admin" if name == ADMIN_NAME else "team"

            account = conn.execute(
                "SELECT id, username FROM User_Accounts WHERE team_member_id = ?",
                (member_id,),
            ).fetchone()

            if account:
                username = str(account["username"])
                conn.execute(
                    """
                    UPDATE User_Accounts
                    SET username = ?, password_hash = ?, role = ?, must_change_password = 1, password_changed_at = NULL
                    WHERE team_member_id = ?
                    """,
                    (username, hash_password(password), role, member_id),
                )
                updated += 1
                continue

            base = _normalize_username(name)
            candidate = base
            suffix = 2
            while candidate.lower() in used_usernames:
                candidate = f"{base}.{suffix}"
                suffix += 1
            used_usernames.add(candidate.lower())

            conn.execute(
                """
                INSERT INTO User_Accounts (
                    team_member_id,
                    username,
                    password_hash,
                    role,
                    must_change_password,
                    password_changed_at
                )
                VALUES (?, ?, ?, ?, 1, NULL)
                """,
                (member_id, candidate, hash_password(password), role),
            )
            created += 1

    return created, updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed User_Accounts from Team_members.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to SQLite DB")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Initial password for all accounts")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    created, updated = seed_user_accounts(db_path, args.password)
    print(f"Seeded user accounts in {db_path}")
    print(f"Created: {created}")
    print(f"Updated: {updated}")


if __name__ == "__main__":
    main()
