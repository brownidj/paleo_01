import uuid
from datetime import datetime


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mission (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    is_deleted INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS locality (
    id TEXT PRIMARY KEY,
    mission_id TEXT,
    name TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    altitude REAL,
    lithology_text TEXT,
    measured_dip REAL,
    dip_direction REAL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    is_deleted INTEGER DEFAULT 0,
    FOREIGN KEY (mission_id) REFERENCES mission(id)
);

CREATE TABLE IF NOT EXISTS specimen (
    id TEXT PRIMARY KEY,
    locality_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    latitude REAL,
    longitude REAL,
    altitude REAL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    is_deleted INTEGER DEFAULT 0,
    FOREIGN KEY (locality_id) REFERENCES locality(id)
);

CREATE TABLE IF NOT EXISTS photo (
    id TEXT PRIMARY KEY,
    parent_id TEXT NOT NULL,
    parent_type TEXT NOT NULL CHECK(parent_type IN ('locality', 'specimen')),
    file_path TEXT NOT NULL,
    caption TEXT,
    latitude REAL,
    longitude REAL,
    heading REAL,
    created_at TEXT DEFAULT (datetime('now')),
    is_deleted INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_locality_mission ON locality(mission_id);
CREATE INDEX IF NOT EXISTS idx_specimen_locality ON specimen(locality_id);
CREATE INDEX IF NOT EXISTS idx_photo_parent ON photo(parent_id, parent_type);
"""


def apply_base_migrations(conn):
    """Apply non-destructive schema migrations for existing databases."""
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='locality'")
    if cursor.fetchone():
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(locality)").fetchall()]
        if "mission_id" not in columns:
            conn.execute("ALTER TABLE locality ADD COLUMN mission_id TEXT")

    sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='photo'"
    ).fetchone()
    if sql_row and "CHECK(parent_type IN ('locality', 'specimen'))" not in sql_row[0]:
        conn.execute("ALTER TABLE photo RENAME TO photo_old")
        conn.executescript("""
            CREATE TABLE photo (
                id TEXT PRIMARY KEY,
                parent_id TEXT NOT NULL,
                parent_type TEXT NOT NULL CHECK(parent_type IN ('locality', 'specimen')),
                file_path TEXT NOT NULL,
                caption TEXT,
                latitude REAL,
                longitude REAL,
                heading REAL,
                created_at TEXT DEFAULT (datetime('now')),
                is_deleted INTEGER DEFAULT 0
            );
            INSERT INTO photo (id, parent_id, parent_type, file_path, caption, latitude, longitude, heading, created_at, is_deleted)
            SELECT id, parent_id, parent_type, file_path, caption, latitude, longitude, heading, created_at, is_deleted
            FROM photo
            WHERE parent_type IN ('locality', 'specimen');
            DROP TABLE photo;
            CREATE INDEX IF NOT EXISTS idx_photo_parent ON photo(parent_id, parent_type);
        """)


def migrate_localities_to_initial_mission(conn):
    """Ensure legacy localities without mission_id are attached to an initial mission."""
    count = conn.execute("SELECT COUNT(*) FROM locality WHERE mission_id IS NULL").fetchone()[0]
    if count <= 0:
        return
    mission_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO mission (id, name, date) VALUES (?, ?, ?)",
        (mission_id, "Initial Mission", datetime.now().strftime("%Y-%m-%d")),
    )
    conn.execute("UPDATE locality SET mission_id = ? WHERE mission_id IS NULL", (mission_id,))
