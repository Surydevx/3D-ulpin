from typing import List, Dict, Tuple

def calculate_bayesian_fusion(sources: List[Dict[str, float]]) -> Tuple[float, float]:
    """
    Computes the validated geometric height and its uncertainty using Bayesian Inference.
    Expects sources to have 'height_m' (mean) and 'variance' (sigma squared).
    """
    if not sources:
        raise ValueError("No sensor data provided for fusion.")

    # Initialize with the first sensor's data
    fused_mu = sources[0]["height_m"]
    fused_var = sources[0]["variance"]

    # Iteratively update the belief using Bayes' theorem for remaining sensors
    for i in range(1, len(sources)):
        meas_mu = sources[i]["height_m"]
        meas_var = sources[i]["variance"]

        # Prevent division by zero if a sensor claims absolute zero variance (impossible in reality)
        if fused_var + meas_var == 0:
            continue

        # Calculate the new fused mean and variance
        new_mu = (fused_mu * meas_var + meas_mu * fused_var) / (fused_var + meas_var)
        new_var = (fused_var * meas_var) / (fused_var + meas_var)

        fused_mu = new_mu
        fused_var = new_var

    # Return the statistically fused height and the final uncertainty (standard deviation)
    return round(fused_mu, 2), round(fused_var ** 0.5, 4)