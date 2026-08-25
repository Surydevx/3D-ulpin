import hashlib

# 1. Define the Coordinate Geometry Bounds (Example: India's approximate bounding box)
LAT_MIN, LAT_MAX = 6.0, 36.0
LON_MIN, LON_MAX = 68.0, 98.0
ELEV_MIN, ELEV_MAX = -50.0, 9000.0 # From underground tunnels to the Himalayas in meters

# Use 21 bits per dimension (yields a 63-bit integer when interleaved)
# 2^21 = 2,097,152 distinct grid points per dimension.
BITS_PER_DIM = 21
MAX_GRID_VAL = (1 << BITS_PER_DIM) - 1

def normalize_coordinate(value: float, min_val: float, max_val: float) -> int:
    """
    Maps a continuous float coordinate to a discrete integer grid using an affine transformation.
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

def generate_3d_ulpin(lat: float, lon: float, elevation: float, parent_2d_ulpin: str) -> dict:
    """
    Generates a mathematically rigorous and secure 3D ULPIN.
    """
    # 1. Map to integer grid
    x_int = normalize_coordinate(lon, LON_MIN, LON_MAX)
    y_int = normalize_coordinate(lat, LAT_MIN, LAT_MAX)
    z_int = normalize_coordinate(elevation, ELEV_MIN, ELEV_MAX)
    
    # 2. Generate 1D Spatial Hash (Morton Code)
    spatial_hash = encode_morton_3d(x_int, y_int, z_int)
    
    # 3. Generate Checksum for integrity 
    hash_input = f"{parent_2d_ulpin}:{spatial_hash}".encode('utf-8')
    checksum = hashlib.sha256(hash_input).hexdigest()[:8].upper() # 8-character hex
    
    # 4. Construct final identifier
    ulpin_3d = f"{parent_2d_ulpin}-Z{spatial_hash}-{checksum}"
    
    return {
        "ulpin_3d": ulpin_3d,
        "morton_index": spatial_hash,
        "checksum": checksum
    }

# --- Testing the Logic ---
if __name__ == "__main__":
    # Test with coordinates for a hypothetical underground tunnel in Delhi
    test_lat = 28.6139
    test_lon = 77.2090
    test_elevation = -15.5 # 15.5 meters underground
    parent_parcel = "IN-DL-45982"
    
    result = generate_3d_ulpin(test_lat, test_lon, test_elevation, parent_parcel)
    
    print(f"Parent 2D Parcel: {parent_parcel}")
    print(f"Raw Coordinates: Lat: {test_lat}, Lon: {test_lon}, Elev: {test_elevation}m")
    print(f"1D Spatial Hash (Morton): {result['morton_index']}")
    print(f"Cryptographic Checksum: {result['checksum']}")
    print(f"Final Validated 3D ULPIN: {result['ulpin_3d']}")