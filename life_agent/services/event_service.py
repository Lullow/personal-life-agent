"""Event service — thin layer between CLI and repository."""

from datetime import datetime

from life_agent.db.repositories import create_event, list_events
from life_agent.models import CalendarEvent
from life_agent.models.common import EventCategory


def add_event(
    title: str,
    start_time: datetime,
    end_time: datetime | None = None,
    location: str | None = None,
    category: EventCategory = EventCategory.OTHER,
    db_path: str | None = None,
) -> CalendarEvent:
    event = CalendarEvent(
        title=title,
        start_time=start_time,
        end_time=end_time,
        location=location,
        category=category,
    )
    return create_event(event, db_path)


def get_all_events(db_path: str | None = None) -> list[CalendarEvent]:
    return list_events(db_path)
