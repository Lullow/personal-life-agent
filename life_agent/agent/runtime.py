"""Lightweight agent runtime that turns user messages into actionable results.

The runtime sits between the chat UI loop and the service layer.  It calls
:class:`AgentRouter` to classify the message, then dispatches read-only
tools immediately and returns structured results for write/update tools so
the caller can handle the confirmation prompt.

The runtime never writes to the database itself — mutations always flow
back to the caller as ``"needs_confirmation"`` responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from life_agent.agent.decisions import AgentDecision
from life_agent.agent.router import AgentRouter


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


class AgentRuntime:
    """Dispatch an :class:`AgentDecision` to the appropriate service.

    Parameters
    ----------
    router:
        An :class:`AgentRouter` instance.  Defaults to the deterministic
        router with the built-in tool registry.
    db_path:
        Optional database path forwarded to service helpers.
    """

    def __init__(
        self,
        *,
        router: AgentRouter | None = None,
        db_path: str | None = None,
    ) -> None:
        self._router = router or AgentRouter.from_settings()
        self._db_path = db_path

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

        return RuntimeResponse(
            kind="unknown",
            text=decision.user_facing_message or "I am not sure what to do with that yet.",
            decision=decision,
        )

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
