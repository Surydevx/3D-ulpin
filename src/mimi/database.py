from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Matches the Docker container credentials
DATABASE_URL = "postgresql://postgres:hexcode_admin@localhost:5432/postgres"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to inject the database session into our FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()