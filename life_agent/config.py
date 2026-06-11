"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_DB_PATH = Path("data") / "life_agent.db"


class Settings(BaseModel):
    """Minimal settings for the MVP foundation."""

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    db_path: str = Field(default=str(DEFAULT_DB_PATH), alias="DB_PATH")

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables with sensible defaults."""
        return cls(
            APP_ENV=os.getenv("APP_ENV", "development"),
            LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
            DB_PATH=os.getenv("DB_PATH", str(DEFAULT_DB_PATH)),
        )


def get_settings() -> Settings:
    """Return application settings."""
    return Settings.from_env()
