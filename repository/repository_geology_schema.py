import sqlite3


class RepositoryGeologySchemaMixin:
    def ensure_geology_tables(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "GeologyContext" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_id INTEGER NOT NULL,
                    location_name TEXT NOT NULL,
                    source_system TEXT NOT NULL DEFAULT 'PBDB',
                    source_reference_no TEXT,
                    early_interval TEXT,
                    late_interval TEXT,
                    max_ma REAL,
                    min_ma REAL,
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
                    paleolat REAL,
                    paleolng REAL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (location_id) REFERENCES Locations(id) ON DELETE CASCADE
                )
                """
            )
            columns = {row["name"] for row in conn.execute('PRAGMA table_info("GeologyContext")').fetchall()}
            if "collection_event_id" in columns and "location_id" not in columns:
                self._migrate_legacy_geology_to_locations(conn)
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS "uq_geology_context_event_source"
                ON "GeologyContext"(location_id, source_system)
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS "uq_geology_context_location_name"
                ON "GeologyContext"(LOWER(TRIM(location_name)))
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "Lithology" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    geology_context_id INTEGER NOT NULL,
                    slot INTEGER NOT NULL,
                    lithology TEXT,
                    lithification TEXT,
                    minor_lithology TEXT,
                    lithology_adjectives TEXT,
                    fossils_from TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (geology_context_id) REFERENCES GeologyContext(id) ON DELETE CASCADE,
                    UNIQUE (geology_context_id, slot)
                )
                """
            )
            self._ensure_locations_geology_fk(conn)
            self._link_locations_to_geology(conn)

    @staticmethod
    def _migrate_legacy_geology_to_locations(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS "GeologyContext_new" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                location_name TEXT NOT NULL,
                source_system TEXT NOT NULL DEFAULT 'PBDB',
                source_reference_no TEXT,
                early_interval TEXT,
                late_interval TEXT,
                max_ma REAL,
                min_ma REAL,
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
                paleolat REAL,
                paleolng REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES Locations(id) ON DELETE CASCADE
            )
            """
        )
        rows = conn.execute(
            """
            SELECT
                gc.id,
                ce.location_id,
                l.name AS location_name,
                gc.source_system,
                gc.source_reference_no,
                gc.early_interval,
                gc.late_interval,
                gc.max_ma,
                gc.min_ma,
                gc.environment,
                gc.geogscale,
                gc.geology_comments,
                gc.formation,
                gc.stratigraphy_group,
                gc.member,
                gc.stratscale,
                gc.stratigraphy_comments,
                gc.geoplate,
                gc.paleomodel,
                gc.paleolat,
                gc.paleolng,
                gc.created_at,
                gc.updated_at
            FROM "GeologyContext" gc
            JOIN "CollectionEvents" ce ON ce.id = gc.collection_event_id
            JOIN "Locations" l ON l.id = ce.location_id
            ORDER BY gc.id
            """
        ).fetchall()
        seen_names: set[str] = set()
        for row in rows:
            location_name = str(row["location_name"] or "").strip()
            key = location_name.lower()
            if not key or key in seen_names:
                continue
            seen_names.add(key)
            conn.execute(
                """
                INSERT INTO "GeologyContext_new" (
                    id, location_id, location_name, source_system, source_reference_no,
                    early_interval, late_interval, max_ma, min_ma, environment, geogscale,
                    geology_comments, formation, stratigraphy_group, member, stratscale,
                    stratigraphy_comments, geoplate, paleomodel, paleolat, paleolng,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["location_id"],
                    location_name,
                    row["source_system"],
                    row["source_reference_no"],
                    row["early_interval"],
                    row["late_interval"],
                    row["max_ma"],
                    row["min_ma"],
                    row["environment"],
                    row["geogscale"],
                    row["geology_comments"],
                    row["formation"],
                    row["stratigraphy_group"],
                    row["member"],
                    row["stratscale"],
                    row["stratigraphy_comments"],
                    row["geoplate"],
                    row["paleomodel"],
                    row["paleolat"],
                    row["paleolng"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        kept_ids = {row["id"] for row in conn.execute('SELECT id FROM "GeologyContext_new"').fetchall()}
        if kept_ids:
            placeholders = ", ".join(["?"] * len(kept_ids))
            conn.execute(
                f'DELETE FROM "Lithology" WHERE geology_context_id NOT IN ({placeholders})',
                tuple(kept_ids),
            )
        else:
            conn.execute('DELETE FROM "Lithology"')
        conn.execute('DROP TABLE "GeologyContext"')
        conn.execute('ALTER TABLE "GeologyContext_new" RENAME TO "GeologyContext"')

    @staticmethod
    def _ensure_locations_geology_fk(conn: sqlite3.Connection) -> None:
        location_columns = [row["name"] for row in conn.execute('PRAGMA table_info("Locations")').fetchall()]
        if "geology_id" in location_columns:
            conn.execute('CREATE INDEX IF NOT EXISTS idx_locations_geology ON "Locations"(geology_id)')
            return

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS "Locations_new" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                geology_id INTEGER,
                FOREIGN KEY (geology_id) REFERENCES GeologyContext(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO "Locations_new" (
                id, name, latitude, longitude, altitude_value, altitude_unit,
                country_code, state, lga, basin, geogscale, geography_comments
            )
            SELECT
                id, name, latitude, longitude, altitude_value, altitude_unit,
                country_code, state, lga, basin, geogscale, geography_comments
            FROM "Locations"
            """
        )
        conn.execute('DROP TABLE "Locations"')
        conn.execute('ALTER TABLE "Locations_new" RENAME TO "Locations"')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_locations_geology ON "Locations"(geology_id)')

    @staticmethod
    def _link_locations_to_geology(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            UPDATE "Locations"
            SET geology_id = (
                SELECT gc.id
                FROM "GeologyContext" gc
                WHERE LOWER(TRIM(gc.location_name)) = LOWER(TRIM("Locations".name))
                LIMIT 1
            )
            WHERE name IS NOT NULL AND TRIM(name) <> ''
            """
        )
