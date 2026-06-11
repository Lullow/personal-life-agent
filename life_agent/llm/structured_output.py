"""Parse raw LLM JSON output into validated extraction schemas."""

from life_agent.schemas.extraction import ExtractionResult


def parse_extraction_result(data: dict) -> ExtractionResult:
    """Validate a JSON-shaped dict against :class:`ExtractionResult`."""
    return ExtractionResult.model_validate(data)
