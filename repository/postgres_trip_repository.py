from __future__ import annotations

import os
import re
from contextlib import contextmanager
from typing import cast

from psycopg import connect
from psycopg.rows import dict_row

from repository.domain_types import CollectionEventRecord, FindRecord, GeologyRecord, LithologyRow, LocationRecord, TeamMemberRecord, TripPayloadMap, TripRecord
from repository.repository_base import DEFAULT_TRIP_FIELDS, LOCATION_FIELDS


class PostgresTripRepository:
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

    def list_location_names(self) -> list[str]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT name FROM locations WHERE name IS NOT NULL AND TRIM(name) <> '' ORDER BY name")
            rows = cur.fetchall()
        return [str(r["name"]) for r in rows]

    def list_locations(self) -> list[LocationRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f'SELECT id, geology_id, {", ".join(LOCATION_FIELDS)} FROM locations')
            loc_rows = cur.fetchall()
            cur.execute("SELECT location_id, collection_name, collection_subset FROM collection_events ORDER BY id")
            event_rows = cur.fetchall()
        events_by_location: dict[int, list[dict[str, str | None]]] = {}
        for row in event_rows:
            lid = int(row["location_id"])
            events_by_location.setdefault(lid, []).append({"collection_name": row["collection_name"], "collection_subset": row["collection_subset"]})
        locations = [cast(LocationRecord, dict(r)) for r in loc_rows]
        for loc in locations:
            events = events_by_location.get(int(loc["id"]), [])
            loc["collection_events"] = events
            first = events[0] if events else None
            loc["collection_name"] = first.get("collection_name") if first else None
            loc["collection_subset"] = first.get("collection_subset") if first else None
        locations.sort(key=lambda r: (str(r.get("name", "")).lower(), str(r.get("lga", "")).lower(), str(r.get("state", "")).lower()))
        return locations

    def get_location(self, location_id: int) -> LocationRecord | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f'SELECT id, geology_id, {", ".join(LOCATION_FIELDS)} FROM locations WHERE id = %s', (location_id,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("SELECT collection_name, collection_subset FROM collection_events WHERE location_id = %s ORDER BY id", (location_id,))
            events = cur.fetchall()
        loc = cast(LocationRecord, dict(row))
        collection_events = [{"collection_name": e["collection_name"], "collection_subset": e["collection_subset"]} for e in events]
        loc["collection_events"] = collection_events
        first = collection_events[0] if collection_events else None
        loc["collection_name"] = first.get("collection_name") if first else None
        loc["collection_subset"] = first.get("collection_subset") if first else None
        return loc

    def create_location(self, data: dict[str, object]) -> int:
        events = self._normalize_collection_events(data.get("collection_events"))
        cols = [f for f in LOCATION_FIELDS if f in data] + (["geology_id"] if "geology_id" in data else [])
        vals = [data.get(c) for c in cols]
        with self._connect() as conn, conn.cursor() as cur:
            if cols:
                cur.execute(f'INSERT INTO locations ({", ".join(cols)}) VALUES ({", ".join(["%s"]*len(cols))}) RETURNING id', vals)
            else:
                cur.execute("INSERT INTO locations DEFAULT VALUES RETURNING id")
            location_id = int(cur.fetchone()["id"])
            for event in events:
                cur.execute("INSERT INTO collection_events (location_id, collection_name, collection_subset) VALUES (%s, %s, %s)", (location_id, event["collection_name"], event["collection_subset"]))
            return location_id

    def update_location(self, location_id: int, data: dict[str, object]) -> None:
        has_events = "collection_events" in data
        events = self._normalize_collection_events(data.get("collection_events"))
        cols = [f for f in LOCATION_FIELDS if f in data] + (["geology_id"] if "geology_id" in data else [])
        with self._connect() as conn, conn.cursor() as cur:
            if cols:
                set_sql = ", ".join([f"{c} = %s" for c in cols])
                cur.execute(f"UPDATE locations SET {set_sql} WHERE id = %s", [data.get(c) for c in cols] + [location_id])
            if has_events:
                cur.execute("DELETE FROM collection_events WHERE location_id = %s", (location_id,))
                for event in events:
                    cur.execute("INSERT INTO collection_events (location_id, collection_name, collection_subset) VALUES (%s, %s, %s)", (location_id, event["collection_name"], event["collection_subset"]))

    def list_collection_events(self, trip_id: int | None = None) -> list[CollectionEventRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            if trip_id is None:
                cur.execute("SELECT ce.id, ce.trip_id, ce.event_year, ce.collection_name, ce.collection_subset, l.name AS location_name, COUNT(f.id) AS find_count FROM collection_events ce JOIN locations l ON l.id=ce.location_id LEFT JOIN finds f ON f.collection_event_id=ce.id GROUP BY ce.id, l.name ORDER BY LOWER(COALESCE(l.name,'')), LOWER(COALESCE(ce.collection_subset,'')), ce.id")
            else:
                cur.execute("SELECT ce.id, ce.trip_id, ce.event_year, ce.collection_name, ce.collection_subset, l.name AS location_name, COUNT(f.id) AS find_count FROM collection_events ce JOIN locations l ON l.id=ce.location_id LEFT JOIN finds f ON f.collection_event_id=ce.id WHERE ce.trip_id = %s GROUP BY ce.id, l.name ORDER BY LOWER(COALESCE(l.name,'')), LOWER(COALESCE(ce.collection_subset,'')), ce.id", (trip_id,))
            rows = cur.fetchall()
        return [cast(CollectionEventRecord, dict(r)) for r in rows]

    def list_finds(self, trip_id: int | None = None) -> list[FindRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            if trip_id is None:
                cur.execute("SELECT f.id, f.source_occurrence_no, f.accepted_name, f.identified_name, f.reference_no, f.collection_year_latest_estimate, t.trip_name, ce.collection_name, ce.collection_subset FROM finds f LEFT JOIN collection_events ce ON ce.id=f.collection_event_id LEFT JOIN trips t ON t.id=ce.trip_id LEFT JOIN locations l ON l.id=f.location_id ORDER BY LOWER(COALESCE(l.name,'')), f.id")
            else:
                cur.execute("SELECT f.id, f.source_occurrence_no, f.accepted_name, f.identified_name, f.reference_no, f.collection_year_latest_estimate, t.trip_name, ce.collection_name, ce.collection_subset FROM finds f LEFT JOIN collection_events ce ON ce.id=f.collection_event_id LEFT JOIN trips t ON t.id=ce.trip_id LEFT JOIN locations l ON l.id=f.location_id WHERE ce.trip_id = %s ORDER BY LOWER(COALESCE(l.name,'')), f.id", (trip_id,))
            rows = cur.fetchall()
        return [cast(FindRecord, dict(r)) for r in rows]

    def count_collection_events_for_trip(self, trip_id: int) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(DISTINCT id) AS event_count FROM collection_events WHERE trip_id = %s", (trip_id,))
            return int(cur.fetchone()["event_count"])

    def count_finds_for_trip(self, trip_id: int) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS find_count FROM finds f JOIN collection_events ce ON ce.id=f.collection_event_id WHERE ce.trip_id = %s", (trip_id,))
            return int(cur.fetchone()["find_count"])

    def create_find(self, data: dict[str, object]) -> int:
        collection_event_id, location_id, text_values, year_value = self._normalize_find_payload(data)
        cols = ["location_id", "collection_event_id", "source_system", "source_occurrence_no", "identified_name", "accepted_name", "identified_rank", "accepted_rank", "difference", "identified_no", "accepted_no", "phylum", "class_name", "taxon_order", "family", "genus", "abund_value", "abund_unit", "reference_no", "taxonomy_comments", "occurrence_comments", "research_group", "notes", "collection_year_latest_estimate"]
        vals = [location_id, collection_event_id] + [text_values[c] for c in cols[2:-1]] + [year_value]
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f'INSERT INTO finds ({", ".join(cols)}) VALUES ({", ".join(["%s"]*len(cols))}) RETURNING id', vals)
            return int(cur.fetchone()["id"])

    def get_find(self, find_id: int) -> FindRecord | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, location_id, collection_event_id, source_system, source_occurrence_no, identified_name, accepted_name, identified_rank, accepted_rank, difference, identified_no, accepted_no, phylum, class_name, taxon_order, family, genus, abund_value, abund_unit, reference_no, taxonomy_comments, occurrence_comments, research_group, notes, collection_year_latest_estimate, created_at::text AS created_at, updated_at::text AS updated_at FROM finds WHERE id = %s", (find_id,))
            row = cur.fetchone()
        return cast(FindRecord, dict(row)) if row else None

    def update_find(self, find_id: int, data: dict[str, object]) -> None:
        collection_event_id, location_id, text_values, year_value = self._normalize_find_payload(data)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE finds SET location_id=%s, collection_event_id=%s, source_system=%s, source_occurrence_no=%s, identified_name=%s, accepted_name=%s, identified_rank=%s, accepted_rank=%s, difference=%s, identified_no=%s, accepted_no=%s, phylum=%s, class_name=%s, taxon_order=%s, family=%s, genus=%s, abund_value=%s, abund_unit=%s, reference_no=%s, taxonomy_comments=%s, occurrence_comments=%s, research_group=%s, notes=%s, collection_year_latest_estimate=%s WHERE id=%s",
                (location_id, collection_event_id, text_values["source_system"], text_values["source_occurrence_no"], text_values["identified_name"], text_values["accepted_name"], text_values["identified_rank"], text_values["accepted_rank"], text_values["difference"], text_values["identified_no"], text_values["accepted_no"], text_values["phylum"], text_values["class_name"], text_values["taxon_order"], text_values["family"], text_values["genus"], text_values["abund_value"], text_values["abund_unit"], text_values["reference_no"], text_values["taxonomy_comments"], text_values["occurrence_comments"], text_values["research_group"], text_values["notes"], year_value, find_id),
            )

    def list_geology_records(self) -> list[GeologyRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT gc.id AS geology_id, gc.source_reference_no, gc.early_interval, gc.late_interval, gc.max_ma, gc.min_ma, gc.environment, gc.formation, gc.stratigraphy_group, gc.member, gc.stratigraphy_comments, gc.geology_comments, gc.geoplate, gc.paleomodel, gc.paleolat, gc.paleolng, l.id AS location_id, l.name AS location_name, l.state, l.country_code FROM geology_context gc JOIN locations l ON l.id=gc.location_id ORDER BY COALESCE(l.name,''), gc.id")
            rows = cur.fetchall()
            cur.execute("SELECT geology_context_id, slot, lithology, lithification, minor_lithology, lithology_adjectives, fossils_from FROM lithology ORDER BY geology_context_id, slot")
            lith_rows = cur.fetchall()
        lithology_by: dict[int, list[LithologyRow]] = {}
        for row in lith_rows:
            gid = int(row["geology_context_id"])
            lithology_by.setdefault(gid, []).append(cast(LithologyRow, dict(row)))
        records: list[GeologyRecord] = []
        for row in rows:
            rec = cast(GeologyRecord, dict(row))
            gid = int(rec["geology_id"])
            lrows = lithology_by.get(gid, [])
            rec["lithology_rows"] = lrows
            rec["lithology_summary"] = ", ".join([str(l.get("lithology") or "").strip() for l in lrows if str(l.get("lithology") or "").strip()])
            records.append(rec)
        return records

    def get_geology_record(self, geology_id: int) -> GeologyRecord | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id AS geology_id, location_id, location_name, source_reference_no, early_interval, late_interval, max_ma, min_ma, environment, geogscale, geology_comments, formation, stratigraphy_group, member, stratscale, stratigraphy_comments, geoplate, paleomodel, paleolat, paleolng FROM geology_context WHERE id = %s", (geology_id,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("SELECT slot, lithology, lithification, minor_lithology, lithology_adjectives, fossils_from FROM lithology WHERE geology_context_id = %s ORDER BY slot", (geology_id,))
            lith_rows = cur.fetchall()
        rec = cast(GeologyRecord, dict(row))
        rec["lithology_rows"] = [cast(LithologyRow, dict(r)) for r in lith_rows]
        return rec

    def create_geology_record(self, location_id: int, data: dict[str, object]) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, name FROM locations WHERE id = %s", (location_id,))
            loc = cur.fetchone()
            if not loc or not str(loc["name"] or "").strip():
                raise ValueError("Selected location has no valid name.")
            cur.execute("INSERT INTO geology_context (location_id, location_name, source_system, source_reference_no, early_interval, late_interval, max_ma, min_ma, environment, geogscale, geology_comments, formation, stratigraphy_group, member, stratscale, stratigraphy_comments, geoplate, paleomodel, paleolat, paleolng) VALUES (%s, %s, 'PBDB', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                        (location_id, str(loc["name"]).strip(), data.get("source_reference_no"), data.get("early_interval"), data.get("late_interval"), data.get("max_ma"), data.get("min_ma"), data.get("environment"), data.get("geogscale"), data.get("geology_comments"), data.get("formation"), data.get("stratigraphy_group"), data.get("member"), data.get("stratscale"), data.get("stratigraphy_comments"), data.get("geoplate"), data.get("paleomodel"), data.get("paleolat"), data.get("paleolng")))
            gid = int(cur.fetchone()["id"])
            for raw in cast(list[dict], data.get("lithology_rows", []) or []):
                slot = raw.get("slot")
                if slot in {1, 2} and any(raw.get(k) for k in ("lithology", "lithification", "minor_lithology", "lithology_adjectives", "fossils_from")):
                    cur.execute("INSERT INTO lithology (geology_context_id, slot, lithology, lithification, minor_lithology, lithology_adjectives, fossils_from) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                (gid, slot, raw.get("lithology"), raw.get("lithification"), raw.get("minor_lithology"), raw.get("lithology_adjectives"), raw.get("fossils_from")))
            return gid

    def update_geology_record(self, geology_id: int, data: dict[str, object]) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("UPDATE geology_context SET source_reference_no=%s, early_interval=%s, late_interval=%s, max_ma=%s, min_ma=%s, environment=%s, geogscale=%s, geology_comments=%s, formation=%s, stratigraphy_group=%s, member=%s, stratscale=%s, stratigraphy_comments=%s, geoplate=%s, paleomodel=%s, paleolat=%s, paleolng=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                        (data.get("source_reference_no"), data.get("early_interval"), data.get("late_interval"), data.get("max_ma"), data.get("min_ma"), data.get("environment"), data.get("geogscale"), data.get("geology_comments"), data.get("formation"), data.get("stratigraphy_group"), data.get("member"), data.get("stratscale"), data.get("stratigraphy_comments"), data.get("geoplate"), data.get("paleomodel"), data.get("paleolat"), data.get("paleolng"), geology_id))
            cur.execute("DELETE FROM lithology WHERE geology_context_id = %s", (geology_id,))
            for raw in cast(list[dict], data.get("lithology_rows", []) or []):
                slot = raw.get("slot")
                if slot in {1, 2} and any(raw.get(k) for k in ("lithology", "lithification", "minor_lithology", "lithology_adjectives", "fossils_from")):
                    cur.execute("INSERT INTO lithology (geology_context_id, slot, lithology, lithification, minor_lithology, lithology_adjectives, fossils_from) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                (geology_id, slot, raw.get("lithology"), raw.get("lithification"), raw.get("minor_lithology"), raw.get("lithology_adjectives"), raw.get("fossils_from")))

    def create_collection_event_for_trip(self, trip_id: int, collection_name: str, event_year: int | None = None) -> int:
        cleaned = self._normalize_collection_event_base_name(collection_name)
        if not cleaned:
            raise ValueError("collection_name is required.")
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, location FROM trips WHERE id = %s", (trip_id,))
            trip = cur.fetchone()
            if not trip:
                raise ValueError("Trip does not exist.")
            location_candidates = [p.strip() for p in str(trip["location"] or "").split(";") if p.strip()]
            if not location_candidates:
                raise ValueError("Trip has no location. Set trip location before creating a Collection Event.")
            location_id = None
            for candidate in location_candidates:
                cur.execute("SELECT id FROM locations WHERE LOWER(TRIM(name)) = LOWER(TRIM(%s)) ORDER BY id LIMIT 1", (candidate,))
                row = cur.fetchone()
                if row:
                    location_id = int(row["id"])
                    break
            if location_id is None:
                raise ValueError("Trip location was not found in Locations.")
            cur.execute("INSERT INTO collection_events (trip_id, location_id, collection_name, collection_subset, event_year) VALUES (%s, %s, %s, NULL, %s) RETURNING id", (trip_id, location_id, cleaned, event_year))
            event_id = int(cur.fetchone()["id"])
            cur.execute("UPDATE collection_events SET collection_name = %s WHERE id = %s", (self._format_collection_event_name(cleaned, event_id), event_id))
            return event_id

    def update_collection_event_name(self, collection_event_id: int, collection_name: str) -> None:
        cleaned = self._normalize_collection_event_base_name(collection_name)
        if not cleaned:
            raise ValueError("collection_name is required.")
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("UPDATE collection_events SET collection_name = %s WHERE id = %s", (self._format_collection_event_name(cleaned, collection_event_id), collection_event_id))
            if int(cur.rowcount or 0) == 0:
                raise ValueError("Collection Event does not exist.")

    @staticmethod
    def _last_name(name: str) -> str:
        parts = [p for p in name.strip().lower().split(" ") if p]
        return parts[-1] if parts else ""

    @staticmethod
    def _normalize_collection_events(raw_events) -> list[dict[str, str | None]]:
        if not isinstance(raw_events, list):
            return []
        events: list[dict[str, str | None]] = []
        for raw in raw_events:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("collection_name") or "").strip()
            subset_raw = raw.get("collection_subset")
            subset = str(subset_raw).strip() if subset_raw is not None else ""
            if name:
                events.append({"collection_name": name, "collection_subset": subset or None})
        return events

    def _normalize_find_payload(self, data: dict[str, object]) -> tuple[int, int, dict[str, str | None], int | None]:
        ce_raw = data.get("collection_event_id")
        if ce_raw in (None, ""):
            raise ValueError("collection_event_id is required.")
        try:
            collection_event_id = int(ce_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("collection_event_id must be an integer.") from exc
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, location_id FROM collection_events WHERE id = %s", (collection_event_id,))
            ce_row = cur.fetchone()
            if not ce_row:
                raise ValueError("Selected collection event does not exist.")
            location_id = int(ce_row["location_id"])
        text_fields = ("source_system", "source_occurrence_no", "identified_name", "accepted_name", "identified_rank", "accepted_rank", "difference", "identified_no", "accepted_no", "phylum", "class_name", "taxon_order", "family", "genus", "abund_value", "abund_unit", "reference_no", "taxonomy_comments", "occurrence_comments", "research_group", "notes")
        text_values: dict[str, str | None] = {}
        for field in text_fields:
            raw = str(data.get(field) or "").strip()
            text_values[field] = (raw or "manual") if field == "source_system" else (raw or None)
        year_raw = data.get("collection_year_latest_estimate")
        if year_raw in (None, ""):
            year_value = None
        else:
            try:
                year_value = int(str(year_raw).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError("collection_year_latest_estimate must be an integer.") from exc
        return collection_event_id, location_id, text_values, year_value

    def _normalize_collection_event_base_name(self, collection_name: str) -> str:
        return self._COLLECTION_EVENT_CODE_RE.sub("", str(collection_name or "").strip()).strip()

    @staticmethod
    def _format_collection_event_name(base_name: str, collection_event_id: int) -> str:
        return f"{base_name} [#{int(collection_event_id)}]"
