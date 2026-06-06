"""User preference domain model."""

from datetime import datetime

from pydantic import BaseModel, Field

from life_agent.models.common import PreferenceCategory, utc_now


class Preference(BaseModel):
    """A key-value preference used by planning and recommendations."""

    id: str | None = None
    category: PreferenceCategory = PreferenceCategory.OTHER
    key: str
    value: str
    created_at: datetime = Field(default_factory=utc_now)
