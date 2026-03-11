from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from erp.backend.core.config import settings

# In production on server, we should use 'localhost' for DB_HOST
# For local dev on Mac, we use the external IP in .env
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
