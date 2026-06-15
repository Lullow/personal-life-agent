"""Agent router that classifies a user message into an :class:`AgentDecision`.

The router supports two modes:

* **deterministic** (default) — regex-based intent matching, always available.
* **llm** — sends the message to an LLM for structured routing.  If the LLM
  is unavailable, returns invalid JSON, or produces an unsafe decision, the
  router falls back to deterministic routing automatically.

The deterministic path reuses the same pattern families as
:mod:`life_agent.services.chat_service` but produces ``AgentDecision``
objects instead of ``ChatIntent`` enums, making every decision inspectable
by :func:`life_agent.agent.policy.validate_decision_safety` before
execution.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal, Protocol

from life_agent.agent.decisions import AgentDecision
from life_agent.agent.policy import validate_decision_safety
from life_agent.agent.prompts import ROUTING_SYSTEM_PROMPT, ROUTING_USER_PROMPT_TEMPLATE
from life_agent.agent.tools import ToolRegistry, build_default_tool_registry
from life_agent.services.completion_service import is_completion_phrase
from life_agent.services.saved_data_query_service import detect_saved_data_query_type

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deterministic pattern groups (unchanged from earlier implementation)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# LLM client protocol — anything with extract_structured() works
# ---------------------------------------------------------------------------

RoutingMode = Literal["deterministic", "llm"]


class RoutingLLMClient(Protocol):
    """Minimal interface the router needs from an LLM client."""

    def extract_structured(
        self, system_prompt: str, user_text: str
    ) -> dict[str, Any] | None: ...


# ---------------------------------------------------------------------------
# AgentRouter
# ---------------------------------------------------------------------------


class AgentRouter:
    """Classify a user message into an :class:`AgentDecision`.

    Parameters
    ----------
    mode:
        ``"deterministic"`` for regex matching (default and always available),
        ``"llm"`` to attempt LLM-based routing first (falls back to
        deterministic on any error or unsafe result).
    registry:
        Tool registry used for validation.  Defaults to the built-in set.
    llm_client:
        An object satisfying :class:`RoutingLLMClient`.  When *mode* is
        ``"llm"`` and no client is provided, one is created from the
        application settings.  Inject a fake in tests.
    """

    def __init__(
        self,
        *,
        mode: RoutingMode = "deterministic",
        registry: ToolRegistry | None = None,
        llm_client: RoutingLLMClient | None = None,
    ) -> None:
        self._mode = mode
        self._registry = registry or build_default_tool_registry()
        self._llm_client = llm_client

    @property
    def mode(self) -> RoutingMode:
        return self._mode

    def route(self, message: str) -> AgentDecision:
        """Return an :class:`AgentDecision` for *message*."""
        if self._mode == "llm":
            decision = self._route_llm(message)
            if decision is not None:
                return decision

        decision = self._route_deterministic(message)
        return self._validated(decision)

    # ------------------------------------------------------------------
    # LLM routing
    # ------------------------------------------------------------------

    def _get_llm_client(self) -> RoutingLLMClient | None:
        if self._llm_client is not None:
            return self._llm_client
        try:
            from life_agent.llm.client import LLMClient

            client = LLMClient.from_settings()
            if not client.enabled:
                return None
            self._llm_client = client
            return client
        except Exception:
            return None

    def _route_llm(self, message: str) -> AgentDecision | None:
        """Attempt LLM routing.  Returns ``None`` on any failure."""
        client = self._get_llm_client()
        if client is None:
            return None

        system_prompt = ROUTING_SYSTEM_PROMPT
        user_text = ROUTING_USER_PROMPT_TEMPLATE.format(text=message.strip())

        try:
            raw = client.extract_structured(system_prompt, user_text)
        except Exception:
            log.debug("LLM routing call failed, falling back to deterministic")
            return None

        if raw is None:
            return None

        return self._parse_llm_decision(raw, message)

    def _parse_llm_decision(
        self, raw: dict[str, Any], original_message: str
    ) -> AgentDecision | None:
        """Parse and validate a raw dict from the LLM into an AgentDecision."""
        try:
            intent = str(raw.get("intent", "unknown"))
            tool_name = raw.get("tool_name")
            action_type = raw.get("action_type", "unknown")
            requires_confirmation = bool(raw.get("requires_confirmation", False))
            arguments = raw.get("arguments") or {}
            confidence_raw = raw.get("confidence")
            confidence = float(confidence_raw) if confidence_raw is not None else None
            user_facing_message = raw.get("user_facing_message")

            if confidence is not None and not (0.0 <= confidence <= 1.0):
                confidence = None

            valid_action_types = {"read", "write", "update", "delete", "clarify", "unknown"}
            if action_type not in valid_action_types:
                action_type = "unknown"

            decision = AgentDecision(
                intent=intent,
                tool_name=tool_name,
                action_type=action_type,
                requires_confirmation=requires_confirmation,
                arguments=arguments,
                confidence=confidence,
                user_facing_message=user_facing_message,
            )
        except Exception:
            log.debug("Failed to parse LLM routing response")
            return None

        safe, reason = validate_decision_safety(decision, registry=self._registry)
        if not safe:
            log.debug("LLM decision rejected: %s", reason)
            return None

        return decision

    # ------------------------------------------------------------------
    # Deterministic routing
    # ------------------------------------------------------------------

    def _route_deterministic(self, message: str) -> AgentDecision:
        stripped = message.strip()
        if not stripped:
            return self._unknown(stripped)

        lower = stripped.lower()

        # Saved-data query detection is checked first: these are specific
        # question forms that would otherwise be caught by broader
        # week/planning patterns.  Uses the centralised classifier in
        # saved_data_query_service so patterns are defined once.
        if detect_saved_data_query_type(stripped) != "unknown":
            return AgentDecision(
                intent="query_saved_data",
                tool_name="query_saved_data",
                action_type="read",
                requires_confirmation=False,
                arguments={"text": stripped},
                confidence=1.0,
            )

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
