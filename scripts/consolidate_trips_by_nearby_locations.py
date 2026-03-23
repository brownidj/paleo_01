#!/usr/bin/env python3
import argparse
import math
import sqlite3
from collections import defaultdict
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


def consolidate_generated_trips_by_location(db_path: Path, threshold_km: float) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        generated_trips = [
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM Trips WHERE notes = 'Generated from trip_linked_collection_events_temp.csv' ORDER BY id"
            ).fetchall()
        ]
        if not generated_trips:
            return {"generated_trips": 0, "events_considered": 0, "events_reassigned": 0, "clusters": 0}

        marks = ",".join(["?"] * len(generated_trips))
        event_rows = conn.execute(
            f"""
            SELECT
                ce.id AS event_id,
                ce.trip_id,
                ce.location_id,
                l.latitude,
                l.longitude
            FROM CollectionEvents ce
            JOIN Locations l ON l.id = ce.location_id
            WHERE ce.trip_id IN ({marks})
            ORDER BY ce.id
            """,
            generated_trips,
        ).fetchall()
        if not event_rows:
            return {
                "generated_trips": len(generated_trips),
                "events_considered": 0,
                "events_reassigned": 0,
                "clusters": 0,
            }

        # Build unique location list with coordinates and participating trips.
        location_points: dict[int, tuple[float, float]] = {}
        location_trips: dict[int, set[int]] = defaultdict(set)
        for row in event_rows:
            location_id = int(row["location_id"])
            location_trips[location_id].add(int(row["trip_id"]))
            lat = _to_float(row["latitude"])
            lng = _to_float(row["longitude"])
            if lat is not None and lng is not None:
                location_points[location_id] = (lat, lng)

        # Cluster only locations with coordinates.
        location_ids = sorted(location_points.keys())
        uf = _UnionFind(location_ids)
        for i, left in enumerate(location_ids):
            lat1, lon1 = location_points[left]
            for right in location_ids[i + 1 :]:
                lat2, lon2 = location_points[right]
                if _haversine_km(lat1, lon1, lat2, lon2) <= threshold_km:
                    uf.union(left, right)

        clusters: dict[int, set[int]] = defaultdict(set)
        for location_id in location_ids:
            clusters[uf.find(location_id)].add(location_id)

        # Locations without coordinates become singleton clusters.
        for location_id in location_trips.keys():
            if location_id not in location_points:
                clusters[-location_id].add(location_id)

        # Choose anchor trip per cluster: smallest trip id currently in that cluster.
        cluster_anchor_trip: dict[int, int] = {}
        for key, location_set in clusters.items():
            trips_in_cluster: set[int] = set()
            for location_id in location_set:
                trips_in_cluster.update(location_trips.get(location_id, set()))
            if not trips_in_cluster:
                continue
            cluster_anchor_trip[key] = min(trips_in_cluster)

        # Build mapping location_id -> anchor trip_id.
        location_to_anchor_trip: dict[int, int] = {}
        for key, location_set in clusters.items():
            anchor = cluster_anchor_trip.get(key)
            if anchor is None:
                continue
            for location_id in location_set:
                location_to_anchor_trip[location_id] = anchor

        # Reassign events and finds.
        events_reassigned = 0
        for row in event_rows:
            event_id = int(row["event_id"])
            old_trip = int(row["trip_id"])
            location_id = int(row["location_id"])
            new_trip = location_to_anchor_trip.get(location_id, old_trip)
            if new_trip == old_trip:
                continue
            conn.execute("UPDATE CollectionEvents SET trip_id = ? WHERE id = ?", (new_trip, event_id))
            conn.execute("UPDATE Finds SET trip_id = ? WHERE collection_event_id = ?", (new_trip, event_id))
            events_reassigned += 1

        # Ensure anchor trips know all cluster locations in TripLocations.
        trip_location_links_added = 0
        for location_id, trip_id in location_to_anchor_trip.items():
            conn.execute(
                "INSERT OR IGNORE INTO TripLocations (id, location_id) VALUES (?, ?)",
                (trip_id, location_id),
            )
            trip_location_links_added += int(conn.execute("SELECT changes()").fetchone()[0])

        conn.commit()
        return {
            "generated_trips": len(generated_trips),
            "events_considered": len(event_rows),
            "events_reassigned": events_reassigned,
            "clusters": len(clusters),
            "trip_location_links_added": trip_location_links_added,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate generated trips by nearby collection-event locations.")
    parser.add_argument("--db", default="data/paleo_trips_01.db")
    parser.add_argument("--threshold-km", type=float, default=100.0)
    args = parser.parse_args()

    stats = consolidate_generated_trips_by_location(Path(args.db).resolve(), args.threshold_km)
    for k, v in stats.items():
        print(f"{k}={v}")


if __name__ == "__main__":
    main()
