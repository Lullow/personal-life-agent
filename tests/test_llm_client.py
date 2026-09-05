"""Tests for the OpenAI-compatible LLM client wrapper.

These tests never make a real network call: the low-level ``_chat_completion``
(or ``_post``) is monkeypatched so we exercise enable/disable logic and JSON
parsing only.
"""

import pytest

from life_agent.config import Settings
from life_agent.llm.client import LLMClient, _extract_json

_LLM_ENV_VARS = (
    "LIFE_AGENT_LLM_API_KEY",
    "LIFE_AGENT_LLM_BASE_URL",
    "LIFE_AGENT_LLM_MODEL",
    "LIFE_AGENT_LLM_PROVIDER",
)


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch):
    """Ensure ambient LLM_* env vars never leak into these tests."""
    for var in _LLM_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


VALID_JSON = (
    '{"tasks": [], "events": [], "activities": [], '
    '"reminders": [], "questions": [], "confidence": 0.9}'
)


def _enabled_client() -> LLMClient:
    return LLMClient(api_key="k", base_url="http://example.test/v1", model="m")


# ---------------------------------------------------------------------------
# enable / disable logic
# ---------------------------------------------------------------------------


def test_client_disabled_without_configuration():
    client = LLMClient()
    assert client.enabled is False
    assert client.extract_structured("sys", "hello") is None


def test_client_enabled_when_fully_configured():
    client = _enabled_client()
    assert client.enabled is True


def test_explicit_enabled_overrides_detection():
    client = LLMClient(enabled=True)
    assert client.enabled is True


def test_from_settings_builds_enabled_client():
    settings = Settings(
        LIFE_AGENT_LLM_API_KEY="k",
        LIFE_AGENT_LLM_BASE_URL="http://example.test/v1",
        LIFE_AGENT_LLM_MODEL="my-model",
    )
    client = LLMClient.from_settings(settings)
    assert client.enabled is True
    assert client.model == "my-model"


def test_from_settings_disabled_without_keys():
    client = LLMClient.from_settings(Settings())
    assert client.enabled is False


# ---------------------------------------------------------------------------
# extract_structured behaviour
# ---------------------------------------------------------------------------


def test_extract_structured_parses_valid_json(monkeypatch):
    client = _enabled_client()
    monkeypatch.setattr(client, "_chat_completion", lambda s, u, **kw: VALID_JSON)
    data = client.extract_structured("sys", "user")
    assert isinstance(data, dict)
    assert data["confidence"] == 0.9
    assert data["tasks"] == []


def test_extract_structured_strips_code_fences(monkeypatch):
    client = _enabled_client()
    fenced = "```json\n" + VALID_JSON + "\n```"
    monkeypatch.setattr(client, "_chat_completion", lambda s, u, **kw: fenced)
    data = client.extract_structured("sys", "user")
    assert isinstance(data, dict)
    assert data["confidence"] == 0.9


def test_extract_structured_invalid_json_returns_none(monkeypatch):
    client = _enabled_client()
    monkeypatch.setattr(client, "_chat_completion", lambda s, u, **kw: "not json at all")
    assert client.extract_structured("sys", "user") is None


def test_extract_structured_network_error_returns_none(monkeypatch):
    client = _enabled_client()

    def boom(system_prompt, user_text, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(client, "_chat_completion", boom)
    assert client.extract_structured("sys", "user") is None


def test_extract_structured_disabled_short_circuits(monkeypatch):
    client = LLMClient()  # disabled

    def fail(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("disabled client must not call the network")

    monkeypatch.setattr(client, "_chat_completion", fail)
    assert client.extract_structured("sys", "user") is None


def test_chat_completion_reads_message_content(monkeypatch):
    client = _enabled_client()
    captured: dict = {}

    def fake_post(url, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {"choices": [{"message": {"content": VALID_JSON}}]}

    monkeypatch.setattr(client, "_post", fake_post)
    content = client._chat_completion("sys", "user", json_mode=True)
    assert content == VALID_JSON
    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["model"] == "m"
    assert captured["payload"]["response_format"] == {"type": "json_object"}


# ---------------------------------------------------------------------------
# _extract_json helper
# ---------------------------------------------------------------------------


def test_extract_json_handles_surrounding_prose():
    text = 'Sure! Here you go:\n{"a": 1}\nHope that helps.'
    assert _extract_json(text) == {"a": 1}


def test_extract_json_returns_none_for_non_object():
    assert _extract_json("[1, 2, 3]") is None
    assert _extract_json("") is None
    assert _extract_json(None) is None
