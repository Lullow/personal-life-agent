"""Formatting layer for saved-data Q&A results.

This module turns a structured ``SavedDataQueryResult`` into user-facing
plain text.  It has no database access and performs no I/O.
"""

from __future__ import annotations

from datetime import date, timedelta

from life_agent.schemas.saved_data_query import (
    QueryType,
    SavedDataQueryResult,
)


def format_saved_data_query_result(result: SavedDataQueryResult) -> str:
    """Format a ``SavedDataQueryResult`` into the user-facing text answer."""
    if result.query_type == QueryType.REMINDER_LOOKUP:
        return _format_reminder(result)
    if result.query_type == QueryType.PLANNED_TOMORROW:
        return _format_tomorrow(result)
    if result.query_type == QueryType.TRAINING_WEEK:
        return _format_training_week(result)
    return result.fallback_message or "I couldn't find a specific answer for that yet."


# ---------------------------------------------------------------------------
# Per-query-type formatters
# ---------------------------------------------------------------------------


def _format_reminder(result: SavedDataQueryResult) -> str:
    if not result.records and result.fallback_message:
        return result.fallback_message

    if not result.matched:
        lines = [f"  • {r.title} at {r.when}" for r in result.records]
        header = result.fallback_message or "No reminder matched your query."
        return header + " Pending reminders:\n" + "\n".join(lines)

    parts = [
        f"You have a reminder for {r.title} at {r.when}."
        for r in result.records
    ]
    return "\n".join(parts)


def _format_tomorrow(result: SavedDataQueryResult) -> str:
    if not result.matched:
        return result.fallback_message or "Nothing is planned for tomorrow."

    date_str = result.records[0].when or ""
    date_part = date_str.split(" ")[0] if " " in date_str else date_str

    lines: list[str] = []
    for r in result.records:
        label = r.record_type.capitalize()
        if r.when:
            lines.append(f"  • {label}: {r.title} at {r.when}")
        else:
            lines.append(f"  • {label}: {r.title}")

    return f"Planned for tomorrow ({date_part}):\n" + "\n".join(lines)


def _format_training_week(result: SavedDataQueryResult) -> str:
    if not result.matched:
        return result.fallback_message or "No training activities found this week."

    dates = [r.when for r in result.records if r.when]
    if dates:
        parsed = sorted(date.fromisoformat(d) for d in dates)
        week_start = parsed[0] - timedelta(days=parsed[0].weekday())
        week_end = week_start + timedelta(days=6)
        header = f"Training this week ({week_start} – {week_end}):"
    else:
        header = "Training this week:"

    lines = [f"  • {r.title} on {r.when}" for r in result.records]
    return header + "\n" + "\n".join(lines)
