import sqlite3


def rebuild_finds_table_without_trip_id(conn: sqlite3.Connection) -> None:
    rows = conn.execute('PRAGMA table_info("Finds")').fetchall()
    names = [row["name"] for row in rows]
    if "trip_id" not in names:
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS "Finds_new" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER,
            collection_event_id INTEGER,
            team_member_id INTEGER,
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
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES Locations(id) ON DELETE SET NULL,
            FOREIGN KEY (collection_event_id) REFERENCES CollectionEvents(id) ON DELETE SET NULL
        )
        """
    )
    copy_columns = [
        "id",
        "location_id",
        "collection_event_id",
        "team_member_id",
        "source_system",
        "source_occurrence_no",
        "identified_name",
        "accepted_name",
        "identified_rank",
        "accepted_rank",
        "difference",
        "identified_no",
        "accepted_no",
        "phylum",
        "class_name",
        "taxon_order",
        "family",
        "genus",
        "abund_value",
        "abund_unit",
        "reference_no",
        "taxonomy_comments",
        "occurrence_comments",
        "research_group",
        "notes",
        "collection_year_latest_estimate",
        "find_date",
        "find_time",
        "latitude",
        "longitude",
        "created_at",
        "updated_at",
    ]
    cols_sql = ", ".join([f'"{c}"' for c in copy_columns if c in names])
    conn.execute(f'INSERT INTO "Finds_new" ({cols_sql}) SELECT {cols_sql} FROM "Finds"')
    conn.execute('DROP TABLE "Finds"')
    conn.execute('ALTER TABLE "Finds_new" RENAME TO "Finds"')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_finds_location ON "Finds"(location_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_finds_collection_event ON "Finds"(collection_event_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_finds_source_occurrence ON "Finds"(source_occurrence_no)')
