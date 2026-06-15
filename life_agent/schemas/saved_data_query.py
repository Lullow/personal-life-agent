"""Schemas for structured saved-data Q&A results (read-only)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class QueryType(StrEnum):
    """Category of a saved-data question."""

    REMINDER_LOOKUP = "reminder_lookup"
    PLANNED_TOMORROW = "planned_tomorrow"
    TRAINING_WEEK = "training_week"
    NEXT_UPCOMING = "next_upcoming"
    UNKNOWN = "unknown"


class SavedDataRecord(BaseModel):
    """A single structured fact extracted from the database."""

    record_type: str
    title: str
    when: str | None = None
    status: str | None = None
    details: str | None = None


class SavedDataQueryResult(BaseModel):
    """Structured result for a saved-data question."""

    query_type: QueryType
    question: str
    matched: bool
    records: list[SavedDataRecord] = []
    fallback_message: str | None = None


class SavedDataAnswer(BaseModel):
    """Grounded answer produced from a ``SavedDataQueryResult``.

    This sits between the raw query result and the final plain-text output,
    carrying both the formatted text and metadata about how the answer was
    derived.
    """

    query_type: str
    text: str
    grounded: bool
    matched: bool
    record_count: int
    source_record_types: list[str] = []
    fallback_message: str | None = None
    limitations: list[str] = []
