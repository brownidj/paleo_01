from typing import cast

from domain_types import TripPayloadMap, TripRecord, UserRecord
from repository_base import DEFAULT_TRIP_FIELDS


class RepositoryTripUserMixin:
    def ensure_trips_table(self, fields: list[str] | None = None) -> None:
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

    def list_active_users(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT name FROM "Users" WHERE active = 1 ORDER BY name'
            ).fetchall()
        return [row["name"] for row in rows]

    def list_users(self) -> list[UserRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT id, name, phone_number, active FROM "Users"'
            ).fetchall()
        users = [cast(UserRecord, dict(row)) for row in rows]
        users.sort(
            key=lambda u: (
                0 if int(u.get("active", 0)) == 1 else 1,
                self._last_name(str(u.get("name", ""))),
                str(u.get("name", "")).lower(),
            )
        )
        return users

    def get_user(self, user_id: int) -> UserRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT id, name, phone_number, active FROM "Users" WHERE id = ?',
                (user_id,),
            ).fetchone()
        return cast(UserRecord, dict(row)) if row else None

    def create_user(self, name: str, phone_number: str, active: bool) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                'INSERT INTO "Users" (name, phone_number, active) VALUES (?, ?, ?)',
                (name, phone_number, 1 if active else 0),
            )
            return int(cur.lastrowid)

    def update_user(self, user_id: int, name: str, phone_number: str, active: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                'UPDATE "Users" SET name = ?, phone_number = ?, active = ? WHERE id = ?',
                (name, phone_number, 1 if active else 0, user_id),
            )

    def delete_user(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute('DELETE FROM "Users" WHERE id = ?', (user_id,))
