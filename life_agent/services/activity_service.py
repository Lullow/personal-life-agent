"""Activity service — thin layer between CLI and repository."""

from datetime import datetime

from life_agent.db.repositories import create_activity, list_activities
from life_agent.models import ActivityLog
from life_agent.models.common import ActivityType


def add_activity(
    title: str,
    activity_type: ActivityType = ActivityType.OTHER,
    duration_minutes: int | None = None,
    notes: str | None = None,
    logged_at: datetime | None = None,
    db_path: str | None = None,
) -> ActivityLog:
    fields = {
        "title": title,
        "activity_type": activity_type,
        "duration_minutes": duration_minutes,
        "notes": notes,
    }
    if logged_at is not None:
        fields["logged_at"] = logged_at
    activity = ActivityLog(**fields)
    return create_activity(activity, db_path)


def get_all_activities(db_path: str | None = None) -> list[ActivityLog]:
    return list_activities(db_path)
