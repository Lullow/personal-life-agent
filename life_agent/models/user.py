"""User domain model."""

from datetime import datetime

from pydantic import BaseModel, Field

from life_agent.models.common import utc_now


class User(BaseModel):
    """The primary account holder for the life agent."""

    id: str | None = None
    name: str
    email: str | None = None
    timezone: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
