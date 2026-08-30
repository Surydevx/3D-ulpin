import os
import sys
import time
import subprocess
from urllib.parse import urlparse

# --- 1. Strict Configuration & Validation ---
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_PASS = os.environ.get("POSTGRES_SUPER_PASS")

if not DATABASE_URL or not ADMIN_PASS:
    sys.exit("\n[!] CRITICAL: 'DATABASE_URL' or 'POSTGRES_SUPER_PASS' missing in .env\n")

parsed_url = urlparse(DATABASE_URL)
APP_USER = parsed_url.username or "ulpin_worker"
APP_PASS = parsed_url.password or ""
DB_NAME = parsed_url.path.lstrip("/") or "ulpin_db"
DB_PORT = str(parsed_url.port or 5432)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
SCHEMA_PATH = os.path.join(PROJECT_ROOT, "src", "mimi", "schema.sql")

# --- 2. Secure Subprocess Helpers ---
def run_secure_sql(sql_query: str) -> None:
    """Feeds SQL through STDIN so passwords never appear in the Linux process tree (ps aux)."""
    res = subprocess.run(
        ["docker", "exec", "-i", "mimi-postgis", "psql", "-U", "postgres", "-d", DB_NAME],
        input=sql_query.encode('utf-8'),
        capture_output=True,
    )
    if res.returncode != 0:
        sys.exit(f"\n[!] SQL Execution Failed:\n{res.stderr.decode('utf-8')}")

def ensure_systemd_service(service_name: str) -> None:
    res = subprocess.run(["systemctl", "is-active", "--quiet", service_name])
    if res.returncode != 0:
        print(f"  -> Starting {service_name}.service via systemctl...")
        subprocess.run(["sudo", "systemctl", "start", service_name], check=True)
    else:
        print(f"  -> {service_name}.service is active.")

def wait_for_postgres(user: str = "postgres", max_retries: int = 20) -> bool:
    for _ in range(max_retries):
        res = subprocess.run(
            ["docker", "exec", "mimi-postgis", "pg_isready", "-U", user, "-d", DB_NAME],
            capture_output=True
        )
        if res.returncode == 0:
            return True
        time.sleep(1)
    return False

# --- 3. Database Bootstrapping ---
def bootstrap_database() -> None:
    print("  -> First-time setup: provisioning database, extensions, and roles...")
    
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
    run_secure_sql(init_sql)

    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, 'r') as f:
            run_secure_sql(f.read())
    
    lockdown_sql = f"""
    ALTER TABLE cadastral_parcels_3d OWNER TO postgres;
    ALTER TABLE evidence_graph OWNER TO postgres;
    REVOKE CREATE ON SCHEMA public FROM {APP_USER};
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_USER};
    GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {APP_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_USER};
    """
    run_secure_sql(lockdown_sql)
    print("  -> Database bootstrapped and secured successfully.")

# --- 4. Environment Orchestration ---
def ensure_environment() -> None:
    print("\n[1/3] Verifying System Services (Docker & Redis)...")
    ensure_systemd_service("docker")
    ensure_systemd_service("redis")

    print("\n[2/3] Verifying PostGIS Container...")
    state = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", "mimi-postgis"],
        capture_output=True, text=True
    )
    
    if "true" in state.stdout.lower():
        print("  -> PostGIS container is running.")
    elif state.returncode == 0:
        print("  -> Starting existing PostGIS container...")
        subprocess.run(["docker", "start", "mimi-postgis"], check=True)
        if not wait_for_postgres():
            sys.exit("[!] Database took too long to wake up.")
    else:
        print("  -> Creating fresh PostGIS container with persistent storage...")
        
        # Inject superuser password into environment to prevent CLI exposure
        secure_env = os.environ.copy()
        secure_env["POSTGRES_PASSWORD"] = ADMIN_PASS
        
        subprocess.run([
            "docker", "run", "--name", "mimi-postgis",
            "-e", "POSTGRES_USER=postgres",
            "-e", "POSTGRES_PASSWORD", # Docker reads this from secure_env implicitly!
            "-e", f"POSTGRES_DB={DB_NAME}",
            "-v", "mimi-postgis-data:/var/lib/postgresql/data",
            "-p", f"127.0.0.1:{DB_PORT}:5432",
            "-d", "postgis/postgis:latest"
        ], env=secure_env, check=True)
        
        if not wait_for_postgres():
            sys.exit("[!] Fresh database initialization timed out.")
        bootstrap_database()

    print("  -> PostgreSQL is online and ready.")

# --- 5. Application Launch ---
def launch_services() -> None:
    print("\n[3/3] Launching ML Workers & API Server...")
    python_bin = sys.executable
    
    celery_proc = subprocess.Popen([python_bin, "-m", "celery", "-A", "src.mimi.worker.celery_app", "worker", "--loglevel=info"])
    uvicorn_proc = subprocess.Popen([python_bin, "-m", "uvicorn", "src.mimi.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"])
    
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