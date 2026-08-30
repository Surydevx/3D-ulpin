# Start from a lightweight Python 3.12 image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install system dependencies required for OpenCV and PostGIS
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install the ultra-fast 'uv' package manager
RUN pip install uv

# 1. Copy ONLY dependency files to leverage Docker caching
COPY pyproject.toml uv.lock ./
# Install dependencies but SKIP installing the 'mimi' project folder for now
RUN uv sync --frozen --no-install-project

# 2. Now copy your actual application code
COPY . .
# Sync one last time to install the 'mimi' package itself
RUN uv sync --frozen

# Expose the API port
EXPOSE 8000