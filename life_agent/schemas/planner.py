"""Schemas for daily and weekly planner output (read-only)."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from life_agent.models import CalendarEvent, Task


class AgendaItemType(StrEnum):
    """Kind of item shown on a daily agenda."""

    TASK = "task"
    EVENT = "event"
    ACTIVITY = "activity"
    MEAL = "meal"
    REMINDER = "reminder"
    OTHER = "other"


class AgendaItem(BaseModel):
    """A single row on a planned daily agenda (generic representation)."""

    title: str
    item_type: AgendaItemType = AgendaItemType.OTHER
    start_time: datetime | None = None
    end_time: datetime | None = None
    source_id: str | None = None
    notes: str | None = None


class DailyAgenda(BaseModel):
    """Ordered agenda for one calendar day (generic AgendaItem rows)."""

    date: date
    items: list[AgendaItem] = Field(default_factory=list)


class DayPlan(BaseModel):
    """Typed events and pending tasks for a single calendar day."""

    date: date
    events: list[CalendarEvent] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)


class TodayAgenda(BaseModel):
    """Today's plan: events, tasks due today, and undated pending tasks."""

    date: date
    events: list[CalendarEvent] = Field(default_factory=list)
    tasks_due_today: list[Task] = Field(default_factory=list)
    undated_tasks: list[Task] = Field(default_factory=list)


class WeekAgenda(BaseModel):
    """Plan spanning a contiguous range of calendar days."""

    start_date: date
    end_date: date
    days: list[DayPlan] = Field(default_factory=list)
