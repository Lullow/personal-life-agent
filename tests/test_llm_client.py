"""Tests for the OpenAI-compatible LLM client wrapper.

These tests never make a real network call: the low-level transport is
monkeypatched so we exercise enable/disable logic and JSON parsing only.
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


VALID_JSON = '{"tool": "list_day", "arguments": {"date": "2026-09-07"}, "reply": "Kollar."}'

MESSAGES = [{"role": "user", "content": "vad har jag imorgon?"}]


def _enabled_client() -> LLMClient:
    return LLMClient(api_key="k", base_url="http://example.test/v1", model="m")


# ---------------------------------------------------------------------------
# enable / disable logic
# ---------------------------------------------------------------------------


def test_client_disabled_without_configuration():
    client = LLMClient()
    assert client.enabled is False
    assert client.chat_json("sys", MESSAGES) is None


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
# chat_json behaviour
# ---------------------------------------------------------------------------


def test_chat_json_parses_valid_json(monkeypatch):
    client = _enabled_client()
    monkeypatch.setattr(client, "_chat_completion_messages", lambda s, m, **kw: VALID_JSON)
    data = client.chat_json("sys", MESSAGES)
    assert data["tool"] == "list_day"
    assert data["arguments"]["date"] == "2026-09-07"


def test_chat_json_strips_code_fences(monkeypatch):
    client = _enabled_client()
    fenced = "```json\n" + VALID_JSON + "\n```"
    monkeypatch.setattr(client, "_chat_completion_messages", lambda s, m, **kw: fenced)
    assert client.chat_json("sys", MESSAGES)["tool"] == "list_day"


def test_chat_json_invalid_json_returns_none(monkeypatch):
    client = _enabled_client()
    monkeypatch.setattr(
        client, "_chat_completion_messages", lambda s, m, **kw: "not json at all"
    )
    assert client.chat_json("sys", MESSAGES) is None


def test_chat_json_network_error_returns_none(monkeypatch):
    client = _enabled_client()

    def boom(system_prompt, messages, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(client, "_chat_completion_messages", boom)
    assert client.chat_json("sys", MESSAGES) is None


def test_chat_json_disabled_short_circuits(monkeypatch):
    client = LLMClient()  # disabled

    def fail(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("disabled client must not call the network")

    monkeypatch.setattr(client, "_chat_completion_messages", fail)
    assert client.chat_json("sys", MESSAGES) is None


def test_the_conversation_is_sent_after_the_system_prompt(monkeypatch):
    client = _enabled_client()
    captured: dict = {}

    def fake_post(url, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {"choices": [{"message": {"content": VALID_JSON}}]}

    monkeypatch.setattr(client, "_post", fake_post)
    history = [
        {"role": "user", "content": "vad har jag idag?"},
        {"role": "assistant", "content": "Inget."},
        {"role": "user", "content": "och imorgon då?"},
    ]
    assert client.chat_json("sys", history)["tool"] == "list_day"

    sent = captured["payload"]["messages"]
    assert sent[0] == {"role": "system", "content": "sys"}
    assert sent[1:] == history
    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["temperature"] == 0


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
