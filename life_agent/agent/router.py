"""Agent router that classifies a user message into an :class:`AgentDecision`.

The router supports two modes:

* **deterministic** (default) — regex-based intent matching, always available.
* **llm** — future mode that will send the message to an LLM and parse the
  structured JSON response into an ``AgentDecision``.  Not wired up yet.

The deterministic path reuses the same pattern families as
:mod:`life_agent.services.chat_service` but produces ``AgentDecision``
objects instead of ``ChatIntent`` enums, making every decision inspectable
by :func:`life_agent.agent.policy.validate_decision_safety` before
execution.
"""

from __future__ import annotations

import re
from typing import Literal

from life_agent.agent.decisions import AgentDecision
from life_agent.agent.policy import validate_decision_safety
from life_agent.agent.tools import ToolRegistry, build_default_tool_registry
from life_agent.services.completion_service import is_completion_phrase

_TODAY_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bvad\s+har\s+jag\s+idag\b",
        r"\bvad\s+händer\s+idag\b",
        r"\bdagens\s+plan\b",
        r"\bvisa\s+idag\b",
        r"\bshow\s+today\b",
        r"^\s*today\s*[.?!]?\s*$",
        r"^\s*idag\s*[.?!]?\s*$",
    )
]

_WEEK_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bvad\s+händer\s+i\s+veckan\b",
        r"\bvisa\s+veckan\b",
        r"\bveckoplan\b",
        r"\bveckans?\s+plan\b",
        r"\bshow\s+week\b",
        r"\bveckan\b",
    )
]

_DEADLINE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bvisa\s+deadlines?\b",
        r"\bvad\s+har\s+jag\s+för\s+deadlines?\b",
        r"\bdeadlines?\b",
        r"\bshow\s+deadlines?\b",
    )
]

_REMINDER_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bvisa\s+påminnelser\b",
        r"\bmina\s+(?:påminnelser|reminders)\b",
        r"\bvisa\s+reminders\b",
        r"\bshow\s+reminders\b",
        r"\bpåminnelser\b",
    )
]

_PLANNING_MARKERS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bjag\s+ska\b",
        r"\bjag\s+behöver\b",
        r"\bjag\s+måste\b",
        r"\bjag\s+har\s+möte\b",
        r"\bjag\s+vill\b",
        r"\bpåminn\s+mig\b",
        r"\bkom\s+ihåg\b",
        r"\bglöm\s+inte\b",
        r"\bträna\b",
        r"\bgymma\b",
        r"\bmöte\b",
        r"\bplugg",
        r"\bhandla\b",
        r"\bbetala\b",
        r"\bboka\b",
        r"\btandläkare",
        r"\bläkare\b",
    )
]

RoutingMode = Literal["deterministic", "llm"]


class AgentRouter:
    """Classify a user message into an :class:`AgentDecision`.

    Parameters
    ----------
    mode:
        ``"deterministic"`` for regex matching (default and always available),
        ``"llm"`` for future LLM-based routing (not yet wired up).
    registry:
        Tool registry used for validation.  Defaults to the built-in set.
    """

    def __init__(
        self,
        *,
        mode: RoutingMode = "deterministic",
        registry: ToolRegistry | None = None,
    ) -> None:
        self._mode = mode
        self._registry = registry or build_default_tool_registry()

    @property
    def mode(self) -> RoutingMode:
        return self._mode

    def route(self, message: str) -> AgentDecision:
        """Return an :class:`AgentDecision` for *message*."""
        if self._mode == "deterministic":
            decision = self._route_deterministic(message)
        else:
            decision = self._route_deterministic(message)

        return self._validated(decision)

    # ------------------------------------------------------------------
    # Deterministic routing
    # ------------------------------------------------------------------

    def _route_deterministic(self, message: str) -> AgentDecision:
        stripped = message.strip()
        if not stripped:
            return self._unknown(stripped)

        lower = stripped.lower()

        for patterns, tool, intent_label in (
            (_TODAY_PATTERNS, "list_today", "show_today"),
            (_WEEK_PATTERNS, "list_week", "show_week"),
            (_DEADLINE_PATTERNS, "list_deadlines", "show_deadlines"),
            (_REMINDER_PATTERNS, "list_reminders", "show_reminders"),
        ):
            for p in patterns:
                if p.search(lower):
                    return self._read_decision(intent_label, tool)

        if is_completion_phrase(stripped):
            return AgentDecision(
                intent="complete_activity",
                tool_name="complete_activity",
                action_type="update",
                requires_confirmation=True,
                arguments={"text": stripped},
                confidence=1.0,
            )

        if self._looks_like_planning(lower):
            return AgentDecision(
                intent="extract_items",
                tool_name="extract_items",
                action_type="read",
                requires_confirmation=False,
                arguments={"text": stripped},
                confidence=1.0,
            )

        return self._unknown(stripped)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_like_planning(lower: str) -> bool:
        return any(p.search(lower) for p in _PLANNING_MARKERS)

    @staticmethod
    def _read_decision(intent: str, tool_name: str) -> AgentDecision:
        return AgentDecision(
            intent=intent,
            tool_name=tool_name,
            action_type="read",
            requires_confirmation=False,
            confidence=1.0,
        )

    @staticmethod
    def _unknown(text: str) -> AgentDecision:
        return AgentDecision(
            intent="unknown",
            action_type="unknown",
            arguments={"text": text} if text else {},
            user_facing_message="I am not sure what to do with that yet.",
        )

    def _validated(self, decision: AgentDecision) -> AgentDecision:
        """Run safety validation; replace unsafe decisions with a safe fallback."""
        safe, reason = validate_decision_safety(decision, registry=self._registry)
        if safe:
            return decision

        if decision.action_type == "unknown":
            return decision

        return AgentDecision(
            intent="safety_fallback",
            action_type="clarify",
            requires_confirmation=False,
            user_facing_message=f"Decision blocked: {reason}",
            confidence=0.0,
        )
