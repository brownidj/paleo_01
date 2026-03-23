#!/usr/bin/env python3
import argparse
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FindRow:
    find_id: int
    trip_id: int | None
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


def infer_collection_events(db_path: Path, window: int, include_empty_trips: bool) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_collection_event_columns(conn)

        find_rows = [
            FindRow(
                find_id=int(r["id"]),
                trip_id=int(r["trip_id"]) if r["trip_id"] is not None else None,
                location_id=int(r["location_id"]),
                estimated_year=int(r["collection_year_latest_estimate"]),
            )
            for r in conn.execute(
                """
                SELECT id, trip_id, location_id, collection_year_latest_estimate
                FROM Finds
                WHERE location_id IS NOT NULL AND collection_year_latest_estimate IS NOT NULL
                ORDER BY trip_id, location_id, collection_year_latest_estimate, id
                """
            ).fetchall()
        ]

        grouped: dict[tuple[int | None, int], list[FindRow]] = defaultdict(list)
        for row in find_rows:
            grouped[(row.trip_id, row.location_id)].append(row)

        conn.execute("DELETE FROM CollectionEvents")
        find_to_event: dict[int, int] = {}
        event_count = 0

        for (trip_id, location_id), rows in sorted(grouped.items(), key=lambda x: ((x[0][0] or 0), x[0][1])):
            unassigned = sorted(rows, key=lambda r: (r.estimated_year, r.find_id))
            seq = 1
            location_name_row = conn.execute("SELECT name FROM Locations WHERE id = ?", (location_id,)).fetchone()
            location_name = str(location_name_row["name"] or f"Location {location_id}").strip()

            while unassigned:
                event_year, covered = _choose_best_year(unassigned, window)
                collection_subset = f"inferred trip={trip_id or 'none'} loc={location_id} seq={seq} y={event_year}"
                cur = conn.execute(
                    """
                    INSERT INTO CollectionEvents (trip_id, location_id, collection_name, collection_subset, event_year)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (trip_id, location_id, location_name, collection_subset, event_year),
                )
                event_id = int(cur.lastrowid)
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

        # Keep finds.trip_id aligned with event trip_id where available.
        conn.execute(
            """
            UPDATE Finds
            SET trip_id = (
                SELECT ce.trip_id
                FROM CollectionEvents ce
                WHERE ce.id = Finds.collection_event_id
            )
            WHERE collection_event_id IS NOT NULL
              AND (
                trip_id IS NULL OR trip_id <> (
                    SELECT ce2.trip_id FROM CollectionEvents ce2 WHERE ce2.id = Finds.collection_event_id
                )
              )
            """
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
