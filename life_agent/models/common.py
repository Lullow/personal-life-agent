"""Shared enums and validation helpers for domain models."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator


class Priority(StrEnum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(StrEnum):
    """Lifecycle status for tasks."""

    PENDING = "pending"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskCategory(StrEnum):
    """Category labels for tasks."""

    STUDY = "study"
    FAMILY = "family"
    HEALTH = "health"
    ERRAND = "errand"
    WORK = "work"
    PERSONAL = "personal"
    MEAL = "meal"
    OTHER = "other"


class EventCategory(StrEnum):
    """Category labels for calendar events."""

    MEETING = "meeting"
    FAMILY = "family"
    STUDY = "study"
    HEALTH = "health"
    PERSONAL = "personal"
    OTHER = "other"


class ActivityType(StrEnum):
    """Types of logged physical or study activities."""

    GYM = "gym"
    WALK = "walk"
    RUN = "run"
    STUDY = "study"
    SPORT = "sport"
    OTHER = "other"


class ReminderStatus(StrEnum):
    """Delivery state for reminders."""

    PENDING = "pending"
    SHOWN = "shown"
    DISMISSED = "dismissed"


class ReminderTargetType(StrEnum):
    """What entity a reminder refers to."""

    TASK = "task"
    EVENT = "event"
    GENERAL = "general"


class MealType(StrEnum):
    """Meal slots in a daily plan."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class PreferenceCategory(StrEnum):
    """Grouping for user preferences."""

    PLANNING = "planning"
    FOOD = "food"
    TRAINING = "training"
    STUDY = "study"
    FAMILY = "family"
    OTHER = "other"


class FamilyRole(StrEnum):
    """Relationship role for a family member."""

    PARTNER = "partner"
    CHILD = "child"
    PARENT = "parent"
    OTHER = "other"


def validate_non_empty_title(value: str) -> str:
    """Strip whitespace and reject empty titles."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("title must not be empty")
    return stripped


def validate_non_negative_minutes(value: int | None) -> int | None:
    """Reject negative minute durations."""
    if value is not None and value < 0:
        raise ValueError("must not be negative")
    return value


def utc_now() -> datetime:
    """Return the current local datetime for model defaults."""
    return datetime.now()


NonEmptyTitle = Annotated[str, BeforeValidator(validate_non_empty_title)]
NonNegativeMinutes = Annotated[int | None, BeforeValidator(validate_non_negative_minutes)]
