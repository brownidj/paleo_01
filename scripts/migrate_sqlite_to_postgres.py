#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path
from typing import Any

from psycopg import Connection, connect
from psycopg.rows import dict_row


def _resolve_postgres_url(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    env_value = os.getenv("DATABASE_URL", "").strip()
    if env_value:
        return env_value
    raise ValueError("DATABASE_URL is required. Pass --postgres-url or export DATABASE_URL.")


def _fetch_sqlite_rows(conn: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]


def _ensure_schema(pg: Connection) -> None:
    with pg.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS team_members (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                phone_number TEXT,
                active BOOLEAN NOT NULL DEFAULT FALSE,
                institution TEXT,
                recruitment_date DATE,
                retirement_date DATE
            )
            """
        )
        cur.execute("ALTER TABLE team_members ADD COLUMN IF NOT EXISTS phone_number TEXT")
        cur.execute("ALTER TABLE team_members ADD COLUMN IF NOT EXISTS institution TEXT")
        cur.execute("ALTER TABLE team_members ADD COLUMN IF NOT EXISTS recruitment_date DATE")
        cur.execute("ALTER TABLE team_members ADD COLUMN IF NOT EXISTS retirement_date DATE")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_accounts (
                id BIGSERIAL PRIMARY KEY,
                team_member_id BIGINT NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'team', 'planner', 'reviewer', 'field_member')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
                password_changed_at TIMESTAMPTZ
            )
            """
        )
        cur.execute("ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trips (
                id BIGSERIAL PRIMARY KEY,
                trip_name TEXT,
                start_date DATE,
                end_date DATE,
                team TEXT,
                notes TEXT,
                location TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS locations (
                id BIGSERIAL PRIMARY KEY,
                name TEXT,
                latitude TEXT,
                longitude TEXT,
                altitude_value TEXT,
                altitude_unit TEXT,
                country_code TEXT,
                state TEXT,
                lga TEXT,
                basin TEXT,
                geogscale TEXT,
                geography_comments TEXT,
                geology_id BIGINT,
                proterozoic_province TEXT,
                orogen TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS geology_context (
                id BIGSERIAL PRIMARY KEY,
                location_id BIGINT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
                location_name TEXT NOT NULL,
                source_system TEXT NOT NULL DEFAULT 'PBDB',
                source_reference_no TEXT,
                early_interval TEXT,
                late_interval TEXT,
                max_ma DOUBLE PRECISION,
                min_ma DOUBLE PRECISION,
                environment TEXT,
                geogscale TEXT,
                geology_comments TEXT,
                formation TEXT,
                stratigraphy_group TEXT,
                member TEXT,
                stratscale TEXT,
                stratigraphy_comments TEXT,
                geoplate TEXT,
                paleomodel TEXT,
                paleolat DOUBLE PRECISION,
                paleolng DOUBLE PRECISION,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lithology (
                id BIGSERIAL PRIMARY KEY,
                geology_context_id BIGINT NOT NULL REFERENCES geology_context(id) ON DELETE CASCADE,
                slot INTEGER NOT NULL,
                lithology TEXT,
                lithification TEXT,
                minor_lithology TEXT,
                lithology_adjectives TEXT,
                fossils_from TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (geology_context_id, slot)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trip_locations (
                trip_id BIGINT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                location_id BIGINT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
                PRIMARY KEY (trip_id, location_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS collection_events (
                id BIGSERIAL PRIMARY KEY,
                location_id BIGINT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
                collection_name TEXT NOT NULL,
                collection_subset TEXT,
                trip_id BIGINT REFERENCES trips(id) ON DELETE SET NULL,
                event_year INTEGER
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS finds (
                id BIGSERIAL PRIMARY KEY,
                location_id BIGINT REFERENCES locations(id) ON DELETE SET NULL,
                collection_event_id BIGINT REFERENCES collection_events(id) ON DELETE SET NULL,
                source_system TEXT,
                source_occurrence_no TEXT,
                identified_name TEXT,
                accepted_name TEXT,
                identified_rank TEXT,
                accepted_rank TEXT,
                difference TEXT,
                identified_no TEXT,
                accepted_no TEXT,
                phylum TEXT,
                class_name TEXT,
                taxon_order TEXT,
                family TEXT,
                genus TEXT,
                abund_value TEXT,
                abund_unit TEXT,
                reference_no TEXT,
                taxonomy_comments TEXT,
                occurrence_comments TEXT,
                research_group TEXT,
                notes TEXT,
                collection_year_latest_estimate INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def _truncate_all(pg: Connection) -> None:
    with pg.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                finds,
                lithology,
                geology_context,
                collection_events,
                trip_locations,
                user_accounts,
                trips,
                locations,
                team_members
            RESTART IDENTITY CASCADE
            """
        )


def _upsert_table(pg: Connection, sql: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with pg.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def _sync_sequences(pg: Connection, tables: list[str]) -> None:
    with pg.cursor() as cur:
        for table in tables:
            cur.execute(
                f"""
                SELECT setval(
                    pg_get_serial_sequence(%s, 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 1),
                    (SELECT COUNT(*) > 0 FROM {table})
                )
                """,
                (table,),
            )


def migrate(sqlite_path: Path, postgres_url: str, truncate_first: bool) -> dict[str, int]:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite file not found: {sqlite_path}")

    with sqlite3.connect(sqlite_path) as sqlite_conn, connect(postgres_url, row_factory=dict_row) as pg_conn:
        _ensure_schema(pg_conn)
        if truncate_first:
            _truncate_all(pg_conn)

        counts: dict[str, int] = {}

        team_rows = _fetch_sqlite_rows(
            sqlite_conn,
            """
            SELECT
                id,
                name,
                phone_number,
                active,
                institution,
                recruitment_date,
                retirement_date
            FROM Team_members
            ORDER BY id
            """,
        )
        for row in team_rows:
            row["active"] = bool(int(row["active"] or 0))
        counts["team_members"] = _upsert_table(
            pg_conn,
            """
            INSERT INTO team_members
                (id, name, phone_number, active, institution, recruitment_date, retirement_date)
            VALUES
                (%(id)s, %(name)s, %(phone_number)s, %(active)s, %(institution)s, %(recruitment_date)s, %(retirement_date)s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                phone_number = EXCLUDED.phone_number,
                active = EXCLUDED.active,
                institution = EXCLUDED.institution,
                recruitment_date = EXCLUDED.recruitment_date,
                retirement_date = EXCLUDED.retirement_date
            """,
            team_rows,
        )

        user_rows = _fetch_sqlite_rows(
            sqlite_conn,
            """
            SELECT
                id,
                team_member_id,
                username,
                password_hash,
                role,
                created_at,
                must_change_password,
                password_changed_at
            FROM User_Accounts
            ORDER BY id
            """,
        )
        for row in user_rows:
            row["must_change_password"] = bool(int(row["must_change_password"] or 0))
        counts["user_accounts"] = _upsert_table(
            pg_conn,
            """
            INSERT INTO user_accounts
                (id, team_member_id, username, password_hash, role, created_at, must_change_password, password_changed_at)
            VALUES
                (
                    %(id)s, %(team_member_id)s, %(username)s, %(password_hash)s, %(role)s,
                    %(created_at)s, %(must_change_password)s, %(password_changed_at)s
                )
            ON CONFLICT (id) DO UPDATE SET
                team_member_id = EXCLUDED.team_member_id,
                username = EXCLUDED.username,
                password_hash = EXCLUDED.password_hash,
                role = EXCLUDED.role,
                created_at = EXCLUDED.created_at,
                must_change_password = EXCLUDED.must_change_password,
                password_changed_at = EXCLUDED.password_changed_at
            """,
            user_rows,
        )

        location_rows = _fetch_sqlite_rows(
            sqlite_conn,
            """
            SELECT
                id,
                name,
                latitude,
                longitude,
                altitude_value,
                altitude_unit,
                country_code,
                state,
                lga,
                basin,
                geogscale,
                geography_comments,
                geology_id,
                proterozoic_province,
                orogen
            FROM Locations
            ORDER BY id
            """,
        )
        counts["locations"] = _upsert_table(
            pg_conn,
            """
            INSERT INTO locations
                (
                    id, name, latitude, longitude, altitude_value, altitude_unit, country_code, state, lga, basin,
                    geogscale, geography_comments, geology_id, proterozoic_province, orogen
                )
            VALUES
                (
                    %(id)s, %(name)s, %(latitude)s, %(longitude)s, %(altitude_value)s, %(altitude_unit)s,
                    %(country_code)s, %(state)s, %(lga)s, %(basin)s, %(geogscale)s, %(geography_comments)s,
                    %(geology_id)s, %(proterozoic_province)s, %(orogen)s
                )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                altitude_value = EXCLUDED.altitude_value,
                altitude_unit = EXCLUDED.altitude_unit,
                country_code = EXCLUDED.country_code,
                state = EXCLUDED.state,
                lga = EXCLUDED.lga,
                basin = EXCLUDED.basin,
                geogscale = EXCLUDED.geogscale,
                geography_comments = EXCLUDED.geography_comments,
                geology_id = EXCLUDED.geology_id,
                proterozoic_province = EXCLUDED.proterozoic_province,
                orogen = EXCLUDED.orogen
            """,
            location_rows,
        )

        geology_rows = _fetch_sqlite_rows(
            sqlite_conn,
            """
            SELECT
                id,
                location_id,
                location_name,
                source_system,
                source_reference_no,
                early_interval,
                late_interval,
                max_ma,
                min_ma,
                environment,
                geogscale,
                geology_comments,
                formation,
                stratigraphy_group,
                member,
                stratscale,
                stratigraphy_comments,
                geoplate,
                paleomodel,
                paleolat,
                paleolng,
                created_at,
                updated_at
            FROM GeologyContext
            ORDER BY id
            """,
        )
        counts["geology_context"] = _upsert_table(
            pg_conn,
            """
            INSERT INTO geology_context
                (
                    id, location_id, location_name, source_system, source_reference_no, early_interval, late_interval,
                    max_ma, min_ma, environment, geogscale, geology_comments, formation, stratigraphy_group, member,
                    stratscale, stratigraphy_comments, geoplate, paleomodel, paleolat, paleolng, created_at, updated_at
                )
            VALUES
                (
                    %(id)s, %(location_id)s, %(location_name)s, %(source_system)s, %(source_reference_no)s,
                    %(early_interval)s, %(late_interval)s, %(max_ma)s, %(min_ma)s, %(environment)s, %(geogscale)s,
                    %(geology_comments)s, %(formation)s, %(stratigraphy_group)s, %(member)s, %(stratscale)s,
                    %(stratigraphy_comments)s, %(geoplate)s, %(paleomodel)s, %(paleolat)s, %(paleolng)s,
                    %(created_at)s, %(updated_at)s
                )
            ON CONFLICT (id) DO UPDATE SET
                location_id = EXCLUDED.location_id,
                location_name = EXCLUDED.location_name,
                source_system = EXCLUDED.source_system,
                source_reference_no = EXCLUDED.source_reference_no,
                early_interval = EXCLUDED.early_interval,
                late_interval = EXCLUDED.late_interval,
                max_ma = EXCLUDED.max_ma,
                min_ma = EXCLUDED.min_ma,
                environment = EXCLUDED.environment,
                geogscale = EXCLUDED.geogscale,
                geology_comments = EXCLUDED.geology_comments,
                formation = EXCLUDED.formation,
                stratigraphy_group = EXCLUDED.stratigraphy_group,
                member = EXCLUDED.member,
                stratscale = EXCLUDED.stratscale,
                stratigraphy_comments = EXCLUDED.stratigraphy_comments,
                geoplate = EXCLUDED.geoplate,
                paleomodel = EXCLUDED.paleomodel,
                paleolat = EXCLUDED.paleolat,
                paleolng = EXCLUDED.paleolng,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            geology_rows,
        )

        lithology_rows = _fetch_sqlite_rows(
            sqlite_conn,
            """
            SELECT
                id,
                geology_context_id,
                slot,
                lithology,
                lithification,
                minor_lithology,
                lithology_adjectives,
                fossils_from,
                created_at,
                updated_at
            FROM Lithology
            ORDER BY id
            """,
        )
        counts["lithology"] = _upsert_table(
            pg_conn,
            """
            INSERT INTO lithology
                (
                    id, geology_context_id, slot, lithology, lithification, minor_lithology,
                    lithology_adjectives, fossils_from, created_at, updated_at
                )
            VALUES
                (
                    %(id)s, %(geology_context_id)s, %(slot)s, %(lithology)s, %(lithification)s, %(minor_lithology)s,
                    %(lithology_adjectives)s, %(fossils_from)s, %(created_at)s, %(updated_at)s
                )
            ON CONFLICT (id) DO UPDATE SET
                geology_context_id = EXCLUDED.geology_context_id,
                slot = EXCLUDED.slot,
                lithology = EXCLUDED.lithology,
                lithification = EXCLUDED.lithification,
                minor_lithology = EXCLUDED.minor_lithology,
                lithology_adjectives = EXCLUDED.lithology_adjectives,
                fossils_from = EXCLUDED.fossils_from,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            lithology_rows,
        )

        trip_rows = _fetch_sqlite_rows(
            sqlite_conn,
            "SELECT id, trip_name, start_date, end_date, team, notes, location FROM Trips ORDER BY id",
        )
        counts["trips"] = _upsert_table(
            pg_conn,
            """
            INSERT INTO trips
                (id, trip_name, start_date, end_date, team, notes, location)
            VALUES
                (%(id)s, %(trip_name)s, %(start_date)s, %(end_date)s, %(team)s, %(notes)s, %(location)s)
            ON CONFLICT (id) DO UPDATE SET
                trip_name = EXCLUDED.trip_name,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                team = EXCLUDED.team,
                notes = EXCLUDED.notes,
                location = EXCLUDED.location
            """,
            trip_rows,
        )

        trip_location_rows = _fetch_sqlite_rows(
            sqlite_conn,
            "SELECT id AS trip_id, location_id FROM TripLocations ORDER BY id, location_id",
        )
        counts["trip_locations"] = _upsert_table(
            pg_conn,
            """
            INSERT INTO trip_locations
                (trip_id, location_id)
            VALUES
                (%(trip_id)s, %(location_id)s)
            ON CONFLICT (trip_id, location_id) DO NOTHING
            """,
            trip_location_rows,
        )

        collection_rows = _fetch_sqlite_rows(
            sqlite_conn,
            """
            SELECT
                id,
                location_id,
                collection_name,
                collection_subset,
                trip_id,
                event_year
            FROM CollectionEvents
            ORDER BY id
            """,
        )
        counts["collection_events"] = _upsert_table(
            pg_conn,
            """
            INSERT INTO collection_events
                (id, location_id, collection_name, collection_subset, trip_id, event_year)
            VALUES
                (%(id)s, %(location_id)s, %(collection_name)s, %(collection_subset)s, %(trip_id)s, %(event_year)s)
            ON CONFLICT (id) DO UPDATE SET
                location_id = EXCLUDED.location_id,
                collection_name = EXCLUDED.collection_name,
                collection_subset = EXCLUDED.collection_subset,
                trip_id = EXCLUDED.trip_id,
                event_year = EXCLUDED.event_year
            """,
            collection_rows,
        )

        find_rows = _fetch_sqlite_rows(
            sqlite_conn,
            """
            SELECT
                id,
                location_id,
                collection_event_id,
                source_system,
                source_occurrence_no,
                identified_name,
                accepted_name,
                identified_rank,
                accepted_rank,
                difference,
                identified_no,
                accepted_no,
                phylum,
                class_name,
                taxon_order,
                family,
                genus,
                abund_value,
                abund_unit,
                reference_no,
                taxonomy_comments,
                occurrence_comments,
                research_group,
                notes,
                collection_year_latest_estimate,
                created_at,
                updated_at
            FROM Finds
            ORDER BY id
            """,
        )
        counts["finds"] = _upsert_table(
            pg_conn,
            """
            INSERT INTO finds
                (
                    id, location_id, collection_event_id, source_system, source_occurrence_no, identified_name,
                    accepted_name, identified_rank, accepted_rank, difference, identified_no, accepted_no, phylum,
                    class_name, taxon_order, family, genus, abund_value, abund_unit, reference_no, taxonomy_comments,
                    occurrence_comments, research_group, notes, collection_year_latest_estimate, created_at, updated_at
                )
            VALUES
                (
                    %(id)s, %(location_id)s, %(collection_event_id)s, %(source_system)s, %(source_occurrence_no)s,
                    %(identified_name)s, %(accepted_name)s, %(identified_rank)s, %(accepted_rank)s, %(difference)s,
                    %(identified_no)s, %(accepted_no)s, %(phylum)s, %(class_name)s, %(taxon_order)s, %(family)s,
                    %(genus)s, %(abund_value)s, %(abund_unit)s, %(reference_no)s, %(taxonomy_comments)s,
                    %(occurrence_comments)s, %(research_group)s, %(notes)s, %(collection_year_latest_estimate)s,
                    %(created_at)s, %(updated_at)s
                )
            ON CONFLICT (id) DO UPDATE SET
                location_id = EXCLUDED.location_id,
                collection_event_id = EXCLUDED.collection_event_id,
                source_system = EXCLUDED.source_system,
                source_occurrence_no = EXCLUDED.source_occurrence_no,
                identified_name = EXCLUDED.identified_name,
                accepted_name = EXCLUDED.accepted_name,
                identified_rank = EXCLUDED.identified_rank,
                accepted_rank = EXCLUDED.accepted_rank,
                difference = EXCLUDED.difference,
                identified_no = EXCLUDED.identified_no,
                accepted_no = EXCLUDED.accepted_no,
                phylum = EXCLUDED.phylum,
                class_name = EXCLUDED.class_name,
                taxon_order = EXCLUDED.taxon_order,
                family = EXCLUDED.family,
                genus = EXCLUDED.genus,
                abund_value = EXCLUDED.abund_value,
                abund_unit = EXCLUDED.abund_unit,
                reference_no = EXCLUDED.reference_no,
                taxonomy_comments = EXCLUDED.taxonomy_comments,
                occurrence_comments = EXCLUDED.occurrence_comments,
                research_group = EXCLUDED.research_group,
                notes = EXCLUDED.notes,
                collection_year_latest_estimate = EXCLUDED.collection_year_latest_estimate,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            find_rows,
        )

        _sync_sequences(
            pg_conn,
            [
                "team_members",
                "user_accounts",
                "locations",
                "geology_context",
                "lithology",
                "trips",
                "collection_events",
                "finds",
            ],
        )
        pg_conn.commit()
        return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite paleo data into PostgreSQL.")
    parser.add_argument("--sqlite", default="data/paleo_trips_01.db", help="Path to source SQLite DB.")
    parser.add_argument("--postgres-url", default=None, help="PostgreSQL DSN. Defaults to DATABASE_URL env var.")
    parser.add_argument(
        "--truncate-first",
        action="store_true",
        help="Truncate target tables before importing.",
    )
    args = parser.parse_args()

    postgres_url = _resolve_postgres_url(args.postgres_url)
    counts = migrate(Path(args.sqlite), postgres_url, truncate_first=args.truncate_first)
    print("Migration complete.")
    for table, count in counts.items():
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()
