import re
from typing import cast

from repository.domain_types import CollectionEventRecord, FindRecord


class RepositoryFindsMixin:
    _COLLECTION_EVENT_CODE_RE = re.compile(r"\s*\[#\d+\]\s*$")
    _FIND_FIELD_OBSERVATION_FIELDS = (
        "provisional_identification",
        "notes",
        "abund_value",
        "abund_unit",
        "occurrence_comments",
        "research_group",
    )
    _FIND_TAXONOMY_TEXT_FIELDS = (
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
        "reference_no",
        "taxonomy_comments",
    )
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
        "find_date",
        "find_time",
        "latitude",
        "longitude",
    )
    _FIND_CORE_TEXT_FIELDS = (
        "source_system",
        "source_occurrence_no",
        "find_date",
        "find_time",
        "latitude",
        "longitude",
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
                        ft.accepted_name AS accepted_name,
                        ft.identified_name AS identified_name,
                        ft.reference_no AS reference_no,
                        ft.collection_year_latest_estimate AS collection_year_latest_estimate,
                        f.find_date,
                        f.find_time,
                        f.latitude,
                        f.longitude,
                        t.trip_name,
                        ce.collection_name,
                        ce.collection_subset
                    FROM "Finds" f
                    LEFT JOIN "FindTaxonomy" ft ON ft.find_id = f.id
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
                        ft.accepted_name AS accepted_name,
                        ft.identified_name AS identified_name,
                        ft.reference_no AS reference_no,
                        ft.collection_year_latest_estimate AS collection_year_latest_estimate,
                        f.find_date,
                        f.find_time,
                        f.latitude,
                        f.longitude,
                        t.trip_name,
                        ce.collection_name,
                        ce.collection_subset
                    FROM "Finds" f
                    LEFT JOIN "FindTaxonomy" ft ON ft.find_id = f.id
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

    def count_collection_events_by_trip(self) -> dict[int, int]:
        self.ensure_locations_table()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ce.trip_id AS trip_id, COUNT(*) AS event_count
                FROM "CollectionEvents" ce
                WHERE ce.trip_id IS NOT NULL
                GROUP BY ce.trip_id
                """
            ).fetchall()
        return {int(row["trip_id"]): int(row["event_count"] or 0) for row in rows}

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

    def count_finds_by_trip(self) -> dict[int, int]:
        self.ensure_locations_table()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ce.trip_id AS trip_id, COUNT(*) AS find_count
                FROM "Finds" f
                JOIN "CollectionEvents" ce ON ce.id = f.collection_event_id
                WHERE ce.trip_id IS NOT NULL
                GROUP BY ce.trip_id
                """
            ).fetchall()
        return {int(row["trip_id"]): int(row["find_count"] or 0) for row in rows}

    def list_latest_collection_events_by_trip(self) -> dict[int, CollectionEventRecord]:
        self.ensure_locations_table()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ce.trip_id, ce.id, ce.collection_name
                FROM "CollectionEvents" ce
                JOIN (
                    SELECT trip_id, MAX(id) AS max_id
                    FROM "CollectionEvents"
                    WHERE trip_id IS NOT NULL
                    GROUP BY trip_id
                ) latest
                    ON latest.trip_id = ce.trip_id AND latest.max_id = ce.id
                """
            ).fetchall()
        return {
            int(row["trip_id"]): cast(
                CollectionEventRecord,
                {
                    "trip_id": int(row["trip_id"]),
                    "id": int(row["id"]),
                    "collection_name": row["collection_name"],
                },
            )
            for row in rows
        }

    def create_find(self, data: dict[str, object]) -> int:
        self.ensure_locations_table()
        collection_event_id, location_id, text_values, year_value = self._normalize_find_payload(data)

        with self._connect() as conn:
            columns = (
                "location_id",
                "collection_event_id",
                *self._FIND_CORE_TEXT_FIELDS,
            )
            values: list[object] = [location_id, collection_event_id]
            values.extend(text_values[field] for field in self._FIND_CORE_TEXT_FIELDS)
            col_sql = ", ".join([f'"{c}"' for c in columns])
            placeholders = ", ".join(["?"] * len(columns))
            cur = conn.execute(
                f'INSERT INTO "Finds" ({col_sql}) VALUES ({placeholders})',
                values,
            )
            find_id = int(cur.lastrowid)
            self._upsert_split_find_rows(conn, find_id, text_values, year_value)
            return find_id

    def get_find(self, find_id: int) -> FindRecord | None:
        self.ensure_locations_table()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    f.id,
                    f.location_id,
                    l.name AS location_name,
                    f.collection_event_id,
                    f.source_system,
                    f.source_occurrence_no,
                    ft.identified_name AS identified_name,
                    ft.accepted_name AS accepted_name,
                    ft.identified_rank AS identified_rank,
                    ft.accepted_rank AS accepted_rank,
                    ft.difference AS difference,
                    ft.identified_no AS identified_no,
                    ft.accepted_no AS accepted_no,
                    ft.phylum AS phylum,
                    ft.class_name AS class_name,
                    ft.taxon_order AS taxon_order,
                    ft.family AS family,
                    ft.genus AS genus,
                    fo.abund_value AS abund_value,
                    fo.abund_unit AS abund_unit,
                    ft.reference_no AS reference_no,
                    ft.taxonomy_comments AS taxonomy_comments,
                    fo.occurrence_comments AS occurrence_comments,
                    fo.research_group AS research_group,
                    fo.notes AS notes,
                    ft.collection_year_latest_estimate AS collection_year_latest_estimate,
                    f.find_date,
                    f.find_time,
                    f.latitude,
                    f.longitude,
                    f.created_at,
                    f.updated_at
                FROM "Finds" f
                LEFT JOIN "Locations" l ON l.id = f.location_id
                LEFT JOIN "FindFieldObservations" fo ON fo.find_id = f.id
                LEFT JOIN "FindTaxonomy" ft ON ft.find_id = f.id
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
                *self._FIND_CORE_TEXT_FIELDS,
            )
            set_sql = ", ".join([f'"{col}" = ?' for col in set_columns])
            values: list[object] = [location_id, collection_event_id]
            values.extend(text_values[field] for field in self._FIND_CORE_TEXT_FIELDS)
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
            self._upsert_split_find_rows(conn, find_id, text_values, year_value)

    def get_find_field_observations(self, find_id: int) -> dict[str, object] | None:
        self.ensure_locations_table()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    fo.find_id,
                    fo.provisional_identification,
                    fo.abund_value,
                    fo.abund_unit,
                    fo.research_group,
                    fo.notes,
                    fo.occurrence_comments,
                    fo.created_at,
                    fo.updated_at
                FROM "FindFieldObservations" fo
                WHERE fo.find_id = ?
                """,
                (find_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_find_field_observations(self, find_id: int, data: dict[str, object]) -> None:
        self.ensure_locations_table()
        values = {k: (str(data.get(k) or "").strip() or None) for k in ("provisional_identification", "abund_value", "abund_unit", "research_group", "notes", "occurrence_comments")}
        with self._connect() as conn:
            row = conn.execute('SELECT id FROM "Finds" WHERE id = ?', (find_id,)).fetchone()
            if not row:
                raise ValueError("Find does not exist.")
            conn.execute(
                """
                INSERT INTO "FindFieldObservations" (
                    find_id,
                    provisional_identification,
                    notes,
                    abund_value,
                    abund_unit,
                    occurrence_comments,
                    research_group
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(find_id) DO UPDATE SET
                    provisional_identification = excluded.provisional_identification,
                    notes = excluded.notes,
                    abund_value = excluded.abund_value,
                    abund_unit = excluded.abund_unit,
                    occurrence_comments = excluded.occurrence_comments,
                    research_group = excluded.research_group,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    find_id,
                    values["provisional_identification"],
                    values["notes"],
                    values["abund_value"],
                    values["abund_unit"],
                    values["occurrence_comments"],
                    values["research_group"],
                ),
            )

    def get_find_taxonomy(self, find_id: int) -> dict[str, object] | None:
        self.ensure_locations_table()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    ft.find_id,
                    ft.identified_name,
                    ft.accepted_name,
                    ft.identified_rank,
                    ft.accepted_rank,
                    ft.difference,
                    ft.identified_no,
                    ft.accepted_no,
                    ft.phylum,
                    ft.class_name,
                    ft.taxon_order,
                    ft.family,
                    ft.genus,
                    ft.reference_no,
                    ft.taxonomy_comments,
                    ft.collection_year_latest_estimate,
                    ft.created_at,
                    ft.updated_at
                FROM "FindTaxonomy" ft
                WHERE ft.find_id = ?
                """,
                (find_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_find_taxonomy(self, find_id: int, data: dict[str, object]) -> None:
        self.ensure_locations_table()
        text_values = {
            k: (str(data.get(k) or "").strip() or None)
            for k in (
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
                "reference_no",
                "taxonomy_comments",
            )
        }
        year_raw = data.get("collection_year_latest_estimate")
        if year_raw in (None, ""):
            year_value = None
        else:
            try:
                year_value = int(str(year_raw).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError("collection_year_latest_estimate must be an integer.") from exc
        with self._connect() as conn:
            row = conn.execute('SELECT id FROM "Finds" WHERE id = ?', (find_id,)).fetchone()
            if not row:
                raise ValueError("Find does not exist.")
            conn.execute(
                """
                INSERT INTO "FindTaxonomy" (
                    find_id,
                    identified_name,
                    accepted_name,
                    identified_rank,
                    accepted_rank,
                    difference,
                    identified_no,
                    accepted_no,
                    phylum,
                    class_name,
                    taxon_order,
                    family,
                    genus,
                    reference_no,
                    taxonomy_comments,
                    collection_year_latest_estimate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(find_id) DO UPDATE SET
                    identified_name = excluded.identified_name,
                    accepted_name = excluded.accepted_name,
                    identified_rank = excluded.identified_rank,
                    accepted_rank = excluded.accepted_rank,
                    difference = excluded.difference,
                    identified_no = excluded.identified_no,
                    accepted_no = excluded.accepted_no,
                    phylum = excluded.phylum,
                    class_name = excluded.class_name,
                    taxon_order = excluded.taxon_order,
                    family = excluded.family,
                    genus = excluded.genus,
                    reference_no = excluded.reference_no,
                    taxonomy_comments = excluded.taxonomy_comments,
                    collection_year_latest_estimate = excluded.collection_year_latest_estimate,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    find_id,
                    text_values["identified_name"],
                    text_values["accepted_name"],
                    text_values["identified_rank"],
                    text_values["accepted_rank"],
                    text_values["difference"],
                    text_values["identified_no"],
                    text_values["accepted_no"],
                    text_values["phylum"],
                    text_values["class_name"],
                    text_values["taxon_order"],
                    text_values["family"],
                    text_values["genus"],
                    text_values["reference_no"],
                    text_values["taxonomy_comments"],
                    year_value,
                ),
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

    def _upsert_split_find_rows(
        self,
        conn,
        find_id: int,
        text_values: dict[str, str | None],
        year_value: int | None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO "FindFieldObservations" (
                find_id,
                provisional_identification,
                notes,
                abund_value,
                abund_unit,
                occurrence_comments,
                research_group
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(find_id) DO UPDATE SET
                provisional_identification = excluded.provisional_identification,
                notes = excluded.notes,
                abund_value = excluded.abund_value,
                abund_unit = excluded.abund_unit,
                occurrence_comments = excluded.occurrence_comments,
                research_group = excluded.research_group,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                find_id,
                text_values["identified_name"],
                text_values["notes"],
                text_values["abund_value"],
                text_values["abund_unit"],
                text_values["occurrence_comments"],
                text_values["research_group"],
            ),
        )
        conn.execute(
            """
            INSERT INTO "FindTaxonomy" (
                find_id,
                identified_name,
                accepted_name,
                identified_rank,
                accepted_rank,
                difference,
                identified_no,
                accepted_no,
                phylum,
                class_name,
                taxon_order,
                family,
                genus,
                reference_no,
                taxonomy_comments,
                collection_year_latest_estimate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(find_id) DO UPDATE SET
                identified_name = excluded.identified_name,
                accepted_name = excluded.accepted_name,
                identified_rank = excluded.identified_rank,
                accepted_rank = excluded.accepted_rank,
                difference = excluded.difference,
                identified_no = excluded.identified_no,
                accepted_no = excluded.accepted_no,
                phylum = excluded.phylum,
                class_name = excluded.class_name,
                taxon_order = excluded.taxon_order,
                family = excluded.family,
                genus = excluded.genus,
                reference_no = excluded.reference_no,
                taxonomy_comments = excluded.taxonomy_comments,
                collection_year_latest_estimate = excluded.collection_year_latest_estimate,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                find_id,
                text_values["identified_name"],
                text_values["accepted_name"],
                text_values["identified_rank"],
                text_values["accepted_rank"],
                text_values["difference"],
                text_values["identified_no"],
                text_values["accepted_no"],
                text_values["phylum"],
                text_values["class_name"],
                text_values["taxon_order"],
                text_values["family"],
                text_values["genus"],
                text_values["reference_no"],
                text_values["taxonomy_comments"],
                year_value,
            ),
        )
