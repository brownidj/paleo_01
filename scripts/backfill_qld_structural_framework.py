#!/usr/bin/env python3
import argparse
import csv
import json
import sqlite3
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from repository import DEFAULT_DB_PATH

SERVICE_QUERY_URL = (
    "https://spatial-gis.information.qld.gov.au/arcgis/rest/services/"
    "GeoscientificInformation/StructuralFramework/MapServer/0/query"
)
EXCLUDE_OROGEN = {"POST OROGENIC BASINS"}
BASIN_TERMS = ("BASIN", "TROUGH", "DEPRESSION", "SUPERBASIN")
PROVINCE_TERMS = ("PROVINCE", "SUBPROVINCE", "CRATON")


def _to_str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _is_basin_name(name: str) -> bool:
    upper = name.upper()
    return any(term in upper for term in BASIN_TERMS)


def _is_proterozoic(age: str) -> bool:
    return "PROTEROZOIC" in age.upper()


def _score(attributes: dict[str, object]) -> int:
    raw = attributes.get("sequence")
    if raw is None:
        return -1
    try:
        return int(raw)
    except (TypeError, ValueError):
        return -1


def _query_features(lon: float, lat: float, max_retries: int = 3) -> list[dict[str, object]]:
    params = {
        "f": "pjson",
        "where": "1=1",
        "outFields": "struct_name,age,rank,parent,province,orogen,sequence",
        "returnGeometry": "false",
        "geometryType": "esriGeometryPoint",
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
    }
    url = f"{SERVICE_QUERY_URL}?{urllib.parse.urlencode(params)}"
    context = ssl._create_unverified_context()
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PaleoTrips/1.0"})
            with urllib.request.urlopen(req, timeout=45, context=context) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return [feature.get("attributes") or {} for feature in payload.get("features", [])]
        except Exception:
            if attempt == max_retries - 1:
                return []
            time.sleep(0.4 * (attempt + 1))
    return []


def _derive_values(features: list[dict[str, object]]) -> tuple[str | None, str | None, str | None]:
    if not features:
        return None, None, None

    basin_candidates: list[tuple[int, str]] = []
    protero_candidates: list[tuple[int, str, str]] = []
    orogen_candidates: list[tuple[int, str]] = []

    for attrs in features:
        seq = _score(attrs)
        struct_name = _to_str(attrs.get("struct_name"))
        province = _to_str(attrs.get("province"))
        orogen = _to_str(attrs.get("orogen"))
        age = _to_str(attrs.get("age"))

        for name in (province, struct_name):
            if name and _is_basin_name(name):
                basin_candidates.append((seq, name))

        if _is_proterozoic(age):
            for name in (province, struct_name):
                upper = name.upper()
                if name and any(term in upper for term in PROVINCE_TERMS) and not _is_basin_name(name):
                    protero_candidates.append((seq, name, orogen))

        if orogen and orogen.upper() not in EXCLUDE_OROGEN:
            orogen_candidates.append((seq, orogen))
        elif not orogen and "OROGEN" in struct_name.upper():
            orogen_candidates.append((seq, struct_name))

    basin = max(basin_candidates, default=None, key=lambda item: item[0])
    protero = max(protero_candidates, default=None, key=lambda item: item[0])
    orogen = None
    if protero and protero[2]:
        orogen = protero[2]
    else:
        top_orogen = max(orogen_candidates, default=None, key=lambda item: item[0])
        orogen = top_orogen[1] if top_orogen else None

    return (
        basin[1] if basin else None,
        protero[1] if protero else None,
        _to_str(orogen) or None,
    )


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(Locations)").fetchall()}
    for col in ("basin", "proterozoic_province", "orogen"):
        if col not in existing:
            conn.execute(f'ALTER TABLE Locations ADD COLUMN "{col}" TEXT')


def backfill(db_path: Path, report_path: Path | None = None) -> dict[str, int]:
    stats = {
        "locations_scanned": 0,
        "locations_with_geometry": 0,
        "locations_with_hits": 0,
        "rows_updated": 0,
        "basin_updated": 0,
        "proterozoic_province_updated": 0,
        "orogen_updated": 0,
    }
    report_rows: list[dict[str, object]] = []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_columns(conn)
        rows = conn.execute(
            """
            SELECT id, name, latitude, longitude, state, country_code, basin, proterozoic_province, orogen
            FROM Locations
            WHERE country_code = 'AU' AND state = 'QLD'
            ORDER BY id
            """
        ).fetchall()
        stats["locations_scanned"] = len(rows)

        for row in rows:
            lat = _to_float(row["latitude"])
            lon = _to_float(row["longitude"])
            if lat is None or lon is None:
                continue
            stats["locations_with_geometry"] += 1
            features = _query_features(lon=lon, lat=lat)
            if features:
                stats["locations_with_hits"] += 1
            basin, protero, orogen = _derive_values(features)

            update_payload: dict[str, str] = {}
            if not _to_str(row["basin"]) and basin:
                update_payload["basin"] = basin
                stats["basin_updated"] += 1
            if not _to_str(row["proterozoic_province"]) and protero:
                update_payload["proterozoic_province"] = protero
                stats["proterozoic_province_updated"] += 1
            if not _to_str(row["orogen"]) and orogen:
                update_payload["orogen"] = orogen
                stats["orogen_updated"] += 1

            if update_payload:
                set_sql = ", ".join([f'"{k}" = ?' for k in update_payload])
                params = list(update_payload.values()) + [row["id"]]
                conn.execute(f'UPDATE Locations SET {set_sql} WHERE id = ?', params)
                stats["rows_updated"] += 1

            report_rows.append(
                {
                    "location_id": row["id"],
                    "name": row["name"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "derived_basin": basin or "",
                    "derived_proterozoic_province": protero or "",
                    "derived_orogen": orogen or "",
                    "updated_basin": update_payload.get("basin", ""),
                    "updated_proterozoic_province": update_payload.get("proterozoic_province", ""),
                    "updated_orogen": update_payload.get("orogen", ""),
                }
            )

        conn.commit()

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "location_id",
                    "name",
                    "latitude",
                    "longitude",
                    "derived_basin",
                    "derived_proterozoic_province",
                    "derived_orogen",
                    "updated_basin",
                    "updated_proterozoic_province",
                    "updated_orogen",
                ],
            )
            writer.writeheader()
            writer.writerows(report_rows)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill Locations.basin/proterozoic_province/orogen from QLD Structural Framework."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite DB path")
    parser.add_argument(
        "--report",
        default="data/location_structural_framework_backfill_report.csv",
        help="CSV report output path",
    )
    args = parser.parse_args()

    stats = backfill(Path(args.db), Path(args.report))
    for key in (
        "locations_scanned",
        "locations_with_geometry",
        "locations_with_hits",
        "rows_updated",
        "basin_updated",
        "proterozoic_province_updated",
        "orogen_updated",
    ):
        print(f"{key}={stats[key]}")


if __name__ == "__main__":
    main()
