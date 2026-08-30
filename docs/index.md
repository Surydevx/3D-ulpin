---
icon: lucide/rocket
---
# 3d ULPIN - A 3D Cadastres System

3D-ULPIN is a spatial computing backend. It provides a robust API to process, store, validate, and retrieve 3D cadastral parcels and their volumetric boundaries.

The entire API backend system is containerized for seamless reproducibility and isolation across different host environments.

## Quick Start

To get the full microservices stack running locally (FastAPI, Redis, PostGIS with SFCGAL, and Celery):

```bash
git clone https://github.com/Surydevx/3D-ulpin.git
cd 3D-ulpin
cp .env.example .env
docker compose up --build
```
