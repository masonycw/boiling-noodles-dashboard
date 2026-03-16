import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env from the backend directory (erp/backend/.env)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

class Settings(BaseSettings):
    PROJECT_NAME: str = "Boiling Noodles ERP"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "changeme")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days for now
    
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    class Config:
        case_sensitive = True

settings = Settings()
