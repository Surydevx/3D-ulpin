import os
import logging
from sqlalchemy import create_engine, text

# 1. Fail-Closed Environment Fetching
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("CRITICAL: DATABASE_URL missing. Halting database initialization.")

# 2. Dynamic Path Resolution
current_dir = os.path.dirname(os.path.abspath(__file__))
schema_path = os.path.join(current_dir, "schema.sql")

engine = create_engine(DATABASE_URL)

with engine.begin() as conn:  # .begin() automatically manages the transaction block
    # 1. Ensure PostGIS is active
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
    
    # 2. Read and execute the schema.sql file
    if os.path.exists(schema_path):
        with open(schema_path, "r") as f:
            # Safely execute the raw SQL string
            conn.execute(text(f.read()))
            
        print("PostGIS extension active.")
        print("3D Cadastre tables and 3D spatial index created successfully.")
    else:
        logging.error(f"Schema file not found at {schema_path}")
        raise FileNotFoundError("CRITICAL: schema.sql is missing.")