from shapely.geometry import Polygon

class VolumetricParcel:
    def __init__(self, parcel_id: str, footprint_coords: list, z_min: float, z_max: float):
        """
        Constructs a 3D volumetric parcel using a 2D polygon footprint and vertical limits.
        """
        self.parcel_id = parcel_id
        self.footprint = Polygon(footprint_coords)
        self.z_min = z_min
        self.z_max = z_max
        
        # Ensure geometry is valid and mathematically closed
        if not self.footprint.is_valid:
            self.footprint = self.footprint.buffer(0)

    def volume(self) -> float:
        """Calculates the total cubic volume of the parcel."""
        return self.footprint.area * (self.z_max - self.z_min)

    def check_spatial_conflict(self, other: 'VolumetricParcel') -> dict:
        """
        Executes Exact Geometric Computation to test for volumetric overlap.
        Checks both 2D horizontal intersection and 1D vertical overlap.
        """
        # 1. 1D Vertical Overlap Check (Strict inequality to allow touching floors)
        vertical_overlap = max(self.z_min, other.z_min) < min(self.z_max, other.z_max)
        
        # 2. 2D Horizontal Intersection Check
        horizontal_overlap = self.footprint.intersects(other.footprint)
        
        # 3. Calculate intersection volume if a conflict exists
        if vertical_overlap and horizontal_overlap:
            intersection_2d = self.footprint.intersection(other.footprint)
            
            # Touching boundaries have 0 area, which is legally acceptable
            if intersection_2d.area > 0:
                overlap_z_min = max(self.z_min, other.z_min)
                overlap_z_max = min(self.z_max, other.z_max)
                conflict_height = overlap_z_max - overlap_z_min
                conflict_volume = intersection_2d.area * conflict_height
                
                return {
                    "conflict_detected": True,
                    "affected_volume_m3": round(conflict_volume, 2),
                    "depth_range": f"{overlap_z_min}m to {overlap_z_max}m"
                }
                
        return {"conflict_detected": False, "affected_volume_m3": 0.0}

# --- Testing Scenario 3: Underground Conflict ---
if __name__ == "__main__":
    # Define an existing private basement (Coordinates in local meters)
    basement_coords = [(0, 0), (0, 50), (50, 50), (50, 0)]
    private_basement = VolumetricParcel("ULPIN-BASEMENT", basement_coords, -20.0, -5.0)
    
    # Define a proposed metro tunnel traversing underneath
    tunnel_coords = [(-10, 20), (60, 20), (60, 30), (-10, 30)]
    proposed_tunnel = VolumetricParcel("ULPIN-METRO-TUNNEL", tunnel_coords, -18.0, -12.0)
    
    # Run Topological Validation
    print("Executing Exact Geometric Computation...\n")
    report = private_basement.check_spatial_conflict(proposed_tunnel)
    
    if report["conflict_detected"]:
        print(f"[STATUS: SPATIAL CONFLICT]")
        print(f"Intersection Volume: {report['affected_volume_m3']} cubic meters")
        print(f"Conflict Depth Range: {report['depth_range']}")
    else:
        print("[STATUS: VALID - No spatial conflict detected]")