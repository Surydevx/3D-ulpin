import pandas as pd
import open3d as o3d
import numpy as np
import time
import os

def build_production_dataset(input_file: str, output_file: str):
    print(f"--- Initiating ETL Pipeline ---")
    print(f"Target: {input_file}")
    start_time = time.time()
    
    # 1. EXTRACT: Use Pandas C-engine to read only X, Y, Z columns
    print("1. Extracting spatial matrix (Bypassing RGB & Intensity)...")
    df = pd.read_csv(
        input_file, 
        sep='\s+', 
        header=None, 
        usecols=[0, 1, 2], 
        dtype=np.float32,
        engine='c'
    )
    
    # 2. TRANSFORM: Load into Open3D and mathematically compress
    print(f"2. Transforming {len(df):,} raw coordinates...")
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(df.values)
    
    # Apply a 10cm Voxel Grid. This averages multiple points falling inside the same 
    # 10cm^3 volume into a single exact mathematical coordinate, stripping redundancy.
    compressed_pcd = pcd.voxel_down_sample(voxel_size=0.1)
    
    # 3. LOAD: Serialize to a binary format (.ply)
    print("3. Loading to compressed binary file...")
    o3d.io.write_point_cloud(output_file, compressed_pcd, write_ascii=False)
    
    # Calculate Metrics
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    new_size = os.path.getsize(output_file) / (1024 * 1024)
    compression_ratio = (1 - (new_size / original_size)) * 100
    
    print(f"\n--- ETL Complete in {round(time.time() - start_time, 2)}s ---")
    print(f"Points Reduced: {len(df):,} -> {len(compressed_pcd.points):,}")
    print(f"File Size: {round(original_size, 2)} MB -> {round(new_size, 2)} MB ({round(compression_ratio, 2)}% Reduction)")
    print(f"Output saved to: {output_file}")

if __name__ == "__main__":
    # Point this to wherever you saved the Kaggle download
    INPUT_TXT = "bildstein_station1_xyz_intensity_rgb.txt"
    OUTPUT_PLY = "optimized_bildstein.ply"
    
    if os.path.exists(INPUT_TXT):
        build_production_dataset(INPUT_TXT, OUTPUT_PLY)
    else:
        print(f"Error: Could not find {INPUT_TXT}. Update the file path.")