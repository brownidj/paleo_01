#!/usr/bin/env python3
import argparse
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FindRow:
    find_id: int
    location_id: int
    estimated_year: int


def _ensure_collection_event_columns(conn: sqlite3.Connection) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(CollectionEvents)").fetchall()]
    if "trip_id" not in cols:
        conn.execute("ALTER TABLE CollectionEvents ADD COLUMN trip_id INTEGER")
        cols = [r[1] for r in conn.execute("PRAGMA table_info(CollectionEvents)").fetchall()]
    if "event_year" not in cols:
        conn.execute("ALTER TABLE CollectionEvents ADD COLUMN event_year INTEGER")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_collection_events_trip ON CollectionEvents(trip_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_collection_events_event_year ON CollectionEvents(event_year)")


def _parse_year(value: str | None) -> int | None:
    text = str(value or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _choose_trip_for_event(
    trip_rows_by_location: dict[int, list[tuple[int, int | None, int | None]]],
    location_id: int,
    event_year: int,
) -> int | None:
    candidates = trip_rows_by_location.get(location_id, [])
    if not candidates:
        return None
    valid = [
        trip
        for trip in candidates
        if (trip[1] is None or trip[1] <= event_year) and (trip[2] is None or event_year <= trip[2])
    ]
    if len(valid) == 1:
        return int(valid[0][0])
    pool = valid if valid else candidates
    closest = min(
        pool,
        key=lambda trip: (
            abs((trip[1] if trip[1] is not None else event_year) - event_year),
            int(trip[0]),
        ),
    )
    return int(closest[0])


def _choose_best_year(unassigned: list[FindRow], window: int) -> tuple[int, list[FindRow]]:
    coverage: dict[int, list[FindRow]] = defaultdict(list)
    for row in unassigned:
        for year in range(row.estimated_year - window, row.estimated_year):
            coverage[year].append(row)
    if not coverage:
        row = unassigned[0]
        fallback_year = row.estimated_year - 1
        return fallback_year, [row]
    # Max coverage first; if tie, choose latest year.
    best_year = max(coverage.keys(), key=lambda y: (len(coverage[y]), y))
    return best_year, coverage[best_year]


def _require_lastrowid(cur: sqlite3.Cursor) -> int:
    lastrowid = cur.lastrowid
    if lastrowid is None:
        raise RuntimeError("Insert did not return a row id.")
    return int(lastrowid)


def infer_collection_events(db_path: Path, window: int, include_empty_trips: bool) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_collection_event_columns(conn)

        find_rows = [
            FindRow(
                find_id=int(r["id"]),
                location_id=int(r["location_id"]),
                estimated_year=int(r["collection_year_latest_estimate"]),
            )
            for r in conn.execute(
                """
                SELECT id, location_id, collection_year_latest_estimate
                FROM Finds
                WHERE location_id IS NOT NULL AND collection_year_latest_estimate IS NOT NULL
                ORDER BY location_id, collection_year_latest_estimate, id
                """
            ).fetchall()
        ]

        grouped: dict[int, list[FindRow]] = defaultdict(list)
        for row in find_rows:
            grouped[row.location_id].append(row)

        trip_rows_by_location: dict[int, list[tuple[int, int | None, int | None]]] = defaultdict(list)
        for trip_row in conn.execute(
            """
            SELECT tl.location_id, t.id, t.start_date, t.end_date
            FROM TripLocations tl
            JOIN Trips t ON t.id = tl.id
            ORDER BY t.id
            """
        ).fetchall():
            trip_rows_by_location[int(trip_row["location_id"])].append(
                (
                    int(trip_row["id"]),
                    _parse_year(trip_row["start_date"]),
                    _parse_year(trip_row["end_date"]),
                )
            )

        conn.execute("DELETE FROM CollectionEvents")
        find_to_event: dict[int, int] = {}
        event_count = 0

        for location_id, rows in sorted(grouped.items(), key=lambda x: x[0]):
            unassigned = sorted(rows, key=lambda r: (r.estimated_year, r.find_id))
            seq = 1
            location_name_row = conn.execute("SELECT name FROM Locations WHERE id = ?", (location_id,)).fetchone()
            location_name = str(location_name_row["name"] or f"Location {location_id}").strip()

            while unassigned:
                event_year, covered = _choose_best_year(unassigned, window)
                inferred_trip_id = _choose_trip_for_event(trip_rows_by_location, location_id, event_year)
                collection_subset = f"inferred loc={location_id} seq={seq} y={event_year}"
                cur = conn.execute(
                    """
                    INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset, event_year)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (inferred_trip_id, location_id, location_name, collection_subset, event_year),
                )
                event_id = _require_lastrowid(cur)
                event_count += 1
                for row in covered:
                    find_to_event[row.find_id] = event_id
                covered_ids = {r.find_id for r in covered}
                unassigned = [r for r in unassigned if r.find_id not in covered_ids]
                seq += 1

        if include_empty_trips:
            trips = conn.execute("SELECT id, start_date FROM Trips ORDER BY id").fetchall()
            for trip in trips:
                trip_id = int(trip["id"])
                existing = conn.execute(
                    "SELECT 1 FROM CollectionEvents WHERE trip_id = ? LIMIT 1",
                    (trip_id,),
                ).fetchone()
                if existing:
                    continue
                trip_locations = conn.execute(
                    "SELECT location_id FROM TripLocations WHERE id = ? ORDER BY location_id LIMIT 1",
                    (trip_id,),
                ).fetchone()
                if not trip_locations:
                    continue
                location_id = int(trip_locations["location_id"])
                location_name_row = conn.execute("SELECT name FROM Locations WHERE id = ?", (location_id,)).fetchone()
                location_name = str(location_name_row["name"] or f"Location {location_id}").strip()
                trip_year = _parse_year(trip["start_date"]) or 1900
                conn.execute(
                    """
                    INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset, event_year)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (trip_id, location_id, location_name, f"inferred empty trip={trip_id}", trip_year),
                )
                event_count += 1

        if find_to_event:
            conn.executemany(
                "UPDATE Finds SET collection_event_id = ? WHERE id = ?",
                [(event_id, find_id) for find_id, event_id in find_to_event.items()],
            )

        conn.commit()
        stats = {
            "finds_considered": len(find_rows),
            "trip_location_buckets": len(grouped),
            "collection_events_created": event_count,
            "finds_relinked": len(find_to_event),
            "finds_total": int(conn.execute("SELECT COUNT(*) FROM Finds").fetchone()[0]),
            "collection_events_total": int(conn.execute("SELECT COUNT(*) FROM CollectionEvents").fetchone()[0]),
        }
        return stats
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Infer minimal single-year collection events from finds.")
    parser.add_argument("--db", default="data/paleo_trips_01.db")
    parser.add_argument("--window", type=int, default=6, help="Preceding-year window size.")
    parser.add_argument(
        "--include-empty-trips",
        action="store_true",
        default=True,
        help="Ensure at least one collection event per trip when possible.",
    )
    parser.add_argument("--no-include-empty-trips", action="store_false", dest="include_empty_trips")
    args = parser.parse_args()

    stats = infer_collection_events(
        db_path=Path(args.db).resolve(),
        window=args.window,
        include_empty_trips=args.include_empty_trips,
    )
    for k, v in stats.items():
        print(f"{k}={v}")


if __name__ == "__main__":
    main()
