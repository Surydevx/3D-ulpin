-- ==============================================================================
-- 1. Main 3D Cadastral Entity Table
-- ==============================================================================
CREATE TABLE IF NOT EXISTS cadastral_parcels_3d (
    id VARCHAR(64) PRIMARY KEY,                  -- Generated 3D ULPIN / Spatial Hash
    parent_2d_ulpin VARCHAR(32) NOT NULL,        -- Parent 2D Surface Parcel ID
    administrative_area VARCHAR(100),
    crs VARCHAR(20) DEFAULT 'EPSG:32643',        -- Projected CRS (UTM Zone 43N) for uniform meter measurements
    
    -- Volumetric 3D Geometry
    geometry_3d GEOMETRY(POLYHEDRALSURFACEZ, 32643),
    
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
    topology_status VARCHAR(20) DEFAULT 'PENDING', -- 'PASS', 'WARNING', 'FAIL', 'SPATIAL_CONFLICT'
    
    -- Temporal Versioning
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP WITH TIME ZONE,

    -- Mathematical Sanity Constraints
    CONSTRAINT check_x_bounds CHECK (x_max >= x_min),
    CONSTRAINT check_y_bounds CHECK (y_max >= y_min),
    CONSTRAINT check_z_bounds CHECK (z_max >= z_min)
);

-- ==============================================================================
-- 2. Evidence Graph / Provenance Table
-- ==============================================================================
CREATE TABLE IF NOT EXISTS evidence_graph (
    id SERIAL PRIMARY KEY,
    parcel_id VARCHAR(64) REFERENCES cadastral_parcels_3d(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,            -- 'LiDAR', 'Drone_DEM', 'FloorPlan', 'CORS'
    horizontal_accuracy_cm DOUBLE PRECISION,     -- e.g., +/- 7 cm
    vertical_accuracy_cm DOUBLE PRECISION,       -- e.g., +/- 5 cm
    reliability_weight DOUBLE PRECISION,         -- w_i factor for probabilistic data fusion
    survey_timestamp TIMESTAMP WITH TIME ZONE,
    raw_reference_uri TEXT,                      -- Link to raw point cloud or drone image
    validation_log JSONB                         -- Output from MLCadastralAnomalyDetector
);

-- ==============================================================================
-- 3. High-Performance Spatial and Relational Indices
-- ==============================================================================

-- 3D Spatial Index (GIST) for accelerated volumetric queries and collision detection
CREATE INDEX IF NOT EXISTS idx_cadastral_geom_3d 
ON cadastral_parcels_3d USING GIST (geometry_3d gist_geometry_ops_nd);

-- B-Tree Index to accelerate temporal queries and historical versioning
CREATE INDEX IF NOT EXISTS idx_cadastral_temporal 
ON cadastral_parcels_3d (valid_from, valid_to);

-- B-Tree Index to prevent slow cascading deletes and speed up provenance lookups
CREATE INDEX IF NOT EXISTS idx_evidence_parcel_id 
ON evidence_graph(parcel_id);