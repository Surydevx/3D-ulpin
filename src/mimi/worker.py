import os
import logging
from celery import Celery
from .vision_segmentation import DroneVisionPipeline
from .lidar_parser import extract_building_geometry

celery_app = Celery(
    "mimi_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

vision_pipeline = None

# Added bind=True to access task metadata, and auto-retries for transient failures
@celery_app.task(name="process_drone_image", bind=True, max_retries=3)
def process_drone_image_task(self, image_path: str, ulpin_id: str):
    global vision_pipeline
    
    if vision_pipeline is None:
        vision_pipeline = DroneVisionPipeline()
        
    try:
        footprint_data = vision_pipeline.extract_footprint_polygon(image_path)
        
        # ONLY delete the file if the ML pipeline successfully processed it
        if os.path.exists(image_path):
            os.remove(image_path)
            
        return {"ulpin_id": ulpin_id, "polygon_data": footprint_data}
        
    except Exception as e:
        logging.error(f"Vision Pipeline Failed for {ulpin_id}: {str(e)}")
        # CRITICAL FIX: Raise the exception so Celery knows the task FAILED and can retry it.
        raise self.retry(exc=e, countdown=60) # Wait 60 seconds before retrying


@celery_app.task(name="process_lidar_cloud", bind=True, max_retries=3)
def process_lidar_cloud_task(self, file_path: str, ulpin_id: str):
    try:
        geometry_data = extract_building_geometry(file_path)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return {"ulpin_id": ulpin_id, "extracted_geometry": geometry_data}
        
    except Exception as e:
        logging.error(f"LiDAR Parser Failed for {ulpin_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)