"""Calendar event domain model."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from life_agent.models.common import EventCategory, NonEmptyTitle, utc_now


class CalendarEvent(BaseModel):
    """A scheduled calendar entry with a start time and optional end time."""

    id: str | None = None
    title: NonEmptyTitle
    description: str | None = None
    category: EventCategory = EventCategory.OTHER
    start_time: datetime
    end_time: datetime | None = None
    location: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def end_not_before_start(self) -> Self:
        """Ensure end_time is not earlier than start_time when provided."""
        if self.end_time is not None and self.end_time < self.start_time:
            raise ValueError("end_time must not be before start_time")
        return self
