---
icon: lucide/terminal
---

# API Reference

The routing layer is split into synchronous fast-paths (database transactions, mathematical verification) and asynchronous worker queues (point cloud segmentation, computer vision inference).

* **Base URL:** `http://localhost:8000/api/v1/cadastre`
* **Interactive OpenAPI (Swagger):** `http://localhost:8000/docs`
* **Raw Schema:** `http://localhost:8000/openapi.json`

> **Note:** All endpoints consume and emit `application/json` by default, except asynchronous ingest routes which accept `multipart/form-data`.

---

## Synchronous Endpoints

### 1. Validate and Register Building

Executes Bayesian sensor height estimation, runs Isolation Forest anomaly detection, generates a deterministic 3D ULPIN, and persists a `POLYHEDRALSURFACE Z` geometry to PostGIS.

* **Method:** `POST`
* **Path:** `/validate-building`
* **Headers:** `Content-Type: application/json`

#### Request Body
```json
{
  "parent_2d_ulpin": "IN-DL-9999",
  "easting_x": 712000.0,
  "northing_y": 3170000.0,
  "footprint_coords": [
    [712000.0, 3170000.0],
    [712050.0, 3170000.0],
    [712050.0, 3170050.0],
    [712000.0, 3170050.0]
  ],
  "registered_height_m": 18.0,
  "sensor_evidence": [
    { "source_name": "Drone_DEM", "height_m": 18.1, "variance": 0.05 },
    { "source_name": "Ground_Survey", "height_m": 18.0, "variance": 0.01 }
  ]
}

```

#### Response (`200 OK`)

```json
{
  "message": "Cadastral unit and evidence graph validated and saved.",
  "ulpin_identity": {
    "ulpin_3d": "IN-DL-9999-Z3891118852878484658-FF9669F4",
    "morton_index": 3891118852878484658,
    "checksum": "FF9669F4"
  },
  "anomaly_report": {
    "status": "VALID",
    "delta_h_m": 0.02,
    "sensor_confidence": 0.9087
  },
  "evidence_records_created": 2
}

```

---

### 2. In-Memory Volumetric Conflict Check

Performs an immediate geometric non-intersection check between two candidate 3D volumes using Shapely planar intersections and vertical Z-interval arithmetic.

* **Method:** `POST`
* **Path:** `/check-conflict`
* **Headers:** `Content-Type: application/json`

#### Request Body

```json
{
  "parcel_a": {
    "footprint_coords": [
      [712000.0, 3170000.0],
      [712050.0, 3170000.0],
      [712050.0, 3170050.0],
      [712000.0, 3170050.0]
    ],
    "z_min": 0.0,
    "z_max": 20.0
  },
  "parcel_b": {
    "footprint_coords": [
      [712025.0, 3170025.0],
      [712075.0, 3170025.0],
      [712075.0, 3170075.0],
      [712025.0, 3170075.0]
    ],
    "z_min": 10.0,
    "z_max": 30.0
  }
}

```

#### Response (`200 OK`)

```json
{
  "conflict": true,
  "overlap_volume_m3": 6250.0,
  "z_overlap": {
    "min": 10.0,
    "max": 20.0
  }
}

```

---

### 3. Database Persistent Conflict Check

Executes a PostGIS SFCGAL query (`ST_3DIntersects`) to test whether two previously stored 3D polyhedral geometries physically collide.

* **Method:** `GET`
* **Path:** `/db-conflict/{id1}/{id2}`

#### Path Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `id1` | `string` | 3D ULPIN identifier of the first parcel |
| `id2` | `string` | 3D ULPIN identifier of the second parcel |

#### Response (`200 OK`)

```json
{
  "ulpin_a": "IN-DL-9999-Z3891118852878484658-FF9669F4",
  "ulpin_b": "IN-DL-9999-Z3891118852878484659-A1B2C3D4",
  "intersects_3d": false
}

```

---

### 4. List 3D Parcels

Retrieves all registered volumetric parcels with precomputed bounding coordinates and Well-Known Text (WKT) geometries for client-side rendering.

* **Method:** `GET`
* **Path:** `/parcels`

#### Response (`200 OK`)

```json
{
  "total_parcels": 1,
  "parcels": [
    {
      "ulpin_3d": "IN-DL-9999-Z3891118852878484658-FF9669F4",
      "parent_2d": "IN-DL-9999",
      "anomaly_status": "VALID",
      "geometry_wkt": "POLYHEDRALSURFACE Z (((712000 3170000 0, 712050 3170000 0, 712050 3170050 0, 712000 3170050 0, 712000 3170000 0)), ...)",
      "bounds": {
        "x_min": 712000.0,
        "x_max": 712050.0,
        "y_min": 3170000.0,
        "y_max": 3170050.0,
        "z_min": 0.0,
        "z_max": 18.02
      }
    }
  ]
}
```

---

## Asynchronous Task Endpoints

Compute-heavy segmentation jobs are offloaded to Celery to prevent event-loop latency.

### 1. Ingest Point Cloud (`.ply`)

Dispatches raw point cloud data for ground plane subtraction (RANSAC) and structural cluster extraction (DBSCAN) using Open3D.

* **Method:** `POST`
* **Path:** `/ingest-lidar`
* **Query Parameters:** `ulpin_id` (`string`, required)
* **Headers:** `Content-Type: multipart/form-data`

#### Form Data

| Key | Type | Description |
| --- | --- | --- |
| `file` | `binary` | Binary `.ply` point cloud file |

#### Response (`200 OK`)

```json
{
  "job_id": "8f3b2d11-5e6a-4d22-b91c-1a2b3c4d5e6f",
  "status_endpoint": "/api/v1/cadastre/job-status/8f3b2d11-5e6a-4d22-b91c-1a2b3c4d5e6f"
}
```

---

### 2. Ingest Aerial Drone Image

Submits aerial orthophotos to YOLOv8-Seg for building mask inference and Ramer-Douglas-Peucker (RDP) footprint simplification.

* **Method:** `POST`
* **Path:** `/ingest-drone`
* **Query Parameters:** `ulpin_id` (`string`, required)
* **Headers:** `Content-Type: multipart/form-data`

#### Form Data

| Key | Type | Description |
| --- | --- | --- |
| `file` | `binary` | Image file (`.jpg` or `.png`) |

#### Response (`200 OK`)

```json
{
  "job_id": "2a4b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d",
  "status_endpoint": "/api/v1/cadastre/job-status/2a4b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d"
}
```

---

### 3. Query Task Status

Polls the task lifecycle state and extracts resultant geometries upon job completion.

* **Method:** `GET`
* **Path:** `/job-status/{job_id}`

#### Response: Task Pending / Running (`200 OK`)

```json
{
  "job_id": "2a4b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d",
  "status": "STARTED",
  "result": null
}

```

#### Response: Task Completed (`200 OK`)

```json
{
  "job_id": "2a4b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d",
  "status": "COMPLETED",
  "result": {
    "extracted_footprint": [
      [712000.0, 3170000.0],
      [712050.0, 3170000.0],
      [712050.0, 3170050.0],
      [712000.0, 3170050.0]
    ],
    "estimated_height_m": 18.04
  }
}
```

#### Response: Task Failed (`200 OK`)

```json
{
  "job_id": "2a4b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d",
  "status": "FAILED",
  "error": "Failed to extract planar geometry from point cloud."
}
```