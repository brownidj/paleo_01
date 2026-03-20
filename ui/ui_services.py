import uuid
import sqlite3
from typing import List, Dict, Any, Optional
from database_manager import DatabaseManager
from logger import logger


class UIServiceError(Exception):
    pass


class UIService:
    """
    Handles UI side effects and state management.
    Acts as an adapter between the UI and the database.
    """
    def __init__(self, db: DatabaseManager):
        self.db = db

    def _db_call(self, op: str, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except sqlite3.Error as e:
            logger.error(f"{op} failed: {e}")
            raise UIServiceError(f"{op} failed") from e

    def get_all_missions(self) -> List[Dict[str, Any]]:
        return self._db_call("List missions", self.db.list_missions)

    def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        return self._db_call("Get mission", self.db.get_mission, mission_id)

    def create_mission(self, name: str, date: str) -> str:
        logger.info(f"Creating mission: {name}")
        data = {
            "id": str(uuid.uuid4()),
            "name": name,
            "date": date
        }
        return self._db_call("Create mission", self.db.insert_mission, data)

    def update_mission(self, mission_id: str, data: Dict[str, Any]):
        self._db_call("Update mission", self.db.update_mission, mission_id, data)

    def delete_mission(self, mission_id: str):
        logger.info(f"Deleting mission: {mission_id}")
        self._db_call("Delete mission", self.db.delete_mission, mission_id)

    def get_localities_for_mission(self, mission_id: str) -> List[Dict[str, Any]]:
        return self._db_call("List localities", self.db.list_localities_for_mission, mission_id)

    def get_locality(self, locality_id: str) -> Optional[Dict[str, Any]]:
        return self._db_call("Get locality", self.db.get_locality, locality_id)

    def create_locality(self, mission_id: str, name: str, lat: float = 0, lon: float = 0, alt: float = 0, lith: str = "", dip: float = 0, dip_dir: float = 0) -> str:
        data = {
            "id": str(uuid.uuid4()),
            "mission_id": mission_id,
            "name": name,
            "latitude": lat,
            "longitude": lon,
            "altitude": alt,
            "lithology_text": lith,
            "measured_dip": dip,
            "dip_direction": dip_dir
        }
        return self._db_call("Create locality", self.db.insert_locality, data)

    def update_locality(self, loc_id: str, data: Dict[str, Any]):
        self._db_call("Update locality", self.db.update_locality, loc_id, data)

    def delete_locality(self, loc_id: str):
        self._db_call("Delete locality", self.db.delete_locality, loc_id)

    def get_specimens_for_locality(self, loc_id: str) -> List[Dict[str, Any]]:
        return self._db_call("List specimens", self.db.list_specimens_for_locality, loc_id)

    def get_specimen(self, spec_id: str) -> Optional[Dict[str, Any]]:
        return self._db_call("Get specimen", self.db.get_specimen, spec_id)

    def create_specimen(self, loc_id: str, name: str, description: str = "", lat: float = 0, lon: float = 0, alt: float = 0) -> str:
        data = {
            "id": str(uuid.uuid4()),
            "locality_id": loc_id,
            "name": name,
            "description": description,
            "latitude": lat,
            "longitude": lon,
            "altitude": alt
        }
        return self._db_call("Create specimen", self.db.insert_specimen, data)

    def update_specimen(self, spec_id: str, data: Dict[str, Any]):
        self._db_call("Update specimen", self.db.update_specimen, spec_id, data)

    def delete_specimen(self, spec_id: str):
        self._db_call("Delete specimen", self.db.delete_specimen, spec_id)

    def get_photos(self, parent_id: str) -> List[Dict[str, Any]]:
        return self._db_call("List photos", self.db.get_photos_for_parent, parent_id)

    def add_photo(self, parent_id: str, parent_type: str, file_path: str, caption: str = ""):
        data = {
            "id": str(uuid.uuid4()),
            "parent_id": parent_id,
            "parent_type": parent_type,
            "file_path": file_path,
            "caption": caption,
            "latitude": 0,
            "longitude": 0,
            "heading": 0
        }
        self._db_call("Add photo", self.db.insert_photo, data)
