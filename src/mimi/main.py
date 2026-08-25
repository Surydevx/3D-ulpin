from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
import uvicorn

# Relative imports for the src/mimi package structure
from .ulpin_generator import generate_3d_ulpin
from .anomaly_detector import CadastralAnomalyDetector
from .fusion_engine import calculate_fused_height
from .egc_topology import VolumetricParcel
from .database import get_db

app = FastAPI(title="3D Cadastral Compiler API", version="1.0")
detector = CadastralAnomalyDetector(tolerance_meters=0.5)

# --- Pydantic Models for API Inputs ---
class SensorData(BaseModel):
    source_name: str
    height_m: float
    weight: float

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
    return {"system": "HexCode 3D Cadastral Compiler API", "status": "Online", "docs_url": "/docs"}

# --- Endpoint 1: Validation and Database Persistence ---
@app.post("/api/v1/cadastre/validate-building")
async def validate_building(request: BuildingValidationRequest, db: Session = Depends(get_db)):
    try:
        # 1. Data Fusion
        evidence_dicts = [s.model_dump() for s in request.sensor_evidence]
        observed_h = calculate_fused_height(evidence_dicts)
        
        total_weight = sum(s.weight for s in request.sensor_evidence)
        aggregate_confidence = min(total_weight / 3.0, 0.99)
        
        # 2. ULPIN Generation
        ulpin_data = generate_3d_ulpin(
            lat=request.latitude, lon=request.longitude,
            elevation=observed_h, parent_2d_ulpin=request.parent_2d_ulpin
        )
        ulpin_id = ulpin_data["ulpin_3d"]
        
        # 3. Anomaly Detection
        validation_report = detector.evaluate_vertical_development(
            ulpin=ulpin_id, h_registered=request.registered_height_m,
            h_observed=observed_h, sensor_confidence=aggregate_confidence
        )
        
        # 4. Database Persistence (Writing to PostGIS)
        insert_query = text("""
            INSERT INTO cadastral_parcels_3d 
            (id, parent_2d_ulpin, confidence_score, topology_status) 
            VALUES (:id, :parent_id, :confidence, :status)
            ON CONFLICT (id) DO NOTHING;
        """)
        
        db.execute(insert_query, {
            "id": ulpin_id,
            "parent_id": request.parent_2d_ulpin,
            "confidence": aggregate_confidence,
            "status": validation_report["status"]
        })
        db.commit()
        
        return {
            "message": "Cadastral unit validated and saved to database.",
            "ulpin_identity": ulpin_data,
            "anomaly_report": validation_report
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
            z_max=request.existing_parcel.z_max
        )
        
        proposed = VolumetricParcel(
            parcel_id=request.proposed_infrastructure.parcel_id,
            footprint_coords=request.proposed_infrastructure.footprint_coords,
            z_min=request.proposed_infrastructure.z_min,
            z_max=request.proposed_infrastructure.z_max
        )
        
        # Execute the combinatorial topology check
        conflict_report = existing.check_spatial_conflict(proposed)
        
        return {
            "existing_parcel": existing.parcel_id,
            "proposed_infrastructure": proposed.parcel_id,
            "egc_validation": conflict_report
        }
    except BaseException as e:
        raise HTTPException(status_code=400, detail=f"Geometry parsing error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)