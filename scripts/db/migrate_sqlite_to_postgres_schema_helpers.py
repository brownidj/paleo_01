from __future__ import annotations

from typing import Any

from psycopg import Connection


def ensure_schema(pg: Connection, include_legacy_finds_columns: bool = True) -> None:
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
                boundary_geojson TEXT,
                trip_id BIGINT REFERENCES trips(id) ON DELETE SET NULL,
                event_year INTEGER
            )
            """
        )
        cur.execute("ALTER TABLE collection_events ADD COLUMN IF NOT EXISTS boundary_geojson TEXT")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS finds (
                id BIGSERIAL PRIMARY KEY,
                location_id BIGINT REFERENCES locations(id) ON DELETE SET NULL,
                collection_event_id BIGINT REFERENCES collection_events(id) ON DELETE SET NULL,
                team_member_id BIGINT REFERENCES team_members(id) ON DELETE SET NULL,
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
                find_date TEXT,
                find_time TEXT,
                latitude TEXT,
                longitude TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS find_date TEXT")
        cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS find_time TEXT")
        cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS latitude TEXT")
        cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS longitude TEXT")
        cur.execute(
            "ALTER TABLE finds ADD COLUMN IF NOT EXISTS team_member_id BIGINT REFERENCES team_members(id) ON DELETE SET NULL"
        )
        # Legacy compatibility columns are only needed for SQLite->Postgres import.
        # App startup must not repeatedly add/drop these, because dropped columns
        # still count toward PostgreSQL's 1600-column table limit.
        if include_legacy_finds_columns:
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS identified_name TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS accepted_name TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS identified_rank TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS accepted_rank TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS difference TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS identified_no TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS accepted_no TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS phylum TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS class_name TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS taxon_order TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS family TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS genus TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS abund_value TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS abund_unit TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS reference_no TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS taxonomy_comments TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS occurrence_comments TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS research_group TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS notes TEXT")
            cur.execute("ALTER TABLE finds ADD COLUMN IF NOT EXISTS collection_year_latest_estimate INTEGER")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS find_field_observations (
                id BIGSERIAL PRIMARY KEY,
                find_id BIGINT NOT NULL UNIQUE REFERENCES finds(id) ON DELETE CASCADE,
                provisional_identification TEXT,
                notes TEXT,
                abund_value TEXT,
                abund_unit TEXT,
                occurrence_comments TEXT,
                research_group TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS find_taxonomy (
                id BIGSERIAL PRIMARY KEY,
                find_id BIGINT NOT NULL UNIQUE REFERENCES finds(id) ON DELETE CASCADE,
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
                reference_no TEXT,
                taxonomy_comments TEXT,
                collection_year_latest_estimate INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
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
            cur.execute(
                """
                INSERT INTO find_field_observations (
                    find_id, provisional_identification, notes, abund_value, abund_unit, occurrence_comments, research_group,
                    created_at, updated_at
                )
                SELECT
                    f.id, f.identified_name, f.notes, f.abund_value, f.abund_unit, f.occurrence_comments, f.research_group,
                    f.created_at, f.updated_at
                FROM finds f
                LEFT JOIN find_field_observations fo ON fo.find_id = f.id
                WHERE fo.find_id IS NULL
                """
            )
            cur.execute(
                """
                INSERT INTO find_taxonomy (
                    find_id, identified_name, accepted_name, identified_rank, accepted_rank, difference, identified_no, accepted_no,
                    phylum, class_name, taxon_order, family, genus, reference_no, taxonomy_comments, collection_year_latest_estimate,
                    created_at, updated_at
                )
                SELECT
                    f.id, f.identified_name, f.accepted_name, f.identified_rank, f.accepted_rank, f.difference, f.identified_no, f.accepted_no,
                    f.phylum, f.class_name, f.taxon_order, f.family, f.genus, f.reference_no, f.taxonomy_comments, f.collection_year_latest_estimate,
                    f.created_at, f.updated_at
                FROM finds f
                LEFT JOIN find_taxonomy ft ON ft.find_id = f.id
                WHERE ft.find_id IS NULL
                """
            )


def truncate_all(pg: Connection) -> None:
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


def upsert_table(pg: Connection, sql: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with pg.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def sync_sequences(pg: Connection, tables: list[str]) -> None:
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
