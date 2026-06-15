"""Tests that LIFE_AGENT_AGENT_ROUTER_MODE config flows through to AgentRouter.

These tests verify that:
  - AgentRouter.from_settings() reads the config env var.
  - AgentRuntime uses the configured mode when no router is injected.
  - chat_service._default_router uses from_settings() at import time.
  - Explicitly injected routers still override the config.

No real LLM calls are made.
"""

import importlib

import pytest

from life_agent.agent.router import AgentRouter
from life_agent.agent.runtime import AgentRuntime


# ---------------------------------------------------------------------------
# AgentRouter.from_settings()
# ---------------------------------------------------------------------------


class TestFromSettings:
    def test_default_is_deterministic(self, monkeypatch):
        monkeypatch.delenv("LIFE_AGENT_AGENT_ROUTER_MODE", raising=False)
        r = AgentRouter.from_settings()
        assert r.mode == "deterministic"

    def test_explicit_deterministic(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_AGENT_ROUTER_MODE", "deterministic")
        r = AgentRouter.from_settings()
        assert r.mode == "deterministic"

    def test_llm_mode(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_AGENT_ROUTER_MODE", "llm")
        r = AgentRouter.from_settings()
        assert r.mode == "llm"

    def test_unknown_value_falls_back_to_deterministic(self, monkeypatch):
        monkeypatch.setenv("LIFE_AGENT_AGENT_ROUTER_MODE", "something_else")
        r = AgentRouter.from_settings()
        assert r.mode == "deterministic"


# ---------------------------------------------------------------------------
# AgentRuntime picks up config when no router is injected
# ---------------------------------------------------------------------------


class TestRuntimeWiring:
    def test_runtime_default_uses_deterministic(self, monkeypatch, tmp_path):
        monkeypatch.delenv("LIFE_AGENT_AGENT_ROUTER_MODE", raising=False)
        monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
        rt = AgentRuntime()
        assert rt.router.mode == "deterministic"

    def test_runtime_respects_llm_config(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LIFE_AGENT_AGENT_ROUTER_MODE", "llm")
        monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
        rt = AgentRuntime()
        assert rt.router.mode == "llm"

    def test_injected_router_overrides_config(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LIFE_AGENT_AGENT_ROUTER_MODE", "llm")
        monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
        explicit = AgentRouter(mode="deterministic")
        rt = AgentRuntime(router=explicit)
        assert rt.router.mode == "deterministic"


# ---------------------------------------------------------------------------
# chat_service._default_router uses from_settings() at import time
# ---------------------------------------------------------------------------


class TestChatServiceWiring:
    def test_reimported_module_reads_config(self, monkeypatch):
        """Re-importing chat_service picks up the env var."""
        monkeypatch.setenv("LIFE_AGENT_AGENT_ROUTER_MODE", "llm")
        import life_agent.services.chat_service as mod

        importlib.reload(mod)
        try:
            assert mod._default_router.mode == "llm"
        finally:
            monkeypatch.delenv("LIFE_AGENT_AGENT_ROUTER_MODE", raising=False)
            importlib.reload(mod)

    def test_classify_intent_uses_configured_router(self, monkeypatch):
        """classify_intent accepts an explicit router, proving the DI path."""
        router = AgentRouter(mode="deterministic")
        from life_agent.services.chat_service import ChatIntent, classify_intent

        intent = classify_intent("vad har jag idag", router=router)
        assert intent == ChatIntent.TODAY
