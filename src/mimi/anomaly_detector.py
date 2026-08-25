class CadastralAnomalyDetector:
    def __init__(self, tolerance_meters: float = 0.5):
        """
        Initializes the detector with a spatial tolerance threshold.
        Differences below this tolerance (e.g., 0.5m) are considered sensor noise,
        not structural anomalies.
        """
        self.tolerance_meters = tolerance_meters

    def evaluate_vertical_development(
        self, 
        ulpin: str, 
        h_registered: float, 
        h_observed: float, 
        sensor_confidence: float
    ) -> dict:
        """
        Evaluates an observed building height against its registered height.
        Calculates ΔH and triggers an anomaly flag if unregistered development is suspected.
        """
        # Calculate the delta between observed and registered heights
        delta_h = h_observed - h_registered
        
        report = {
            "ulpin": ulpin,
            "registered_height_m": h_registered,
            "observed_height_m": h_observed,
            "delta_h_m": round(delta_h, 2),
            "sensor_confidence": sensor_confidence,
            "status": "VALID",
            "flag_message": None
        }

        # Check if the discrepancy exceeds the allowed tolerance
        if delta_h > self.tolerance_meters:
            if sensor_confidence >= 0.85: # Require at least 85% confidence to flag
                report["status"] = "ANOMALY_DETECTED"
                report["flag_message"] = "Possible unregistered vertical development."
            else:
                report["status"] = "REQUIRES_SURVEY"
                report["flag_message"] = "Discrepancy detected but sensor confidence is too low to confirm."
                
        # Handle cases where the observed building is unexpectedly shorter (e.g., demolition)
        elif delta_h < -self.tolerance_meters:
            report["status"] = "ANOMALY_DETECTED"
            report["flag_message"] = "Observed structure is significantly lower than registered. Possible demolition."

        return report

# --- Testing Scenario 2: Unauthorized Vertical Development ---
if __name__ == "__main__":
    detector = CadastralAnomalyDetector(tolerance_meters=1.0)
    
    # Data from Scenario 2 in the specification
    ulpin_target = "IN-DL-BLDG-X73"
    registered_height = 14.2  
    observed_height = 17.8    
    
    # Assume the LiDAR/Drone fusion gave us a 92% confidence score
    confidence_score = 0.92 
    
    print(f"Running AI Anomaly Detection for {ulpin_target}...\n")
    result = detector.evaluate_vertical_development(
        ulpin=ulpin_target,
        h_registered=registered_height,
        h_observed=observed_height,
        sensor_confidence=confidence_score
    )
    
    print(f"Registered Height: {result['registered_height_m']}m")
    print(f"Observed Height: {result['observed_height_m']}m")
    print(f"Difference (ΔH): {result['delta_h_m']}m")
    
    if result["status"] == "ANOMALY_DETECTED":
        print(f"STATUS: {result['status']}")
        print(f"WARNING: {result['flag_message']} (Confidence: {result['sensor_confidence'] * 100}%)")
    else:
        print(f"STATUS: {result['status']}")