from typing import cast

from repository.domain_types import CollectionEventRecord, FindRecord


class RepositoryFindsMixin:
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
            values = [location_id, collection_event_id]
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
            values = [location_id, collection_event_id]
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
            collection_event_id = int(ce_raw)
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
