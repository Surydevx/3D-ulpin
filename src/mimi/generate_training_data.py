import numpy as np
import csv
import os

# Parameters for statistical distribution
NUM_SAMPLES = 10000
OUTLIER_RATIO = 0.05

def generate_dataset(filename="src/mimi/ml_training_data.csv"):
    num_outliers = int(NUM_SAMPLES * OUTLIER_RATIO)
    num_inliers = NUM_SAMPLES - num_outliers

    # 1. Generate Inliers (Valid Buildings)
    # Using a Gaussian normal distribution around 0 for height differences
    inlier_delta_h = np.random.normal(loc=0.0, scale=0.2, size=num_inliers)
    inlier_confidence = np.random.normal(loc=0.95, scale=0.03, size=num_inliers)
    inlier_variance = np.random.normal(loc=0.05, scale=0.02, size=num_inliers)

    # 2. Generate Outliers (Illegal Vertical Developments)
    # Using uniform distributions for extreme, unpredictable anomalies
    outlier_delta_h = np.random.uniform(low=2.0, high=15.0, size=num_outliers)
    
    # Randomly flip half the outliers to negative (e.g., unauthorized deep basements)
    outlier_delta_h[:num_outliers // 2] *= -1 
    
    outlier_confidence = np.random.uniform(low=0.4, high=0.8, size=num_outliers)
    outlier_variance = np.random.uniform(low=0.5, high=1.5, size=num_outliers)

    # 3. Combine the arrays
    delta_h = np.concatenate([inlier_delta_h, outlier_delta_h])
    confidence = np.concatenate([inlier_confidence, outlier_confidence])
    variance = np.concatenate([inlier_variance, outlier_variance])
    
    # Strictly bound the confidence interval between [0, 1]
    confidence = np.clip(confidence, 0.0, 1.0)

    # Stack into a 2D matrix and mathematically shuffle the rows
    dataset = np.column_stack((delta_h, confidence, variance))
    np.random.shuffle(dataset)

    # 4. Write to CSV
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["delta_h_m", "sensor_confidence", "geometry_variance"])
        writer.writerows(dataset)

    print(f"Mathematical dataset generated: {NUM_SAMPLES} records successfully mapped to {filename}")

if __name__ == "__main__":
    generate_dataset()