"""Tests for the conversational LLM fallback in AgentRuntime.

These tests verify that:
  - Unknown messages use the LLM when conversation mode is on.
  - Unknown messages use the static fallback when conversation mode is off.
  - LLM errors or empty responses gracefully fall back to static text.
  - Known deterministic messages never invoke the conversation LLM.

No real LLM API calls are made — all tests inject a fake client.
"""

import os

import pytest
from typer.testing import CliRunner

from life_agent.agent.runtime import AgentRuntime, _STATIC_UNKNOWN
from life_agent.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def _db_path() -> str:
    return os.environ["DB_PATH"]


# ---------------------------------------------------------------------------
# Fake conversation LLM client
# ---------------------------------------------------------------------------


class FakeConversationClient:
    """Mimics ConversationLLMClient for testing."""

    def __init__(
        self,
        response: str | None = "Hello! How can I help you?",
        raise_on_call: Exception | None = None,
    ):
        self.response = response
        self.raise_on_call = raise_on_call
        self.calls: list[tuple[str, str]] = []

    def generate_text(self, system_prompt: str, user_text: str) -> str | None:
        self.calls.append((system_prompt, user_text))
        if self.raise_on_call is not None:
            raise self.raise_on_call
        return self.response


# ---------------------------------------------------------------------------
# Conversation mode ON — LLM available and working
# ---------------------------------------------------------------------------


class TestConversationModeOn:
    def test_unknown_message_uses_llm(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response="Sure, I'd be happy to chat!")
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        resp = rt.handle_message("hello there friend")
        assert resp.kind == "display"
        assert resp.text == "Sure, I'd be happy to chat!"
        assert len(fake.calls) == 1

    def test_llm_receives_user_message(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response="Got it.")
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        rt.handle_message("  what is the meaning of life  ")
        assert fake.calls[0][1] == "what is the meaning of life"

    def test_llm_receives_system_prompt(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response="Hi!")
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        rt.handle_message("hej")
        system_prompt = fake.calls[0][0]
        assert "personal assistant" in system_prompt.lower()
        assert "cannot" in system_prompt.lower() or "CANNOT" in system_prompt


# ---------------------------------------------------------------------------
# Conversation mode OFF — static fallback
# ---------------------------------------------------------------------------


class TestConversationModeOff:
    def test_unknown_message_returns_static_fallback(self, monkeypatch):
        monkeypatch.delenv("LIFE_AGENT_CONVERSATION_MODE", raising=False)
        fake = FakeConversationClient(response="You should not see me")
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        resp = rt.handle_message("random unknown text")
        assert resp.kind == "unknown"
        assert _STATIC_UNKNOWN in resp.text
        assert len(fake.calls) == 0

    def test_explicit_off_returns_static_fallback(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "off")
        fake = FakeConversationClient(response="Nope")
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        resp = rt.handle_message("xyzzy")
        assert resp.kind == "unknown"
        assert len(fake.calls) == 0


# ---------------------------------------------------------------------------
# Graceful degradation — LLM errors and empty responses
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    def test_llm_raises_exception_falls_back(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(raise_on_call=RuntimeError("API down"))
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        resp = rt.handle_message("random stuff")
        assert resp.kind == "unknown"
        assert _STATIC_UNKNOWN in resp.text

    def test_llm_returns_none_falls_back(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response=None)
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        resp = rt.handle_message("nothing here")
        assert resp.kind == "unknown"
        assert _STATIC_UNKNOWN in resp.text

    def test_llm_returns_empty_string_falls_back(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response="")
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        resp = rt.handle_message("empty response")
        assert resp.kind == "unknown"

    def test_llm_returns_whitespace_only_falls_back(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response="   \n  ")
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        resp = rt.handle_message("whitespace response")
        assert resp.kind == "unknown"


# ---------------------------------------------------------------------------
# Known messages are never sent to the conversation LLM
# ---------------------------------------------------------------------------


class TestKnownMessagesUnaffected:
    def test_today_does_not_call_conversation_llm(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient()
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        resp = rt.handle_message("vad har jag idag")
        assert resp.kind == "display"
        assert resp.decision.tool_name == "list_today"
        assert len(fake.calls) == 0

    def test_planning_does_not_call_conversation_llm(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient()
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        resp = rt.handle_message("påminn mig att handla mat imorgon kl 10")
        assert resp.kind == "needs_confirmation"
        assert len(fake.calls) == 0

    def test_completion_does_not_call_conversation_llm(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient()
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        resp = rt.handle_message("jag har tränat klart")
        assert resp.kind == "needs_confirmation"
        assert len(fake.calls) == 0

    def test_saved_data_query_does_not_call_conversation_llm(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient()
        rt = AgentRuntime(
            db_path=_db_path(),
            conversation_llm_client=fake,
        )

        resp = rt.handle_message("har jag något planerat imorgon")
        assert resp.kind == "display"
        assert resp.decision.tool_name == "query_saved_data"
        assert len(fake.calls) == 0
