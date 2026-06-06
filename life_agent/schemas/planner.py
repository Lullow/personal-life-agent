"""Schemas for daily planning output (no planner logic yet)."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AgendaItemType(StrEnum):
    """Kind of item shown on a daily agenda."""

    TASK = "task"
    EVENT = "event"
    ACTIVITY = "activity"
    MEAL = "meal"
    REMINDER = "reminder"
    OTHER = "other"


class AgendaItem(BaseModel):
    """A single row on a planned daily agenda."""

    title: str
    item_type: AgendaItemType = AgendaItemType.OTHER
    start_time: datetime | None = None
    end_time: datetime | None = None
    source_id: str | None = None
    notes: str | None = None


class DailyAgenda(BaseModel):
    """Ordered agenda for one calendar day."""

    date: date
    items: list[AgendaItem] = Field(default_factory=list)
