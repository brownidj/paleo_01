#!/usr/bin/env python3
import argparse
import csv
import random
import sqlite3
from pathlib import Path


def _find_occurrence_header(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip('"')
        if stripped.startswith("occurrence_no,") or stripped.startswith('occurrence_no",'):
            return i
    raise ValueError("Could not find occurrence header row.")


def _load_rows(csv_path: Path) -> list[dict[str, str]]:
    lines = csv_path.read_text(encoding="utf-8-sig").splitlines()
    return [dict(row) for row in csv.DictReader(lines[_find_occurrence_header(lines):])]


def _parse_year(value: str | None) -> int | None:
    text = str(value or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        year = int(text[:4])
        if 1000 <= year <= 2200:
            return year
    return None


def _build_year_maps(csv_paths: list[Path]) -> tuple[dict[str, int], dict[str, int]]:
    by_occurrence: dict[str, int] = {}
    by_reference: dict[str, int] = {}
    for path in csv_paths:
        if not path.exists():
            continue
        for row in _load_rows(path):
            year = _parse_year(row.get("paper_publication_year")) or _parse_year(row.get("ref_pubyr"))
            if year is None:
                continue
            occurrence_no = str(row.get("occurrence_no") or "").strip()
            reference_no = str(row.get("reference_no") or "").strip()
            if occurrence_no:
                by_occurrence[occurrence_no] = min(year, by_occurrence.get(occurrence_no, year))
            if reference_no:
                by_reference[reference_no] = min(year, by_reference.get(reference_no, year))
    return by_occurrence, by_reference


def ensure_column(conn: sqlite3.Connection) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(Finds)").fetchall()]
    if "collection_year_latest_estimate" not in columns:
        conn.execute("ALTER TABLE Finds ADD COLUMN collection_year_latest_estimate INTEGER")


def backfill(
    db_path: Path,
    csv_paths: list[Path],
    min_subtract: int,
    max_subtract: int,
    seed: int | None,
) -> tuple[int, int]:
    if seed is not None:
        random.seed(seed)
    by_occurrence, by_reference = _build_year_maps(csv_paths)

    conn = sqlite3.connect(db_path)
    try:
        ensure_column(conn)
        rows = conn.execute(
            """
            SELECT id, source_occurrence_no, reference_no
            FROM Finds
            WHERE collection_year_latest_estimate IS NULL
            """
        ).fetchall()
        updated = 0
        for find_id, occurrence_no, reference_no in rows:
            occ = str(occurrence_no or "").strip()
            ref = str(reference_no or "").strip()
            inferred = by_occurrence.get(occ) or by_reference.get(ref)
            if inferred is None:
                continue
            estimate = max(1, inferred - random.randint(min_subtract, max_subtract))
            conn.execute(
                "UPDATE Finds SET collection_year_latest_estimate = ? WHERE id = ?",
                (estimate, int(find_id)),
            )
            updated += 1
        conn.commit()
        return updated, len(rows)
    finally:
        conn.close()


def _resolve_paths(paths: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw in paths:
        p = Path(raw)
        resolved.append(p if p.is_absolute() else Path.cwd() / p)
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Finds.collection_year_latest_estimate from PBDB CSV years.")
    parser.add_argument("--db", default="data/paleo_trips_01.db", help="Path to SQLite database.")
    parser.add_argument(
        "--csv",
        action="append",
        default=[
            "data/pbdb_data-2_publication_enriched.csv",
            "data/pbdb_data-2.csv",
            "data/pbdb_data-3.csv",
        ],
        help="PBDB/enriched CSV path (can be provided multiple times).",
    )
    parser.add_argument("--min-subtract", type=int, default=2)
    parser.add_argument("--max-subtract", type=int, default=6)
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for repeatability.")
    args = parser.parse_args()

    if args.min_subtract < 0 or args.max_subtract < args.min_subtract:
        raise ValueError("Invalid subtract range.")
    db_path = Path(args.db) if Path(args.db).is_absolute() else Path.cwd() / args.db
    updated, candidates = backfill(
        db_path=db_path,
        csv_paths=_resolve_paths(args.csv),
        min_subtract=args.min_subtract,
        max_subtract=args.max_subtract,
        seed=args.seed,
    )
    print(f"Backfill complete: updated {updated} of {candidates} candidate find rows.")


if __name__ == "__main__":
    main()
