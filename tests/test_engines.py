import pytest
from src.mimi.fusion_engine import calculate_bayesian_fusion
from src.mimi.egc_topology import VolumetricParcel

def test_bayesian_fusion_weighting():
    """Validates inverse-variance fusion favors the more accurate sensor."""
    evidence = [
        {"source_name": "Bad_Sensor", "height_m": 20.0, "variance": 1.0},
        {"source_name": "Good_Sensor", "height_m": 10.0, "variance": 0.01}
    ]
    
    # 10.0 has 100x lower variance, so it should overwhelmingly dominate the math
    fused_mu, std_dev = calculate_bayesian_fusion(evidence)
    
    # Formula results in 10.099, which rounds to 10.1
    assert fused_mu == 10.1
    assert std_dev < 1.0

def test_bayesian_outlier_rejection():
    """Ensures the median consensus drops wild anomalies before fusion."""
    evidence = [
        {"source_name": "Sensor1", "height_m": 15.0, "variance": 0.1},
        {"source_name": "Sensor2", "height_m": 15.1, "variance": 0.1},
        {"source_name": "Sensor3", "height_m": 14.9, "variance": 0.1},
        {"source_name": "Rogue_Drone", "height_m": 80.0, "variance": 0.1} # Massive outlier
    ]
    
    # The outlier threshold should detect and drop the 80.0m reading
    fused_mu, std_dev = calculate_bayesian_fusion(evidence, outlier_threshold_m=2.5)
    
    assert 14.8 <= fused_mu <= 15.2

def test_egc_z_axis_isolation():
    """Verifies that overlapping 2D footprints do NOT conflict if Z-axes are separate."""
    parcel_a = VolumetricParcel(
        parcel_id="PARCEL-A",
        footprint_coords=[(0, 0), (0, 10), (10, 10), (10, 0)],
        z_min=0.0, 
        z_max=10.0
    )
    
    parcel_b_safe = VolumetricParcel(
        parcel_id="PARCEL-B",
        footprint_coords=[(5, 5), (5, 15), (15, 15), (15, 5)], # 2D footprint overlaps A
        z_min=15.0, 
        z_max=25.0                                             # 3D Z-bounds completely separate
    )
    
    result = parcel_a.check_spatial_conflict(parcel_b_safe)
    
    assert result["conflict_detected"] is False
    assert result["affected_volume_m3"] == 0.0

def test_egc_volumetric_conflict():
    """Verifies true 3D intersection calculates the correct overlap volume."""
    parcel_a = VolumetricParcel("P-A", [(0, 0), (0, 10), (10, 10), (10, 0)], 0.0, 10.0)
    parcel_b = VolumetricParcel("P-B", [(0, 0), (0, 10), (10, 10), (10, 0)], 5.0, 15.0)
    
    result = parcel_a.check_spatial_conflict(parcel_b)
    
    assert result["conflict_detected"] is True
    # 10x10 footprint = 100 sq meters. Z overlap is from 5 to 10 = 5 meters. 
    # Volume = 100 * 5 = 500 cubic meters.
    assert result["affected_volume_m3"] == 500.0