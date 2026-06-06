"""Application configuration loaded from environment variables."""

import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Minimal settings for the MVP foundation."""

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables with sensible defaults."""
        return cls(
            APP_ENV=os.getenv("APP_ENV", "development"),
            LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        )


def get_settings() -> Settings:
    """Return application settings."""
    return Settings.from_env()
