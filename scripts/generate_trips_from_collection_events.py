#!/usr/bin/env python3
import argparse
import math
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def _to_float(value: str | None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class _UnionFind:
    def __init__(self, items: list[int]):
        self.parent = {item: item for item in items}

    def find(self, item: int) -> int:
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            nxt = self.parent[item]
            self.parent[item] = root
            item = nxt
        return root

    def union(self, a: int, b: int) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            self.parent[rb] = ra


@dataclass
class EventRow:
    event_id: int
    location_id: int
    location_name: str
    event_year: int


def _ensure_collection_event_year(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(CollectionEvents)").fetchall()}
    if "event_year" not in cols:
        conn.execute("ALTER TABLE CollectionEvents ADD COLUMN event_year INTEGER")
    if "trip_id" not in cols:
        conn.execute("ALTER TABLE CollectionEvents ADD COLUMN trip_id INTEGER")


def _delete_previous_generated_trips(conn: sqlite3.Connection) -> int:
    generated = [r[0] for r in conn.execute(
        "SELECT id FROM Trips WHERE notes = 'Generated from collection-event clusters'"
    ).fetchall()]
    if not generated:
        return 0
    marks = ",".join(["?"] * len(generated))
    # Revert attached events to import trip 1 temporarily.
    conn.execute(f"UPDATE CollectionEvents SET trip_id = 1 WHERE trip_id IN ({marks})", generated)
    conn.execute(f"DELETE FROM TripLocations WHERE id IN ({marks})", generated)
    conn.execute(f"DELETE FROM Trips WHERE id IN ({marks})", generated)
    return len(generated)


def _load_event_rows(conn: sqlite3.Connection) -> list[EventRow]:
    rows = conn.execute(
        """
        SELECT
            ce.id AS event_id,
            ce.location_id,
            l.name AS location_name,
            ce.event_year
        FROM CollectionEvents ce
        JOIN Locations l ON l.id = ce.location_id
        WHERE ce.event_year IS NOT NULL
          AND EXISTS (SELECT 1 FROM Finds f WHERE f.collection_event_id = ce.id)
        ORDER BY ce.id
        """
    ).fetchall()
    out: list[EventRow] = []
    for row in rows:
        out.append(
            EventRow(
                event_id=int(row["event_id"]),
                location_id=int(row["location_id"]),
                location_name=str(row["location_name"] or f"Location {row['location_id']}").strip(),
                event_year=int(row["event_year"]),
            )
        )
    return out


def _cluster_locations(conn: sqlite3.Connection, location_ids: set[int], threshold_km: float) -> dict[int, int]:
    loc_rows = conn.execute(
        f"""
        SELECT id, latitude, longitude
        FROM Locations
        WHERE id IN ({",".join(["?"] * len(location_ids))})
        """,
        tuple(sorted(location_ids)),
    ).fetchall()
    points: dict[int, tuple[float, float]] = {}
    for row in loc_rows:
        lat = _to_float(row["latitude"])
        lng = _to_float(row["longitude"])
        if lat is not None and lng is not None:
            points[int(row["id"])] = (lat, lng)
    ids = sorted(points.keys())
    uf = _UnionFind(ids)
    for i, left in enumerate(ids):
        lat1, lon1 = points[left]
        for right in ids[i + 1 :]:
            lat2, lon2 = points[right]
            if _haversine_km(lat1, lon1, lat2, lon2) <= threshold_km:
                uf.union(left, right)

    cluster_by_location: dict[int, int] = {}
    for loc in location_ids:
        if loc in points:
            cluster_by_location[loc] = uf.find(loc)
        else:
            cluster_by_location[loc] = -loc
    return cluster_by_location


def _partition_years(events: list[EventRow], max_gap_years: int) -> list[list[EventRow]]:
    ordered = sorted(events, key=lambda e: (e.event_year, e.event_id))
    groups: list[list[EventRow]] = []
    current: list[EventRow] = []
    prev_year: int | None = None
    for event in ordered:
        if not current:
            current = [event]
            prev_year = event.event_year
            continue
        if prev_year is not None and event.event_year - prev_year > max_gap_years:
            groups.append(current)
            current = [event]
        else:
            current.append(event)
        prev_year = event.event_year
    if current:
        groups.append(current)
    return groups


def generate_trips(db_path: Path, location_km: float, date_gap_years: int) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_collection_event_year(conn)
        removed_old_generated = _delete_previous_generated_trips(conn)

        events = _load_event_rows(conn)
        if not events:
            conn.commit()
            return {
                "removed_old_generated_trips": removed_old_generated,
                "events_considered": 0,
                "new_trips_created": 0,
                "events_reassigned": 0,
            }

        cluster_by_location = _cluster_locations(
            conn,
            {event.location_id for event in events},
            threshold_km=location_km,
        )
        events_by_cluster: dict[int, list[EventRow]] = defaultdict(list)
        for event in events:
            events_by_cluster[cluster_by_location[event.location_id]].append(event)

        # Build trip groups: tight by location cluster, loose by date gap.
        grouped_events: list[list[EventRow]] = []
        for cluster_events in events_by_cluster.values():
            grouped_events.extend(_partition_years(cluster_events, max_gap_years=date_gap_years))

        max_trip_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) FROM Trips").fetchone()[0])
        new_trips_created = 0
        events_reassigned = 0

        # Name sequencing per base location name.
        name_seq: dict[str, int] = defaultdict(int)
        for group in sorted(grouped_events, key=lambda g: (min(e.event_year for e in g), min(e.event_id for e in g))):
            anchor = min(group, key=lambda e: (e.location_name.lower(), e.location_id, e.event_id))
            start_year = min(e.event_year for e in group)
            base_name = anchor.location_name
            name_seq[base_name] += 1
            seq = name_seq[base_name]
            trip_name = f"{base_name} ({start_year}/{seq})"

            max_trip_id += 1
            trip_id = max_trip_id
            conn.execute(
                """
                INSERT INTO Trips (id, trip_name, start_date, end_date, team, location, notes)
                VALUES (?, ?, ?, ?, NULL, ?, 'Generated from collection-event clusters')
                """,
                (trip_id, trip_name, f"{start_year:04d}-01-01", f"{start_year:04d}-12-31", base_name),
            )
            new_trips_created += 1

            # TripLocations: all locations represented by the grouped events.
            for loc_id in sorted({e.location_id for e in group}):
                conn.execute(
                    "INSERT OR IGNORE INTO TripLocations (id, location_id) VALUES (?, ?)",
                    (trip_id, loc_id),
                )

            # Repoint events to the new trip.
            for event in group:
                conn.execute("UPDATE CollectionEvents SET trip_id = ? WHERE id = ?", (trip_id, event.event_id))
                events_reassigned += int(conn.execute("SELECT changes()").fetchone()[0])

        conn.commit()
        return {
            "removed_old_generated_trips": removed_old_generated,
            "events_considered": len(events),
            "location_clusters": len(events_by_cluster),
            "trip_groups_created": len(grouped_events),
            "new_trips_created": new_trips_created,
            "events_reassigned": events_reassigned,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate trips from collection events grouped by tight location and loose date.")
    parser.add_argument("--db", default="data/paleo_trips_01.db")
    parser.add_argument("--location-km", type=float, default=10.0, help="Tight location clustering threshold in km.")
    parser.add_argument(
        "--date-gap-years",
        type=int,
        default=12,
        help="Loose date grouping: start a new trip group when year gap exceeds this value.",
    )
    args = parser.parse_args()

    stats = generate_trips(
        db_path=Path(args.db).resolve(),
        location_km=args.location_km,
        date_gap_years=args.date_gap_years,
    )
    for k, v in stats.items():
        print(f"{k}={v}")


if __name__ == "__main__":
    main()
