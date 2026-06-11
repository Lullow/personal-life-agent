"""Tests for activity repository functions."""

import tempfile
from pathlib import Path

import pytest

from life_agent.db.repositories import create_activity, list_activities
from life_agent.db.schema import init_db
from life_agent.models import ActivityLog
from life_agent.models.common import ActivityType


@pytest.fixture()
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "test.db")
        init_db(path)
        yield path


def test_create_activity(db_path):
    activity = ActivityLog(
        title="Morning run",
        activity_type=ActivityType.RUN,
        duration_minutes=35,
        notes="Easy pace",
    )
    saved = create_activity(activity, db_path)
    assert saved.id is not None
    assert saved.title == "Morning run"
    assert saved.activity_type == ActivityType.RUN
    assert saved.duration_minutes == 35


def test_list_activities(db_path):
    create_activity(ActivityLog(title="Gym session", activity_type=ActivityType.GYM), db_path)
    create_activity(ActivityLog(title="Evening walk", activity_type=ActivityType.WALK), db_path)

    activities = list_activities(db_path)
    assert len(activities) == 2
    titles = {a.title for a in activities}
    assert titles == {"Gym session", "Evening walk"}


def test_activity_roundtrip_preserves_fields(db_path):
    activity = ActivityLog(
        title="Study algebra",
        activity_type=ActivityType.STUDY,
        duration_minutes=90,
        notes="Chapters 3-4",
    )
    saved = create_activity(activity, db_path)
    fetched = list_activities(db_path)
    match = [a for a in fetched if a.id == saved.id][0]
    assert match.activity_type == ActivityType.STUDY
    assert match.duration_minutes == 90
    assert match.notes == "Chapters 3-4"
    assert match.logged_at is not None
    assert match.created_at is not None
