from database_manager import DatabaseManager
import uuid

def demo():
    db = DatabaseManager("demo_paleo.db")
    
    # 0. Create a Mission
    mission_id = str(uuid.uuid4())
    mission_data = {
        "id": mission_id,
        "name": "Ghost Ranch Expedition",
        "date": "2026-03-19"
    }
    db.insert_mission(mission_data)
    print(f"Inserted mission: {mission_data['name']}")

    # 1. Create a Locality
    locality_id = str(uuid.uuid4())
    locality_data = {
        "id": locality_id,
        "mission_id": mission_id,
        "name": "Ghost Ranch",
        "latitude": 36.3283,
        "longitude": -106.4691,
        "altitude": 1900.0,
        "lithology_text": "Red silty mudstone, Chinle Formation",
        "measured_dip": 5.0,
        "dip_direction": 180.0
    }
    db.insert_locality(locality_data)
    print(f"Inserted locality: {locality_data['name']}")

    # 2. Create a Specimen
    specimen_id = str(uuid.uuid4())
    specimen_data = {
        "id": specimen_id,
        "locality_id": locality_id,
        "name": "Coelophysis bauri",
        "description": "Partially articulated skeleton",
        "latitude": 36.3284,
        "longitude": -106.4692,
        "altitude": 1901.0
    }
    db.insert_specimen(specimen_data)
    print(f"Inserted specimen: {specimen_data['name']}")

    # 3. Add a Photo
    photo_id = str(uuid.uuid4())
    photo_data = {
        "id": photo_id,
        "parent_id": specimen_id,
        "parent_type": "specimen",
        "file_path": "images/coelo_01.jpg",
        "caption": "In situ view of the pelvic region",
        "latitude": 36.3284,
        "longitude": -106.4692,
        "heading": 45.0
    }
    db.insert_photo(photo_data)
    print(f"Inserted photo for specimen: {photo_data['caption']}")

    # 4. Retrieval
    loc = db.get_locality(locality_id)
    print(f"Retrieved locality: {loc['name']} with dip {loc['measured_dip']}°")

    photos = db.get_photos_for_parent(specimen_id)
    print(f"Retrieved {len(photos)} photos for specimen.")

if __name__ == "__main__":
    demo()
