from typing import cast

from repository.domain_types import TeamMemberRecord, TripPayloadMap, TripRecord
from repository.repository_base import DEFAULT_TRIP_FIELDS


class RepositoryTripUserMixin:
    def _ensure_team_members_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "Team_members" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    institution TEXT,
                    recruitment_date TEXT,
                    retirement_date TEXT,
                    active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))
                )
                """
            )
            legacy_users_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='Users' LIMIT 1"
            ).fetchone()
            if legacy_users_exists:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO Team_members (id, name, phone_number, active)
                    SELECT id, name, phone_number, COALESCE(active, 0)
                    FROM Users
                    """
                )
                conn.execute('DROP TABLE "Users"')
            columns = [row["name"] for row in conn.execute('PRAGMA table_info("Team_members")').fetchall()]
            if "institution" not in columns:
                conn.execute('ALTER TABLE "Team_members" ADD COLUMN institution TEXT')
                columns = [row["name"] for row in conn.execute('PRAGMA table_info("Team_members")').fetchall()]
            if "recruitment_date" not in columns:
                conn.execute('ALTER TABLE "Team_members" ADD COLUMN recruitment_date TEXT')
                columns = [row["name"] for row in conn.execute('PRAGMA table_info("Team_members")').fetchall()]
            if "retirement_date" not in columns:
                conn.execute('ALTER TABLE "Team_members" ADD COLUMN retirement_date TEXT')
                columns = [row["name"] for row in conn.execute('PRAGMA table_info("Team_members")').fetchall()]
            if "active" not in columns:
                conn.execute(
                    'ALTER TABLE "Team_members" ADD COLUMN active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1))'
                )

    def ensure_trips_table(self, fields: list[str] | None = None) -> None:
        self._ensure_team_members_table()
        trip_fields = self._normalize_trip_fields(fields or DEFAULT_TRIP_FIELDS)
        cols = ", ".join([f'"{name}" TEXT' for name in trip_fields if name != "id"])
        with self._connect() as conn:
            conn.execute(
                f'''
                CREATE TABLE IF NOT EXISTS "Trips" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                    {", " + cols if cols else ""}
                )
                '''
            )
            self._migrate_legacy_trips_table(conn, trip_fields)
            existing = {row["name"] for row in conn.execute('PRAGMA table_info("Trips")').fetchall()}
            for field in trip_fields:
                if field not in existing:
                    conn.execute(f'ALTER TABLE "Trips" ADD COLUMN "{field}" TEXT')
            self._migrate_legacy_region_to_location(conn)
            self._rebuild_trips_table_without_region(conn)

    def get_fields(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute('PRAGMA table_info("Trips")').fetchall()
        fields = [row["name"] for row in rows]
        if fields:
            return fields
        self.ensure_trips_table()
        return self._normalize_trip_fields(DEFAULT_TRIP_FIELDS)

    def list_trips(self) -> list[TripRecord]:
        fields = self.get_fields()
        col_sql = ", ".join([f'"{name}"' for name in fields])
        with self._connect() as conn:
            rows = conn.execute(
                f'''
                SELECT {col_sql}
                FROM "Trips"
                ORDER BY
                    LOWER(COALESCE(trip_name, '')),
                    COALESCE(start_date, ''),
                    id
                '''
            ).fetchall()
        return [cast(TripRecord, dict(row)) for row in rows]

    def get_trip(self, trip_id: int) -> TripRecord | None:
        fields = self.get_fields()
        col_sql = ", ".join([f'"{name}"' for name in fields])
        with self._connect() as conn:
            row = conn.execute(
                f'SELECT {col_sql} FROM "Trips" WHERE id = ?',
                (trip_id,),
            ).fetchone()
        return cast(TripRecord, dict(row)) if row else None

    def create_trip(self, data: TripPayloadMap) -> int:
        fields = self.get_fields()
        with self._connect() as conn:
            insert_fields = [name for name in fields if name != "id" and name in data]
            if insert_fields:
                col_sql = ", ".join([f'"{name}"' for name in insert_fields])
                placeholders = ", ".join(["?"] * len(insert_fields))
                values = [data[name] for name in insert_fields]
                cur = conn.execute(
                    f'INSERT INTO "Trips" ({col_sql}) VALUES ({placeholders})',
                    values,
                )
            else:
                cur = conn.execute('INSERT INTO "Trips" DEFAULT VALUES')
            return int(cur.lastrowid)

    def update_trip(self, trip_id: int, data: TripPayloadMap) -> None:
        fields = self.get_fields()
        update_fields = [name for name in fields if name != "id" and name in data]
        if not update_fields:
            raise ValueError("No valid Trip fields supplied.")
        set_sql = ", ".join([f'"{name}" = ?' for name in update_fields])
        values = [data[name] for name in update_fields] + [trip_id]
        with self._connect() as conn:
            conn.execute(
                f'UPDATE "Trips" SET {set_sql} WHERE id = ?',
                values,
            )

    def list_active_team_members(self) -> list[str]:
        self._ensure_team_members_table()
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT name FROM "Team_members" WHERE active = 1 ORDER BY name'
            ).fetchall()
        return [row["name"] for row in rows]

    def list_team_members(self) -> list[TeamMemberRecord]:
        self._ensure_team_members_table()
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT id, name, phone_number, institution, recruitment_date, retirement_date, active FROM "Team_members"'
            ).fetchall()
        team_members = [cast(TeamMemberRecord, dict(row)) for row in rows]
        team_members.sort(
            key=lambda tm: (
                0 if int(tm.get("active", 0)) == 1 else 1,
                self._last_name(str(tm.get("name", ""))),
                str(tm.get("name", "")).lower(),
            )
        )
        return team_members

    def get_team_member(self, team_member_id: int) -> TeamMemberRecord | None:
        self._ensure_team_members_table()
        with self._connect() as conn:
            row = conn.execute(
                'SELECT id, name, phone_number, institution, recruitment_date, retirement_date, active FROM "Team_members" WHERE id = ?',
                (team_member_id,),
            ).fetchone()
        return cast(TeamMemberRecord, dict(row)) if row else None

    def create_team_member(self, name: str, phone_number: str, active: bool, institution: str | None = None) -> int:
        self._ensure_team_members_table()
        with self._connect() as conn:
            cur = conn.execute(
                'INSERT INTO "Team_members" (name, phone_number, institution, active) VALUES (?, ?, ?, ?)',
                (name, phone_number, institution, 1 if active else 0),
            )
            return int(cur.lastrowid)

    def update_team_member(
        self,
        team_member_id: int,
        name: str,
        phone_number: str,
        active: bool,
        institution: str | None = None,
    ) -> None:
        self._ensure_team_members_table()
        with self._connect() as conn:
            conn.execute(
                'UPDATE "Team_members" SET name = ?, phone_number = ?, institution = ?, active = ? WHERE id = ?',
                (name, phone_number, institution, 1 if active else 0, team_member_id),
            )

    def delete_team_member(self, team_member_id: int) -> None:
        self._ensure_team_members_table()
        with self._connect() as conn:
            conn.execute('DELETE FROM "Team_members" WHERE id = ?', (team_member_id,))
