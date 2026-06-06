"""Activity log domain model."""

from datetime import datetime

from pydantic import BaseModel, Field

from life_agent.models.common import (
    ActivityType,
    NonEmptyTitle,
    NonNegativeMinutes,
    utc_now,
)


class ActivityLog(BaseModel):
    """A logged physical or study activity."""

    id: str | None = None
    title: NonEmptyTitle
    activity_type: ActivityType = ActivityType.OTHER
    duration_minutes: NonNegativeMinutes = None
    logged_at: datetime = Field(default_factory=utc_now)
    notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
