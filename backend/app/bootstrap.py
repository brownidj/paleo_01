from __future__ import annotations

from psycopg import connect

from app.config import get_settings
from app.passwords import hash_password


def bootstrap_postgres_auth() -> None:
    settings = get_settings()
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS team_members (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    active BOOLEAN NOT NULL DEFAULT TRUE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_accounts (
                    id BIGSERIAL PRIMARY KEY,
                    team_member_id BIGINT NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'team', 'planner', 'reviewer', 'field_member')),
                    must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
                    password_changed_at TIMESTAMPTZ
                )
                """
            )
            cur.execute(
                """
                INSERT INTO team_members (name, active)
                VALUES (%s, TRUE)
                ON CONFLICT (name) DO NOTHING
                """,
                (settings.bootstrap_admin_display_name,),
            )
            cur.execute(
                """
                INSERT INTO user_accounts (team_member_id, username, password_hash, role, must_change_password)
                SELECT tm.id, %s, %s, 'admin', TRUE
                FROM team_members tm
                WHERE tm.name = %s
                ON CONFLICT (username) DO NOTHING
                """,
                (
                    settings.bootstrap_admin_username,
                    hash_password(settings.bootstrap_admin_password),
                    settings.bootstrap_admin_display_name,
                ),
            )
