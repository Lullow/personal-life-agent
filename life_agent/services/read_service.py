"""Read-only responses the agent can hand back to the user.

Each function renders one view of the database as text.  Nothing here writes,
and nothing here interprets the user's words — the agent decides which view it
wants and with which dates, and the model answers the actual question from the
text these return.
"""

from datetime import date


def get_day_response(day: date, db_path: str | None = None) -> str:
    """Render one calendar day as a timeline, in the order it is lived."""
    from life_agent.cli.formatters import format_daily_agenda
    from life_agent.services.planner_service import get_day_timeline

    return format_daily_agenda(get_day_timeline(day, db_path=db_path))


def get_range_response(start: date, end: date, db_path: str | None = None) -> str:
    """Render every day between two dates, inclusive, as timelines."""
    from life_agent.cli.formatters import format_range_timeline
    from life_agent.services.planner_service import get_range_timeline

    return format_range_timeline(get_range_timeline(start, end, db_path=db_path))


def get_deadlines_response(db_path: str | None = None) -> str:
    """Render pending tasks that have a due date."""
    from life_agent.cli.formatters import format_deadlines
    from life_agent.services.planner_service import get_upcoming_deadlines

    return format_deadlines(get_upcoming_deadlines(db_path=db_path))


def get_reminders_response(db_path: str | None = None) -> str:
    """Render pending reminders, soonest first."""
    from life_agent.cli.formatters import format_reminder_line
    from life_agent.services.reminder_service import (
        list_reminders as svc_list_reminders,
    )

    pending = svc_list_reminders(db_path=db_path)
    if not pending:
        return "No pending reminders."
    return "\n".join(format_reminder_line(r) for r in pending)
