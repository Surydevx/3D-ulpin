import os
from celery import Celery
from .vision_segmentation import DroneVisionPipeline
from .lidar_parser import extract_building_geometry

# Initialize Celery and connect it to your local Redis server
celery_app = Celery(
    "mimi_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

# Global variables for ML models (Lazy Loading)
vision_pipeline = None

@celery_app.task(name="process_drone_image")
def process_drone_image_task(image_path: str, ulpin_id: str):
    """Background task to run YOLOv8 Vision Segmentation."""
    global vision_pipeline
    
    # Lazy load the ML model only when the worker boots up
    if vision_pipeline is None:
        vision_pipeline = DroneVisionPipeline()
        
    try:
        # 1. Run the heavy neural network processing
        footprint_data = vision_pipeline.extract_footprint_polygon(image_path)
        
        # 2. Return the data to the Redis backend
        # In a full pipeline, you would also trigger a DB update here.
        return {"ulpin_id": ulpin_id, "polygon_data": footprint_data}
        
    except Exception as e:
        return {"error": str(e)}
        
    finally:
        # 3. Clean up the system memory ONLY after the ML worker finishes
        if os.path.exists(image_path):
            os.remove(image_path)


@celery_app.task(name="process_lidar_cloud")
def process_lidar_cloud_task(file_path: str, ulpin_id: str):
    """Background task to run RANSAC/DBSCAN Spatial Segmentation."""
    try:
        geometry_data = extract_building_geometry(file_path)
        return {"ulpin_id": ulpin_id, "extracted_geometry": geometry_data}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)