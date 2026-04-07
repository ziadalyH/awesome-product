"""Application configuration loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Top-level application settings sourced from the environment or .env file.

    Attributes:
        OPENAI_API_KEY: OpenAI API key forwarded to the agents SDK.
        CORS_ORIGINS: Allowed CORS origins for the FastAPI middleware.
    """

    OPENAI_API_KEY: Optional[str] = None
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields in .env


settings = Settings()

# Ensure OPENAI_API_KEY is set in environment for agents SDK
if settings.OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
