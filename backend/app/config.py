from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    AGENT_BASE_URL: str = "http://localhost:8001"

    class Config:
        env_file = ".env"


settings = Settings()
