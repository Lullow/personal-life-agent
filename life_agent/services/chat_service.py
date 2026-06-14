"""Deterministic intent classifier and response builder for chat mode.

The chat service takes a single user message and classifies it into one of a
small set of intents.  Slash commands (/help, /quit, /exit) are handled
directly; everything else is delegated to :class:`AgentRouter` so that the
routing logic is shared with the agent runtime.

This service never writes to the database.  Persistence always goes through
the existing confirmation / completion services — and only after the user
explicitly confirms.
"""

from __future__ import annotations

from enum import StrEnum

from life_agent.agent.router import AgentRouter


class ChatIntent(StrEnum):
    """Possible intent categories recognised by the chat router."""

    HELP = "help"
    QUIT = "quit"
    TODAY = "today"
    WEEK = "week"
    DEADLINES = "deadlines"
    REMINDERS = "reminders"
    ADD_ITEMS = "add_items"
    COMPLETE = "complete"
    UNKNOWN = "unknown"


_TOOL_TO_INTENT: dict[str | None, ChatIntent] = {
    "list_today": ChatIntent.TODAY,
    "list_week": ChatIntent.WEEK,
    "list_deadlines": ChatIntent.DEADLINES,
    "list_reminders": ChatIntent.REMINDERS,
    "extract_items": ChatIntent.ADD_ITEMS,
    "complete_activity": ChatIntent.COMPLETE,
}

_default_router = AgentRouter()


def classify_intent(text: str, *, router: AgentRouter | None = None) -> ChatIntent:
    """Classify a single user message into a chat intent.

    Slash commands are handled locally; everything else is delegated to the
    :class:`AgentRouter` so that the routing patterns are defined in one place.
    """
    stripped = text.strip()
    if not stripped:
        return ChatIntent.UNKNOWN

    lower = stripped.lower()

    if lower in ("/help", "help", "/h"):
        return ChatIntent.HELP
    if lower in ("/quit", "/exit", "quit", "exit"):
        return ChatIntent.QUIT

    r = router or _default_router
    decision = r.route(stripped)

    return _TOOL_TO_INTENT.get(decision.tool_name, ChatIntent.UNKNOWN)


# ---------------------------------------------------------------------------
# Responses for read-only intents
# ---------------------------------------------------------------------------

GREETING = (
    "Hello! I am your personal life agent.\n"
    "Type a message, or /help for available commands."
)

HELP_TEXT = (
    "Available commands:\n"
    "  /help          Show this help\n"
    "  /quit          Exit chat mode\n"
    "\n"
    "You can also type naturally:\n"
    '  "vad har jag idag"          Show today\'s agenda\n'
    '  "vad händer i veckan"       Show this week\'s plan\n'
    '  "visa deadlines"            Show upcoming deadlines\n'
    '  "visa påminnelser"          Show pending reminders\n'
    '  "jag ska träna kl 18"       Plan a new item (asks to save)\n'
    '  "jag har tränat klart"      Mark an activity as completed\n'
)

UNKNOWN_TEXT = (
    "I am not sure what to do with that yet.\n"
    "\n"
    "Try something like:\n"
    '  "vad har jag idag"\n'
    '  "jag ska träna rygg och biceps kl 12 imorgon"\n'
    '  "påminn mig att handla mat imorgon kl 10"\n'
    '  "jag har tränat klart"\n'
    "Or type /help for more options."
)


def get_today_response(db_path: str | None = None) -> str:
    from life_agent.cli.formatters import format_today_agenda
    from life_agent.services.planner_service import get_today_agenda

    return format_today_agenda(get_today_agenda(db_path=db_path))


def get_week_response(db_path: str | None = None) -> str:
    from life_agent.cli.formatters import format_week_agenda
    from life_agent.services.planner_service import get_week_agenda

    return format_week_agenda(get_week_agenda(db_path=db_path))


def get_deadlines_response(db_path: str | None = None) -> str:
    from life_agent.cli.formatters import format_deadlines
    from life_agent.services.planner_service import get_upcoming_deadlines

    return format_deadlines(get_upcoming_deadlines(db_path=db_path))


def get_reminders_response(db_path: str | None = None) -> str:
    from life_agent.cli.formatters import format_reminder_line
    from life_agent.services.reminder_service import (
        list_reminders as svc_list_reminders,
    )

    pending = svc_list_reminders(db_path=db_path)
    if not pending:
        return "No pending reminders."
    return "\n".join(format_reminder_line(r) for r in pending)
