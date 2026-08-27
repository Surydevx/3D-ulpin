import subprocess
import time
import os
import sys

def run_command(command, background=False):
    """Executes a shell command safely."""
    print(f"[System Boot] Running: {command}")
    if background:
        return subprocess.Popen(command, shell=True)
    else:
        result = subprocess.run(command, shell=True)
        if result.returncode != 0:
            print(f"[Error] Command failed: {command}")
            sys.exit(1)

def check_redis():
    """Ensures Redis service is active on Arch Linux."""
    print("[1/4] Checking Redis service...")
    # Check if redis is active via systemctl
    res = subprocess.run("systemctl is-active --quiet redis", shell=True)
    if res.returncode != 0:
        print("Starting Redis server...")
        run_command("sudo systemctl start redis")
    else:
        print("Redis is already running.")

def check_postgis_docker():
    """Ensures the PostGIS Docker container is running."""
    print("[2/4] Checking PostGIS Docker container...")
    # Check if container exists and is running
    check_container = subprocess.run("docker inspect -f '{{.State.Running}}' mimi-postgis", shell=True, capture_output=True, text=True)
    
    if check_container.returncode == 0 and "true" in check_container.stdout.lower():
        print("PostGIS container 'mimi-postgis' is already running.")
    else:
        # Check if container exists but is stopped
        exists = subprocess.run("docker inspect mimi-postgis", shell=True, capture_output=True)
        if exists.returncode == 0:
            print("Starting existing PostGIS container...")
            run_command("docker start mimi-postgis")
        else:
            print("Creating and starting new PostGIS container...")
            run_command(
                "docker run --name mimi-postgis "
                "-e POSTGRES_USER=postgres "
                "-e POSTGRES_PASSWORD=hexcode_admin "
                "-e POSTGRES_DB=postgres "
                "-p 5432:5432 -d postgis/postgis:latest"
            )
    
    # Give Postgres a brief second to accept connections
    time.sleep(2)

def start_services():
    """Boots Celery worker and Uvicorn API concurrently."""
    print("[3/4] Initializing Database Schema...")
    run_command("python src/mimi/init_db.py")

    print("[4/4] Launching Background ML Worker & API Server...")
    
    celery_process = None
    uvicorn_process = None
    
    try:
        # Start Celery Worker in the background
        celery_cmd = "python -m celery -A src.mimi.worker.celery_app worker --loglevel=info"
        celery_process = run_command(celery_cmd, background=True)
        
        # Start Uvicorn API Server in the background
        uvicorn_cmd = "uvicorn src.mimi.main:app --host 0.0.0.0 --port 8000 --reload"
        uvicorn_process = run_command(uvicorn_cmd, background=True)
        
        # Keep orchestrator alive and monitor processes
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[System Shutdown] Terminating background processes gracefully...")
        if celery_process:
            celery_process.terminate()
        if uvicorn_process:
            uvicorn_process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    print("=======================================================")
    print("   HEXCODE 3D CADASTRAL SYSTEM - AUTOMATIC ORCHESTRATOR")
    print("=======================================================")
    check_redis()
    check_postgis_docker()
    start_services()