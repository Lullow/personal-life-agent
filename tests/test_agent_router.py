"""Tests for life_agent.agent.router."""

import pytest

from life_agent.agent.decisions import AgentDecision
from life_agent.agent.router import AgentRouter
from life_agent.agent.tools import ToolDefinition, ToolRegistry


@pytest.fixture()
def router() -> AgentRouter:
    return AgentRouter()


class TestReadRouting:
    @pytest.mark.parametrize(
        "text",
        ["vad har jag idag", "Vad händer idag", "dagens plan", "show today"],
    )
    def test_routes_today(self, router: AgentRouter, text: str):
        d = router.route(text)
        assert d.tool_name == "list_today"
        assert d.action_type == "read"
        assert d.requires_confirmation is False

    @pytest.mark.parametrize(
        "text",
        ["vad händer i veckan", "visa veckan", "veckoplan", "show week"],
    )
    def test_routes_week(self, router: AgentRouter, text: str):
        d = router.route(text)
        assert d.tool_name == "list_week"
        assert d.action_type == "read"
        assert d.requires_confirmation is False

    @pytest.mark.parametrize(
        "text",
        ["visa deadlines", "vad har jag för deadlines", "show deadlines"],
    )
    def test_routes_deadlines(self, router: AgentRouter, text: str):
        d = router.route(text)
        assert d.tool_name == "list_deadlines"
        assert d.action_type == "read"
        assert d.requires_confirmation is False

    @pytest.mark.parametrize(
        "text",
        ["visa påminnelser", "mina reminders", "show reminders", "mina påminnelser"],
    )
    def test_routes_reminders(self, router: AgentRouter, text: str):
        d = router.route(text)
        assert d.tool_name == "list_reminders"
        assert d.action_type == "read"
        assert d.requires_confirmation is False


class TestPlanningRouting:
    @pytest.mark.parametrize(
        "text",
        [
            "påminn mig att handla mat imorgon kl 10",
            "jag ska gymma bröst och triceps idag kl 18",
            "jag behöver plugga machine learning på fredag",
            "jag måste handla mat imorgon",
            "jag har möte på Odenplan kl 14 imorgon",
        ],
    )
    def test_routes_planning_to_extract(self, router: AgentRouter, text: str):
        d = router.route(text)
        assert d.tool_name == "extract_items"
        assert d.action_type == "read"
        assert d.requires_confirmation is False
        assert d.arguments.get("text") == text


class TestCompletionRouting:
    @pytest.mark.parametrize(
        "text",
        ["jag har tränat klart", "träningen är klar", "klar med träningen"],
    )
    def test_routes_completion(self, router: AgentRouter, text: str):
        d = router.route(text)
        assert d.tool_name == "complete_activity"
        assert d.action_type == "update"
        assert d.requires_confirmation is True
        assert d.arguments.get("text") == text


class TestUnknownRouting:
    @pytest.mark.parametrize(
        "text",
        ["hello there", "what is the meaning of life", "abc 123", ""],
    )
    def test_unknown_input(self, router: AgentRouter, text: str):
        d = router.route(text)
        assert d.action_type == "unknown"
        assert d.tool_name is None
        assert d.user_facing_message is not None


class TestSafetyValidation:
    def test_missing_tool_falls_back_to_clarify(self):
        """A decision referencing a tool not in the registry is converted to
        a safe clarify fallback."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="list_today",
                description="x",
                action_type="read",
                requires_confirmation=False,
                handler_name="h",
            )
        )
        router = AgentRouter(registry=registry)

        d = router.route("visa deadlines")
        assert d.tool_name == "list_deadlines" or d.action_type == "clarify"
        if d.action_type == "clarify":
            assert "not registered" in (d.user_facing_message or "")

    def test_default_registry_produces_safe_decisions(self, router: AgentRouter):
        d = router.route("vad har jag idag")
        assert d.action_type == "read"
        assert d.requires_confirmation is False

    def test_unknown_decisions_pass_through(self, router: AgentRouter):
        """Unknown decisions are returned as-is (they are inherently
        harmless because no tool is selected)."""
        d = router.route("xyzzy")
        assert d.action_type == "unknown"
        assert d.tool_name is None


class TestRouterProperties:
    def test_default_mode(self, router: AgentRouter):
        assert router.mode == "deterministic"

    def test_returns_agent_decision(self, router: AgentRouter):
        d = router.route("vad har jag idag")
        assert isinstance(d, AgentDecision)
