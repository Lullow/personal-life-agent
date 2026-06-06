"""Task domain model."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from life_agent.models.common import (
    NonEmptyTitle,
    NonNegativeMinutes,
    Priority,
    TaskCategory,
    TaskStatus,
    utc_now,
)


class Task(BaseModel):
    """A single actionable item to complete."""

    id: str | None = None
    title: NonEmptyTitle
    description: str | None = None
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    category: TaskCategory = TaskCategory.OTHER
    estimated_minutes: NonNegativeMinutes = None
    due_date: date | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime | None = None
