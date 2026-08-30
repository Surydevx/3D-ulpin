import os
import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# 1. Fail-Closed Environment Fetching
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("CRITICAL: DATABASE_URL missing. Halting database initialization.")

# 2. Dynamic Path Resolution
current_dir = os.path.dirname(os.path.abspath(__file__))
schema_path = os.path.join(current_dir, "schema.sql")

engine = create_engine(DATABASE_URL)

max_retries = 10
retry_delay = 2  # seconds

print("Attempting to connect and initialize database...")

for attempt in range(1, max_retries + 1):
    try:
        with engine.begin() as conn:
            # 1. Ensure PostGIS is active
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_sfcgal;"))
            # 2. Read and execute the schema.sql file
            if os.path.exists(schema_path):
                with open(schema_path, "r") as f:
                    conn.execute(text(f.read()))
                    
                print("✅ PostGIS extension active.")
                print("✅ 3D Cadastre tables and spatial indices created successfully.")
                break  # Success! Exit the retry loop.
            else:
                logging.error(f"Schema file not found at {schema_path}")
                raise FileNotFoundError("CRITICAL: schema.sql is missing.")
                
    except OperationalError as e:
        if attempt == max_retries:
            print(f"❌ CRITICAL: Failed to connect after {max_retries} attempts.")
            raise e
        print(f"   Database restarting/not ready (Attempt {attempt}/{max_retries}). Retrying in {retry_delay}s...")
        time.sleep(retry_delay)