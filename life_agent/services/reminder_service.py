"""Reminder service — thin layer between CLI and repository."""

from datetime import datetime

from life_agent.db.repositories import (
    create_reminder,
    list_reminders as repo_list_reminders,
    list_upcoming_reminders,
    update_reminder_status,
)
from life_agent.models import Reminder
from life_agent.models.common import ReminderStatus, ReminderTargetType


def add_reminder(
    title: str,
    remind_at: datetime,
    target_type: ReminderTargetType = ReminderTargetType.GENERAL,
    target_id: int | None = None,
    message: str | None = None,
    db_path: str | None = None,
) -> Reminder:
    reminder = Reminder(
        title=title,
        remind_at=remind_at,
        target_type=target_type,
        target_id=target_id,
        message=message,
    )
    return create_reminder(reminder, db_path)


def list_reminders(
    status: ReminderStatus | str | None = ReminderStatus.PENDING,
    db_path: str | None = None,
) -> list[Reminder]:
    """List reminders, defaulting to pending only.

    Pass ``status=None`` to include every reminder regardless of status.
    """
    if status is None:
        return repo_list_reminders(status=None, db_path=db_path)
    if status == ReminderStatus.PENDING:
        return list_upcoming_reminders(db_path)
    return repo_list_reminders(status=str(status), db_path=db_path)


def dismiss_reminder(reminder_id: int, db_path: str | None = None) -> Reminder | None:
    """Mark a reminder as dismissed by its database id."""
    return update_reminder_status(
        reminder_id, str(ReminderStatus.DISMISSED), db_path
    )
