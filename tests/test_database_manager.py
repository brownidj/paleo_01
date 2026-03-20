import unittest
import os
import uuid
import sqlite3
from database_manager import DatabaseManager

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        # Use a temporary file for testing to avoid in-memory URI issues with executescript
        self.db_path = f"test_{uuid.uuid4()}.db"
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        # Cleanup temporary database file
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_database_initialization(self):
        """Verify that all required tables and indexes are created."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            self.assertIn("mission", tables)
            self.assertIn("locality", tables)
            self.assertIn("specimen", tables)
            self.assertIn("photo", tables)

    def test_mission_crud(self):
        """Test inserting, retrieving, and listing missions."""
        mission_id = str(uuid.uuid4())
        data = {
            "id": mission_id,
            "name": "Expedition 2026",
            "date": "2026-03-19"
        }
        self.db.insert_mission(data)

        retrieved = self.db.get_mission(mission_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["name"], "Expedition 2026")

        all_missions = self.db.list_missions()
        self.assertTrue(any(m["id"] == mission_id for m in all_missions))

    def test_locality_crud(self):
        """Test inserting, retrieving, and listing localities."""
        mission_id = str(uuid.uuid4())
        self.db.insert_mission({"id": mission_id, "name": "M", "date": "2026-01-01"})
        
        locality_id = str(uuid.uuid4())
        data = {
            "id": locality_id,
            "mission_id": mission_id,
            "name": "Test Site A",
            "latitude": 10.0,
            "longitude": 20.0,
            "altitude": 100.0,
            "lithology_text": "Sandstone",
            "measured_dip": 15.0,
            "dip_direction": 90.0
        }
        self.db.insert_locality(data)

        # Get specific
        retrieved = self.db.get_locality(locality_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["name"], "Test Site A")
        self.assertEqual(retrieved["mission_id"], mission_id)

        # List for mission
        locs = self.db.list_localities_for_mission(mission_id)
        self.assertEqual(len(locs), 1)
        self.assertEqual(locs[0]["id"], locality_id)

    def test_specimen_crud(self):
        """Test specimen insertion and foreign key relationship."""
        # 0. Mission
        mission_id = str(uuid.uuid4())
        self.db.insert_mission({"id": mission_id, "name": "M", "date": "2026-01-01"})
        
        # 1. Create a Locality first
        loc_id = str(uuid.uuid4())
        self.db.insert_locality({
            "id": loc_id, "mission_id": mission_id, "name": "Parent Locality", "latitude": 0, "longitude": 0,
            "altitude": 0, "lithology_text": "N/A", "measured_dip": 0, "dip_direction": 0
        })

        # 2. Insert Specimen
        spec_id = str(uuid.uuid4())
        spec_data = {
            "id": spec_id,
            "locality_id": loc_id,
            "name": "Fossil 01",
            "description": "Interesting tooth",
            "latitude": 0.1,
            "longitude": 0.1,
            "altitude": 5.0
        }
        self.db.insert_specimen(spec_data)

        retrieved = self.db.get_specimen(spec_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["name"], "Fossil 01")
        self.assertEqual(retrieved["locality_id"], loc_id)

    def test_foreign_key_constraint(self):
        """Verify that inserting a specimen for a non-existent locality fails."""
        spec_data = {
            "id": str(uuid.uuid4()),
            "locality_id": "non_existent_id",
            "name": "Orphaned Specimen",
            "description": "Should fail",
            "latitude": 0, "longitude": 0, "altitude": 0
        }
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.insert_specimen(spec_data)

    def test_photo_crud(self):
        """Test photo attachment to both locality and specimen."""
        mission_id = str(uuid.uuid4())
        self.db.insert_mission({"id": mission_id, "name": "M", "date": "2026-01-01"})
        
        loc_id = str(uuid.uuid4())
        self.db.insert_locality({"id": loc_id, "mission_id": mission_id, "name": "L", "latitude": 0, "longitude": 0, "altitude": 0, "lithology_text": "", "measured_dip": 0, "dip_direction": 0})
        
        photo_id = str(uuid.uuid4())
        photo_data = {
            "id": photo_id,
            "parent_id": loc_id,
            "parent_type": "locality",
            "file_path": "/tmp/test.jpg",
            "caption": "Test Photo",
            "latitude": 1.1,
            "longitude": 2.2,
            "heading": 180.0
        }
        self.db.insert_photo(photo_data)
        
        photos = self.db.get_photos_for_parent(loc_id)
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0]["caption"], "Test Photo")

    def test_soft_delete(self):
        """Verify that retrieval methods ignore records where is_deleted = 1."""
        mission_id = str(uuid.uuid4())
        self.db.insert_mission({"id": mission_id, "name": "M", "date": "2026-01-01"})
        
        loc_id = str(uuid.uuid4())
        self.db.insert_locality({"id": loc_id, "mission_id": mission_id, "name": "Delete Me", "latitude": 0, "longitude": 0, "altitude": 0, "lithology_text": "", "measured_dip": 0, "dip_direction": 0})
        
        # Manually set is_deleted = 1
        with self.db._get_connection() as conn:
            conn.execute("UPDATE locality SET is_deleted = 1 WHERE id = ?", (loc_id,))
        
        # Test get_locality
        retrieved = self.db.get_locality(loc_id)
        self.assertIsNone(retrieved, "Soft-deleted locality should not be returned by get_locality.")
        
        # Test list_localities_for_mission
        all_locs = self.db.list_localities_for_mission(mission_id)
        self.assertEqual(len(all_locs), 0, "Soft-deleted locality should not be returned.")

    def test_update_locality(self):
        """Test updating locality fields."""
        mission_id = str(uuid.uuid4())
        self.db.insert_mission({"id": mission_id, "name": "M", "date": "2026-01-01"})
        
        loc_id = str(uuid.uuid4())
        self.db.insert_locality({
            "id": loc_id, "mission_id": mission_id, "name": "Old Name", "latitude": 0, "longitude": 0,
            "altitude": 0, "lithology_text": "Old Lith", "measured_dip": 0, "dip_direction": 0
        })
        
        self.db.update_locality(loc_id, {"name": "New Name", "lithology_text": "New Lith"})
        
        retrieved = self.db.get_locality(loc_id)
        self.assertEqual(retrieved["name"], "New Name")
        self.assertEqual(retrieved["lithology_text"], "New Lith")
        self.assertIsNotNone(retrieved["updated_at"])

    def test_specimen_list_and_update(self):
        """Test listing specimens for a locality and updating a specimen."""
        mission_id = str(uuid.uuid4())
        self.db.insert_mission({"id": mission_id, "name": "M", "date": "2026-01-01"})
        
        loc_id = str(uuid.uuid4())
        self.db.insert_locality({
            "id": loc_id, "mission_id": mission_id, "name": "L", "latitude": 0, "longitude": 0,
            "altitude": 0, "lithology_text": "", "measured_dip": 0, "dip_direction": 0
        })
        
        spec_id = str(uuid.uuid4())
        self.db.insert_specimen({
            "id": spec_id, "locality_id": loc_id, "name": "S1", "description": "D1",
            "latitude": 0, "longitude": 0, "altitude": 0
        })
        
        specs = self.db.list_specimens_for_locality(loc_id)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["id"], spec_id)
        
        self.db.update_specimen(spec_id, {"name": "S1 Updated"})
        retrieved = self.db.get_specimen(spec_id)
        self.assertEqual(retrieved["name"], "S1 Updated")

    def test_delete_specimen(self):
        """Test soft delete for specimen."""
        mission_id = str(uuid.uuid4())
        self.db.insert_mission({"id": mission_id, "name": "M", "date": "2026-01-01"})
        
        loc_id = str(uuid.uuid4())
        self.db.insert_locality({"id": loc_id, "mission_id": mission_id, "name": "L", "latitude": 0, "longitude": 0, "altitude": 0, "lithology_text": "", "measured_dip": 0, "dip_direction": 0})
        spec_id = str(uuid.uuid4())
        self.db.insert_specimen({"id": spec_id, "locality_id": loc_id, "name": "S", "description": "", "latitude": 0, "longitude": 0, "altitude": 0})
        
        self.db.delete_specimen(spec_id)
        self.assertIsNone(self.db.get_specimen(spec_id))
        self.assertEqual(len(self.db.list_specimens_for_locality(loc_id)), 0)

    def test_update_locality_rejects_invalid_field(self):
        mission_id = str(uuid.uuid4())
        self.db.insert_mission({"id": mission_id, "name": "M", "date": "2026-01-01"})
        loc_id = str(uuid.uuid4())
        self.db.insert_locality({
            "id": loc_id, "mission_id": mission_id, "name": "L", "latitude": 0, "longitude": 0,
            "altitude": 0, "lithology_text": "", "measured_dip": 0, "dip_direction": 0
        })
        with self.assertRaises(ValueError):
            self.db.update_locality(loc_id, {"is_deleted": 1})

    def test_insert_photo_rejects_invalid_parent_type(self):
        with self.assertRaises(ValueError):
            self.db.insert_photo({
                "id": str(uuid.uuid4()),
                "parent_id": "x",
                "parent_type": "mission",
                "file_path": "/tmp/test.jpg",
                "caption": "bad",
                "latitude": 0,
                "longitude": 0,
                "heading": 0,
            })

if __name__ == "__main__":
    unittest.main()
