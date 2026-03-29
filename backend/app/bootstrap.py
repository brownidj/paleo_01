from __future__ import annotations

from psycopg import connect

from app.config import get_settings
from app.passwords import hash_password


def _is_placeholder_secret(value: str) -> bool:
    lowered = value.strip().lower()
    return (
        not lowered
        or "replace-with" in lowered
        or lowered == "change-me"
        or lowered == "qwer1234"
    )


def bootstrap_postgres_auth() -> None:
    settings = get_settings()
    if _is_placeholder_secret(settings.bootstrap_admin_password):
        raise RuntimeError(
            "BOOTSTRAP_ADMIN_PASSWORD must be set to a non-placeholder value before bootstrapping auth."
        )
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
            cur.execute("SELECT to_regclass('public.trips') IS NOT NULL AS trips_present")
            trips_present = bool(cur.fetchone()[0])
            if trips_present:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS trip_team_members (
                        trip_id BIGINT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                        team_member_id BIGINT NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
                        PRIMARY KEY (trip_id, team_member_id)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_trip_team_members_member ON trip_team_members(team_member_id)
                    """
                )
                cur.execute(
                    """
                    INSERT INTO trip_team_members (trip_id, team_member_id)
                    SELECT DISTINCT
                        t.id AS trip_id,
                        tm.id AS team_member_id
                    FROM trips t
                    CROSS JOIN LATERAL regexp_split_to_table(COALESCE(t.team, ''), ';') AS raw_member(name_part)
                    JOIN team_members tm
                      ON lower(trim(tm.name)) = lower(trim(raw_member.name_part))
                    WHERE trim(raw_member.name_part) <> ''
                    ON CONFLICT (trip_id, team_member_id) DO NOTHING
                    """
                )
