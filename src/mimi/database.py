from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://postgres:hexcode_admin@localhost:5432/postgres"

# Systems Upgrade: High-Concurrency Connection Pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=50,          # Keep 50 connections open and ready
    max_overflow=100,      # Allow up to 100 extra connections during massive spikes
    pool_timeout=30,       # Wait up to 30 seconds before timing out
    pool_recycle=1800      # Refresh connections every 30 mins to prevent stale drops
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()