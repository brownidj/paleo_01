from __future__ import annotations

import os
import re
from contextlib import contextmanager
from typing import cast

from psycopg import connect
from psycopg.rows import dict_row

from repository.domain_types import TeamMemberRecord, TripPayloadMap, TripRecord
from repository.postgres_trip_repository_domain import PostgresTripRepositoryDomainMixin
from repository.repository_base import DEFAULT_TRIP_FIELDS


class PostgresTripRepository(PostgresTripRepositoryDomainMixin):
    _COLLECTION_EVENT_CODE_RE = re.compile(r"\s*\[#\d+\]\s*$")

    def __init__(self, _db_path: str = ""):
        self.database_url = os.getenv("PALEO_DESKTOP_DATABASE_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()
        if not self.database_url:
            raise RuntimeError("PALEO_DESKTOP_DATABASE_URL or DATABASE_URL is required for PostgresTripRepository.")

    @contextmanager
    def _connect(self):
        conn = connect(self.database_url, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_trips_table(self, fields: list[str] | None = None) -> None:
        _ = fields
        return

    def get_fields(self) -> list[str]:
        return ["id", *[f for f in DEFAULT_TRIP_FIELDS if f != "id"]]

    def list_trips(self) -> list[TripRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, trip_name, start_date::text AS start_date, end_date::text AS end_date, team, location, notes
                FROM trips
                ORDER BY LOWER(COALESCE(trip_name, '')), COALESCE(start_date::text, ''), id
                """
            )
            rows = cur.fetchall()
        return [cast(TripRecord, dict(r)) for r in rows]

    def get_trip(self, trip_id: int) -> TripRecord | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, trip_name, start_date::text AS start_date, end_date::text AS end_date, team, location, notes
                FROM trips
                WHERE id = %s
                """,
                (trip_id,),
            )
            row = cur.fetchone()
        return cast(TripRecord, dict(row)) if row else None

    def create_trip(self, data: TripPayloadMap) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trips (trip_name, start_date, end_date, team, location, notes)
                VALUES (%s, NULLIF(%s, '')::date, NULLIF(%s, '')::date, %s, %s, %s)
                RETURNING id
                """,
                (data.get("trip_name"), data.get("start_date"), data.get("end_date"), data.get("team"), data.get("location"), data.get("notes")),
            )
            return int(cur.fetchone()["id"])

    def update_trip(self, trip_id: int, data: TripPayloadMap) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE trips
                SET
                    trip_name = COALESCE(%s, trip_name),
                    start_date = COALESCE(NULLIF(%s, '')::date, start_date),
                    end_date = COALESCE(NULLIF(%s, '')::date, end_date),
                    team = %s,
                    location = %s,
                    notes = %s
                WHERE id = %s
                """,
                (data.get("trip_name"), data.get("start_date"), data.get("end_date"), data.get("team"), data.get("location"), data.get("notes"), trip_id),
            )

    def list_active_team_members(self) -> list[str]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT name FROM team_members WHERE active IS TRUE ORDER BY name")
            rows = cur.fetchall()
        return [str(r["name"]) for r in rows]

    def list_team_members(self) -> list[TeamMemberRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    tm.id,
                    tm.name,
                    COALESCE(tm.phone_number, '') AS phone_number,
                    tm.institution,
                    ua.role AS role,
                    tm.recruitment_date::text AS recruitment_date,
                    tm.retirement_date::text AS retirement_date,
                    CASE WHEN tm.active THEN 1 ELSE 0 END AS active
                FROM team_members tm
                LEFT JOIN user_accounts ua ON ua.team_member_id = tm.id
                """
            )
            rows = cur.fetchall()
        members = [cast(TeamMemberRecord, dict(r)) for r in rows]
        members.sort(key=lambda tm: (0 if int(tm.get("active", 0)) == 1 else 1, self._last_name(str(tm.get("name", ""))), str(tm.get("name", "")).lower()))
        return members

    def get_team_member(self, team_member_id: int) -> TeamMemberRecord | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, COALESCE(phone_number, '') AS phone_number, institution,
                       recruitment_date::text AS recruitment_date, retirement_date::text AS retirement_date,
                       CASE WHEN active THEN 1 ELSE 0 END AS active
                FROM team_members WHERE id = %s
                """,
                (team_member_id,),
            )
            row = cur.fetchone()
        return cast(TeamMemberRecord, dict(row)) if row else None

    def create_team_member(self, name: str, phone_number: str, active: bool, institution: str | None = None) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO team_members (name, phone_number, institution, active) VALUES (%s, %s, %s, %s) RETURNING id",
                (name, phone_number, institution, active),
            )
            return int(cur.fetchone()["id"])

    def update_team_member(self, team_member_id: int, name: str, phone_number: str, active: bool, institution: str | None = None) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE team_members SET name=%s, phone_number=%s, institution=%s, active=%s WHERE id=%s",
                (name, phone_number, institution, active, team_member_id),
            )

    @staticmethod
    def _last_name(name: str) -> str:
        parts = [p for p in name.strip().lower().split(" ") if p]
        return parts[-1] if parts else ""
