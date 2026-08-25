import open3d as o3d
import numpy as np

def extract_building_geometry(file_path: str) -> dict:
    """Loads a LiDAR point cloud and extracts strict geometric boundaries."""
    print(f"Loading point cloud from {file_path}...")
    pcd = o3d.io.read_point_cloud(file_path)
    
    if pcd.is_empty():
        raise ValueError("Point cloud is empty or unreadable.")

    # Compute the Axis-Aligned Bounding Box (AABB)
    aabb = pcd.get_axis_aligned_bounding_box()
    
    # Extract coordinate limits as NumPy arrays: [x, y, z]
    min_bounds = aabb.get_min_bound()
    max_bounds = aabb.get_max_bound()
    
    return {
        "x_min": float(min_bounds[0]), "x_max": float(max_bounds[0]),
        "y_min": float(min_bounds[1]), "y_max": float(max_bounds[1]),
        "z_min": float(min_bounds[2]), "z_max": float(max_bounds[2]),
        "total_points": np.asarray(pcd.points).shape[0]
    }