from typing import cast

from repository.domain_types import CollectionEventRecord, FindRecord


class RepositoryFindsMixin:
    def list_collection_events(self, trip_id: int | None = None) -> list[CollectionEventRecord]:
        self.ensure_locations_table()
        with self._connect() as conn:
            if trip_id is None:
                rows = conn.execute(
                    """
                    SELECT
                        ce.id,
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
                        ce.collection_name,
                        ce.collection_subset,
                        l.name AS location_name,
                        COUNT(f.id) AS find_count
                    FROM "CollectionEvents" ce
                    JOIN "Locations" l ON l.id = ce.location_id
                    LEFT JOIN "Finds" f ON f.collection_event_id = ce.id
                    WHERE ce.id IN (
                        SELECT DISTINCT f2.collection_event_id
                        FROM "Finds" f2
                        WHERE f2.trip_id = ? AND f2.collection_event_id IS NOT NULL
                    )
                    GROUP BY ce.id, ce.collection_name, ce.collection_subset, l.name
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
                        t.trip_name,
                        l.name AS location_name,
                        ce.collection_subset
                    FROM "Finds" f
                    LEFT JOIN "Trips" t ON t.id = f.trip_id
                    LEFT JOIN "Locations" l ON l.id = f.location_id
                    LEFT JOIN "CollectionEvents" ce ON ce.id = f.collection_event_id
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
                        t.trip_name,
                        l.name AS location_name,
                        ce.collection_subset
                    FROM "Finds" f
                    LEFT JOIN "Trips" t ON t.id = f.trip_id
                    LEFT JOIN "Locations" l ON l.id = f.location_id
                    LEFT JOIN "CollectionEvents" ce ON ce.id = f.collection_event_id
                    WHERE f.trip_id = ?
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
                SELECT COUNT(DISTINCT f.collection_event_id) AS event_count
                FROM "Finds" f
                WHERE f.trip_id = ? AND f.collection_event_id IS NOT NULL
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
                FROM "Finds"
                WHERE trip_id = ?
                """,
                (trip_id,),
            ).fetchone()
        return int(row["find_count"] if row else 0)
