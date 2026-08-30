import hashlib
import os

# 1. Projected Coordinate Geometry Bounds (Meters instead of Degrees)
# Assuming EPSG:32643 (UTM) to match your schema.sql
X_MIN, X_MAX = 100000.0, 900000.0     # Easting in meters
Y_MIN, Y_MAX = 600000.0, 4000000.0    # Northing in meters
Z_MIN, Z_MAX = -50.0, 9000.0          # Elevation in meters

# Use 21 bits per dimension (yields a 63-bit integer when interleaved)
# 2^21 = 2,097,152 distinct grid points per dimension.
BITS_PER_DIM = 21
MAX_GRID_VAL = (1 << BITS_PER_DIM) - 1

# 2. Strict Environment Fetching (Fail-Closed Cryptography)
SYSTEM_SALT = os.environ.get("HEXCODE_SALT")
if not SYSTEM_SALT:
    raise ValueError("CRITICAL: HEXCODE_SALT missing. Halting ULPIN generation to prevent insecure hashing.")

def normalize_coordinate(value: float, min_val: float, max_val: float) -> int:
    """
    Maps a continuous float coordinate (in meters) to a discrete integer grid.
    """
    if value < min_val or value > max_val:
        raise ValueError(f"Coordinate {value} is out of bounds [{min_val}, {max_val}]")
    
    # Calculate the ratio and scale to the max grid value
    ratio = (value - min_val) / (max_val - min_val)
    return int(ratio * MAX_GRID_VAL)

def encode_morton_3d(x: int, y: int, z: int) -> int:
    """
    Combinatorial interleaving of 3 integers to create a 3D Z-order curve.
    """
    morton = 0
    for i in range(BITS_PER_DIM):
        morton |= ((x & (1 << i)) << (2 * i))
        morton |= ((y & (1 << i)) << (2 * i + 1))
        morton |= ((z & (1 << i)) << (2 * i + 2))
    return morton

def generate_3d_ulpin(easting_x: float, northing_y: float, elevation_z: float, parent_2d_ulpin: str) -> dict:
    """
    Generates a mathematically rigorous and secure 3D ULPIN.
    """
    # 1. Map to uniform metric integer grid
    x_int = normalize_coordinate(easting_x, X_MIN, X_MAX)
    y_int = normalize_coordinate(northing_y, Y_MIN, Y_MAX)
    z_int = normalize_coordinate(elevation_z, Z_MIN, Z_MAX)
    
    # 2. Generate 1D Spatial Hash (Morton Code)
    spatial_hash = encode_morton_3d(x_int, y_int, z_int)
    
    # 3. Generate Checksum for integrity 
    hash_input = f"{parent_2d_ulpin}:{spatial_hash}:{SYSTEM_SALT}".encode('utf-8')
    checksum = hashlib.sha256(hash_input).hexdigest()[:8].upper()
    
    # 4. Construct final identifier
    ulpin_3d = f"{parent_2d_ulpin}-Z{spatial_hash}-{checksum}"
    
    return {
        "ulpin_3d": ulpin_3d,
        "morton_index": spatial_hash,
        "checksum": checksum
    }