from unittest.mock import patch

def test_root_health(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "Online"

def test_validate_building_mocked_db(client, mock_db, valid_building_payload):
    """Tests the primary endpoint without executing real SQL insertions."""
    mock_db.execute.return_value = None 
    
    res = client.post("/api/v1/cadastre/validate-building", json=valid_building_payload)
    assert res.status_code == 200
    
    data = res.json()
    
    # Assertions updated to match your nested JSON schema
    assert "ulpin_identity" in data
    assert "ulpin_3d" in data["ulpin_identity"]
    assert "anomaly_report" in data
    assert data["anomaly_report"]["status"] in ["VALID", "ANOMALY"]
    
    # Verify the database was called exactly 3 times (1 parcel + 2 evidence records)
    assert mock_db.execute.call_count == 3

def test_get_parcels_serialization(client, mock_db):
    """Tests if the API correctly formats PostGIS data into JSON."""
    mock_db.execute.return_value.fetchall.return_value = [
        ("ID-123", "PARENT-1", 0.99, "VALID", "POLYHEDRALSURFACE Z(...)", 0, 10, 0, 10, 0, 10)
    ]
    
    res = client.get("/api/v1/cadastre/parcels")
    assert res.status_code == 200
    
    data = res.json()
    assert data["total_parcels"] == 1
    assert data["parcels"][0]["ulpin_3d"] == "ID-123"
    assert data["parcels"][0]["bounds"]["x_max"] == 10

@patch("src.mimi.main.process_drone_image_task.delay")
def test_drone_ingestion_mocked_worker(mock_celery_delay, client):
    """Ensures uploading an image triggers Celery, but intercepts the actual ML job."""
    mock_celery_delay.return_value.id = "fake-celery-task-id-999"
    
    files = {"file": ("test.jpg", b"fake_image_data", "image/jpeg")}
    res = client.post("/api/v1/cadastre/ingest-drone?ulpin_id=TEST-1", files=files)
    
    # Synced to expect your API's 200 status code
    assert res.status_code == 200
    assert res.json()["job_id"] == "fake-celery-task-id-999"
    
    mock_celery_delay.assert_called_once()