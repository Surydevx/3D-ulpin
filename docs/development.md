---
icon: lucide/code
---

# Local Development & Contributing

This guide covers how to set up your local environment to write code, modify the database schema, and run the test suite.

We use `uv` for package management and environment isolation. Do not use standard `pip`, `pipenv`, or `conda` in this repository.

## 1. Environment Setup

Instead of relying on Docker for writing code and running the language server in your IDE, set up a local `.venv` using `uv`.

```bash
# 1. Install uv (if you haven't already)
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh

# 2. Sync dependencies (this automatically creates a .venv)
uv sync

# 3. Activate the virtual environment
source .venv/bin/activate

```

Because we explicitly defined the PyTorch CPU wheels in `pyproject.toml`, this sync will be fast and won't download 3GB of unnecessary CUDA binaries to your local machine.

## 2. Running the Test Suite

We use `pytest` for unit and integration testing. The test suite is designed to run locally without requiring a dedicated GPU or a live connection to PostGIS and Redis (we mock the database sessions and the Celery broker).

```bash
# Run the entire test suite
uv run pytest

# Run tests with verbose output and print statements
uv run pytest -v -s

# Run a specific test file
uv run pytest tests/test_engines.py

```

### Note on Machine Learning Inference

You do not need an NVIDIA GPU to run the tests. The YOLOv8 segmentation and Open3D point cloud logic are bypassed/mocked in the `test_api.py` and `test_engines.py` files to ensure the CI pipeline runs quickly.

## 3. Modifying the Database Schema

If you need to add a new column to a table or create a new PostGIS geometry index, follow these steps:

1. Update the raw SQL definitions in `src/mimi/schema.sql`.
2. Because Docker caches the database initialization, your existing local database will not pick up the changes automatically.
3. You must tear down the local database volume and let Docker rebuild it from scratch:

```bash
# Stop containers and wipe the database volume
docker compose down -v

# Bring the stack back up (this triggers 01_init.sql and schema.sql)
docker compose up -d

```

## 4. Managing Dependencies

If you need to add a new library to the project (e.g., `boto3` for AWS S3 uploads), do not use `pip install`. Use `uv` so it updates the `pyproject.toml` and lockfile automatically.

```bash
# Add a production dependency
uv add boto3

# Add a development dependency (like a new linter)
uv add --dev ruff

# If you manually edit pyproject.toml, regenerate the lockfile
uv lock

```

Always commit the updated `uv.lock` file in your pull request.

## 5. Pull Request Guidelines

Before submitting a PR to the `main` branch:

1. Ensure all tests pass (`uv run pytest`).
2. Verify you haven't added massive binary files (like raw `.ply` scans) to the git history.
3. Select **"Squash and merge"** when closing the PR to keep the `main` branch history clean.
