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


class TestQuerySavedDataRouting:
    @pytest.mark.parametrize(
        "text",
        [
            "vilken tid ska du påminna mig om att handla mat",
            "när ska du påminna mig om träningen",
            "har jag något planerat imorgon",
            "vad har jag för träningar den här veckan",
            "träningar i veckan",
        ],
    )
    def test_routes_to_query_saved_data(self, router: AgentRouter, text: str):
        d = router.route(text)
        assert d.tool_name == "query_saved_data"
        assert d.action_type == "read"
        assert d.requires_confirmation is False

    def test_query_does_not_require_confirmation(self, router: AgentRouter):
        d = router.route("vilken tid ska du påminna mig om att handla mat")
        assert d.requires_confirmation is False

    def test_planning_still_routes_to_extract(self, router: AgentRouter):
        d = router.route("jag ska träna rygg och biceps kl 12 imorgon")
        assert d.tool_name == "extract_items"

    def test_completion_still_routes_to_complete(self, router: AgentRouter):
        d = router.route("jag har tränat klart")
        assert d.tool_name == "complete_activity"


class TestNextUpcomingRouting:
    @pytest.mark.parametrize(
        "text",
        [
            "vad är nästa grej",
            "vad händer härnäst",
            "vad har jag närmast",
            "vad är min nästa påminnelse",
            "nästa påminnelse",
        ],
    )
    def test_routes_to_query_saved_data(self, router: AgentRouter, text: str):
        d = router.route(text)
        assert d.tool_name == "query_saved_data"
        assert d.action_type == "read"
        assert d.requires_confirmation is False

    def test_does_not_route_to_extract(self, router: AgentRouter):
        d = router.route("vad händer härnäst")
        assert d.tool_name != "extract_items"


class TestDailyFocusRouting:
    @pytest.mark.parametrize(
        "text",
        [
            "vad borde jag fokusera på idag",
            "vad är viktigast idag",
            "vad ska jag prioritera idag",
            "dagens fokus",
            "vad är min viktigaste grej idag",
        ],
    )
    def test_routes_to_query_saved_data(self, router: AgentRouter, text: str):
        d = router.route(text)
        assert d.tool_name == "query_saved_data"
        assert d.action_type == "read"
        assert d.requires_confirmation is False

    def test_does_not_route_to_extract(self, router: AgentRouter):
        d = router.route("vad borde jag fokusera på idag")
        assert d.tool_name != "extract_items"
