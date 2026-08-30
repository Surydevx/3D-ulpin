from shapely.geometry import Polygon
from typing import Sequence, Tuple

class VolumetricParcel:
    def __init__(self, parcel_id: str, footprint_coords: Sequence[Tuple[float, float]], z_min: float, z_max: float):
        """
        Constructs a 3D volumetric parcel using a 2D polygon footprint and vertical limits.
        """
        self.parcel_id = parcel_id
        
        # 1. Mathematical Sanity Lock
        if z_max <= z_min:
            raise ValueError(f"CRITICAL: Inverted or flat volume detected for {parcel_id}. z_max ({z_max}) must be > z_min ({z_min}).")
            
        self.z_min = z_min
        self.z_max = z_max
        self.footprint = Polygon(footprint_coords)
        
        # Ensure geometry is valid and mathematically closed
        if not self.footprint.is_valid:
            self.footprint = self.footprint.buffer(0)

    def volume(self) -> float:
        """Calculates the total cubic volume of the parcel."""
        return self.footprint.area * (self.z_max - self.z_min)

    def check_spatial_conflict(self, other: 'VolumetricParcel', tolerance: float = 1e-4) -> dict:
        """
        Executes Geometric Computation to test for volumetric overlap.
        Uses a tolerance epsilon to prevent floating-point micro-collisions.
        """
        # 1D Vertical Overlap Check
        vertical_overlap = max(self.z_min, other.z_min) < min(self.z_max, other.z_max)
        
        # 2D Horizontal Intersection Check
        horizontal_overlap = self.footprint.intersects(other.footprint)
        
        if vertical_overlap and horizontal_overlap:
            intersection_2d = self.footprint.intersection(other.footprint)
            
            # 2. Floating-Point Tolerance Check (e.g., ignore overlaps smaller than 1cm^2)
            if intersection_2d.area > tolerance:
                overlap_z_min = max(self.z_min, other.z_min)
                overlap_z_max = min(self.z_max, other.z_max)
                conflict_height = overlap_z_max - overlap_z_min
                conflict_volume = intersection_2d.area * conflict_height
                
                # 3. Consistent, informative payload
                return {
                    "conflict_detected": True,
                    "parcel_a": self.parcel_id,
                    "parcel_b": other.parcel_id,
                    "affected_volume_m3": round(conflict_volume, 3),
                    "depth_range": f"{round(overlap_z_min, 2)}m to {round(overlap_z_max, 2)}m"
                }
                
        # Return consistent schema even on failure
        return {
            "conflict_detected": False, 
            "parcel_a": self.parcel_id,
            "parcel_b": other.parcel_id,
            "affected_volume_m3": 0.0,
            "depth_range": None
        }

# --- Testing Scenario 3: Underground Conflict ---
if __name__ == "__main__":
    # Define an existing private basement (Coordinates in local meters)
    basement_coords = [(0.0, 0.0), (0.0, 50.0), (50.0, 50.0), (50.0, 0.0)]
    private_basement = VolumetricParcel("ULPIN-BASEMENT", basement_coords, -20.0, -5.0)
    
    # Define a proposed metro tunnel traversing underneath
    tunnel_coords = [(-10.0, 20.0), (60.0, 20.0), (60.0, 30.0), (-10.0, 30.0)]
    proposed_tunnel = VolumetricParcel("ULPIN-METRO-TUNNEL", tunnel_coords, -18.0, -12.0)
    
    print("Executing Geometric Computation...\n")
    report = private_basement.check_spatial_conflict(proposed_tunnel)
    
    if report["conflict_detected"]:
        print(f"[STATUS: SPATIAL CONFLICT]")
        print(f"Conflict between {report['parcel_a']} and {report['parcel_b']}")
        print(f"Intersection Volume: {report['affected_volume_m3']} cubic meters")
        print(f"Conflict Depth Range: {report['depth_range']}")
    else:
        print("[STATUS: VALID - No spatial conflict detected]")