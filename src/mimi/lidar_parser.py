import open3d as o3d
import numpy as np
import time

def extract_building_geometry(file_path: str) -> dict:
    """
    Ingests a raw LiDAR point cloud and applies RANSAC and DBSCAN ML algorithms
    to segment the primary building structure from ground and noise.
    """
    print(f"[ML Pipeline] Ingesting point cloud: {file_path}")
    start_time = time.time()
    
    pcd = o3d.io.read_point_cloud(file_path)
    if pcd.is_empty():
        raise ValueError("Point cloud is empty or unreadable.")
        
    initial_points = len(pcd.points)

    # 1. Voxel Downsampling (Performance Optimization)
    # Reduces point density while mathematically preserving the exact geometric shape
    pcd = pcd.voxel_down_sample(voxel_size=0.1)
    
    # 2. RANSAC Ground Plane Segmentation
    # Mathematically isolates the ground plane and removes it from the dataset
    plane_model, inliers = pcd.segment_plane(
        distance_threshold=0.2,
        ransac_n=3,
        num_iterations=1000
    )
    non_ground_cloud = pcd.select_by_index(inliers, invert=True)
    
    # 3. DBSCAN Spatial Clustering
    # Groups remaining points by density to isolate the building from trees/noise
    # eps = spatial search radius, min_points = minimum density for a valid cluster
    with o3d.utility.VerbosityContextManager(o3d.utility.VerbosityLevel.Error):
        labels = np.array(non_ground_cloud.cluster_dbscan(eps=0.5, min_points=50, print_progress=False))
        
    if labels.size == 0 or labels.max() == -1:
        raise ValueError("ML Segmentation Failed: No structural clusters detected above ground plane.")
        
    # Isolate the largest high-density cluster (statistically, the primary building)
    largest_cluster_idx = np.bincount(labels[labels >= 0]).argmax()
    building_cluster_indices = np.where(labels == largest_cluster_idx)[0]
    building_cloud = non_ground_cloud.select_by_index(building_cluster_indices)
    
    # 4. Extract Exact Geometric Boundaries from the isolated building
    aabb = building_cloud.get_axis_aligned_bounding_box()
    min_bounds = aabb.get_min_bound()
    max_bounds = aabb.get_max_bound()
    
    computation_time = round(time.time() - start_time, 4)
    
    return {
        "x_min": float(min_bounds[0]), "x_max": float(max_bounds[0]),
        "y_min": float(min_bounds[1]), "y_max": float(max_bounds[1]),
        "z_min": float(min_bounds[2]), "z_max": float(max_bounds[2]),
        "pipeline_metrics": {
            "initial_points": initial_points,
            "ground_points_removed": len(inliers),
            "building_points_isolated": len(building_cluster_indices),
            "segmentation_time_sec": computation_time,
            "algorithms_applied": ["VoxelDownsample", "RANSAC", "DBSCAN"]
        }
    }