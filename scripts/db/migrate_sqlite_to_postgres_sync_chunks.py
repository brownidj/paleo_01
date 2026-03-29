from __future__ import annotations

import sqlite3

from psycopg import Connection

from scripts.db.migrate_sqlite_to_postgres_schema_helpers import upsert_table


def _to_bool_from_row(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, float):
        return int(value) != 0
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="ignore").strip()
        return bool(int(text)) if text else False
    if isinstance(value, str):
        text = value.strip()
        return bool(int(text)) if text else False
    return False


def _fetch_sqlite_rows(conn: sqlite3.Connection, sql: str) -> list[dict[str, object]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]


def sync_people_and_locations(sqlite_conn: sqlite3.Connection, pg_conn: Connection) -> dict[str, int]:
    counts: dict[str, int] = {}

    team_rows = _fetch_sqlite_rows(
        sqlite_conn,
        """
        SELECT id, name, phone_number, active, institution, recruitment_date, retirement_date
        FROM Team_members ORDER BY id
        """,
    )
    for row in team_rows:
        row["active"] = _to_bool_from_row(row.get("active"))
    counts["team_members"] = upsert_table(
        pg_conn,
        """
        INSERT INTO team_members (id, name, phone_number, active, institution, recruitment_date, retirement_date)
        VALUES (%(id)s, %(name)s, %(phone_number)s, %(active)s, %(institution)s, %(recruitment_date)s, %(retirement_date)s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name, phone_number = EXCLUDED.phone_number, active = EXCLUDED.active,
            institution = EXCLUDED.institution, recruitment_date = EXCLUDED.recruitment_date, retirement_date = EXCLUDED.retirement_date
        """,
        team_rows,
    )

    user_rows = _fetch_sqlite_rows(
        sqlite_conn,
        """
        SELECT id, team_member_id, username, password_hash, role, created_at, must_change_password, password_changed_at
        FROM User_Accounts ORDER BY id
        """,
    )
    for row in user_rows:
        row["must_change_password"] = _to_bool_from_row(row.get("must_change_password"))
    counts["user_accounts"] = upsert_table(
        pg_conn,
        """
        INSERT INTO user_accounts (id, team_member_id, username, password_hash, role, created_at, must_change_password, password_changed_at)
        VALUES (%(id)s, %(team_member_id)s, %(username)s, %(password_hash)s, %(role)s, %(created_at)s, %(must_change_password)s, %(password_changed_at)s)
        ON CONFLICT (id) DO UPDATE SET
            team_member_id = EXCLUDED.team_member_id, username = EXCLUDED.username, password_hash = EXCLUDED.password_hash,
            role = EXCLUDED.role, created_at = EXCLUDED.created_at, must_change_password = EXCLUDED.must_change_password,
            password_changed_at = EXCLUDED.password_changed_at
        """,
        user_rows,
    )

    location_rows = _fetch_sqlite_rows(
        sqlite_conn,
        """
        SELECT id, name, latitude, longitude, altitude_value, altitude_unit, country_code, state, lga, basin,
               geogscale, geography_comments, geology_id, proterozoic_province, orogen
        FROM Locations ORDER BY id
        """,
    )
    counts["locations"] = upsert_table(
        pg_conn,
        """
        INSERT INTO locations
            (id, name, latitude, longitude, altitude_value, altitude_unit, country_code, state, lga, basin,
             geogscale, geography_comments, geology_id, proterozoic_province, orogen)
        VALUES
            (%(id)s, %(name)s, %(latitude)s, %(longitude)s, %(altitude_value)s, %(altitude_unit)s,
             %(country_code)s, %(state)s, %(lga)s, %(basin)s, %(geogscale)s, %(geography_comments)s,
             %(geology_id)s, %(proterozoic_province)s, %(orogen)s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name, latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
            altitude_value = EXCLUDED.altitude_value, altitude_unit = EXCLUDED.altitude_unit, country_code = EXCLUDED.country_code,
            state = EXCLUDED.state, lga = EXCLUDED.lga, basin = EXCLUDED.basin, geogscale = EXCLUDED.geogscale,
            geography_comments = EXCLUDED.geography_comments, geology_id = EXCLUDED.geology_id,
            proterozoic_province = EXCLUDED.proterozoic_province, orogen = EXCLUDED.orogen
        """,
        location_rows,
    )
    return counts


def sync_geology_and_trips(sqlite_conn: sqlite3.Connection, pg_conn: Connection) -> dict[str, int]:
    counts: dict[str, int] = {}

    geology_rows = _fetch_sqlite_rows(
        sqlite_conn,
        """
        SELECT id, location_id, location_name, source_system, source_reference_no, early_interval, late_interval, max_ma, min_ma,
               environment, geogscale, geology_comments, formation, stratigraphy_group, member, stratscale, stratigraphy_comments,
               geoplate, paleomodel, paleolat, paleolng, created_at, updated_at
        FROM GeologyContext ORDER BY id
        """,
    )
    counts["geology_context"] = upsert_table(
        pg_conn,
        """
        INSERT INTO geology_context
            (id, location_id, location_name, source_system, source_reference_no, early_interval, late_interval,
             max_ma, min_ma, environment, geogscale, geology_comments, formation, stratigraphy_group, member,
             stratscale, stratigraphy_comments, geoplate, paleomodel, paleolat, paleolng, created_at, updated_at)
        VALUES
            (%(id)s, %(location_id)s, %(location_name)s, %(source_system)s, %(source_reference_no)s, %(early_interval)s,
             %(late_interval)s, %(max_ma)s, %(min_ma)s, %(environment)s, %(geogscale)s, %(geology_comments)s, %(formation)s,
             %(stratigraphy_group)s, %(member)s, %(stratscale)s, %(stratigraphy_comments)s, %(geoplate)s, %(paleomodel)s,
             %(paleolat)s, %(paleolng)s, %(created_at)s, %(updated_at)s)
        ON CONFLICT (id) DO UPDATE SET
            location_id = EXCLUDED.location_id, location_name = EXCLUDED.location_name, source_system = EXCLUDED.source_system,
            source_reference_no = EXCLUDED.source_reference_no, early_interval = EXCLUDED.early_interval,
            late_interval = EXCLUDED.late_interval, max_ma = EXCLUDED.max_ma, min_ma = EXCLUDED.min_ma,
            environment = EXCLUDED.environment, geogscale = EXCLUDED.geogscale, geology_comments = EXCLUDED.geology_comments,
            formation = EXCLUDED.formation, stratigraphy_group = EXCLUDED.stratigraphy_group, member = EXCLUDED.member,
            stratscale = EXCLUDED.stratscale, stratigraphy_comments = EXCLUDED.stratigraphy_comments, geoplate = EXCLUDED.geoplate,
            paleomodel = EXCLUDED.paleomodel, paleolat = EXCLUDED.paleolat, paleolng = EXCLUDED.paleolng,
            created_at = EXCLUDED.created_at, updated_at = EXCLUDED.updated_at
        """,
        geology_rows,
    )

    lithology_rows = _fetch_sqlite_rows(
        sqlite_conn,
        """
        SELECT id, geology_context_id, slot, lithology, lithification, minor_lithology,
               lithology_adjectives, fossils_from, created_at, updated_at
        FROM Lithology ORDER BY id
        """,
    )
    counts["lithology"] = upsert_table(
        pg_conn,
        """
        INSERT INTO lithology
            (id, geology_context_id, slot, lithology, lithification, minor_lithology,
             lithology_adjectives, fossils_from, created_at, updated_at)
        VALUES
            (%(id)s, %(geology_context_id)s, %(slot)s, %(lithology)s, %(lithification)s, %(minor_lithology)s,
             %(lithology_adjectives)s, %(fossils_from)s, %(created_at)s, %(updated_at)s)
        ON CONFLICT (id) DO UPDATE SET
            geology_context_id = EXCLUDED.geology_context_id, slot = EXCLUDED.slot, lithology = EXCLUDED.lithology,
            lithification = EXCLUDED.lithification, minor_lithology = EXCLUDED.minor_lithology,
            lithology_adjectives = EXCLUDED.lithology_adjectives, fossils_from = EXCLUDED.fossils_from,
            created_at = EXCLUDED.created_at, updated_at = EXCLUDED.updated_at
        """,
        lithology_rows,
    )

    trip_rows = _fetch_sqlite_rows(
        sqlite_conn,
        "SELECT id, trip_name, start_date, end_date, team, notes, location FROM Trips ORDER BY id",
    )
    counts["trips"] = upsert_table(
        pg_conn,
        """
        INSERT INTO trips (id, trip_name, start_date, end_date, team, notes, location)
        VALUES (%(id)s, %(trip_name)s, %(start_date)s, %(end_date)s, %(team)s, %(notes)s, %(location)s)
        ON CONFLICT (id) DO UPDATE SET
            trip_name = EXCLUDED.trip_name, start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date,
            team = EXCLUDED.team, notes = EXCLUDED.notes, location = EXCLUDED.location
        """,
        trip_rows,
    )

    trip_location_rows = _fetch_sqlite_rows(
        sqlite_conn,
        "SELECT id AS trip_id, location_id FROM TripLocations ORDER BY id, location_id",
    )
    counts["trip_locations"] = upsert_table(
        pg_conn,
        """
        INSERT INTO trip_locations (trip_id, location_id)
        VALUES (%(trip_id)s, %(location_id)s)
        ON CONFLICT (trip_id, location_id) DO NOTHING
        """,
        trip_location_rows,
    )
    return counts


def sync_collection_events_and_finds(sqlite_conn: sqlite3.Connection, pg_conn: Connection) -> dict[str, int]:
    counts: dict[str, int] = {}

    collection_rows = _fetch_sqlite_rows(
        sqlite_conn,
        "SELECT id, location_id, collection_name, collection_subset, trip_id, event_year FROM CollectionEvents ORDER BY id",
    )
    counts["collection_events"] = upsert_table(
        pg_conn,
        """
        INSERT INTO collection_events (id, location_id, collection_name, collection_subset, trip_id, event_year)
        VALUES (%(id)s, %(location_id)s, %(collection_name)s, %(collection_subset)s, %(trip_id)s, %(event_year)s)
        ON CONFLICT (id) DO UPDATE SET
            location_id = EXCLUDED.location_id, collection_name = EXCLUDED.collection_name,
            collection_subset = EXCLUDED.collection_subset, trip_id = EXCLUDED.trip_id, event_year = EXCLUDED.event_year
        """,
        collection_rows,
    )

    find_rows = _fetch_sqlite_rows(
        sqlite_conn,
        """
        SELECT id, location_id, collection_event_id, source_system, source_occurrence_no, identified_name, accepted_name,
               identified_rank, accepted_rank, difference, identified_no, accepted_no, phylum, class_name, taxon_order,
               family, genus, abund_value, abund_unit, reference_no, taxonomy_comments, occurrence_comments, research_group,
               notes, find_date, find_time, latitude, longitude, collection_year_latest_estimate, created_at, updated_at
        FROM Finds ORDER BY id
        """,
    )
    counts["finds"] = upsert_table(
        pg_conn,
        """
        INSERT INTO finds
            (id, location_id, collection_event_id, source_system, source_occurrence_no, identified_name, accepted_name,
             identified_rank, accepted_rank, difference, identified_no, accepted_no, phylum, class_name, taxon_order, family,
             genus, abund_value, abund_unit, reference_no, taxonomy_comments, occurrence_comments, research_group, notes,
             find_date, find_time, latitude, longitude, collection_year_latest_estimate, created_at, updated_at)
        VALUES
            (%(id)s, %(location_id)s, %(collection_event_id)s, %(source_system)s, %(source_occurrence_no)s, %(identified_name)s,
             %(accepted_name)s, %(identified_rank)s, %(accepted_rank)s, %(difference)s, %(identified_no)s, %(accepted_no)s,
             %(phylum)s, %(class_name)s, %(taxon_order)s, %(family)s, %(genus)s, %(abund_value)s, %(abund_unit)s,
             %(reference_no)s, %(taxonomy_comments)s, %(occurrence_comments)s, %(research_group)s, %(notes)s,
             %(find_date)s, %(find_time)s, %(latitude)s, %(longitude)s, %(collection_year_latest_estimate)s, %(created_at)s, %(updated_at)s)
        ON CONFLICT (id) DO UPDATE SET
            location_id = EXCLUDED.location_id, collection_event_id = EXCLUDED.collection_event_id, source_system = EXCLUDED.source_system,
            source_occurrence_no = EXCLUDED.source_occurrence_no, identified_name = EXCLUDED.identified_name, accepted_name = EXCLUDED.accepted_name,
            identified_rank = EXCLUDED.identified_rank, accepted_rank = EXCLUDED.accepted_rank, difference = EXCLUDED.difference,
            identified_no = EXCLUDED.identified_no, accepted_no = EXCLUDED.accepted_no, phylum = EXCLUDED.phylum, class_name = EXCLUDED.class_name,
            taxon_order = EXCLUDED.taxon_order, family = EXCLUDED.family, genus = EXCLUDED.genus, abund_value = EXCLUDED.abund_value,
            abund_unit = EXCLUDED.abund_unit, reference_no = EXCLUDED.reference_no, taxonomy_comments = EXCLUDED.taxonomy_comments,
            occurrence_comments = EXCLUDED.occurrence_comments, research_group = EXCLUDED.research_group, notes = EXCLUDED.notes,
            find_date = EXCLUDED.find_date, find_time = EXCLUDED.find_time, latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
            collection_year_latest_estimate = EXCLUDED.collection_year_latest_estimate, created_at = EXCLUDED.created_at, updated_at = EXCLUDED.updated_at
        """,
        find_rows,
    )
    return counts
