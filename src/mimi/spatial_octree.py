from typing import List, Tuple

class BoundingBox:
    def __init__(self, x_min: float, x_max: float, y_min: float, y_max: float, z_min: float, z_max: float):
        self.bounds = (x_min, x_max, y_min, y_max, z_min, z_max)
        
    def intersects(self, other: 'BoundingBox') -> bool:
        """Calculates topological intersection using strict coordinate inequalities."""
        return not (self.bounds[1] < other.bounds[0] or self.bounds[0] > other.bounds[1] or
                    self.bounds[3] < other.bounds[2] or self.bounds[2] > other.bounds[3] or
                    self.bounds[5] < other.bounds[4] or self.bounds[4] > other.bounds[5])

class OctreeNode:
    def __init__(self, boundary: BoundingBox, capacity: int = 4):
        self.boundary = boundary
        self.capacity = capacity
        self.parcels: List[Tuple[str, BoundingBox]] = []
        self.divided = False
        self.children: List['OctreeNode'] = []

    def subdivide(self):
        """Combinatorially partitions the current spatial node into 8 equal octants."""
        x_min, x_max, y_min, y_max, z_min, z_max = self.boundary.bounds
        x_mid = (x_min + x_max) / 2
        y_mid = (y_min + y_max) / 2
        z_mid = (z_min + z_max) / 2

        octants = [
            BoundingBox(x_min, x_mid, y_min, y_mid, z_min, z_mid),
            BoundingBox(x_mid, x_max, y_min, y_mid, z_min, z_mid),
            BoundingBox(x_min, x_mid, y_mid, y_max, z_min, z_mid),
            BoundingBox(x_mid, x_max, y_mid, y_max, z_min, z_mid),
            BoundingBox(x_min, x_mid, y_min, y_mid, z_mid, z_max),
            BoundingBox(x_mid, x_max, y_min, y_mid, z_mid, z_max),
            BoundingBox(x_min, x_mid, y_mid, y_max, z_mid, z_max),
            BoundingBox(x_mid, x_max, y_mid, y_max, z_mid, z_max)
        ]
        
        for octant in octants:
            self.children.append(OctreeNode(octant, self.capacity))
        self.divided = True

        # CRITICAL FIX: Redistribute existing parcels into the new children
        for parcel_id, p_bounds in self.parcels:
            for child in self.children:
                child.insert(parcel_id, p_bounds)
        self.parcels = [] # Clear parent list after pushing down

    def insert(self, parcel_id: str, parcel_bounds: BoundingBox) -> bool:
        """Recursively inserts a spatial parcel into all intersecting octants."""
        if not self.boundary.intersects(parcel_bounds):
            return False

        if not self.divided:
            if len(self.parcels) < self.capacity:
                self.parcels.append((parcel_id, parcel_bounds))
                return True
            else:
                self.subdivide()

        # CRITICAL FIX: Do not 'return True' early. A parcel might span MULTIPLE octants.
        inserted = False
        for child in self.children:
            if child.insert(parcel_id, parcel_bounds):
                inserted = True
        return inserted

    def query(self, search_bounds: BoundingBox, found_parcels: set[str] | None = None) -> set[str]:
        """Searches the Octree and returns a unique set of parcel_ids that intersect the search area."""
        if found_parcels is None:
            found_parcels = set()
            
        if not self.boundary.intersects(search_bounds):
            return found_parcels

        if not self.divided:
            for parcel_id, p_bounds in self.parcels:
                if search_bounds.intersects(p_bounds):
                    found_parcels.add(parcel_id)
            return found_parcels

        for child in self.children:
            child.query(search_bounds, found_parcels)
            
        return found_parcels