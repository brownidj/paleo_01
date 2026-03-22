from typing import cast

from repository.domain_types import GeologyRecord, GeologyUpdatePayloadMap, LithologyRow

class RepositoryGeologyDataMixin:
    def list_geology_records(self) -> list[GeologyRecord]:
        self.ensure_locations_table()
        self.ensure_geology_tables()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    gc.id AS geology_id,
                    gc.source_reference_no,
                    gc.early_interval,
                    gc.late_interval,
                    gc.max_ma,
                    gc.min_ma,
                    gc.environment,
                    gc.formation,
                    gc.stratigraphy_group,
                    gc.member,
                    gc.stratigraphy_comments,
                    gc.geology_comments,
                    gc.geoplate,
                    gc.paleomodel,
                    gc.paleolat,
                    gc.paleolng,
                    l.id AS location_id,
                    l.name AS location_name,
                    l.state,
                    l.country_code
                FROM "GeologyContext" gc
                JOIN "Locations" l ON l.id = gc.location_id
                ORDER BY
                    COALESCE(l.name, ''),
                    gc.id
                """
            ).fetchall()
            lith_rows = conn.execute(
                """
                SELECT
                    geology_context_id,
                    slot,
                    lithology,
                    lithification,
                    minor_lithology,
                    lithology_adjectives,
                    fossils_from
                FROM "Lithology"
                ORDER BY geology_context_id, slot
                """
            ).fetchall()

        lithology_by_geology: dict[int, list[LithologyRow]] = {}
        for row in lith_rows:
            geology_id = int(row["geology_context_id"])
            lithology_by_geology.setdefault(geology_id, []).append(
                {
                    "slot": row["slot"],
                    "lithology": row["lithology"],
                    "lithification": row["lithification"],
                    "minor_lithology": row["minor_lithology"],
                    "lithology_adjectives": row["lithology_adjectives"],
                    "fossils_from": row["fossils_from"],
                }
            )

        records: list[GeologyRecord] = []
        for row in rows:
            record = cast(GeologyRecord, dict(row))
            geology_id = int(record["geology_id"])
            lithology_rows = lithology_by_geology.get(geology_id, [])
            summary_parts: list[str] = []
            for lith in lithology_rows:
                label = str(lith.get("lithology") or "").strip()
                if label:
                    summary_parts.append(label)
            record["lithology_rows"] = lithology_rows
            record["lithology_summary"] = ", ".join(summary_parts)
            records.append(record)
        return records

    def get_geology_record(self, geology_id: int) -> GeologyRecord | None:
        self.ensure_locations_table()
        self.ensure_geology_tables()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    gc.id AS geology_id,
                    gc.location_id,
                    gc.location_name,
                    gc.source_reference_no,
                    gc.early_interval,
                    gc.late_interval,
                    gc.max_ma,
                    gc.min_ma,
                    gc.environment,
                    gc.geogscale,
                    gc.geology_comments,
                    gc.formation,
                    gc.stratigraphy_group,
                    gc.member,
                    gc.stratscale,
                    gc.stratigraphy_comments,
                    gc.geoplate,
                    gc.paleomodel,
                    gc.paleolat,
                    gc.paleolng
                FROM "GeologyContext" gc
                WHERE gc.id = ?
                """,
                (geology_id,),
            ).fetchone()
            if not row:
                return None
            lith_rows = conn.execute(
                """
                SELECT
                    slot,
                    lithology,
                    lithification,
                    minor_lithology,
                    lithology_adjectives,
                    fossils_from
                FROM "Lithology"
                WHERE geology_context_id = ?
                ORDER BY slot
                """,
                (geology_id,),
            ).fetchall()

        record = cast(GeologyRecord, dict(row))
        record["lithology_rows"] = [cast(LithologyRow, dict(r)) for r in lith_rows]
        return record

    def update_geology_record(self, geology_id: int, data: GeologyUpdatePayloadMap) -> None:
        self.ensure_locations_table()
        self.ensure_geology_tables()
        allowed_fields = [
            "source_reference_no",
            "early_interval",
            "late_interval",
            "max_ma",
            "min_ma",
            "environment",
            "geogscale",
            "geology_comments",
            "formation",
            "stratigraphy_group",
            "member",
            "stratscale",
            "stratigraphy_comments",
            "geoplate",
            "paleomodel",
            "paleolat",
            "paleolng",
        ]
        update_fields = [f for f in allowed_fields if f in data]
        lithology_rows = data.get("lithology_rows", [])
        with self._connect() as conn:
            if update_fields:
                set_sql = ", ".join([f'"{name}" = ?' for name in update_fields])
                values = [data.get(name) for name in update_fields] + [geology_id]
                conn.execute(f'UPDATE "GeologyContext" SET {set_sql} WHERE id = ?', values)
                conn.execute(
                    'UPDATE "GeologyContext" SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (geology_id,),
                )
            conn.execute('DELETE FROM "Lithology" WHERE geology_context_id = ?', (geology_id,))
            inserts: list[tuple[object, ...]] = []
            if isinstance(lithology_rows, list):
                for raw in lithology_rows:
                    if not isinstance(raw, dict):
                        continue
                    slot = raw.get("slot")
                    if slot not in {1, 2}:
                        continue
                    lithology = raw.get("lithology")
                    lithification = raw.get("lithification")
                    minor_lithology = raw.get("minor_lithology")
                    lithology_adjectives = raw.get("lithology_adjectives")
                    fossils_from = raw.get("fossils_from")
                    if not any([lithology, lithification, minor_lithology, lithology_adjectives, fossils_from]):
                        continue
                    inserts.append(
                        (
                            geology_id,
                            slot,
                            lithology,
                            lithification,
                            minor_lithology,
                            lithology_adjectives,
                            fossils_from,
                        )
                    )
            if inserts:
                conn.executemany(
                    """
                    INSERT INTO "Lithology" (
                        geology_context_id,
                        slot,
                        lithology,
                        lithification,
                        minor_lithology,
                        lithology_adjectives,
                        fossils_from
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    inserts,
                )
