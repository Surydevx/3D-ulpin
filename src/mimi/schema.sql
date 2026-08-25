-- 1. Main 3D Cadastral Entity Table
CREATE TABLE IF NOT EXISTS cadastral_parcels_3d (
    id VARCHAR(64) PRIMARY KEY,                  -- Generated 3D ULPIN / Spatial Hash
    parent_2d_ulpin VARCHAR(32) NOT NULL,        -- Parent 2D Surface Parcel ID
    administrative_area VARCHAR(100),
    crs VARCHAR(20) DEFAULT 'EPSG:4326',
    
    -- Volumetric 3D Geometry (PolyhedralSurfaceZ or MultiPolygonZ)
    geometry_3d GEOMETRY(POLYHEDRALSURFACEZ, 4326),
    
    -- Explicit 3D Bounding Extents
    x_min DOUBLE PRECISION,
    x_max DOUBLE PRECISION,
    y_min DOUBLE PRECISION,
    y_max DOUBLE PRECISION,
    z_min DOUBLE PRECISION,
    z_max DOUBLE PRECISION,
    
    -- Hierarchy & Legal Structure
    parent_building VARCHAR(64),
    parent_floor VARCHAR(32),
    rights JSONB,                                -- Ownership, lease, easement, air rights
    restrictions JSONB,
    responsibilities JSONB,
    
    -- Validation & Confidence
    confidence_score DOUBLE PRECISION,           -- e.g., 0.96 (96%)
    topology_status VARCHAR(20) DEFAULT 'PENDING', -- 'PASS', 'WARNING', 'FAIL'
    
    -- Temporal Versioning
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP WITH TIME ZONE
);

-- 2. Evidence Graph / Provenance Table
CREATE TABLE IF NOT EXISTS evidence_graph (
    id SERIAL PRIMARY KEY,
    parcel_id VARCHAR(64) REFERENCES cadastral_parcels_3d(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,            -- 'LiDAR', 'Drone_DEM', 'FloorPlan', 'CORS'
    horizontal_accuracy_cm DOUBLE PRECISION,     -- e.g., +/- 7 cm
    vertical_accuracy_cm DOUBLE PRECISION,       -- e.g., +/- 5 cm
    reliability_weight DOUBLE PRECISION,         -- w_i factor for data fusion
    survey_timestamp TIMESTAMP WITH TIME ZONE,
    raw_reference_uri TEXT,
    validation_log JSONB
);

-- 3. Create a 3D Spatial Index (GIST) for accelerated queries
CREATE INDEX IF NOT EXISTS idx_cadastral_geom_3d 
ON cadastral_parcels_3d USING GIST (geometry_3d);