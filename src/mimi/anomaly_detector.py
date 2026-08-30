import numpy as np
import csv
import os
import logging
import joblib
from sklearn.ensemble import IsolationForest

class MLCadastralAnomalyDetector:


    def __init__(self, data_filename="ml_training_data.csv", model_filename="iso_forest.joblib"):
        """
        Loads a pre-trained Isolation Forest model or trains one if it doesn't exist,
        using safe path resolution and defensive data parsing.
        """

        # Ensure robust path resolution regardless of execution directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_path = os.path.join(current_dir, data_filename)
        self.model_path = os.path.join(current_dir, model_filename)
        
        if os.path.exists(self.model_path):
            # Load pre-trained model to prevent re-fitting on every instantiation
            self.model = joblib.load(self.model_path)

        else:
            # Initialize, train, and persist the model
            self.model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
            self._train_and_save_model()


    def _train_and_save_model(self):
        training_data = []
        if os.path.exists(self.data_path):
            with open(self.data_path, 'r') as f:
                reader = csv.reader(f)
                next(reader, None)  # Safely skip header
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Parse row and keep only [delta_h, sensor_confidence]
                        vals = [float(val) for val in row]
                        training_data.append(vals[:2]) 
                    except ValueError:
                        logging.warning(f"Malformed data at row {row_num}, skipping.")
            
            training_matrix = np.array(training_data)

        else:
            logging.info("Training CSV missing. Using fallback synthetic matrix.")
            # Fallback matrix: [delta_h, sensor_confidence]
            training_matrix = np.array([
                [0.1, 0.95], [0.2, 0.90], [-0.1, 0.98],
                [3.5, 0.60], [-2.8, 0.55] 
            ])
            
        # Fit the isolation trees and serialize the model to disk
        self.model.fit(training_matrix)
        joblib.dump(self.model, self.model_path)


    def evaluate_vertical_development(
            self, ulpin: str, h_registered: float, h_observed: float, sensor_confidence: float
        ) -> dict:
            
            delta_h = h_observed - h_registered
    
            feature_vector = np.array([[delta_h, sensor_confidence]])
            
            # 1. Get the binary prediction (-1 for anomaly, 1 for valid)
            prediction = self.model.predict(feature_vector)[0]
            
            # 2. Get the raw continuous anomaly score (lower/negative means more anomalous)
            raw_score = self.model.decision_function(feature_vector)[0]
            
            # 3. Translate the raw score into a Confidence Percentage.
            # Isolation Forest scores typically hover between -0.5 and 0.5. 
            # We calculate the absolute distance from the 0.0 decision boundary.
            confidence = min(round(abs(raw_score) * 200, 1), 99.9)
            
            # 4. Generate human-readable diagnostics for the evidence graph
            if prediction == -1:
            
                if abs(delta_h) > 2.0:
                    diagnostic_reason = f"High vertical discrepancy ({round(delta_h, 2)}m) detected."
    
                elif sensor_confidence < 0.7:
                    diagnostic_reason = "Flagged due to highly unstable sensor confidence."
    
                else:
                    diagnostic_reason = "Marginal spatial anomaly detected by isolation trees."
    
            else:
                diagnostic_reason = "Measurements fall within normal historical distribution."
    
            # Return a fully transparent payload
            return {
                "ulpin": ulpin,
                "status": "SPATIAL_CONFLICT" if prediction == -1 else "VALID",
                "delta_h_m": round(delta_h, 2),
                "sensor_confidence": sensor_confidence,
                "model_confidence_score": f"{confidence}%",
                "raw_anomaly_score": round(raw_score, 4),# this parameter is purely for debugging purposes main dahsboard shouldn't
                                                         # include it.
                "diagnostics": diagnostic_reason,
                "engine": "Scikit-Learn IsolationForest"
            }