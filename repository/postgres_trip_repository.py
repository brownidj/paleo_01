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
        self._ensure_core_schema()
        self._ensure_finds_schema()

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

    def _ensure_core_schema(self) -> None:
        from scripts.db.migrate_sqlite_to_postgres_schema_helpers import ensure_schema

        with connect(self.database_url, row_factory=dict_row) as conn:
            ensure_schema(conn, include_legacy_finds_columns=False)
            conn.commit()

    def _ensure_finds_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS find_date TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS find_time TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS latitude TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS longitude TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS team_member_id BIGINT REFERENCES team_members(id) ON DELETE SET NULL")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS source_system TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS source_occurrence_no TEXT")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS find_field_observations (
                    id BIGSERIAL PRIMARY KEY,
                    find_id BIGINT NOT NULL UNIQUE REFERENCES finds(id) ON DELETE CASCADE,
                    provisional_identification TEXT,
                    notes TEXT,
                    abund_value TEXT,
                    abund_unit TEXT,
                    occurrence_comments TEXT,
                    research_group TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS find_taxonomy (
                    id BIGSERIAL PRIMARY KEY,
                    find_id BIGINT NOT NULL UNIQUE REFERENCES finds(id) ON DELETE CASCADE,
                    identified_name TEXT,
                    accepted_name TEXT,
                    identified_rank TEXT,
                    accepted_rank TEXT,
                    difference TEXT,
                    identified_no TEXT,
                    accepted_no TEXT,
                    phylum TEXT,
                    class_name TEXT,
                    taxon_order TEXT,
                    family TEXT,
                    genus TEXT,
                    reference_no TEXT,
                    taxonomy_comments TEXT,
                    collection_year_latest_estimate INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Performance indexes for trip/finds loading paths.
            cur.execute("CREATE INDEX IF NOT EXISTS idx_collection_events_trip_id ON collection_events(trip_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_collection_events_location_id ON collection_events(location_id)")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_collection_events_trip_id_id_desc ON collection_events(trip_id, id DESC)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_finds_collection_event_id ON finds(collection_event_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_finds_location_id ON finds(location_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_finds_team_member_id ON finds(team_member_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_trips_trip_name_lower ON trips((LOWER(COALESCE(trip_name, ''))))")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_locations_name_lower_trim ON locations((LOWER(TRIM(name))))")
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='finds' AND column_name='identified_name'
                LIMIT 1
                """
            )
            has_legacy_detail_columns = cur.fetchone() is not None
            if has_legacy_detail_columns:
                cur.execute(
                    """
                    INSERT INTO find_field_observations (
                        find_id, provisional_identification, notes, abund_value, abund_unit,
                        occurrence_comments, research_group, created_at, updated_at
                    )
                    SELECT
                        f.id, f.identified_name, f.notes, f.abund_value, f.abund_unit,
                        f.occurrence_comments, f.research_group, f.created_at, f.updated_at
                    FROM finds f
                    LEFT JOIN find_field_observations fo ON fo.find_id = f.id
                    WHERE fo.find_id IS NULL
                    """
                )
                cur.execute(
                    """
                    INSERT INTO find_taxonomy (
                        find_id, identified_name, accepted_name, identified_rank, accepted_rank,
                        difference, identified_no, accepted_no, phylum, class_name, taxon_order,
                        family, genus, reference_no, taxonomy_comments, collection_year_latest_estimate,
                        created_at, updated_at
                    )
                    SELECT
                        f.id, f.identified_name, f.accepted_name, f.identified_rank, f.accepted_rank,
                        f.difference, f.identified_no, f.accepted_no, f.phylum, f.class_name, f.taxon_order,
                        f.family, f.genus, f.reference_no, f.taxonomy_comments, f.collection_year_latest_estimate,
                        f.created_at, f.updated_at
                    FROM finds f
                    LEFT JOIN find_taxonomy ft ON ft.find_id = f.id
                    WHERE ft.find_id IS NULL
                    """
                )
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS identified_name")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS accepted_name")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS identified_rank")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS accepted_rank")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS difference")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS identified_no")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS accepted_no")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS phylum")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS class_name")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS taxon_order")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS family")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS genus")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS abund_value")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS abund_unit")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS reference_no")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS taxonomy_comments")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS occurrence_comments")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS research_group")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS notes")
                cur.execute("ALTER TABLE finds DROP COLUMN IF EXISTS collection_year_latest_estimate")

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
            trip_id = int(cur.fetchone()["id"])
            if "team" in data:
                self._sync_trip_team_members(cur, trip_id, data.get("team"))
            return trip_id

    def update_trip(self, trip_id: int, data: TripPayloadMap) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            location_id: int | None = None
            if "location" in data:
                location_name = self._first_location_candidate(data.get("location"))
                if not location_name:
                    raise ValueError("Trip location is required.")
                cur.execute(
                    """
                    SELECT id
                    FROM locations
                    WHERE LOWER(TRIM(name)) = LOWER(TRIM(%s))
                    ORDER BY id
                    LIMIT 1
                    """,
                    (location_name,),
                )
                location_row = cur.fetchone()
                if not location_row:
                    raise ValueError("Trip location was not found in Locations.")
                location_id = int(location_row["id"])
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
            if location_id is not None:
                cur.execute(
                    """
                    UPDATE collection_events
                    SET location_id = %s
                    WHERE trip_id = %s
                    """,
                    (location_id, trip_id),
                )
            if "team" in data:
                self._sync_trip_team_members(cur, trip_id, data.get("team"))

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

    @staticmethod
    def _parse_team_names(raw_team: object) -> list[str]:
        raw = str(raw_team or "")
        names: list[str] = []
        seen: set[str] = set()
        for name in (part.strip() for part in raw.split(";")):
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)
        return names

    @staticmethod
    def _first_location_candidate(raw_location: object) -> str:
        return next(
            (part.strip() for part in str(raw_location or "").split(";") if part.strip()),
            "",
        )

    def _sync_trip_team_members(self, cur, trip_id: int, raw_team: object) -> None:
        team_names = self._parse_team_names(raw_team)
        cur.execute("DELETE FROM trip_team_members WHERE trip_id = %s", (trip_id,))
        if not team_names:
            return
        lowered = [name.lower() for name in team_names]
        cur.execute(
            """
            SELECT id, LOWER(TRIM(name)) AS normalized_name
            FROM team_members
            WHERE LOWER(TRIM(name)) = ANY(%s)
            """,
            (lowered,),
        )
        rows = cur.fetchall()
        by_name: dict[str, int] = {}
        for row in rows:
            normalized = str(row.get("normalized_name") or "")
            member_id = int(row.get("id") or 0)
            if normalized and member_id > 0 and normalized not in by_name:
                by_name[normalized] = member_id
        for team_name in team_names:
            matched_member_id = by_name.get(team_name.lower())
            if matched_member_id is None:
                continue
            cur.execute(
                """
                INSERT INTO trip_team_members (trip_id, team_member_id)
                VALUES (%s, %s)
                ON CONFLICT (trip_id, team_member_id) DO NOTHING
                """,
                (trip_id, matched_member_id),
            )
