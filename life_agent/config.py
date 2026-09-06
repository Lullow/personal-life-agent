"""Application configuration loaded from environment variables.

Values are read from the process environment first and from a local ``.env``
file second.  The ``.env`` file is never merged into ``os.environ``: a real
environment variable always wins, and tests neutralise the file entirely (see
``tests/conftest.py``) so a machine with LLM credentials configured behaves
exactly like one without.
"""

import os
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_DB_PATH = Path("data") / "life_agent.db"
DEFAULT_ENV_FILE = Path(".env")

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

_env_file_cache: dict[str, str] | None = None


def parse_env_file(text: str) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines from *text*.

    Blank lines and ``#`` comments are ignored, an optional ``export`` prefix
    is stripped, and a value wrapped in matching quotes is unwrapped.
    """
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def load_env_file(path: str | Path | None = None) -> dict[str, str]:
    """Return the values in the local ``.env`` file, or ``{}`` if absent.

    The default path is read once and cached; an explicit *path* is always
    read fresh and never cached.
    """
    global _env_file_cache
    if path is None and _env_file_cache is not None:
        return _env_file_cache

    env_path = Path(path) if path is not None else DEFAULT_ENV_FILE
    try:
        values = parse_env_file(env_path.read_text(encoding="utf-8"))
    except OSError:
        values = {}

    if path is None:
        _env_file_cache = values
    return values


def env_value(key: str, default: str | None = None) -> str | None:
    """Return *key* from the environment, then ``.env``, then *default*."""
    if key in os.environ:
        return os.environ[key]
    return load_env_file().get(key, default)


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
            APP_ENV=env_value("APP_ENV", "development"),
            LOG_LEVEL=env_value("LOG_LEVEL", "INFO"),
            DB_PATH=env_value("DB_PATH", str(DEFAULT_DB_PATH)),
            LIFE_AGENT_EXTRACTION_MODE=env_value(
                "LIFE_AGENT_EXTRACTION_MODE", EXTRACTION_MODE_DETERMINISTIC
            ),
            LIFE_AGENT_AGENT_ROUTER_MODE=env_value(
                "LIFE_AGENT_AGENT_ROUTER_MODE", ROUTER_MODE_DETERMINISTIC
            ),
            LIFE_AGENT_SAVED_DATA_RESPONSE_MODE=env_value(
                "LIFE_AGENT_SAVED_DATA_RESPONSE_MODE", RESPONSE_MODE_TEMPLATE
            ),
            LIFE_AGENT_CONVERSATION_MODE=env_value(
                "LIFE_AGENT_CONVERSATION_MODE", CONVERSATION_MODE_OFF
            ),
            LIFE_AGENT_LLM_PROVIDER=env_value(
                "LIFE_AGENT_LLM_PROVIDER", "openai_compatible"
            ),
            LIFE_AGENT_LLM_BASE_URL=env_value("LIFE_AGENT_LLM_BASE_URL"),
            LIFE_AGENT_LLM_API_KEY=env_value("LIFE_AGENT_LLM_API_KEY"),
            LIFE_AGENT_LLM_MODEL=env_value("LIFE_AGENT_LLM_MODEL"),
        )


def get_settings() -> Settings:
    """Return application settings."""
    return Settings.from_env()
