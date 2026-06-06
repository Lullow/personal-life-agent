"""Tests for the CalendarEvent model."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from life_agent.models import CalendarEvent, EventCategory


def test_valid_calendar_event_creation():
    start = datetime(2026, 6, 6, 9, 0)
    end = datetime(2026, 6, 6, 10, 0)
    event = CalendarEvent(
        title="Team standup",
        category=EventCategory.MEETING,
        start_time=start,
        end_time=end,
        location="Office",
    )
    assert event.title == "Team standup"
    assert event.category == EventCategory.MEETING
    assert event.start_time == start
    assert event.end_time == end
    assert event.location == "Office"
    assert event.created_at is not None


def test_calendar_event_rejects_end_time_before_start_time():
    start = datetime(2026, 6, 6, 10, 0)
    end = datetime(2026, 6, 6, 9, 0)
    with pytest.raises(ValidationError):
        CalendarEvent(title="Overlap", start_time=start, end_time=end)
