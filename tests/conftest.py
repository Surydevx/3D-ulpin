import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from src.mimi.main import app, get_db

@pytest.fixture
def mock_db():
    """Provides a mocked database session to prevent live SQL execution."""
    session = MagicMock()
    return session

@pytest.fixture
def client(mock_db):
    """Overrides the FastAPI dependency to use the mocked DB."""
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def valid_building_payload():
    return {
        "parent_2d_ulpin": "IN-DL-9999",
        "easting_x": 712000.0,
        "northing_y": 3170000.0,
        "footprint_coords": [
            [712000.0, 3170000.0], [712050.0, 3170000.0],
            [712050.0, 3170050.0], [712000.0, 3170050.0]
        ],
        "registered_height_m": 18.0,
        "sensor_evidence": [
            {"source_name": "Drone_DEM", "height_m": 18.1, "variance": 0.05},
            {"source_name": "Ground_Survey", "height_m": 18.0, "variance": 0.01}
        ]
    }

@pytest.fixture
def conflict_payload():
    return {
        "existing_parcel": {
            "parcel_id": "ULPIN-BASEMENT",
            "footprint_coords": [[0.0, 0.0], [0.0, 50.0], [50.0, 50.0], [50.0, 0.0]],
            "z_min": -20.0, "z_max": -5.0
        },
        "proposed_infrastructure": {
            "parcel_id": "ULPIN-METRO-TUNNEL",
            "footprint_coords": [[-10.0, 20.0], [60.0, 20.0], [60.0, 30.0], [-10.0, 30.0]],
            "z_min": -18.0, "z_max": -12.0
        }
    }