"""Reminder domain model."""

from datetime import datetime

from pydantic import BaseModel, Field

from life_agent.models.common import (
    NonEmptyTitle,
    ReminderStatus,
    ReminderTargetType,
    utc_now,
)


class Reminder(BaseModel):
    """A time-based notification linked to a task, event, or general note.

    Reminders use an auto-incrementing integer ``id`` (assigned by SQLite)
    so they can be referenced by short, user-typeable numbers at the CLI.
    """

    id: int | None = None
    title: NonEmptyTitle
    message: str | None = None
    status: ReminderStatus = ReminderStatus.PENDING
    target_type: ReminderTargetType = ReminderTargetType.GENERAL
    target_id: int | None = None
    remind_at: datetime
    created_at: datetime = Field(default_factory=utc_now)
