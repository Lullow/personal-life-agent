"""Safety policy helpers for agent decisions.

These functions enforce the project's core safety rule:

    Natural language input must not write to the database without explicit
    user confirmation.

They inspect an :class:`~life_agent.agent.decisions.AgentDecision` and
determine whether it is safe to execute.
"""

from __future__ import annotations

from life_agent.agent.decisions import AgentDecision
from life_agent.agent.tools import ToolRegistry

_SAFE_ACTION_TYPES: frozenset[str] = frozenset({"read", "clarify"})
_CONFIRMATION_REQUIRED_TYPES: frozenset[str] = frozenset({"write", "update", "delete"})


def requires_confirmation(action_type: str) -> bool:
    """Return whether *action_type* requires explicit user confirmation."""
    return action_type in _CONFIRMATION_REQUIRED_TYPES


def validate_decision_safety(
    decision: AgentDecision,
    registry: ToolRegistry | None = None,
) -> tuple[bool, str | None]:
    """Check whether *decision* is safe to execute.

    Returns ``(True, None)`` when the decision passes all checks, or
    ``(False, reason)`` with a human-readable explanation when it does not.
    """
    if decision.action_type == "unknown":
        return False, "unknown action type is not safe to execute"

    if decision.action_type in _CONFIRMATION_REQUIRED_TYPES and not decision.requires_confirmation:
        return (
            False,
            f"{decision.action_type} actions must require confirmation",
        )

    if registry is not None and decision.tool_name is not None:
        if not registry.has_tool(decision.tool_name):
            return False, f"tool '{decision.tool_name}' is not registered"

    return True, None
