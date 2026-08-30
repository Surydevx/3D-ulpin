import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Strict Environment Fetching (Fail-Closed)
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("CRITICAL: DATABASE_URL environment variable is missing. Halting execution to prevent insecure state.")

# 2. Optimized Concurrency Connection Pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=20,          
    max_overflow=50,       
    pool_timeout=30,       
    pool_recycle=1800      
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()