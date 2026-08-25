class BoundingBox:
    def __init__(self, x_min, x_max, y_min, y_max, z_min, z_max):
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
        self.parcels = []
        self.divided = False
        self.children = []

    def subdivide(self):
        """Combinatorially partitions the current spatial node into 8 equal octants."""
        x_min, x_max, y_min, y_max, z_min, z_max = self.boundary.bounds
        x_mid = (x_min + x_max) / 2
        y_mid = (y_min + y_max) / 2
        z_mid = (z_min + z_max) / 2

        # Generate the 8 sub-boundaries mathematically
        octants = [
            # Bottom 4 octants (z_min to z_mid)
            BoundingBox(x_min, x_mid, y_min, y_mid, z_min, z_mid),
            BoundingBox(x_mid, x_max, y_min, y_mid, z_min, z_mid),
            BoundingBox(x_min, x_mid, y_mid, y_max, z_min, z_mid),
            BoundingBox(x_mid, x_max, y_mid, y_max, z_min, z_mid),
            # Top 4 octants (z_mid to z_max)
            BoundingBox(x_min, x_mid, y_min, y_mid, z_mid, z_max),
            BoundingBox(x_mid, x_max, y_min, y_mid, z_mid, z_max),
            BoundingBox(x_min, x_mid, y_mid, y_max, z_mid, z_max),
            BoundingBox(x_mid, x_max, y_mid, y_max, z_mid, z_max)
        ]
        
        for octant in octants:
            self.children.append(OctreeNode(octant, self.capacity))
        self.divided = True

    def insert(self, parcel_id: str, parcel_bounds: BoundingBox) -> bool:
        """Recursively inserts a spatial parcel into the correct octant."""
        if not self.boundary.intersects(parcel_bounds):
            return False

        if len(self.parcels) < self.capacity and not self.divided:
            self.parcels.append((parcel_id, parcel_bounds))
            return True

        if not self.divided:
            self.subdivide()

        for child in self.children:
            if child.insert(parcel_id, parcel_bounds):
                return True
        return False