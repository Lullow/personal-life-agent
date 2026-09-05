"""CLI-level tests proving `python -m life_agent chat` reaches the 18A
conversational LLM fallback via AgentRuntime.

These tests use monkeypatch to inject a fake LLM client into the runtime
that the chat command creates.  No real LLM/API calls are made.
"""

import os
from unittest.mock import patch

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


def _chat(messages: str) -> str:
    """Run the chat command, feeding *messages* as stdin lines."""
    if not messages.endswith("\n"):
        messages += "\n"
    if "/quit" not in messages and "/exit" not in messages:
        messages += "/quit\n"
    result = runner.invoke(app, ["chat"], input=messages)
    assert result.exit_code == 0, result.stdout
    return result.stdout


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


def _patch_runtime_with_fake(fake_client: FakeConversationClient):
    """Patch AgentRuntime.__init__ to inject our fake client."""
    original_init = AgentRuntime.__init__

    def patched_init(self, *, router=None, db_path=None, conversation_llm_client=None):
        original_init(
            self,
            router=router,
            db_path=db_path,
            conversation_llm_client=fake_client,
        )

    return patch.object(AgentRuntime, "__init__", patched_init)


# ---------------------------------------------------------------------------
# Unknown message + conversation mode ON → LLM response shown in CLI
# ---------------------------------------------------------------------------


class TestChatUnknownUsesConversationFallbackWhenEnabled:
    def test_unknown_message_shows_llm_response(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response="Sure, I'd love to chat!")

        with _patch_runtime_with_fake(fake):
            output = _chat("hej allihopa vad gör ni\n")

        assert "Sure, I'd love to chat!" in output
        assert len(fake.calls) == 1

    def test_unknown_message_llm_receives_user_text(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response="Interesting question!")

        with _patch_runtime_with_fake(fake):
            _chat("what is the meaning of life\n")

        assert fake.calls[0][1] == "what is the meaning of life"


# ---------------------------------------------------------------------------
# Unknown message + conversation mode OFF → static fallback
# ---------------------------------------------------------------------------


class TestChatUnknownStaticFallbackWhenConversationModeOff:
    def test_static_fallback_when_mode_off(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "off")
        fake = FakeConversationClient(response="You should not see me")

        with _patch_runtime_with_fake(fake):
            output = _chat("hej allihopa\n")

        assert "not sure" in output.lower()
        assert "You should not see me" not in output
        assert len(fake.calls) == 0

    def test_static_fallback_when_mode_unset(self, monkeypatch):
        monkeypatch.delenv("LIFE_AGENT_CONVERSATION_MODE", raising=False)
        fake = FakeConversationClient(response="Nope")

        with _patch_runtime_with_fake(fake):
            output = _chat("random gibberish xyz\n")

        assert "not sure" in output.lower()
        assert len(fake.calls) == 0


# ---------------------------------------------------------------------------
# Known intents do NOT use conversation fallback
# ---------------------------------------------------------------------------


class TestChatKnownTodayDoesNotUseConversationFallback:
    def test_today_does_not_invoke_llm(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response="LLM should not appear")

        with _patch_runtime_with_fake(fake):
            output = _chat("vad har jag idag\n")

        assert "Today" in output
        assert "LLM should not appear" not in output
        assert len(fake.calls) == 0


# ---------------------------------------------------------------------------
# Planning still requires confirmation (not affected by conversation mode)
# ---------------------------------------------------------------------------


class TestChatPlanningStillRequiresConfirmation:
    def test_planning_asks_confirmation(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response="LLM should not appear")

        with _patch_runtime_with_fake(fake):
            output = _chat("jag ska träna rygg kl 18 imorgon\nn\n")

        assert "Save this?" in output
        assert "Cancelled" in output
        assert "LLM should not appear" not in output
        assert len(fake.calls) == 0


# ---------------------------------------------------------------------------
# Completion still requires confirmation (not affected by conversation mode)
# ---------------------------------------------------------------------------


class TestChatCompletionStillRequiresConfirmation:
    def test_completion_asks_confirmation(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response="LLM should not appear")

        runner.invoke(app, ["add", "--yes", "Jag ska träna gym kl 18 idag"])

        with _patch_runtime_with_fake(fake):
            output = _chat("jag har tränat klart\nn\n")

        assert "Mark this activity as completed?" in output
        assert "Cancelled" in output
        assert "LLM should not appear" not in output
        assert len(fake.calls) == 0


# ---------------------------------------------------------------------------
# Graceful degradation — LLM fails → static fallback in CLI
# ---------------------------------------------------------------------------


class TestChatConversationGracefulDegradation:
    def test_llm_exception_shows_static_fallback(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(raise_on_call=RuntimeError("API down"))

        with _patch_runtime_with_fake(fake):
            output = _chat("some unknown text\n")

        assert "not sure" in output.lower()
        assert len(fake.calls) == 1

    def test_llm_returns_none_shows_static_fallback(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response=None)

        with _patch_runtime_with_fake(fake):
            output = _chat("another unknown text\n")

        assert "not sure" in output.lower()

    def test_llm_returns_empty_shows_static_fallback(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_CONVERSATION_MODE", "on")
        fake = FakeConversationClient(response="")

        with _patch_runtime_with_fake(fake):
            output = _chat("yet another unknown\n")

        assert "not sure" in output.lower()
