"""Schemas for the natural-language add confirmation flow."""

from pydantic import BaseModel, Field

from life_agent.schemas.extraction import ExtractionResult


class SavedItemSummary(BaseModel):
    """Outcome for a single extracted item during a save attempt."""

    item_type: str  # "task" | "event" | "activity" | "reminder"
    title: str
    saved: bool
    reason: str | None = None  # why an item was skipped, if applicable


class ConfirmationProposal(BaseModel):
    """A preview of what *would* be saved if the user confirms."""

    extraction: ExtractionResult
    saveable_count: int = 0
    skipped_count: int = 0


class ConfirmationSaveResult(BaseModel):
    """The result of saving a confirmed extraction."""

    saved: list[SavedItemSummary] = Field(default_factory=list)
    skipped: list[SavedItemSummary] = Field(default_factory=list)

    @property
    def saved_count(self) -> int:
        return len(self.saved)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)
