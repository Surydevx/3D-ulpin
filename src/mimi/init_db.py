from sqlalchemy import create_engine, text

# Database connection URL (matches your Docker container credentials)
DATABASE_URL = "postgresql://postgres:hexcode_admin@localhost:5432/postgres"

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # 1. Ensure PostGIS extension is active
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
    
    # 2. Read and execute the schema.sql file
    with open("schema.sql", "r") as f:
        conn.execute(text(f.read()))
        
    conn.commit()
    print("PostGIS extension active.")
    print("3D Cadastre tables and 3D spatial index created successfully.")