#!/usr/bin/env python3
import argparse
import csv
import io
import random
import sqlite3
from pathlib import Path


def _find_occurrence_header(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip('"')
        if stripped.startswith("occurrence_no,") or stripped.startswith('occurrence_no",'):
            return i
    raise ValueError("Could not find occurrence header row.")


def _load_pbdb_rows(csv_path: Path) -> list[dict[str, str]]:
    lines = csv_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    header_idx = _find_occurrence_header(lines)
    return [dict(row) for row in csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))]


def _norm_name(value: str | None) -> str:
    return str(value or "").strip().lower()


def _infer_collection_year(row: dict[str, str], rng: random.Random) -> int | None:
    pub = str(row.get("ref_pubyr") or "").strip()
    if not pub[:4].isdigit():
        return None
    pub_year = int(pub[:4])
    return max(1, pub_year - rng.randint(2, 6))


def _require_lastrowid(cur: sqlite3.Cursor) -> int:
    lastrowid = cur.lastrowid
    if lastrowid is None:
        raise RuntimeError("Insert did not return a row id.")
    return int(lastrowid)


def _get_or_create_pbdb_trip(conn: sqlite3.Connection, trip_name: str) -> int:
    existing = conn.execute('SELECT id FROM "Trips" WHERE trip_name = ? LIMIT 1', (trip_name,)).fetchone()
    if existing:
        return int(existing[0])
    cur = conn.execute(
        """
        INSERT INTO "Trips" (trip_name, start_date, end_date, team, location, notes)
        VALUES (?, DATE('now'), DATE('now'), ?, ?, ?)
        """,
        (trip_name, "PBDB import", "PBDB", "Auto-generated from PBDB occurrence CSV"),
    )
    return _require_lastrowid(cur)


def _coalesce(existing: str | None, incoming: str | None) -> str | None:
    ex = str(existing or "").strip()
    inc = str(incoming or "").strip()
    return ex if ex else (inc if inc else None)


def _get_or_create_location(conn: sqlite3.Connection, row: dict[str, str]) -> int:
    name = (row.get("collection_name") or row.get("collection_aka") or "").strip()
    if not name:
        name = f"PBDB collection {str(row.get('collection_no') or '').strip()}".strip()
    key = _norm_name(name)
    existing = conn.execute(
        'SELECT id, latitude, longitude, country_code, state, geogscale FROM "Locations" '
        "WHERE LOWER(TRIM(name)) = ? LIMIT 1",
        (key,),
    ).fetchone()
    lat = (row.get("lat") or "").strip() or None
    lng = (row.get("lng") or "").strip() or None
    country = (row.get("cc") or "").strip() or None
    state = (row.get("state") or "").strip() or None
    geogscale = (row.get("geogscale") or "").strip() or None
    if existing:
        location_id = int(existing[0])
        conn.execute(
            """
            UPDATE "Locations"
            SET latitude = ?, longitude = ?, country_code = ?, state = ?, geogscale = ?
            WHERE id = ?
            """,
            (
                _coalesce(existing[1], lat),
                _coalesce(existing[2], lng),
                _coalesce(existing[3], country),
                _coalesce(existing[4], state),
                _coalesce(existing[5], geogscale),
                location_id,
            ),
        )
        return location_id
    cur = conn.execute(
        """
        INSERT INTO "Locations" (
            name, latitude, longitude, country_code, state, geogscale
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, lat, lng, country, state, geogscale),
    )
    return _require_lastrowid(cur)


def _get_or_create_collection_event(
    conn: sqlite3.Connection,
    trip_id: int,
    location_id: int,
    row: dict[str, str],
) -> int:
    collection_name = (row.get("collection_name") or "").strip() or f"Location {location_id}"
    collection_no = (row.get("collection_no") or "").strip()
    collection_dates = (row.get("collection_dates") or "").strip()
    if collection_no and collection_dates:
        subset = f"PBDB #{collection_no} ({collection_dates})"
    elif collection_no:
        subset = f"PBDB #{collection_no}"
    elif collection_dates:
        subset = collection_dates
    else:
        subset = None
    existing = conn.execute(
        """
        SELECT id, trip_id
        FROM "CollectionEvents"
        WHERE location_id = ?
          AND collection_name = ?
          AND COALESCE(collection_subset, '') = COALESCE(?, '')
        LIMIT 1
        """,
        (location_id, collection_name, subset),
    ).fetchone()
    if existing:
        event_id = int(existing[0])
        if existing[1] is None:
            conn.execute('UPDATE "CollectionEvents" SET trip_id = ? WHERE id = ?', (trip_id, event_id))
        return event_id
    cur = conn.execute(
        """
        INSERT INTO "CollectionEvents" (trip_id, location_id, collection_name, collection_subset)
        VALUES (?, ?, ?, ?)
        """,
        (trip_id, location_id, collection_name, subset),
    )
    return _require_lastrowid(cur)


def _insert_find(
    conn: sqlite3.Connection,
    location_id: int,
    collection_event_id: int,
    row: dict[str, str],
    inferred_year: int | None,
) -> None:
    conn.execute(
        """
        INSERT INTO "Finds" (
            location_id, collection_event_id, source_system, source_occurrence_no,
            identified_name, accepted_name, identified_rank, accepted_rank, difference,
            identified_no, accepted_no, phylum, class_name, taxon_order, family, genus,
            abund_value, abund_unit, reference_no, taxonomy_comments, occurrence_comments,
            research_group, notes, collection_year_latest_estimate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            location_id,
            collection_event_id,
            "PBDB",
            (row.get("occurrence_no") or "").strip() or None,
            (row.get("identified_name") or "").strip() or None,
            (row.get("accepted_name") or "").strip() or None,
            (row.get("identified_rank") or "").strip() or None,
            (row.get("accepted_rank") or "").strip() or None,
            (row.get("difference") or "").strip() or None,
            (row.get("identified_no") or "").strip() or None,
            (row.get("accepted_no") or "").strip() or None,
            (row.get("phylum") or "").strip() or None,
            (row.get("class") or "").strip() or None,
            (row.get("order") or "").strip() or None,
            (row.get("family") or "").strip() or None,
            (row.get("genus") or "").strip() or None,
            (row.get("abund_value") or "").strip() or None,
            (row.get("abund_unit") or "").strip() or None,
            (row.get("reference_no") or "").strip() or None,
            (row.get("taxon_comments") or "").strip() or None,
            (row.get("occurrence_comments") or "").strip() or None,
            (row.get("research_group") or "").strip() or None,
            (row.get("collection_dates") or "").strip() or None,
            inferred_year,
        ),
    )


def import_pbdb_finds(
    db_path: Path,
    csv_path: Path,
    trip_name: str,
    replace_finds: bool,
    seed: int | None,
) -> tuple[int, int, int]:
    rows = _load_pbdb_rows(csv_path)
    rng = random.Random(seed)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        trip_id = _get_or_create_pbdb_trip(conn, trip_name)
        if replace_finds:
            conn.execute('DELETE FROM "Finds"')
        imported = 0
        seen_locations: set[int] = set()
        seen_events: set[int] = set()
        for row in rows:
            location_id = _get_or_create_location(conn, row)
            collection_event_id = _get_or_create_collection_event(conn, trip_id, location_id, row)
            inferred = _infer_collection_year(row, rng)
            _insert_find(conn, location_id, collection_event_id, row, inferred)
            imported += 1
            seen_locations.add(location_id)
            seen_events.add(collection_event_id)
        conn.commit()
        return imported, len(seen_locations), len(seen_events)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import PBDB occurrence rows into Finds linked to Locations/CollectionEvents.")
    parser.add_argument("--db", default="data/paleo_trips_01.db")
    parser.add_argument("--csv", default="data/pbdb_data-2.csv")
    parser.add_argument("--trip-name", default="PBDB Import - data/pbdb_data-2.csv")
    parser.add_argument("--replace-finds", action="store_true", default=True)
    parser.add_argument("--no-replace-finds", action="store_false", dest="replace_finds")
    parser.add_argument("--seed", type=int, default=None, help="Optional seed for deterministic inferred years.")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    csv_path = Path(args.csv).resolve()
    imported, locations, events = import_pbdb_finds(
        db_path=db_path,
        csv_path=csv_path,
        trip_name=args.trip_name,
        replace_finds=args.replace_finds,
        seed=args.seed,
    )
    print(
        f"Imported {imported} finds from {csv_path.name}; linked to {locations} locations and {events} collection events."
    )


if __name__ == "__main__":
    main()
