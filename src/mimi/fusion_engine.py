from typing import List, Dict

def calculate_fused_height(sources: List[Dict[str, float]]) -> float:
    """
    Computes the validated geometric height by fusing multi-source evidence based on reliability weights.
    """
    weighted_sum = 0.0
    total_weight = 0.0
    
    for source in sources:
        # Use bracket notation instead of .get() to enforce strict typing
        h = source["height_m"]
        w = source["weight"]
        
        weighted_sum += (h * w)
        total_weight += w
        
    if total_weight == 0:
        raise ValueError("Total sensor weight cannot be zero.")
        
    return round(weighted_sum / total_weight, 2)