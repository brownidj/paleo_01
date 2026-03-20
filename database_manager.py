import sqlite3
from typing import List, Dict, Any, Optional
from database_schema import SCHEMA_SQL, apply_base_migrations, migrate_localities_to_initial_mission
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
        with self._get_connection() as conn:
            apply_base_migrations(conn)
            conn.executescript(SCHEMA_SQL)
            migrate_localities_to_initial_mission(conn)

    def _validate_update_fields(self, table: str, data: Dict[str, Any]):
        invalid = set(data) - self._ALLOWED_UPDATE_FIELDS[table]
        if invalid:
            raise ValueError(f"Invalid {table} update fields: {sorted(invalid)}")

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
        self._validate_update_fields("mission", data)
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
        self._validate_update_fields("locality", data)
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
        self._validate_update_fields("specimen", data)
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
        if data.get("parent_type") not in ("locality", "specimen"):
            raise ValueError("photo.parent_type must be 'locality' or 'specimen'")
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
    _ALLOWED_UPDATE_FIELDS = {
        "mission": {"name", "date"},
        "locality": {"name", "latitude", "longitude", "altitude", "lithology_text", "measured_dip", "dip_direction", "mission_id"},
        "specimen": {"name", "description", "latitude", "longitude", "altitude", "locality_id"},
    }
