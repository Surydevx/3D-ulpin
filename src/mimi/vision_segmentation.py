import os
import cv2
import numpy as np
from typing import cast  # <-- 1. Import cast
from ultralytics import YOLO
from ultralytics.engine.results import Results  # <-- 2. Import the YOLO Results type

class DroneVisionPipeline:
    def __init__(self, model_path="yolov8n-seg.pt"):
        print(f"[Vision Pipeline] Loading Neural Network: {model_path}")
        self.model = YOLO(model_path)
        
    def extract_footprint_polygon(self, image_path: str) -> dict:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Vision Pipeline: Cannot locate image at {image_path}")

        # --- THE FIX IS HERE ---
        # Run inference
        raw_predictions = self.model(image_path, verbose=False)
        
        # Convert to list (satisfies the Iterator warning) and explicitly cast it to a Results object
        results = cast(Results, list(raw_predictions)[0])
        # -----------------------
        
        # Pylance now knows 'results' is a YOLO Results object, so the errors below will vanish!
        if results.masks is None or len(results.masks) == 0:
            raise ValueError("Vision Pipeline: No valid structures detected in imagery.")
            
        polygons = results.masks.xy
        
        largest_polygon = max(
            polygons, 
            key=lambda p: cv2.contourArea(np.array(p, dtype=np.float32))
        )
        
        if len(largest_polygon) == 0:
            raise ValueError("Vision Pipeline: Mask detected, but polygon is empty.")
            
        largest_polygon_reshaped = largest_polygon.reshape(-1, 1, 2).astype(np.float32)
        
        epsilon = 0.01 * cv2.arcLength(largest_polygon_reshaped, True)
        approx_polygon = cv2.approxPolyDP(largest_polygon_reshaped, epsilon, True)
        
        footprint_coords = [
            (float(point[0][0]), float(point[0][1])) for point in approx_polygon
        ]
        
        return {
            "source_image": image_path,
            "footprint_2d_pixels": footprint_coords,
            "polygon_vertices": len(footprint_coords),
            "ml_engine": "YOLOv8-Seg + RDP Simplification"
        }