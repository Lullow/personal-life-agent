"""Tests for the ActivityLog model."""

import pytest
from pydantic import ValidationError

from life_agent.models import ActivityLog, ActivityType


def test_valid_activity_log_creation():
    activity = ActivityLog(
        title="Morning run",
        activity_type=ActivityType.RUN,
        duration_minutes=45,
        notes="Felt good",
    )
    assert activity.title == "Morning run"
    assert activity.activity_type == ActivityType.RUN
    assert activity.duration_minutes == 45
    assert activity.notes == "Felt good"
    assert activity.logged_at is not None
    assert activity.created_at is not None


def test_activity_log_rejects_negative_duration_minutes():
    with pytest.raises(ValidationError):
        ActivityLog(title="Stretch", duration_minutes=-10)
