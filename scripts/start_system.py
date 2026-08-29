import os
import sys
import time
import subprocess
from urllib.parse import urlparse

# --- Configuration ---
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("\n[!] CRITICAL: 'DATABASE_URL' missing. Run with: uv run --env-file .env scripts/start_system.py\n")

parsed_url = urlparse(DATABASE_URL)
APP_USER = parsed_url.username or "ulpin_worker"
APP_PASS = parsed_url.password or "SuperSecretStrongPassword"
DB_NAME = parsed_url.path.lstrip("/") or "ulpin_db"
DB_PORT = str(parsed_url.port or 5432)
ADMIN_PASS = "AdminSuperPassword"

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
SCHEMA_PATH = os.path.join(PROJECT_ROOT, "src", "mimi", "schema.sql")


def run_cmd(cmd: str, bg: bool = False, capture: bool = False):
    """Executes shell commands cleanly."""
    if bg:
        return subprocess.Popen(cmd, shell=True)
    res = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    if not capture and res.returncode != 0:
        sys.exit(f"\n[!] Command failed: {cmd}")
    return res


def ensure_systemd_service(service_name: str):
    """Ensures a Linux systemd service is active."""
    res = run_cmd(f"systemctl is-active --quiet {service_name}", capture=True)
    if res.returncode != 0:
        print(f"  -> Starting {service_name}.service via systemctl...")
        run_cmd(f"sudo systemctl start {service_name}")
    else:
        print(f"  -> {service_name}.service is active.")


def wait_for_postgres(user: str = "postgres", max_retries: int = 20):
    """Waits for PostgreSQL inside Docker to accept queries."""
    for _ in range(max_retries):
        check = run_cmd(f"docker exec mimi-postgis pg_isready -U {user} -d {DB_NAME}", capture=True)
        if check.returncode == 0:
            return True
        time.sleep(1)
    return False


def bootstrap_database():
    """Fully provisions extensions, roles, permissions, and schema automatically."""
    print("  -> First-time setup: provisioning database, extensions, and roles...")
    
    # 1. Enable 3D extensions
    init_sql = f"""
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS postgis_sfcgal;
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{APP_USER}') THEN
            CREATE ROLE {APP_USER} WITH LOGIN PASSWORD '{APP_PASS}';
        END IF;
    END
    $$;
    GRANT CONNECT ON DATABASE {DB_NAME} TO {APP_USER};
    GRANT USAGE, CREATE ON SCHEMA public TO {APP_USER};
    """
    run_cmd(f'docker exec mimi-postgis psql -U postgres -d {DB_NAME} -c "{init_sql}"', capture=True)

    # 2. Apply Schema Tables
    if os.path.exists(SCHEMA_PATH):
        run_cmd(f'docker exec -i mimi-postgis psql -U postgres -d {DB_NAME} < "{SCHEMA_PATH}"', capture=True)
    
    # 3. Lock down permissions (Least-Privilege)
    lockdown_sql = f"""
    ALTER TABLE cadastral_parcels_3d OWNER TO postgres;
    ALTER TABLE evidence_graph OWNER TO postgres;
    REVOKE CREATE ON SCHEMA public FROM {APP_USER};
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_USER};
    GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {APP_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_USER};
    """
    run_cmd(f'docker exec mimi-postgis psql -U postgres -d {DB_NAME} -c "{lockdown_sql}"', capture=True)
    print("  -> Database bootstrapped and secured successfully.")


def ensure_environment():
    print("\n[1/3] Verifying System Services (Docker & Redis)...")
    ensure_systemd_service("docker")
    ensure_systemd_service("redis")

    print("\n[2/3] Verifying PostGIS Container...")
    state = run_cmd("docker inspect -f '{{.State.Running}}' mimi-postgis", capture=True)
    
    if "true" in state.stdout.lower():
        print("  -> PostGIS container is running.")
    elif state.returncode == 0:
        print("  -> Starting existing PostGIS container...")
        run_cmd("docker start mimi-postgis")
        if not wait_for_postgres():
            sys.exit("[!] Database took too long to wake up.")
    else:
        print("  -> Creating fresh PostGIS container with persistent storage...")
        run_cmd(
            f"docker run --name mimi-postgis "
            f"-e POSTGRES_USER=postgres "
            f"-e POSTGRES_PASSWORD={ADMIN_PASS} "
            f"-e POSTGRES_DB={DB_NAME} "
            f"-v mimi-postgis-data:/var/lib/postgresql/data "
            f"-p 127.0.0.1:{DB_PORT}:5432 -d postgis/postgis:latest"
        )
        if not wait_for_postgres():
            sys.exit("[!] Fresh database initialization timed out.")
        bootstrap_database()

    print("  -> PostgreSQL is online and ready.")


def launch_services():
    print("\n[3/3] Launching ML Workers & API Server...")
    python_bin = sys.executable
    
    celery_proc = run_cmd(f"{python_bin} -m celery -A src.mimi.worker.celery_app worker --loglevel=info", bg=True)
    uvicorn_proc = run_cmd(f"{python_bin} -m uvicorn src.mimi.main:app --host 0.0.0.0 --port 8000 --reload", bg=True)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[System Shutdown] Terminating processes...")
        celery_proc.terminate()
        uvicorn_proc.terminate()
        sys.exit(0)


if __name__ == "__main__":
    print("=======================================================")
    print("   HEXCODE 3D CADASTRAL SYSTEM - AUTO ORCHESTRATOR")
    print("=======================================================")
    ensure_environment()
    launch_services()