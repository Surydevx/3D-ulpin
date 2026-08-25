import os
import shutil
from typing import List, Tuple

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
import uvicorn

# Relative imports within the src/mimi package structure
from .anomaly_detector import CadastralAnomalyDetector
from .database import get_db
from .egc_topology import VolumetricParcel
from .fusion_engine import calculate_bayesian_fusion
from .lidar_parser import extract_building_geometry
from .spatial_octree import BoundingBox, OctreeNode
from .ulpin_generator import generate_3d_ulpin

# --- Application & Service Initialization ---
app = FastAPI(title="3D Cadastral Compiler API", version="1.0")
detector = CadastralAnomalyDetector(tolerance_meters=0.5)

# Initialize the global in-memory Octree (Covering a massive coordinate grid)
global_boundary = BoundingBox(0, 10000, 0, 10000, -500, 5000)
cadastral_octree = OctreeNode(global_boundary, capacity=10)


# --- Pydantic Models for API Inputs ---
class SensorData(BaseModel):
    source_name: str
    height_m: float
    variance: float


class BuildingValidationRequest(BaseModel):
    parent_2d_ulpin: str
    latitude: float
    longitude: float
    registered_height_m: float
    sensor_evidence: List[SensorData]


class ParcelCoordinates(BaseModel):
    parcel_id: str
    footprint_coords: List[Tuple[float, float]]
    z_min: float
    z_max: float


class ConflictCheckRequest(BaseModel):
    existing_parcel: ParcelCoordinates
    proposed_infrastructure: ParcelCoordinates


# --- Root Route ---
@app.get("/")
async def root():
    return {
        "system": "HexCode 3D Cadastral Compiler API",
        "status": "Online",
        "docs_url": "/docs",
    }


# --- Endpoint 1: Validation and Database Persistence ---
@app.post("/api/v1/cadastre/validate-building")
async def validate_building(
    request: BuildingValidationRequest, db: Session = Depends(get_db)
):
    try:
        # 1. Data Fusion (Bayesian)
        evidence_dicts = [s.model_dump() for s in request.sensor_evidence]

        # Unpack the tuple: fused height (mu) and uncertainty (sigma)
        observed_h, uncertainty = calculate_bayesian_fusion(evidence_dicts)

        # Derive confidence from statistical uncertainty (max 99% confidence)
        aggregate_confidence = min(max(0.0, 1.0 - uncertainty), 0.99)

        # 2. ULPIN Generation
        ulpin_data = generate_3d_ulpin(
            lat=request.latitude,
            lon=request.longitude,
            elevation=observed_h,
            parent_2d_ulpin=request.parent_2d_ulpin,
        )
        ulpin_id = ulpin_data["ulpin_3d"]

        # 3. Anomaly Detection
        validation_report = detector.evaluate_vertical_development(
            ulpin=ulpin_id,
            h_registered=request.registered_height_m,
            h_observed=observed_h,
            sensor_confidence=aggregate_confidence,
        )

        # 4. Database Persistence (Writing to PostGIS)
        insert_query = text("""
            INSERT INTO cadastral_parcels_3d 
            (id, parent_2d_ulpin, confidence_score, topology_status) 
            VALUES (:id, :parent_id, :confidence, :status)
            ON CONFLICT (id) DO NOTHING;
        """)

        db.execute(
            insert_query,
            {
                "id": ulpin_id,
                "parent_id": request.parent_2d_ulpin,
                "confidence": aggregate_confidence,
                "status": validation_report["status"],
            },
        )
        db.commit()

        return {
            "message": "Cadastral unit validated and saved to database.",
            "ulpin_identity": ulpin_data,
            "anomaly_report": validation_report,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# --- Endpoint 2: Exact Geometric Computation (EGC) ---
@app.post("/api/v1/cadastre/check-conflict")
async def check_underground_conflict(request: ConflictCheckRequest):
    try:
        # Reconstruct the 3D parcels from the incoming JSON
        existing = VolumetricParcel(
            parcel_id=request.existing_parcel.parcel_id,
            footprint_coords=request.existing_parcel.footprint_coords,
            z_min=request.existing_parcel.z_min,
            z_max=request.existing_parcel.z_max,
        )

        proposed = VolumetricParcel(
            parcel_id=request.proposed_infrastructure.parcel_id,
            footprint_coords=request.proposed_infrastructure.footprint_coords,
            z_min=request.proposed_infrastructure.z_min,
            z_max=request.proposed_infrastructure.z_max,
        )

        # Execute the combinatorial topology check
        conflict_report = existing.check_spatial_conflict(proposed)

        return {
            "existing_parcel": existing.parcel_id,
            "proposed_infrastructure": proposed.parcel_id,
            "egc_validation": conflict_report,
        }
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Geometry parsing error: {str(e)}"
        )


# --- Endpoint 3: LiDAR Ingestion & Spatial Indexing ---
@app.post("/api/v1/cadastre/ingest-lidar")
async def ingest_lidar_point_cloud(
    ulpin_id: str, file: UploadFile = File(...)
):
    try:
        # 1. Save the uploaded file temporarily
        temp_file_path = f"temp_{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Extract Exact Geometric Boundaries using Open3D
        geometry_bounds = extract_building_geometry(temp_file_path)

        # 3. Create a BoundingBox and insert it into the combinatorial Octree
        parcel_box = BoundingBox(
            geometry_bounds["x_min"],
            geometry_bounds["x_max"],
            geometry_bounds["y_min"],
            geometry_bounds["y_max"],
            geometry_bounds["z_min"],
            geometry_bounds["z_max"],
        )

        inserted = cadastral_octree.insert(ulpin_id, parcel_box)

        # Cleanup temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        return {
            "ulpin_id": ulpin_id,
            "status": "INDEXED_IN_OCTREE" if inserted else "OUT_OF_BOUNDS",
            "extracted_geometry": geometry_bounds,
            "computational_complexity": "O(log n) Ready",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)