"""Family member domain model."""

from datetime import datetime

from pydantic import BaseModel, Field

from life_agent.models.common import FamilyRole, utc_now


class FamilyMember(BaseModel):
    """A person in the user's household or close family."""

    id: str | None = None
    name: str
    role: FamilyRole = FamilyRole.OTHER
    notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
