import os
import cv2
import numpy as np
from typing import cast, Tuple, Optional, Dict, Any, List
from ultralytics import YOLO
from ultralytics.engine.results import Results

class DroneVisionPipeline:
    def __init__(self, model_path: str = "yolov8n-seg.pt") -> None:
        print(f"[Vision Pipeline] Loading Neural Network: {model_path}")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Vision Pipeline: Model weights not found at {model_path}")
        self.model = YOLO(model_path)
        
    def _pixel_to_geo(self, px: float, py: float, geo_bounds: Dict[str, float]) -> Tuple[float, float]:
        """
        Translates raw image pixels into EPSG:32643 geographic meters using an Affine Transform.
        """
        gsd_x: float = geo_bounds.get("gsd_x", 0.05)
        gsd_y: float = geo_bounds.get("gsd_y", 0.05)
        top_left_x: float = geo_bounds.get("top_left_x", 0.0)
        top_left_y: float = geo_bounds.get("top_left_y", 0.0)
        
        geo_x = top_left_x + (px * gsd_x)
        geo_y = top_left_y - (py * gsd_y)
        
        return round(geo_x, 3), round(geo_y, 3)

    def extract_footprint_polygon(
        self, 
        image_path: str, 
        geo_bounds: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Extracts structural segmentation masks, simplifies them via RDP, 
        and optionally projects them into real-world meter coordinates.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Vision Pipeline: Cannot locate image at {image_path}")

        raw_predictions = self.model(image_path, verbose=False)
        results = cast(Results, list(raw_predictions)[0])
        
        if results.masks is None or len(results.masks) == 0:
            raise ValueError("Vision Pipeline: No valid structures detected in imagery.")
            
        polygons = results.masks.xy
        
        def safe_contour_area(p: np.ndarray) -> float:
            reshaped = np.array(p, dtype=np.float32).reshape(-1, 1, 2)
            return float(cv2.contourArea(reshaped))
            
        largest_polygon = max(polygons, key=safe_contour_area)
        
        if len(largest_polygon) == 0:
            raise ValueError("Vision Pipeline: Mask detected, but polygon is empty.")
            
        largest_polygon_reshaped = np.array(largest_polygon, dtype=np.float32).reshape(-1, 1, 2)
        
        epsilon = 0.01 * cv2.arcLength(largest_polygon_reshaped, True)
        approx_polygon = cv2.approxPolyDP(largest_polygon_reshaped, epsilon, True)
        
        footprint_coords: List[Tuple[float, float]] = []
        for point in approx_polygon:
            px, py = float(point[0][0]), float(point[0][1])
            
            if geo_bounds is not None:
                geo_x, geo_y = self._pixel_to_geo(px, py, geo_bounds)
                footprint_coords.append((geo_x, geo_y))
            else:
                footprint_coords.append((px, py))
        
        return {
            "source_image": image_path,
            "footprint_geometry": footprint_coords,
            "polygon_vertices": len(footprint_coords),
            "is_georeferenced": geo_bounds is not None,
            "ml_engine": "YOLOv8-Seg + RDP Simplification"
        }