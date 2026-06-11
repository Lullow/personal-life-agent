"""Tests for event repository functions."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from life_agent.db.repositories import create_event, list_events
from life_agent.db.schema import init_db
from life_agent.models import CalendarEvent
from life_agent.models.common import EventCategory


@pytest.fixture()
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "test.db")
        init_db(path)
        yield path


def test_create_event(db_path):
    event = CalendarEvent(
        title="Team standup",
        category=EventCategory.MEETING,
        start_time=datetime(2026, 6, 12, 9, 0),
        end_time=datetime(2026, 6, 12, 9, 30),
        location="Office",
    )
    saved = create_event(event, db_path)
    assert saved.id is not None
    assert saved.title == "Team standup"
    assert saved.category == EventCategory.MEETING
    assert saved.location == "Office"


def test_list_events_ordered_by_start_time(db_path):
    later = CalendarEvent(
        title="Afternoon review",
        start_time=datetime(2026, 6, 12, 15, 0),
    )
    earlier = CalendarEvent(
        title="Morning standup",
        start_time=datetime(2026, 6, 12, 9, 0),
    )
    create_event(later, db_path)
    create_event(earlier, db_path)

    events = list_events(db_path)
    assert len(events) == 2
    assert events[0].title == "Morning standup"
    assert events[1].title == "Afternoon review"


def test_event_roundtrip_preserves_fields(db_path):
    start = datetime(2026, 6, 15, 14, 0)
    end = datetime(2026, 6, 15, 15, 30)
    event = CalendarEvent(
        title="Study session",
        description="Linear algebra revision",
        category=EventCategory.STUDY,
        start_time=start,
        end_time=end,
    )
    saved = create_event(event, db_path)
    fetched = list_events(db_path)
    match = [e for e in fetched if e.id == saved.id][0]
    assert match.description == "Linear algebra revision"
    assert match.category == EventCategory.STUDY
    assert match.start_time == start
    assert match.end_time == end
    assert match.created_at is not None
