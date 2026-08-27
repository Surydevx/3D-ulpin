import open3d as o3d
import numpy as np
import os

def generate_noisy_environment(filename="noisy_test_cloud.ply"):
    print("Mathematically synthesizing a noisy LiDAR environment...")
    
    # 1. The Ground Plane (10,000 points scattered across z ~ 0)
    ground_x = np.random.uniform(0, 100, 10000)
    ground_y = np.random.uniform(0, 100, 10000)
    ground_z = np.random.normal(0, 0.1, 10000) # Slight Gaussian noise on the ground
    ground_points = np.column_stack((ground_x, ground_y, ground_z))
    
    # 2. The Primary Building (5,000 points, dense cluster)
    # Dimensions: x[40-60], y[40-60], z[0-30]
    bldg_x = np.random.uniform(40, 60, 5000)
    bldg_y = np.random.uniform(40, 60, 5000)
    bldg_z = np.random.uniform(0, 30, 5000)
    building_points = np.column_stack((bldg_x, bldg_y, bldg_z))
    
    # 3. Ambient Noise / Trees (1,000 points, scattered density)
    noise_x = np.random.uniform(10, 90, 1000)
    noise_y = np.random.uniform(10, 90, 1000)
    noise_z = np.random.uniform(2, 15, 1000)
    noise_points = np.column_stack((noise_x, noise_y, noise_z))
    
    # Combine everything into a single unstructured matrix
    all_points = np.vstack((ground_points, building_points, noise_points))
    
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(all_points)
    
    # Save the synthetic data
    o3d.io.write_point_cloud(filename, pcd)
    print(f"Generated {len(all_points)} total points and saved to {filename}")

if __name__ == "__main__":
    generate_noisy_environment()