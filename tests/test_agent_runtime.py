"""Tests for life_agent.agent.runtime."""

import os

import pytest
from typer.testing import CliRunner

from life_agent.agent.runtime import AgentRuntime
from life_agent.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def _db_path() -> str:
    return os.environ["DB_PATH"]


@pytest.fixture()
def rt() -> AgentRuntime:
    return AgentRuntime(db_path=_db_path())


# ------------------------------------------------------------------
# Read-only dispatches
# ------------------------------------------------------------------


class TestReadDispatches:
    def test_today(self, rt: AgentRuntime):
        resp = rt.handle_message("vad har jag idag")
        assert resp.kind == "display"
        assert "Today" in resp.text
        assert resp.decision.tool_name == "list_today"

    def test_week(self, rt: AgentRuntime):
        resp = rt.handle_message("vad händer i veckan")
        assert resp.kind == "display"
        assert "Week" in resp.text
        assert resp.decision.tool_name == "list_week"

    def test_deadlines(self, rt: AgentRuntime):
        resp = rt.handle_message("visa deadlines")
        assert resp.kind == "display"
        assert resp.decision.tool_name == "list_deadlines"

    def test_reminders(self, rt: AgentRuntime):
        resp = rt.handle_message("visa påminnelser")
        assert resp.kind == "display"
        assert resp.decision.tool_name == "list_reminders"

    def test_read_does_not_require_confirmation(self, rt: AgentRuntime):
        resp = rt.handle_message("vad har jag idag")
        assert resp.decision.requires_confirmation is False


# ------------------------------------------------------------------
# Planning / extraction
# ------------------------------------------------------------------


class TestPlanningDispatch:
    def test_planning_returns_needs_confirmation(self, rt: AgentRuntime):
        resp = rt.handle_message("påminn mig att handla mat imorgon kl 10")
        assert resp.kind == "needs_confirmation"
        assert resp.data["flow"] == "add_items"

    def test_planning_decision_is_extract_items(self, rt: AgentRuntime):
        resp = rt.handle_message("jag ska gymma bröst och triceps idag kl 18")
        assert resp.decision.tool_name == "extract_items"
        assert resp.decision.action_type == "read"


# ------------------------------------------------------------------
# Completion
# ------------------------------------------------------------------


class TestCompletionDispatch:
    def test_completion_returns_needs_confirmation(self, rt: AgentRuntime):
        resp = rt.handle_message("jag har tränat klart")
        assert resp.kind == "needs_confirmation"
        assert resp.data["flow"] == "complete"

    def test_completion_decision_requires_confirmation(self, rt: AgentRuntime):
        resp = rt.handle_message("jag har tränat klart")
        assert resp.decision.tool_name == "complete_activity"
        assert resp.decision.requires_confirmation is True


# ------------------------------------------------------------------
# Unknown
# ------------------------------------------------------------------


class TestUnknownDispatch:
    def test_unknown_returns_unknown_kind(self, rt: AgentRuntime):
        resp = rt.handle_message("hello there")
        assert resp.kind == "unknown"
        assert "not sure" in resp.text.lower()

    def test_empty_returns_unknown(self, rt: AgentRuntime):
        resp = rt.handle_message("")
        assert resp.kind == "unknown"


# ------------------------------------------------------------------
# Router is accessible
# ------------------------------------------------------------------


class TestRouterAccess:
    def test_router_property(self, rt: AgentRuntime):
        assert rt.router.mode == "deterministic"
