import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://equitie:equitie@localhost:5432/equitie"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""
    app_env: str = "development"
    data_dir: str = "/app/data"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
