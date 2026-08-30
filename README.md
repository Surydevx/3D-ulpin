# 3D ULPIN- A 3D Cadastral System

3D-ULPIN is a spatial computing backend. It provides a robust API to process, store, validate, and retrieve 3D cadastral parcels and their volumetric boundaries.

The entire API backend system is containerized for seamless reproducibility and isolation across different host environments.

It handles varied inputs like raw LiDAR point clouds, aerial drone surveys using a mix of exact geometric computation (EGC) and statistical fusion.

## Project Mechanics

The system relies on five main engines to process and validate data:

* **Spatial Indexing:** We chunk raw point clouds into an in-memory Octree, which keeps spatial query times down to $\mathcal{O}(\log n)$.
* **Bayesian Sensor Fusion:** Sensors lie. When we get conflicting height data (e.g., a drone scan vs. a ground survey), we use inverse-variance Bayesian inference to calculate the actual ground truth and drop the outliers.
* **Anomaly Detection:** An unsupervised Scikit-Learn `IsolationForest` monitors footprint and height variances to flag illegal or anomalous vertical developments.
* **3D ULPIN Generation:** We create deterministic, immutable spatial IDs by combining 3D Morton code bit-shifting with salted SHA-256 checksums.
* **Collision Detection:** Checks if two infrastructure volumes (like a basement and a proposed metro tunnel) intersect. We use Shapely for fast in-memory checks and PostGIS SFCGAL (`ST_3DIntersects`) for persistent database validation.

---

## Tech Stack

* **API & Core:** Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic
* **Async Task Queue:** Celery + Redis
* **Math & ML:** Shapely, Open3D, Scikit-Learn, Ultralytics YOLOv8-Seg
* **Database:** PostgreSQL + PostGIS (with SFCGAL 3D extension)
* **Environment:** `uv` (package management), Docker Compose

---

## API Endpoints

### 1. Synchronous (Immediate Response)

These endpoints handle mathematical computations and database writes on the fly.

| Method | Endpoint | What it does |
| :--- | :--- | :--- |
| `POST` | `/api/v1/cadastre/validate-building` | Takes sensor data and 2D footprints. Computes the real height, runs anomaly checks, generates a 3D ULPIN, and saves a `POLYHEDRALSURFACE Z` to PostGIS. |
| `POST` | `/api/v1/cadastre/check-conflict` | In-memory check to prove two spatial volumes do not intersect. |
| `GET` | `/api/v1/cadastre/db-conflict/{id1}/{id2}` | Asks PostGIS to verify if two saved parcels collide in 3D space. |
| `GET` | `/api/v1/cadastre/parcels` | Returns all 3D parcels as Well-Known Text (WKT) with computed bounding boxes for frontend mapping. |

### 2. Asynchronous (Background Workers)

Heavy processing jobs offloaded to Celery. Submit a file and poll the status using the returned `job_id`.

| Method | Endpoint | What it does |
| :--- | :--- | :--- |
| `POST` | `/api/v1/cadastre/ingest-lidar` | Upload a `.ply` point cloud. Open3D downsamples it, removes the ground plane via RANSAC, and isolates structures with DBSCAN. |
| `POST` | `/api/v1/cadastre/ingest-drone` | Upload a `.jpg`/`.png` drone image. YOLOv8-Seg and the Ramer-Douglas-Peucker algorithm extract the vector footprints. |
| `GET` | `/api/v1/cadastre/job-status/{id}` | Check if your Celery task is `PENDING`, `COMPLETED`, or `FAILED`. |

---

## Local Setup

### 1. Configure the Environment

Clone the repo and set up your environment variables. 

```bash
cp .env.example .env

```

Make sure your `.env` contains:

```env
DATABASE_URL="postgresql://ulpin_worker:SuperSecretStrongPassword@db:5432/ulpin_db"
HEXCODE_SALT="your_secure_random_string"
POSTGRES_SUPER_PASS="AdminSuperPassword"
```

### 2. Boot the Stack

The entire architecture is containerized:

```bash
docker compose up --build
```

This spins up PostgreSQL, Redis, the Celery worker, and the FastAPI server.

* Interactiive API Docs: `http://127.0.0.1:8000/docs`

### 3. Run the Tests

We use `pytest` with mocked database connections and Celery workers to keep tests fast and isolated.

*If running locally outside of Docker:*

```bash
uv sync
uv run --env-file .env pytest -v
```
