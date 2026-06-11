"""Activity service — thin layer between CLI and repository."""

from datetime import datetime

from life_agent.db.repositories import (
    create_activity,
    list_activities,
    list_planned_activities,
    update_activity_status,
)
from life_agent.models import ActivityLog
from life_agent.models.common import ActivityStatus, ActivityType


def add_activity(
    title: str,
    activity_type: ActivityType = ActivityType.OTHER,
    duration_minutes: int | None = None,
    notes: str | None = None,
    logged_at: datetime | None = None,
    status: ActivityStatus = ActivityStatus.COMPLETED,
    db_path: str | None = None,
) -> ActivityLog:
    fields = {
        "title": title,
        "activity_type": activity_type,
        "status": status,
        "duration_minutes": duration_minutes,
        "notes": notes,
    }
    if logged_at is not None:
        fields["logged_at"] = logged_at
    activity = ActivityLog(**fields)
    return create_activity(activity, db_path)


def get_all_activities(
    status: ActivityStatus | str | None = None,
    db_path: str | None = None,
) -> list[ActivityLog]:
    """Return activities, optionally filtered by status."""
    status_str = str(status) if status is not None else None
    return list_activities(status=status_str, db_path=db_path)


def get_planned_activities(db_path: str | None = None) -> list[ActivityLog]:
    return list_planned_activities(db_path)


def mark_activity_completed(
    activity_id: str,
    db_path: str | None = None,
) -> ActivityLog | None:
    """Mark an activity as completed by its database id."""
    return update_activity_status(
        activity_id, str(ActivityStatus.COMPLETED), db_path
    )
