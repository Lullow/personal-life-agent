"""Tests for life_agent.agent.tools."""

from life_agent.agent.tools import (
    ToolDefinition,
    ToolRegistry,
    build_default_tool_registry,
)


class TestToolDefinition:
    def test_creation(self):
        t = ToolDefinition(
            name="list_day",
            description="Show one day",
            action_type="read",
            requires_confirmation=False,
            handler_name="get_day_response",
        )
        assert t.name == "list_day"
        assert t.action_type == "read"
        assert t.requires_confirmation is False


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = ToolDefinition(
            name="my_tool",
            description="test",
            action_type="read",
            requires_confirmation=False,
            handler_name="handler",
        )
        reg.register(tool)
        assert reg.get("my_tool") == tool

    def test_get_missing_returns_none(self):
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_has_tool(self):
        reg = ToolRegistry()
        tool = ToolDefinition(
            name="t",
            description="d",
            action_type="read",
            requires_confirmation=False,
            handler_name="h",
        )
        assert reg.has_tool("t") is False
        reg.register(tool)
        assert reg.has_tool("t") is True

    def test_list_tools(self):
        reg = ToolRegistry()
        assert reg.list_tools() == []
        tool = ToolDefinition(
            name="t",
            description="d",
            action_type="read",
            requires_confirmation=False,
            handler_name="h",
        )
        reg.register(tool)
        assert len(reg.list_tools()) == 1


class TestDefaultRegistry:
    def test_contains_expected_tools(self):
        reg = build_default_tool_registry()
        expected = [
            "list_day",
            "list_range",
            "list_deadlines",
            "list_reminders",
            "save_extracted_items",
            "complete_activity",
            "reschedule_item",
            "delete_item",
            "ask_clarifying_question",
        ]
        for name in expected:
            assert reg.has_tool(name), f"missing tool: {name}"

    def test_list_day_is_read(self):
        reg = build_default_tool_registry()
        t = reg.get("list_day")
        assert t is not None
        assert t.action_type == "read"
        assert t.requires_confirmation is False

    def test_save_extracted_items_requires_confirmation(self):
        reg = build_default_tool_registry()
        t = reg.get("save_extracted_items")
        assert t is not None
        assert t.action_type == "write"
        assert t.requires_confirmation is True

    def test_complete_activity_requires_confirmation(self):
        reg = build_default_tool_registry()
        t = reg.get("complete_activity")
        assert t is not None
        assert t.action_type == "update"
        assert t.requires_confirmation is True

    def test_ask_clarifying_question_no_confirmation(self):
        reg = build_default_tool_registry()
        t = reg.get("ask_clarifying_question")
        assert t is not None
        assert t.action_type == "clarify"
        assert t.requires_confirmation is False

    def test_delete_item_requires_confirmation(self):
        reg = build_default_tool_registry()
        t = reg.get("delete_item")
        assert t is not None
        assert t.action_type == "delete"
        assert t.requires_confirmation is True

    def test_reschedule_item_requires_confirmation(self):
        reg = build_default_tool_registry()
        t = reg.get("reschedule_item")
        assert t is not None
        assert t.action_type == "update"
        assert t.requires_confirmation is True

    def test_no_tool_assumes_a_day(self):
        """A tool that picks the day for you is how "imorgon" got today's plan."""
        reg = build_default_tool_registry()
        assert reg.get("list_today") is None
        assert reg.get("list_week") is None

    def test_tool_count(self):
        reg = build_default_tool_registry()
        assert len(reg.list_tools()) == 9
