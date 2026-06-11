"""Parse raw LLM JSON output into validated extraction schemas."""

from life_agent.schemas.extraction import ExtractionResult


def parse_extraction_result(data: dict) -> ExtractionResult:
    """Validate a JSON-shaped dict against :class:`ExtractionResult`.

    Raises ``pydantic.ValidationError`` (or ``TypeError``) on malformed input.
    """
    return ExtractionResult.model_validate(data)


def safe_parse_extraction_result(data: object) -> ExtractionResult | None:
    """Validate *data* into an :class:`ExtractionResult`, or return ``None``.

    Unlike :func:`parse_extraction_result`, this never raises — it is the
    convenient entry point for untrusted LLM output, where invalid shapes must
    degrade gracefully rather than crash the app.
    """
    if not isinstance(data, dict):
        return None
    try:
        return ExtractionResult.model_validate(data)
    except Exception:
        return None
