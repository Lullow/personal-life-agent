"""Tool definitions and registry for the agent runtime.

A :class:`ToolDefinition` describes a single capability the agent may invoke.
The :class:`ToolRegistry` collects those definitions so the runtime (and
:mod:`life_agent.agent.policy`) can look them up by name.

:func:`build_default_tool_registry` returns a pre-populated registry with the
tools that map to the existing service layer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ToolDefinition(BaseModel):
    """Metadata for a single tool the agent can call."""

    name: str
    description: str
    action_type: Literal["read", "write", "update", "delete", "clarify"]
    requires_confirmation: bool
    handler_name: str


class ToolRegistry:
    """In-memory collection of :class:`ToolDefinition` objects, keyed by name."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def has_tool(self, name: str) -> bool:
        return name in self._tools


_DEFAULT_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="list_today",
        description="Show today's schedule",
        action_type="read",
        requires_confirmation=False,
        handler_name="get_today_response",
    ),
    ToolDefinition(
        name="list_week",
        description="Show this week's schedule",
        action_type="read",
        requires_confirmation=False,
        handler_name="get_week_response",
    ),
    ToolDefinition(
        name="list_day",
        description="Show the schedule for one specific date",
        action_type="read",
        requires_confirmation=False,
        handler_name="get_day_response",
    ),
    ToolDefinition(
        name="list_range",
        description="Show everything scheduled or logged between two dates",
        action_type="read",
        requires_confirmation=False,
        handler_name="get_range_response",
    ),
    ToolDefinition(
        name="list_deadlines",
        description="Show upcoming deadlines",
        action_type="read",
        requires_confirmation=False,
        handler_name="get_deadlines_response",
    ),
    ToolDefinition(
        name="list_reminders",
        description="Show pending reminders",
        action_type="read",
        requires_confirmation=False,
        handler_name="get_reminders_response",
    ),
    ToolDefinition(
        name="list_activities",
        description="Show logged activities",
        action_type="read",
        requires_confirmation=False,
        handler_name="get_activities_response",
    ),
    ToolDefinition(
        name="extract_items",
        description="Extract tasks/events/activities/reminders from text",
        action_type="read",
        requires_confirmation=False,
        handler_name="extract",
    ),
    ToolDefinition(
        name="save_extracted_items",
        description="Save previously extracted items to the database",
        action_type="write",
        requires_confirmation=True,
        handler_name="save_extraction",
    ),
    ToolDefinition(
        name="complete_activity",
        description="Mark a planned activity as completed",
        action_type="update",
        requires_confirmation=True,
        handler_name="complete_activity",
    ),
    ToolDefinition(
        name="ask_clarifying_question",
        description="Ask the user a clarifying question",
        action_type="clarify",
        requires_confirmation=False,
        handler_name="ask_clarification",
    ),
    ToolDefinition(
        name="query_saved_data",
        description="Answer read-only questions about saved reminders, tasks, events, and activities",
        action_type="read",
        requires_confirmation=False,
        handler_name="answer_saved_data_question",
    ),
]


def build_default_tool_registry() -> ToolRegistry:
    """Return a :class:`ToolRegistry` pre-loaded with all built-in tools."""
    registry = ToolRegistry()
    for tool in _DEFAULT_TOOLS:
        registry.register(tool)
    return registry
