import re
from typing import cast

from repository.domain_types import CollectionEventRecord, FindRecord


class RepositoryFindsMixin:
    _COLLECTION_EVENT_CODE_RE = re.compile(r"\s*\[#\d+\]\s*$")
    _FIND_MUTABLE_TEXT_FIELDS = (
        "source_system",
        "source_occurrence_no",
        "identified_name",
        "accepted_name",
        "identified_rank",
        "accepted_rank",
        "difference",
        "identified_no",
        "accepted_no",
        "phylum",
        "class_name",
        "taxon_order",
        "family",
        "genus",
        "abund_value",
        "abund_unit",
        "reference_no",
        "taxonomy_comments",
        "occurrence_comments",
        "research_group",
        "notes",
    )

    def list_collection_events(self, trip_id: int | None = None) -> list[CollectionEventRecord]:
        self.ensure_locations_table()
        with self._connect() as conn:
            if trip_id is None:
                rows = conn.execute(
                    """
                    SELECT
                        ce.id,
                        ce.trip_id,
                        ce.event_year,
                        ce.collection_name,
                        ce.collection_subset,
                        l.name AS location_name,
                        COUNT(f.id) AS find_count
                    FROM "CollectionEvents" ce
                    JOIN "Locations" l ON l.id = ce.location_id
                    LEFT JOIN "Finds" f ON f.collection_event_id = ce.id
                    GROUP BY ce.id, ce.collection_name, ce.collection_subset, l.name
                    ORDER BY LOWER(COALESCE(l.name, '')), LOWER(COALESCE(ce.collection_subset, '')), ce.id
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        ce.id,
                        ce.trip_id,
                        ce.event_year,
                        ce.collection_name,
                        ce.collection_subset,
                        l.name AS location_name,
                        COUNT(f.id) AS find_count
                    FROM "CollectionEvents" ce
                    JOIN "Locations" l ON l.id = ce.location_id
                    LEFT JOIN "Finds" f ON f.collection_event_id = ce.id
                    WHERE ce.trip_id = ?
                    GROUP BY ce.id, ce.trip_id, ce.event_year, ce.collection_name, ce.collection_subset, l.name
                    ORDER BY LOWER(COALESCE(l.name, '')), LOWER(COALESCE(ce.collection_subset, '')), ce.id
                    """,
                    (trip_id,),
                ).fetchall()
        return [cast(CollectionEventRecord, dict(row)) for row in rows]

    def create_collection_event_for_trip(
        self,
        trip_id: int,
        collection_name: str,
        event_year: int | None = None,
    ) -> int:
        self.ensure_locations_table()
        cleaned_name = self._normalize_collection_event_base_name(collection_name)
        if not cleaned_name:
            raise ValueError("collection_name is required.")
        with self._connect() as conn:
            trip_row = conn.execute(
                'SELECT id, location FROM "Trips" WHERE id = ?',
                (trip_id,),
            ).fetchone()
            if not trip_row:
                raise ValueError("Trip does not exist.")
            location_value = str(trip_row["location"] or "").strip()
            location_candidates = [part.strip() for part in location_value.split(";") if part.strip()]
            if not location_candidates:
                raise ValueError("Trip has no location. Set trip location before creating a Collection Event.")

            location_id: int | None = None
            for candidate in location_candidates:
                row = conn.execute(
                    """
                    SELECT id
                    FROM "Locations"
                    WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
                    ORDER BY id
                    LIMIT 1
                    """,
                    (candidate,),
                ).fetchone()
                if row:
                    location_id = int(row["id"])
                    break
            if location_id is None:
                raise ValueError("Trip location was not found in Locations.")

            cur = conn.execute(
                """
                INSERT INTO "CollectionEvents" (trip_id, location_id, collection_name, collection_subset, event_year)
                VALUES (?, ?, ?, NULL, ?)
                """,
                (trip_id, location_id, cleaned_name, event_year),
            )
            collection_event_id = int(cur.lastrowid)
            formatted_name = self._format_collection_event_name(cleaned_name, collection_event_id)
            conn.execute(
                'UPDATE "CollectionEvents" SET collection_name = ? WHERE id = ?',
                (formatted_name, collection_event_id),
            )
            return collection_event_id

    def update_collection_event_name(self, collection_event_id: int, collection_name: str) -> None:
        self.ensure_locations_table()
        cleaned_name = self._normalize_collection_event_base_name(collection_name)
        if not cleaned_name:
            raise ValueError("collection_name is required.")
        formatted_name = self._format_collection_event_name(cleaned_name, collection_event_id)
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE "CollectionEvents"
                SET collection_name = ?
                WHERE id = ?
                """,
                (formatted_name, collection_event_id),
            )
            if int(cur.rowcount or 0) == 0:
                raise ValueError("Collection Event does not exist.")

    def backfill_collection_event_codes(self) -> int:
        self.ensure_locations_table()
        updated = 0
        with self._connect() as conn:
            rows = conn.execute('SELECT id, collection_name FROM "CollectionEvents"').fetchall()
            for row in rows:
                collection_event_id = int(row["id"])
                base_name = self._normalize_collection_event_base_name(str(row["collection_name"] or ""))
                if not base_name:
                    base_name = "Collection Event"
                formatted_name = self._format_collection_event_name(base_name, collection_event_id)
                if formatted_name != str(row["collection_name"] or ""):
                    conn.execute(
                        'UPDATE "CollectionEvents" SET collection_name = ? WHERE id = ?',
                        (formatted_name, collection_event_id),
                    )
                    updated += 1
        return updated

    def _normalize_collection_event_base_name(self, collection_name: str) -> str:
        raw = str(collection_name or "").strip()
        return self._COLLECTION_EVENT_CODE_RE.sub("", raw).strip()

    @staticmethod
    def _format_collection_event_name(base_name: str, collection_event_id: int) -> str:
        return f"{base_name} [#{int(collection_event_id)}]"

    def list_finds(self, trip_id: int | None = None) -> list[FindRecord]:
        self.ensure_locations_table()
        with self._connect() as conn:
            if trip_id is None:
                rows = conn.execute(
                    """
                    SELECT
                        f.id,
                        f.source_occurrence_no,
                        f.accepted_name,
                        f.identified_name,
                        f.reference_no,
                        f.collection_year_latest_estimate,
                        t.trip_name,
                        ce.collection_name,
                        ce.collection_subset
                    FROM "Finds" f
                    LEFT JOIN "CollectionEvents" ce ON ce.id = f.collection_event_id
                    LEFT JOIN "Trips" t ON t.id = ce.trip_id
                    LEFT JOIN "Locations" l ON l.id = f.location_id
                    ORDER BY LOWER(COALESCE(l.name, '')), f.id
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        f.id,
                        f.source_occurrence_no,
                        f.accepted_name,
                        f.identified_name,
                        f.reference_no,
                        f.collection_year_latest_estimate,
                        t.trip_name,
                        ce.collection_name,
                        ce.collection_subset
                    FROM "Finds" f
                    LEFT JOIN "CollectionEvents" ce ON ce.id = f.collection_event_id
                    LEFT JOIN "Trips" t ON t.id = ce.trip_id
                    LEFT JOIN "Locations" l ON l.id = f.location_id
                    WHERE ce.trip_id = ?
                    ORDER BY LOWER(COALESCE(l.name, '')), f.id
                    """,
                    (trip_id,),
                ).fetchall()
        return [cast(FindRecord, dict(row)) for row in rows]

    def count_collection_events_for_trip(self, trip_id: int) -> int:
        self.ensure_locations_table()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(DISTINCT ce.id) AS event_count
                FROM "CollectionEvents" ce
                WHERE ce.trip_id = ?
                """,
                (trip_id,),
            ).fetchone()
        return int(row["event_count"] if row else 0)

    def count_finds_for_trip(self, trip_id: int) -> int:
        self.ensure_locations_table()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS find_count
                FROM "Finds" f
                JOIN "CollectionEvents" ce ON ce.id = f.collection_event_id
                WHERE ce.trip_id = ?
                """,
                (trip_id,),
            ).fetchone()
        return int(row["find_count"] if row else 0)

    def create_find(self, data: dict[str, object]) -> int:
        self.ensure_locations_table()
        collection_event_id, location_id, text_values, year_value = self._normalize_find_payload(data)

        with self._connect() as conn:
            columns = (
                "location_id",
                "collection_event_id",
                *self._FIND_MUTABLE_TEXT_FIELDS,
                "collection_year_latest_estimate",
            )
            values: list[object] = [location_id, collection_event_id]
            values.extend(text_values[field] for field in self._FIND_MUTABLE_TEXT_FIELDS)
            values.append(year_value)
            col_sql = ", ".join([f'"{c}"' for c in columns])
            placeholders = ", ".join(["?"] * len(columns))
            cur = conn.execute(
                f'INSERT INTO "Finds" ({col_sql}) VALUES ({placeholders})',
                values,
            )
            return int(cur.lastrowid)

    def get_find(self, find_id: int) -> FindRecord | None:
        self.ensure_locations_table()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    f.id,
                    f.location_id,
                    f.collection_event_id,
                    f.source_system,
                    f.source_occurrence_no,
                    f.identified_name,
                    f.accepted_name,
                    f.identified_rank,
                    f.accepted_rank,
                    f.difference,
                    f.identified_no,
                    f.accepted_no,
                    f.phylum,
                    f.class_name,
                    f.taxon_order,
                    f.family,
                    f.genus,
                    f.abund_value,
                    f.abund_unit,
                    f.reference_no,
                    f.taxonomy_comments,
                    f.occurrence_comments,
                    f.research_group,
                    f.notes,
                    f.collection_year_latest_estimate
                    ,
                    f.created_at,
                    f.updated_at
                FROM "Finds" f
                WHERE f.id = ?
                """,
                (find_id,),
            ).fetchone()
        return cast(FindRecord, dict(row)) if row else None

    def update_find(self, find_id: int, data: dict[str, object]) -> None:
        self.ensure_locations_table()
        collection_event_id, location_id, text_values, year_value = self._normalize_find_payload(data)

        with self._connect() as conn:
            set_columns = (
                "location_id",
                "collection_event_id",
                *self._FIND_MUTABLE_TEXT_FIELDS,
                "collection_year_latest_estimate",
            )
            set_sql = ", ".join([f'"{col}" = ?' for col in set_columns])
            values: list[object] = [location_id, collection_event_id]
            values.extend(text_values[field] for field in self._FIND_MUTABLE_TEXT_FIELDS)
            values.append(year_value)
            values.append(find_id)
            conn.execute(
                """
                UPDATE "Finds"
                SET
                """
                + set_sql
                + """
                WHERE id = ?
                """,
                values,
            )

    def _normalize_find_payload(
        self,
        data: dict[str, object],
    ) -> tuple[int, int, dict[str, str | None], int | None]:
        ce_raw = data.get("collection_event_id")
        if ce_raw in (None, ""):
            raise ValueError("collection_event_id is required.")
        try:
            collection_event_id = int(str(ce_raw).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError("collection_event_id must be an integer.") from exc

        with self._connect() as conn:
            ce_row = conn.execute(
                'SELECT id, location_id FROM "CollectionEvents" WHERE id = ?',
                (collection_event_id,),
            ).fetchone()
            if not ce_row:
                raise ValueError("Selected collection event does not exist.")
            location_id = int(ce_row["location_id"])

        text_values: dict[str, str | None] = {}
        for field in self._FIND_MUTABLE_TEXT_FIELDS:
            raw = str(data.get(field) or "").strip()
            if field == "source_system":
                text_values[field] = raw or "manual"
            else:
                text_values[field] = raw or None

        year_raw = data.get("collection_year_latest_estimate")
        if year_raw in (None, ""):
            year_value = None
        else:
            try:
                year_value = int(str(year_raw).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError("collection_year_latest_estimate must be an integer.") from exc

        return collection_event_id, location_id, text_values, year_value
