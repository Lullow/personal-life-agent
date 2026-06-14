"""Agent decision schema for the future AI agent runtime.

An :class:`AgentDecision` represents what the agent *intends* to do in
response to a user message.  It is a structured, validated proposal that
the runtime can inspect before executing — especially to enforce the
confirmation-before-write safety rule.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ACTION_TYPES = ("read", "write", "update", "delete", "clarify", "unknown")
ActionType = Literal["read", "write", "update", "delete", "clarify", "unknown"]

_MUTATING_ACTIONS: frozenset[str] = frozenset({"write", "update", "delete"})


class AgentDecision(BaseModel):
    """A validated proposal describing what the agent wants to do next."""

    intent: str
    tool_name: str | None = None
    action_type: ActionType = "unknown"
    requires_confirmation: bool = False
    arguments: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    user_facing_message: str | None = None

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be between 0 and 1")
        return v

    @property
    def is_mutating(self) -> bool:
        return self.action_type in _MUTATING_ACTIONS
