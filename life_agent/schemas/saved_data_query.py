"""Schemas for structured saved-data Q&A results (read-only)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class QueryType(StrEnum):
    """Category of a saved-data question."""

    REMINDER_LOOKUP = "reminder_lookup"
    PLANNED_TOMORROW = "planned_tomorrow"
    TRAINING_WEEK = "training_week"
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
