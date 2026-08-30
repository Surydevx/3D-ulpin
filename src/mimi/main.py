import os
import math
import shutil
import uuid
from typing import List, Tuple

from celery.result import AsyncResult
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
import uvicorn

# Relative imports within the src/mimi package structure
from .anomaly_detector import MLCadastralAnomalyDetector
from .database import get_db
from .egc_topology import VolumetricParcel
from .fusion_engine import calculate_bayesian_fusion
from .ulpin_generator import generate_3d_ulpin

# Import Celery app and tasks from your worker module
from .worker import celery_app, process_drone_image_task, process_lidar_cloud_task

# --- Shared Configuration for Distributed Workers ---
# We define a specific directory that MUST be mounted as a shared volume 
# between your FastAPI container and your Celery worker container.
SHARED_UPLOAD_DIR = "/tmp/mimi_uploads"
os.makedirs(SHARED_UPLOAD_DIR, exist_ok=True)

# --- Application & Service Initialization ---
app = FastAPI(title="3D Cadastral Compiler API", version="1.0")

# --- Enable CORS for Web Frontend ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)

# Initialize the Isolation Forest Machine Learning model
detector = MLCadastralAnomalyDetector()

# --- Pydantic Models for API Inputs ---
class SensorData(BaseModel):
    source_name: str
    height_m: float
    variance: float


class BuildingValidationRequest(BaseModel):
    parent_2d_ulpin: str
    easting_x: float          # Updated from latitude
    northing_y: float         # Updated from longitude
    footprint_coords: List[Tuple[float, float]]  # REQUIRED to build the 3D shape in PostGIS
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
def root():
    return {
        "system": "HexCode 3D Cadastral Compiler API",
        "status": "Online",
        "docs_url": "/docs",
    }


# --- Endpoint 1: Validation and Database Persistence ---
@app.post("/api/v1/cadastre/validate-building")
def validate_building(
    request: BuildingValidationRequest, db: Session = Depends(get_db)
):
    try:
        # 1. Execute Bayesian Sensor Fusion
        evidence_dicts = [s.model_dump() for s in request.sensor_evidence]
        observed_h, uncertainty = calculate_bayesian_fusion(evidence_dicts)
        aggregate_confidence = min(max(0.0, 1.0 - uncertainty), 0.99)

        # 2. Generate 3D Morton Code Identity
        ulpin_data = generate_3d_ulpin(
            easting_x=request.easting_x,     # Updated parameters
            northing_y=request.northing_y,
            elevation_z=observed_h,
            parent_2d_ulpin=request.parent_2d_ulpin,
        )
        ulpin_id = ulpin_data["ulpin_3d"]

        # 3. ML Anomaly Detection (Isolation Forest)
        validation_report = detector.evaluate_vertical_development(
            ulpin=ulpin_id,
            h_registered=request.registered_height_m,
            h_observed=observed_h,
            sensor_confidence=aggregate_confidence,
        )

        # 4. Construct the WKT (Well-Known Text) Polygon for PostGIS
        # Closes the loop by ensuring the last point matches the first point
        coords = request.footprint_coords
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        polygon_wkt = "POLYGON((" + ", ".join([f"{x} {y}" for x, y in coords]) + "))"

        # 5. PRIMARY INSERT: Save core cadastral parcel WITH Geometry
        insert_parcel_query = text("""
            INSERT INTO cadastral_parcels_3d 
            (id, parent_2d_ulpin, confidence_score, topology_status, geometry_3d) 
            VALUES (
                :id, :parent_id, :confidence, :status,
                -- Use standard SQL CAST to avoid SQLAlchemy colon parsing errors
                ST_Extrude(ST_GeomFromText(:poly_wkt, 32643), 0.0, 0.0, CAST(:height AS float8))
            )
            ON CONFLICT (id) DO NOTHING;
        """)

        db.execute(
            insert_parcel_query,
            {
                "id": ulpin_id,
                "parent_id": request.parent_2d_ulpin,
                "confidence": aggregate_confidence,
                "status": validation_report["status"],
                "poly_wkt": polygon_wkt,
                "height": observed_h
            },
        )

        # 6. SECONDARY INSERT: Build the Evidence Graph
        insert_evidence_query = text("""
            INSERT INTO evidence_graph 
            (parcel_id, source_type, vertical_accuracy_cm, reliability_weight) 
            VALUES (:parcel_id, :source_type, :accuracy_cm, :weight);
        """)

        for sensor in request.sensor_evidence:
            # Convert variance (m^2) to std deviation in cm
            std_dev_m = math.sqrt(sensor.variance)
            accuracy_cm = std_dev_m * 100
            
            # Inverse variance weighting
            weight = 1.0 / sensor.variance if sensor.variance > 0 else 999.9

            db.execute(
                insert_evidence_query,
                {
                    "parcel_id": ulpin_id,
                    "source_type": sensor.source_name,
                    "accuracy_cm": accuracy_cm,
                    "weight": weight
                }
            )

        # 7. COMMIT TRANSACTION: Lock both tables simultaneously
        db.commit()

        return {
            "message": "Cadastral unit and evidence graph validated and saved.",
            "ulpin_identity": ulpin_data,
            "anomaly_report": validation_report,
            "evidence_records_created": len(request.sensor_evidence)
        }

    except Exception as e:
        # If any part of the math or insertion fails, rollback the entire transaction
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# --- Endpoint 2: Exact Geometric Computation (EGC) ---
@app.post("/api/v1/cadastre/check-conflict")
def check_underground_conflict(request: ConflictCheckRequest):
    try:
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


# --- Endpoint 3: LiDAR Ingestion (Asynchronous) ---
@app.post("/api/v1/cadastre/ingest-lidar")
def ingest_lidar_point_cloud(ulpin_id: str, file: UploadFile = File(...)):
    """Accepts LiDAR data, saves it to a shared volume, and queues it for Celery."""
    temp_file_path = os.path.join(SHARED_UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")
    
    try:
        # 1. Save the file rapidly to the shared disk
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Fire-and-forget: Push the job to the Redis queue
        job = process_lidar_cloud_task.delay(temp_file_path, ulpin_id)
        
        return {
            "ulpin_id": ulpin_id,
            "message": "Point cloud queued for RANSAC/DBSCAN spatial processing.",
            "job_id": job.id,
            "status_endpoint": f"/api/v1/cadastre/job-status/{job.id}"
        }
    except Exception as e:
        # If writing the file fails, cleanup and return error
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=str(e))


# --- Endpoint 4: Database Conflict ---
@app.get("/api/v1/cadastre/db-conflict/{ulpin_1}/{ulpin_2}")
def check_database_conflict(ulpin_1: str, ulpin_2: str, db: Session = Depends(get_db)):
    """Offloads 3D topological intersection checks directly to PostGIS."""
    try:
        query = text("""
            SELECT ST_3DIntersects(
                (SELECT geometry_3d FROM cadastral_parcels_3d WHERE id = :id1),
                (SELECT geometry_3d FROM cadastral_parcels_3d WHERE id = :id2)
            ) as is_conflict;
        """)
        
        result = db.execute(query, {"id1": ulpin_1, "id2": ulpin_2}).fetchone()
        
        if result is None or result[0] is None:
            raise HTTPException(status_code=404, detail="One or both ULPINs not found in database.")
            
        return {
            "ulpin_1": ulpin_1,
            "ulpin_2": ulpin_2,
            "spatial_conflict_detected": result[0],
            "computation_engine": "PostGIS Native"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Endpoint 5: Drone Imagery (Asynchronous) ---
@app.post("/api/v1/cadastre/ingest-drone")
def ingest_drone_imagery(ulpin_id: str, file: UploadFile = File(...)):
    """Accepts drone imagery, saves it to a shared volume, and queues it for YOLO inference."""
    temp_file_path = os.path.join(SHARED_UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Push the job to the Redis queue
        job = process_drone_image_task.delay(temp_file_path, ulpin_id)
        
        return {
            "ulpin_id": ulpin_id,
            "message": "Drone imagery queued for YOLOv8 neural inference.",
            "job_id": job.id,
            "status_endpoint": f"/api/v1/cadastre/job-status/{job.id}"
        }
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=str(e))


# --- Endpoint 6: Job Polling ---
@app.get("/api/v1/cadastre/job-status/{job_id}")
def get_job_status(job_id: str):
    """Allows clients to poll the Redis backend for ML job completion."""
    job_result = AsyncResult(job_id, app=celery_app)
    
    if job_result.state == "PENDING":
        return {"job_id": job_id, "status": "PENDING (In Queue)"}
    elif job_result.state == "SUCCESS":
        return {"job_id": job_id, "status": "COMPLETED", "result": job_result.result}
    elif job_result.state == "FAILURE":
        return {"job_id": job_id, "status": "FAILED", "error": str(job_result.info)}
    else:
        return {"job_id": job_id, "status": job_result.state}


# --- Endpoint 7: Retrieve All 3D Parcels for Visualization ---
@app.get("/api/v1/cadastre/parcels")
def get_all_parcels(db: Session = Depends(get_db)):
    """
    Pulls all 3D cadastral parcels from PostGIS, converting 
    polyhedral geometries into WKT and bounding boxes.
    """
    try:
        query = text("""
            SELECT 
                id, 
                parent_2d_ulpin, 
                confidence_score, 
                topology_status, 
                ST_AsText(geometry_3d) as geometry_wkt,
                ST_XMin(geometry_3d) as x_min, ST_XMax(geometry_3d) as x_max, 
                ST_YMin(geometry_3d) as y_min, ST_YMax(geometry_3d) as y_max, 
                ST_ZMin(geometry_3d) as z_min, ST_ZMax(geometry_3d) as z_max
            FROM cadastral_parcels_3d;
        """)
        
        result = db.execute(query).fetchall()
        
        parcels = []
        for row in result:
            parcels.append({
                "ulpin_3d": row[0],
                "parent_2d_ulpin": row[1],
                "confidence_score": row[2],
                "topology_status": row[3],
                "geometry_wkt": row[4],
                "bounds": {
                    "x_min": row[5], "x_max": row[6],
                    "y_min": row[7], "y_max": row[8],
                    "z_min": row[9], "z_max": row[10]
                }
            })
            
        return {
            "total_parcels": len(parcels),
            "parcels": parcels
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)