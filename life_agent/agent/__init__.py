"""Agent prompts, decisions, tools, and policy helpers."""

from life_agent.agent.decisions import AgentDecision
from life_agent.agent.policy import requires_confirmation, validate_decision_safety
from life_agent.agent.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT_TEMPLATE,
)
from life_agent.agent.tools import (
    ToolDefinition,
    ToolRegistry,
    build_default_tool_registry,
)

__all__ = [
    "EXTRACTION_SYSTEM_PROMPT",
    "EXTRACTION_USER_PROMPT_TEMPLATE",
    "AgentDecision",
    "ToolDefinition",
    "ToolRegistry",
    "build_default_tool_registry",
    "requires_confirmation",
    "validate_decision_safety",
]
