"""Tests for LLM-based routing in AgentRouter.

All tests use a fake LLM client — no real API calls are made.
"""

from __future__ import annotations

from typing import Any

import pytest

from life_agent.agent.router import AgentRouter


class FakeLLMClient:
    """Fake that returns a pre-configured dict (or raises)."""

    def __init__(
        self,
        response: dict[str, Any] | None = None,
        *,
        raise_on_call: Exception | None = None,
    ) -> None:
        self._response = response
        self._raise_on_call = raise_on_call
        self.calls: list[tuple[str, str]] = []

    def extract_structured(
        self, system_prompt: str, user_text: str
    ) -> dict[str, Any] | None:
        self.calls.append((system_prompt, user_text))
        if self._raise_on_call is not None:
            raise self._raise_on_call
        return self._response


# ------------------------------------------------------------------
# Mode defaults
# ------------------------------------------------------------------


class TestModeDefaults:
    def test_default_mode_is_deterministic(self):
        r = AgentRouter()
        assert r.mode == "deterministic"

    def test_deterministic_mode_ignores_llm_client(self):
        fake = FakeLLMClient(response={
            "intent": "show_today",
            "tool_name": "list_today",
            "action_type": "read",
            "requires_confirmation": False,
            "confidence": 0.9,
        })
        r = AgentRouter(mode="deterministic", llm_client=fake)
        r.route("hello there")
        assert fake.calls == []


# ------------------------------------------------------------------
# Valid LLM decisions
# ------------------------------------------------------------------


class TestValidLLMDecisions:
    def test_routes_to_list_today(self):
        fake = FakeLLMClient(response={
            "intent": "show_today",
            "tool_name": "list_today",
            "action_type": "read",
            "requires_confirmation": False,
            "confidence": 0.95,
        })
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("what do I have today")
        assert d.tool_name == "list_today"
        assert d.action_type == "read"
        assert d.requires_confirmation is False
        assert len(fake.calls) == 1

    def test_routes_to_list_reminders(self):
        fake = FakeLLMClient(response={
            "intent": "show_reminders",
            "tool_name": "list_reminders",
            "action_type": "read",
            "requires_confirmation": False,
            "confidence": 0.9,
        })
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("visa påminnelser")
        assert d.tool_name == "list_reminders"

    def test_routes_planning_to_extract_items(self):
        fake = FakeLLMClient(response={
            "intent": "extract_items",
            "tool_name": "extract_items",
            "action_type": "read",
            "requires_confirmation": False,
            "arguments": {"text": "buy groceries tomorrow"},
            "confidence": 0.85,
        })
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("buy groceries tomorrow")
        assert d.tool_name == "extract_items"
        assert d.action_type == "read"

    def test_routes_completion_with_confirmation(self):
        fake = FakeLLMClient(response={
            "intent": "complete_activity",
            "tool_name": "complete_activity",
            "action_type": "update",
            "requires_confirmation": True,
            "confidence": 0.9,
        })
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("jag har tränat klart")
        assert d.tool_name == "complete_activity"
        assert d.requires_confirmation is True

    def test_llm_confidence_is_preserved(self):
        fake = FakeLLMClient(response={
            "intent": "show_today",
            "tool_name": "list_today",
            "action_type": "read",
            "requires_confirmation": False,
            "confidence": 0.42,
        })
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("vad har jag idag")
        assert d.confidence == 0.42


# ------------------------------------------------------------------
# Fallback scenarios
# ------------------------------------------------------------------


class TestLLMFallback:
    def test_invalid_json_falls_back_to_deterministic(self):
        fake = FakeLLMClient(response=None)
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("vad har jag idag")
        assert d.tool_name == "list_today"
        assert d.action_type == "read"

    def test_unknown_tool_falls_back_to_deterministic(self):
        fake = FakeLLMClient(response={
            "intent": "magic",
            "tool_name": "nonexistent_tool",
            "action_type": "read",
            "requires_confirmation": False,
            "confidence": 0.5,
        })
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("vad har jag idag")
        assert d.tool_name == "list_today"

    def test_exception_falls_back_to_deterministic(self):
        fake = FakeLLMClient(raise_on_call=RuntimeError("boom"))
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("visa deadlines")
        assert d.tool_name == "list_deadlines"
        assert len(fake.calls) == 1

    def test_unknown_message_falls_back_to_unknown(self):
        fake = FakeLLMClient(response=None)
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("xyzzy random stuff")
        assert d.action_type == "unknown"


# ------------------------------------------------------------------
# Safety rejection of LLM decisions
# ------------------------------------------------------------------


class TestLLMSafetyRejection:
    def test_write_without_confirmation_rejected(self):
        fake = FakeLLMClient(response={
            "intent": "save",
            "tool_name": "save_extracted_items",
            "action_type": "write",
            "requires_confirmation": False,
            "confidence": 0.8,
        })
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("vad har jag idag")
        assert d.tool_name == "list_today"

    def test_update_without_confirmation_rejected(self):
        fake = FakeLLMClient(response={
            "intent": "complete",
            "tool_name": "complete_activity",
            "action_type": "update",
            "requires_confirmation": False,
            "confidence": 0.8,
        })
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("jag har tränat klart")
        assert d.tool_name == "complete_activity"
        assert d.requires_confirmation is True

    def test_unknown_action_type_rejected(self):
        fake = FakeLLMClient(response={
            "intent": "something",
            "tool_name": "list_today",
            "action_type": "unknown",
            "requires_confirmation": False,
            "confidence": 0.5,
        })
        r = AgentRouter(mode="llm", llm_client=fake)
        d = r.route("vad har jag idag")
        assert d.tool_name == "list_today"
        assert d.action_type == "read"


# ------------------------------------------------------------------
# No real LLM calls
# ------------------------------------------------------------------


class TestNoRealLLMCalls:
    def test_no_network_in_deterministic(self):
        r = AgentRouter(mode="deterministic")
        d = r.route("hello")
        assert d is not None

    def test_fake_client_captures_calls(self):
        fake = FakeLLMClient(response={
            "intent": "x",
            "tool_name": "list_today",
            "action_type": "read",
            "requires_confirmation": False,
            "confidence": 0.9,
        })
        r = AgentRouter(mode="llm", llm_client=fake)
        r.route("test message")
        assert len(fake.calls) == 1
        assert "test message" in fake.calls[0][1]
