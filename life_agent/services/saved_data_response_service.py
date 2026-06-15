"""Formatting layer for saved-data Q&A results.

This module turns a structured ``SavedDataQueryResult`` into a grounded
``SavedDataAnswer`` and then into user-facing plain text.  It has no
database access and performs no I/O beyond an optional LLM call for
response wording.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, Protocol

from life_agent.schemas.saved_data_query import (
    QueryType,
    SavedDataAnswer,
    SavedDataQueryResult,
)

ResponseMode = Literal["template", "llm"]

_RESPONSE_GENERATION_PROMPT = """\
You are formatting a response to the user from already-grounded data.

Rules:
- Do NOT add facts, dates, times, titles, records, or statuses that are \
not present in the provided answer data.
- Do NOT invent or hallucinate any information.
- If "grounded" is false, clearly state that no matching saved data was found.
- Keep the answer concise and natural.
- Return plain text only. No markdown, no JSON.
- Preserve all factual details (titles, times, dates) exactly as given.
"""


class ResponseLLMClient(Protocol):
    """Minimal interface for an LLM client used by the response service."""

    def extract_structured(
        self, system_prompt: str, user_text: str
    ) -> dict[str, object] | None: ...


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_saved_data_answer(result: SavedDataQueryResult) -> SavedDataAnswer:
    """Build a grounded ``SavedDataAnswer`` from a query result."""
    text = _format_query_result(result)
    has_records = len(result.records) > 0

    limitations: list[str] = []
    if not result.matched and result.fallback_message:
        limitations.append(result.fallback_message)

    return SavedDataAnswer(
        query_type=result.query_type.value,
        text=text,
        grounded=has_records,
        matched=result.matched,
        record_count=len(result.records),
        source_record_types=sorted({r.record_type for r in result.records}),
        fallback_message=result.fallback_message,
        limitations=limitations,
    )


def format_saved_data_answer(
    answer: SavedDataAnswer,
    *,
    mode: ResponseMode | None = None,
    llm_client: ResponseLLMClient | None = None,
) -> str:
    """Return the plain-text representation of a ``SavedDataAnswer``.

    Parameters
    ----------
    mode
        ``"template"`` (default) uses deterministic formatting.
        ``"llm"`` attempts LLM-based rewording with template fallback.
        When *None*, the mode is read from application settings.
    llm_client
        An object satisfying :class:`ResponseLLMClient`.  Inject a fake
        in tests.  When *mode* is ``"llm"`` and no client is provided,
        one is created from application settings.
    """
    resolved_mode = mode or _get_config_mode()

    if resolved_mode == "llm":
        client = llm_client or _get_default_llm_client()
        if client is not None:
            generated = _try_llm_format(answer, client)
            if generated:
                return generated

    return answer.text


def format_saved_data_query_result(
    result: SavedDataQueryResult,
    *,
    mode: ResponseMode | None = None,
    llm_client: ResponseLLMClient | None = None,
) -> str:
    """Format a ``SavedDataQueryResult`` into the user-facing text answer.

    Backward-compatible entry point that builds the intermediate answer
    object and then formats it.
    """
    answer = build_saved_data_answer(result)
    return format_saved_data_answer(answer, mode=mode, llm_client=llm_client)


# ---------------------------------------------------------------------------
# LLM response generation (internal)
# ---------------------------------------------------------------------------


def _try_llm_format(
    answer: SavedDataAnswer, client: ResponseLLMClient
) -> str | None:
    """Attempt to generate a response via the LLM.  Returns *None* on failure."""
    user_text = answer.model_dump_json()
    try:
        resp = client.extract_structured(_RESPONSE_GENERATION_PROMPT, user_text)
    except Exception:
        return None

    if resp is None:
        return None

    text = resp.get("text") if isinstance(resp, dict) else None
    if not isinstance(text, str) or not text.strip():
        return None

    return text.strip()


def _get_config_mode() -> ResponseMode:
    """Read the response mode from application settings."""
    try:
        from life_agent.config import get_settings

        value = get_settings().saved_data_response_mode
        if value == "llm":
            return "llm"
    except Exception:
        pass
    return "template"


def _get_default_llm_client() -> ResponseLLMClient | None:
    """Try to create an LLM client from application settings."""
    try:
        from life_agent.llm.client import LLMClient

        client = LLMClient.from_settings()
        if not client.enabled:
            return None
        return client  # type: ignore[return-value]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-query-type formatters (internal, deterministic)
# ---------------------------------------------------------------------------


def _format_query_result(result: SavedDataQueryResult) -> str:
    """Dispatch to the appropriate per-type formatter."""
    if result.query_type == QueryType.REMINDER_LOOKUP:
        return _format_reminder(result)
    if result.query_type == QueryType.PLANNED_TOMORROW:
        return _format_tomorrow(result)
    if result.query_type == QueryType.TRAINING_WEEK:
        return _format_training_week(result)
    return result.fallback_message or "I couldn't find a specific answer for that yet."


def _format_reminder(result: SavedDataQueryResult) -> str:
    if not result.records and result.fallback_message:
        return result.fallback_message

    if not result.matched:
        lines = [f"  • {r.title} at {r.when}" for r in result.records]
        header = result.fallback_message or "No reminder matched your query."
        return header + " Pending reminders:\n" + "\n".join(lines)

    parts = [
        f"You have a reminder for {r.title} at {r.when}."
        for r in result.records
    ]
    return "\n".join(parts)


def _format_tomorrow(result: SavedDataQueryResult) -> str:
    if not result.matched:
        return result.fallback_message or "Nothing is planned for tomorrow."

    date_str = result.records[0].when or ""
    date_part = date_str.split(" ")[0] if " " in date_str else date_str

    lines: list[str] = []
    for r in result.records:
        label = r.record_type.capitalize()
        if r.when:
            lines.append(f"  • {label}: {r.title} at {r.when}")
        else:
            lines.append(f"  • {label}: {r.title}")

    return f"Planned for tomorrow ({date_part}):\n" + "\n".join(lines)


def _format_training_week(result: SavedDataQueryResult) -> str:
    if not result.matched:
        return result.fallback_message or "No training activities found this week."

    dates = [r.when for r in result.records if r.when]
    if dates:
        parsed = sorted(date.fromisoformat(d) for d in dates)
        week_start = parsed[0] - timedelta(days=parsed[0].weekday())
        week_end = week_start + timedelta(days=6)
        header = f"Training this week ({week_start} – {week_end}):"
    else:
        header = "Training this week:"

    lines = [f"  • {r.title} on {r.when}" for r in result.records]
    return header + "\n" + "\n".join(lines)
