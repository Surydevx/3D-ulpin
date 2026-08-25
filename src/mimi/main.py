from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import uvicorn

# Import the previously built modules
from .ulpin_generator import generate_3d_ulpin
from .anomaly_detector import CadastralAnomalyDetector
from .fusion_engine import calculate_fused_height

app = FastAPI(title="3D Cadastral Compiler API", version="1.0")
detector = CadastralAnomalyDetector(tolerance_meters=0.5)

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

@app.post("/api/v1/cadastre/validate-building")
async def validate_building(request: BuildingValidationRequest):
    try:
        # 1. Multi-Source Data Fusion
        evidence_dicts = [s.model_dump() for s in request.sensor_evidence]
        observed_h = calculate_fused_height(evidence_dicts)
        
        # Calculate a mock aggregate confidence score based on weights
        total_weight = sum(s.weight for s in request.sensor_evidence)
        aggregate_confidence = min(total_weight / 3.0, 0.99) 
        
        # 2. 3D ULPIN Generation
        ulpin_data = generate_3d_ulpin(
            lat=request.latitude,
            lon=request.longitude,
            elevation=observed_h,
            parent_2d_ulpin=request.parent_2d_ulpin
        )
        
        # 3. AI Anomaly Detection
        validation_report = detector.evaluate_vertical_development(
            ulpin=ulpin_data["ulpin_3d"],
            h_registered=request.registered_height_m,
            h_observed=observed_h,
            sensor_confidence=aggregate_confidence
        )
        
        return {
            "ulpin_identity": ulpin_data,
            "fusion_results": {
                "fused_observed_height": observed_h,
                "confidence_score": round(aggregate_confidence, 2)
            },
            "anomaly_report": validation_report
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)