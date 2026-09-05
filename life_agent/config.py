"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_DB_PATH = Path("data") / "life_agent.db"

# Extraction modes
EXTRACTION_MODE_DETERMINISTIC = "deterministic"
EXTRACTION_MODE_LLM = "llm"

# Agent router modes
ROUTER_MODE_DETERMINISTIC = "deterministic"
ROUTER_MODE_LLM = "llm"

# Saved-data response modes
RESPONSE_MODE_TEMPLATE = "template"
RESPONSE_MODE_LLM = "llm"

# Conversation fallback modes
CONVERSATION_MODE_OFF = "off"
CONVERSATION_MODE_ON = "on"


class Settings(BaseModel):
    """Minimal settings for the MVP foundation."""

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    db_path: str = Field(default=str(DEFAULT_DB_PATH), alias="DB_PATH")

    # Natural language extraction
    extraction_mode: str = Field(
        default=EXTRACTION_MODE_DETERMINISTIC,
        alias="LIFE_AGENT_EXTRACTION_MODE",
    )

    # Agent router mode
    agent_router_mode: str = Field(
        default=ROUTER_MODE_DETERMINISTIC,
        alias="LIFE_AGENT_AGENT_ROUTER_MODE",
    )

    # Saved-data response mode
    saved_data_response_mode: str = Field(
        default=RESPONSE_MODE_TEMPLATE,
        alias="LIFE_AGENT_SAVED_DATA_RESPONSE_MODE",
    )

    # Conversational LLM fallback for unknown messages
    conversation_mode: str = Field(
        default=CONVERSATION_MODE_OFF,
        alias="LIFE_AGENT_CONVERSATION_MODE",
    )

    # Optional LLM provider (OpenAI-compatible). Unset by default so the app
    # works fully offline with the deterministic extractor.
    llm_provider: str = Field(
        default="openai_compatible", alias="LIFE_AGENT_LLM_PROVIDER"
    )
    llm_base_url: str | None = Field(default=None, alias="LIFE_AGENT_LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, alias="LIFE_AGENT_LLM_API_KEY")
    llm_model: str | None = Field(default=None, alias="LIFE_AGENT_LLM_MODEL")

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables with sensible defaults."""
        return cls(
            APP_ENV=os.getenv("APP_ENV", "development"),
            LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
            DB_PATH=os.getenv("DB_PATH", str(DEFAULT_DB_PATH)),
            LIFE_AGENT_EXTRACTION_MODE=os.getenv(
                "LIFE_AGENT_EXTRACTION_MODE", EXTRACTION_MODE_DETERMINISTIC
            ),
            LIFE_AGENT_AGENT_ROUTER_MODE=os.getenv(
                "LIFE_AGENT_AGENT_ROUTER_MODE", ROUTER_MODE_DETERMINISTIC
            ),
            LIFE_AGENT_SAVED_DATA_RESPONSE_MODE=os.getenv(
                "LIFE_AGENT_SAVED_DATA_RESPONSE_MODE", RESPONSE_MODE_TEMPLATE
            ),
            LIFE_AGENT_CONVERSATION_MODE=os.getenv(
                "LIFE_AGENT_CONVERSATION_MODE", CONVERSATION_MODE_OFF
            ),
            LIFE_AGENT_LLM_PROVIDER=os.getenv(
                "LIFE_AGENT_LLM_PROVIDER", "openai_compatible"
            ),
            LIFE_AGENT_LLM_BASE_URL=os.getenv("LIFE_AGENT_LLM_BASE_URL"),
            LIFE_AGENT_LLM_API_KEY=os.getenv("LIFE_AGENT_LLM_API_KEY"),
            LIFE_AGENT_LLM_MODEL=os.getenv("LIFE_AGENT_LLM_MODEL"),
        )


def get_settings() -> Settings:
    """Return application settings."""
    return Settings.from_env()
