#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from psycopg import connect
from psycopg.rows import dict_row


@dataclass
class CheckResult:
    label: str
    value: int
    ok: bool


def _resolve_postgres_url(cli_value: str | None) -> str:
    if cli_value:
        return cli_value.strip()
    for env_key in ("PALEO_DESKTOP_DATABASE_URL", "DATABASE_URL"):
        env_value = os.getenv(env_key, "").strip()
        if env_value:
            return env_value
    _load_dotenv_if_present()
    for env_key in ("PALEO_DESKTOP_DATABASE_URL", "DATABASE_URL"):
        env_value = os.getenv(env_key, "").strip()
        if env_value:
            return env_value
    raise ValueError("Postgres URL required. Pass --postgres-url or set PALEO_DESKTOP_DATABASE_URL/DATABASE_URL.")


def _load_dotenv_if_present() -> None:
    project_root = Path(__file__).resolve().parents[2]
    candidates = [project_root / "config" / "env" / "local.env", project_root / ".env"]
    env_path = next((path for path in candidates if path.exists()), None)
    if env_path is None:
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _count(cur, sql: str) -> int:
    cur.execute(sql)
    row = cur.fetchone()
    return int(row["count"] if row else 0)


def run_validation(postgres_url: str) -> tuple[list[CheckResult], int]:
    checks: list[CheckResult] = []
    mismatch_total = 0
    with connect(postgres_url, row_factory=dict_row) as conn, conn.cursor() as cur:
        finds_count = _count(cur, "SELECT COUNT(*) AS count FROM finds")
        observations_count = _count(cur, "SELECT COUNT(*) AS count FROM find_field_observations")
        taxonomy_count = _count(cur, "SELECT COUNT(*) AS count FROM find_taxonomy")
        missing_observations = _count(
            cur,
            """
            SELECT COUNT(*) AS count
            FROM finds f
            LEFT JOIN find_field_observations fo ON fo.find_id = f.id
            WHERE fo.find_id IS NULL
            """,
        )
        missing_taxonomy = _count(
            cur,
            """
            SELECT COUNT(*) AS count
            FROM finds f
            LEFT JOIN find_taxonomy ft ON ft.find_id = f.id
            WHERE ft.find_id IS NULL
            """,
        )
        orphan_observations = _count(
            cur,
            """
            SELECT COUNT(*) AS count
            FROM find_field_observations fo
            LEFT JOIN finds f ON f.id = fo.find_id
            WHERE f.id IS NULL
            """,
        )
        orphan_taxonomy = _count(
            cur,
            """
            SELECT COUNT(*) AS count
            FROM find_taxonomy ft
            LEFT JOIN finds f ON f.id = ft.find_id
            WHERE f.id IS NULL
            """,
        )
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='finds' AND column_name='identified_name'
            LIMIT 1
            """
        )
        has_legacy_detail_columns = cur.fetchone() is not None
        if has_legacy_detail_columns:
            field_value_mismatch = _count(
                cur,
                """
                SELECT COUNT(*) AS count
                FROM finds f
                JOIN find_field_observations fo ON fo.find_id = f.id
                WHERE COALESCE(f.identified_name, '') <> COALESCE(fo.provisional_identification, '')
                   OR COALESCE(f.notes, '') <> COALESCE(fo.notes, '')
                   OR COALESCE(f.abund_value, '') <> COALESCE(fo.abund_value, '')
                   OR COALESCE(f.abund_unit, '') <> COALESCE(fo.abund_unit, '')
                   OR COALESCE(f.occurrence_comments, '') <> COALESCE(fo.occurrence_comments, '')
                   OR COALESCE(f.research_group, '') <> COALESCE(fo.research_group, '')
                """,
            )
            taxonomy_value_mismatch = _count(
                cur,
                """
                SELECT COUNT(*) AS count
                FROM finds f
                JOIN find_taxonomy ft ON ft.find_id = f.id
                WHERE COALESCE(f.identified_name, '') <> COALESCE(ft.identified_name, '')
                   OR COALESCE(f.accepted_name, '') <> COALESCE(ft.accepted_name, '')
                   OR COALESCE(f.identified_rank, '') <> COALESCE(ft.identified_rank, '')
                   OR COALESCE(f.accepted_rank, '') <> COALESCE(ft.accepted_rank, '')
                   OR COALESCE(f.difference, '') <> COALESCE(ft.difference, '')
                   OR COALESCE(f.identified_no, '') <> COALESCE(ft.identified_no, '')
                   OR COALESCE(f.accepted_no, '') <> COALESCE(ft.accepted_no, '')
                   OR COALESCE(f.phylum, '') <> COALESCE(ft.phylum, '')
                   OR COALESCE(f.class_name, '') <> COALESCE(ft.class_name, '')
                   OR COALESCE(f.taxon_order, '') <> COALESCE(ft.taxon_order, '')
                   OR COALESCE(f.family, '') <> COALESCE(ft.family, '')
                   OR COALESCE(f.genus, '') <> COALESCE(ft.genus, '')
                   OR COALESCE(f.reference_no, '') <> COALESCE(ft.reference_no, '')
                   OR COALESCE(f.taxonomy_comments, '') <> COALESCE(ft.taxonomy_comments, '')
                   OR COALESCE(f.collection_year_latest_estimate, -2147483648) <> COALESCE(ft.collection_year_latest_estimate, -2147483648)
                """,
            )
        else:
            field_value_mismatch = 0
            taxonomy_value_mismatch = 0

        checks.extend(
            [
                CheckResult("finds_count", finds_count, finds_count >= 0),
                CheckResult("find_field_observations_count", observations_count, observations_count == finds_count),
                CheckResult("find_taxonomy_count", taxonomy_count, taxonomy_count == finds_count),
                CheckResult("missing_find_field_observations", missing_observations, missing_observations == 0),
                CheckResult("missing_find_taxonomy", missing_taxonomy, missing_taxonomy == 0),
                CheckResult("orphan_find_field_observations", orphan_observations, orphan_observations == 0),
                CheckResult("orphan_find_taxonomy", orphan_taxonomy, orphan_taxonomy == 0),
                CheckResult("field_observation_value_mismatches", field_value_mismatch, field_value_mismatch == 0),
                CheckResult("taxonomy_value_mismatches", taxonomy_value_mismatch, taxonomy_value_mismatch == 0),
            ]
        )
        mismatch_total = field_value_mismatch + taxonomy_value_mismatch
    return checks, mismatch_total


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate finds split-table consistency against legacy finds columns.")
    parser.add_argument("--postgres-url", default=None, help="PostgreSQL DSN. Defaults to env vars.")
    args = parser.parse_args()

    postgres_url = _resolve_postgres_url(args.postgres_url)
    checks, mismatch_total = run_validation(postgres_url)

    print("Finds split validation results:")
    failed = 0
    for check in checks:
        status = "OK" if check.ok else "FAIL"
        print(f"- {status}: {check.label}={check.value}")
        if not check.ok:
            failed += 1
    print(f"summary: failed={failed} mismatches={mismatch_total}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
