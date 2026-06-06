"""Meal plan domain model."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from life_agent.models.common import MealType, NonEmptyTitle, utc_now


class MealPlan(BaseModel):
    """A planned meal for a given day and meal slot."""

    id: str | None = None
    title: NonEmptyTitle
    meal_type: MealType
    date: date
    notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
