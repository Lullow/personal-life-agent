"""Schemas for structured extraction output.

These models describe what an LLM (or the deterministic fallback extractor)
returns for a single user utterance.  Extraction is read-only: nothing here
touches the database.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field

from life_agent.models.common import (
    ActivityType,
    EventCategory,
    Priority,
    ReminderTargetType,
    TaskCategory,
)


class ExtractedTask(BaseModel):
    """A task parsed from natural language before confirmation."""

    title: str | None = None
    description: str | None = None
    priority: Priority | None = None
    category: TaskCategory | None = None
    estimated_minutes: int | None = None
    due_date: date | None = None


class ExtractedEvent(BaseModel):
    """A calendar event parsed from natural language before confirmation."""

    title: str | None = None
    description: str | None = None
    category: EventCategory | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = None


class ExtractedActivity(BaseModel):
    """An activity log entry parsed from natural language before confirmation."""

    title: str | None = None
    activity_type: ActivityType | None = None
    duration_minutes: int | None = None
    logged_at: datetime | None = None
    notes: str | None = None


class ExtractedReminder(BaseModel):
    """A reminder parsed from natural language before confirmation."""

    title: str | None = None
    remind_at: datetime | None = None
    target_type: ReminderTargetType | None = None
    notes: str | None = None


class ExtractionResult(BaseModel):
    """Combined extraction output from a single user utterance."""

    tasks: list[ExtractedTask] = Field(default_factory=list)
    events: list[ExtractedEvent] = Field(default_factory=list)
    activities: list[ExtractedActivity] = Field(default_factory=list)
    reminders: list[ExtractedReminder] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    confidence: float | None = None
    raw_text: str | None = None
