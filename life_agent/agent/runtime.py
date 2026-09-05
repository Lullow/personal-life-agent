"""Lightweight agent runtime that turns user messages into actionable results.

The runtime sits between the chat UI loop and the service layer.  It calls
:class:`AgentRouter` to classify the message, then dispatches read-only
tools immediately and returns structured results for write/update tools so
the caller can handle the confirmation prompt.

When conversation mode is enabled and the router returns an ``"unknown"``
decision, the runtime asks the LLM for a text-only conversational response.
The LLM has no tool access and no database access in this path.

The runtime never writes to the database itself — mutations always flow
back to the caller as ``"needs_confirmation"`` responses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from life_agent.agent.decisions import AgentDecision
from life_agent.agent.router import AgentRouter

log = logging.getLogger(__name__)

ResponseKind = Literal["display", "needs_confirmation", "unknown"]


@dataclass
class RuntimeResponse:
    """Value object returned by :meth:`AgentRuntime.handle_message`."""

    kind: ResponseKind
    text: str
    decision: AgentDecision
    data: dict[str, Any] = field(default_factory=dict)


_READ_DISPATCHERS: dict[str, str] = {
    "list_today": "get_today_response",
    "list_week": "get_week_response",
    "list_deadlines": "get_deadlines_response",
    "list_reminders": "get_reminders_response",
}

_STATIC_UNKNOWN = "I am not sure what to do with that yet."


# ---------------------------------------------------------------------------
# Conversation LLM client protocol — anything with generate_text() works
# ---------------------------------------------------------------------------


class ConversationLLMClient(Protocol):
    """Minimal interface the runtime needs for conversational fallback."""

    def generate_text(
        self, system_prompt: str, user_text: str
    ) -> str | None: ...


class AgentRuntime:
    """Dispatch an :class:`AgentDecision` to the appropriate service.

    Parameters
    ----------
    router:
        An :class:`AgentRouter` instance.  Defaults to the configured
        router from application settings.
    db_path:
        Optional database path forwarded to service helpers.
    conversation_llm_client:
        An object satisfying :class:`ConversationLLMClient`.  Inject a
        fake in tests.  When conversation mode is enabled and no client
        is provided, one is created from application settings.
    """

    def __init__(
        self,
        *,
        router: AgentRouter | None = None,
        db_path: str | None = None,
        conversation_llm_client: ConversationLLMClient | None = None,
    ) -> None:
        self._router = router or AgentRouter.from_settings()
        self._db_path = db_path
        self._conversation_llm_client = conversation_llm_client

    @property
    def router(self) -> AgentRouter:
        return self._router

    def handle_message(self, message: str) -> RuntimeResponse:
        """Route *message* and return a :class:`RuntimeResponse`."""
        decision = self._router.route(message)

        tool = decision.tool_name

        if tool in _READ_DISPATCHERS:
            text = self._dispatch_read(tool)
            return RuntimeResponse(kind="display", text=text, decision=decision)

        if tool == "query_saved_data":
            from life_agent.services.saved_data_query_service import answer_saved_data_question

            text = answer_saved_data_question(message, db_path=self._db_path)
            return RuntimeResponse(kind="display", text=text, decision=decision)

        if tool == "extract_items":
            return RuntimeResponse(
                kind="needs_confirmation",
                text="",
                decision=decision,
                data={"flow": "add_items", "text": decision.arguments.get("text", message.strip())},
            )

        if tool == "complete_activity":
            return RuntimeResponse(
                kind="needs_confirmation",
                text="",
                decision=decision,
                data={"flow": "complete", "text": decision.arguments.get("text", message.strip())},
            )

        # Unknown decision — try conversational LLM fallback if enabled.
        fallback_text = decision.user_facing_message or _STATIC_UNKNOWN
        conv_text = self._try_conversation_fallback(message)
        if conv_text is not None:
            return RuntimeResponse(kind="display", text=conv_text, decision=decision)

        return RuntimeResponse(kind="unknown", text=fallback_text, decision=decision)

    # ------------------------------------------------------------------
    # Conversational LLM fallback
    # ------------------------------------------------------------------

    def _try_conversation_fallback(self, message: str) -> str | None:
        """Ask the LLM for a conversational text response.

        Returns ``None`` when conversation mode is off, the LLM is
        unavailable, or the response is empty/invalid — so the caller
        can fall back to the static unknown text.
        """
        if not self._is_conversation_mode_on():
            return None

        client = self._get_conversation_client()
        if client is None:
            return None

        from life_agent.agent.prompts import CONVERSATION_SYSTEM_PROMPT

        try:
            text = client.generate_text(CONVERSATION_SYSTEM_PROMPT, message.strip())
        except Exception:
            log.debug("Conversation LLM call failed, using static fallback")
            return None

        if not text or not text.strip():
            return None

        return text.strip()

    @staticmethod
    def _is_conversation_mode_on() -> bool:
        from life_agent.config import get_settings

        return get_settings().conversation_mode == "on"

    def _get_conversation_client(self) -> ConversationLLMClient | None:
        if self._conversation_llm_client is not None:
            return self._conversation_llm_client
        try:
            from life_agent.llm.client import LLMClient

            client = LLMClient.from_settings()
            if not client.enabled:
                return None
            self._conversation_llm_client = client
            return client
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Read dispatchers
    # ------------------------------------------------------------------

    def _dispatch_read(self, tool_name: str) -> str:
        from life_agent.services.chat_service import (
            get_deadlines_response,
            get_reminders_response,
            get_today_response,
            get_week_response,
        )

        handlers = {
            "list_today": get_today_response,
            "list_week": get_week_response,
            "list_deadlines": get_deadlines_response,
            "list_reminders": get_reminders_response,
        }
        handler = handlers[tool_name]
        return handler(db_path=self._db_path)
