import statistics
from typing import List, Dict, Tuple

def calculate_bayesian_fusion(sources: List[Dict[str, float]], outlier_threshold_m: float = 2.5) -> Tuple[float, float]:
    """
    Computes the validated geometric height and its uncertainty using Bayesian Inference.
    Includes pre-fusion Outlier Rejection to prevent anomalous sensor data 
    from poisoning the statistical model.
    """
    if not sources:
        raise ValueError("No sensor data provided for fusion.")

    # 1. Numerical Stability: Clamp minimum variance
    for src in sources:
        src["variance"] = max(src.get("variance", 1.0), 1e-6)

    # 2. Outlier Rejection via Median Consensus
    if len(sources) >= 3:
        median_height = statistics.median([s["height_m"] for s in sources])
        
        # Keep only sensors within the threshold (e.g., 2.5 meters) of the consensus
        valid_sources = [s for s in sources if abs(s["height_m"] - median_height) <= outlier_threshold_m]
        
        # Fallback: if all sensors wildly disagree, process all of them
        if not valid_sources:
            valid_sources = sources
    else:
        valid_sources = sources

    # 3. Establish the Prior: Sort by variance (lowest variance first)
    valid_sources = sorted(valid_sources, key=lambda x: x["variance"])

    # 4. Iterative Bayesian Fusion
    fused_mu = valid_sources[0]["height_m"]
    fused_var = valid_sources[0]["variance"]

    for i in range(1, len(valid_sources)):
        meas_mu = valid_sources[i]["height_m"]
        meas_var = valid_sources[i]["variance"]

        # Bayesian update 
        new_mu = (fused_mu * meas_var + meas_mu * fused_var) / (fused_var + meas_var)
        new_var = (fused_var * meas_var) / (fused_var + meas_var)

        fused_mu = new_mu
        fused_var = new_var

    return round(fused_mu, 2), round(fused_var ** 0.5, 4)