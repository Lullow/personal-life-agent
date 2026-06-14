"""Deterministic intent classifier and response builder for chat mode.

The chat service takes a single user message and classifies it into one of a
small set of intents.  Read-only intents (TODAY, WEEK, DEADLINES, REMINDERS)
produce a response immediately; write intents (ADD_ITEMS, COMPLETE) return the
classification so the CLI loop can handle the confirmation prompt.

This service never writes to the database.  Persistence always goes through
the existing confirmation / completion services — and only after the user
explicitly confirms.
"""

import re
from enum import StrEnum

from life_agent.services.completion_service import is_completion_phrase


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


# ---------------------------------------------------------------------------
# Pattern groups — order matters: first match wins
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


def classify_intent(text: str) -> ChatIntent:
    """Classify a single user message into a chat intent.

    The function is pure and deterministic — it does not touch the database or
    make any side effects.  The ordering is intentional: slash-commands first,
    then read-only queries (to avoid accidentally routing "visa idag" into
    extraction), then write intents, then fallback.
    """
    stripped = text.strip()
    if not stripped:
        return ChatIntent.UNKNOWN

    lower = stripped.lower()

    if lower in ("/help", "help", "/h"):
        return ChatIntent.HELP
    if lower in ("/quit", "/exit", "quit", "exit"):
        return ChatIntent.QUIT

    # Read-only planner queries (checked before extraction triggers so that
    # short words like "idag" match the planner, not the extractor).
    for p in _TODAY_PATTERNS:
        if p.search(lower):
            return ChatIntent.TODAY
    for p in _WEEK_PATTERNS:
        if p.search(lower):
            return ChatIntent.WEEK
    for p in _DEADLINE_PATTERNS:
        if p.search(lower):
            return ChatIntent.DEADLINES
    for p in _REMINDER_PATTERNS:
        if p.search(lower):
            return ChatIntent.REMINDERS

    if is_completion_phrase(stripped):
        return ChatIntent.COMPLETE

    # Planning phrases that would produce at least one extracted item.
    if _looks_like_planning(lower):
        return ChatIntent.ADD_ITEMS

    return ChatIntent.UNKNOWN


def _looks_like_planning(lower: str) -> bool:
    """Heuristic: does the text look like it would produce extracted items?"""
    planning_markers = (
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
    return any(re.search(m, lower) for m in planning_markers)


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
