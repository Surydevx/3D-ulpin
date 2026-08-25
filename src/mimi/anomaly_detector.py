import numpy as np
import csv
import os
from sklearn.ensemble import IsolationForest

class MLCadastralAnomalyDetector:
    def __init__(self, data_path="src/mimi/ml_training_data.csv"):
        """
        Initializes the Isolation Forest and trains it on a synthetic distribution dataset.
        """
        self.model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        
        # Load the 10,000-row synthetic dataset
        if os.path.exists(data_path):
            with open(data_path, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip the header row
                training_matrix = np.array([list(map(float, row)) for row in reader])
        else:
            # Fallback if the CSV hasn't been generated yet
            training_matrix = np.array([
                [0.1, 0.95, 0.05], [0.2, 0.90, 0.10], [-0.1, 0.98, 0.02],
                [3.5, 0.60, 1.20], [-2.8, 0.55, 0.90] 
            ])
            
        # Mathematically fit the isolation trees to the hyper-dimensional data
        self.model.fit(training_matrix)

    def evaluate_vertical_development(
        self, ulpin: str, h_registered: float, h_observed: float, sensor_confidence: float
    ) -> dict:
        delta_h = h_observed - h_registered
        geometry_var = 1.0 - sensor_confidence
        
        feature_vector = np.array([[delta_h, sensor_confidence, geometry_var]])
        prediction = self.model.predict(feature_vector)[0]
        
        status = "ANOMALY_DETECTED" if prediction == -1 else "VALID"
        
        return {
            "ulpin": ulpin,
            "delta_h_m": round(delta_h, 2),
            "status": status,
            "engine": "Scikit-Learn IsolationForest"
        }