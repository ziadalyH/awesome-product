from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields in .env


settings = Settings()

# Ensure OPENAI_API_KEY is set in environment for agents SDK
if settings.OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
