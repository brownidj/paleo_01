import sqlite3
import os
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
from logger import logger

class DatabaseManager:
    """
    Manages SQLite database connections, schema creation, and CRUD operations.
    Follows standards in CURRENT_STATE.md.
    """

    def __init__(self, db_path: str = "paleo_field.db"):
        self.db_path = db_path
        logger.info(f"Initializing DatabaseManager with {db_path}")
        self._initialize_db()

    def _get_connection(self):
        """Returns a connection with foreign keys enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_db(self):
        """Initializes the database schema if it doesn't exist."""
        # 1. Run migrations first to ensure existing tables have required columns
        with self._get_connection() as conn:
            self._apply_migrations(conn)

        # 2. Define schema with IF NOT EXISTS
        schema = """
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
            parent_id TEXT NOT NULL, -- Can be locality_id or specimen_id
            parent_type TEXT NOT NULL, -- 'locality' or 'specimen'
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
        with self._get_connection() as conn:
            conn.executescript(schema)
            self._migrate_to_missions(conn)

    def _apply_migrations(self, conn):
        """Add mission_id column to locality if missing."""
        # Check if locality table exists first
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='locality'")
        if not cursor.fetchone():
            return

        cursor = conn.execute("PRAGMA table_info(locality)")
        columns = [row['name'] for row in cursor.fetchall()]
        if 'mission_id' not in columns:
            conn.execute("ALTER TABLE locality ADD COLUMN mission_id TEXT")

    def _migrate_to_missions(self, conn):
        """Migrate existing data to a dummy mission if needed."""
        # Check if we have any localities without a mission_id
        cursor = conn.execute("SELECT COUNT(*) FROM locality WHERE mission_id IS NULL")
        count = cursor.fetchone()[0]
        if count > 0:
            import uuid
            mission_id = str(uuid.uuid4())
            # Create a dummy mission
            conn.execute(
                "INSERT INTO mission (id, name, date) VALUES (?, ?, ?)",
                (mission_id, "Initial Mission", datetime.now().strftime("%Y-%m-%d"))
            )
            # Link all localities without a mission to this dummy mission
            conn.execute("UPDATE locality SET mission_id = ? WHERE mission_id IS NULL", (mission_id,))

    # Mission CRUD
    def insert_mission(self, data: Dict[str, Any]) -> str:
        logger.debug(f"Inserting mission: {data.get('name')}")
        query = """
        INSERT INTO mission (id, name, date)
        VALUES (:id, :name, :date)
        """
        with self._get_connection() as conn:
            conn.execute(query, data)
        return data['id']

    def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM mission WHERE id = ? AND is_deleted = 0"
        with self._get_connection() as conn:
            row = conn.execute(query, (mission_id,)).fetchone()
            return dict(row) if row else None

    def list_missions(self) -> List[Dict[str, Any]]:
        query = "SELECT * FROM mission WHERE is_deleted = 0 ORDER BY date DESC, created_at DESC"
        with self._get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]

    def update_mission(self, mission_id: str, data: Dict[str, Any]):
        fields = []
        values = []
        for key, value in data.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        fields.append("updated_at = datetime('now')")
        query = f"UPDATE mission SET {', '.join(fields)} WHERE id = ?"
        values.append(mission_id)
        
        with self._get_connection() as conn:
            conn.execute(query, tuple(values))

    def delete_mission(self, mission_id: str):
        """Soft delete mission."""
        query = "UPDATE mission SET is_deleted = 1, updated_at = datetime('now') WHERE id = ?"
        with self._get_connection() as conn:
            conn.execute(query, (mission_id,))

    # Locality CRUD
    def insert_locality(self, data: Dict[str, Any]) -> str:
        logger.debug(f"Inserting locality: {data.get('name')}")
        query = """
        INSERT INTO locality (id, mission_id, name, latitude, longitude, altitude, lithology_text, measured_dip, dip_direction)
        VALUES (:id, :mission_id, :name, :latitude, :longitude, :altitude, :lithology_text, :measured_dip, :dip_direction)
        """
        with self._get_connection() as conn:
            conn.execute(query, data)
        return data['id']

    def list_localities_for_mission(self, mission_id: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM locality WHERE mission_id = ? AND is_deleted = 0 ORDER BY created_at DESC"
        with self._get_connection() as conn:
            rows = conn.execute(query, (mission_id,)).fetchall()
            return [dict(row) for row in rows]

    def get_locality(self, locality_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM locality WHERE id = ? AND is_deleted = 0"
        with self._get_connection() as conn:
            row = conn.execute(query, (locality_id,)).fetchone()
            return dict(row) if row else None

    def list_localities(self) -> List[Dict[str, Any]]:
        query = "SELECT * FROM locality WHERE is_deleted = 0 ORDER BY created_at DESC"
        with self._get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]

    def update_locality(self, locality_id: str, data: Dict[str, Any]):
        fields = []
        values = []
        for key, value in data.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        fields.append("updated_at = datetime('now')")
        query = f"UPDATE locality SET {', '.join(fields)} WHERE id = ?"
        values.append(locality_id)
        
        with self._get_connection() as conn:
            conn.execute(query, tuple(values))

    def delete_locality(self, locality_id: str):
        """Soft delete locality."""
        query = "UPDATE locality SET is_deleted = 1, updated_at = datetime('now') WHERE id = ?"
        with self._get_connection() as conn:
            conn.execute(query, (locality_id,))

    # Specimen CRUD
    def insert_specimen(self, data: Dict[str, Any]) -> str:
        query = """
        INSERT INTO specimen (id, locality_id, name, description, latitude, longitude, altitude)
        VALUES (:id, :locality_id, :name, :description, :latitude, :longitude, :altitude)
        """
        with self._get_connection() as conn:
            conn.execute(query, data)
        return data['id']

    def get_specimen(self, specimen_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM specimen WHERE id = ? AND is_deleted = 0"
        with self._get_connection() as conn:
            row = conn.execute(query, (specimen_id,)).fetchone()
            return dict(row) if row else None

    def list_specimens_for_locality(self, locality_id: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM specimen WHERE locality_id = ? AND is_deleted = 0 ORDER BY created_at DESC"
        with self._get_connection() as conn:
            rows = conn.execute(query, (locality_id,)).fetchall()
            return [dict(row) for row in rows]

    def update_specimen(self, specimen_id: str, data: Dict[str, Any]):
        fields = []
        values = []
        for key, value in data.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        fields.append("updated_at = datetime('now')")
        query = f"UPDATE specimen SET {', '.join(fields)} WHERE id = ?"
        values.append(specimen_id)
        
        with self._get_connection() as conn:
            conn.execute(query, tuple(values))

    def delete_specimen(self, specimen_id: str):
        """Soft delete specimen."""
        query = "UPDATE specimen SET is_deleted = 1, updated_at = datetime('now') WHERE id = ?"
        with self._get_connection() as conn:
            conn.execute(query, (specimen_id,))

    # Photo CRUD
    def insert_photo(self, data: Dict[str, Any]) -> str:
        query = """
        INSERT INTO photo (id, parent_id, parent_type, file_path, caption, latitude, longitude, heading)
        VALUES (:id, :parent_id, :parent_type, :file_path, :caption, :latitude, :longitude, :heading)
        """
        with self._get_connection() as conn:
            conn.execute(query, data)
        return data['id']

    def get_photos_for_parent(self, parent_id: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM photo WHERE parent_id = ? AND is_deleted = 0 ORDER BY created_at DESC"
        with self._get_connection() as conn:
            rows = conn.execute(query, (parent_id,)).fetchall()
            return [dict(row) for row in rows]

    def delete_photo(self, photo_id: str):
        """Soft delete photo."""
        query = "UPDATE photo SET is_deleted = 1 WHERE id = ?"
        with self._get_connection() as conn:
            conn.execute(query, (photo_id,))
