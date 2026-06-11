"""Extract structured items from unstructured user text.

This module never writes to the database.  It either calls an LLM (when one
is configured) or falls back to a deterministic rule-based extractor that
recognises common Swedish and English phrases used in this project.

The fallback is intentionally minimal: it understands the patterns the MVP
needs (``kl HH[:MM]``, ``imorgon``, ``påminn mig``, durations like ``1h`` or
``30 min``) and bails out cleanly on anything else.
"""

import re
from datetime import date, datetime, time, timedelta

from life_agent.agent.prompts import EXTRACTION_SYSTEM_PROMPT
from life_agent.llm.client import LLMClient
from life_agent.llm.structured_output import parse_extraction_result
from life_agent.models.common import ActivityType
from life_agent.schemas.extraction import (
    ExtractedActivity,
    ExtractedEvent,
    ExtractedReminder,
    ExtractionResult,
)

# ---------------------------------------------------------------------------
# Regex building blocks
# ---------------------------------------------------------------------------

# "kl 12", "kl. 12", "kl 12:30", "klockan 12"
_TIME_RE = re.compile(
    r"\b(?:kl|klockan)\.?\s*(\d{1,2})(?::(\d{2}))?\b",
    re.IGNORECASE,
)

# Relative-date keywords
_TOMORROW_RE = re.compile(r"\b(?:i\s*morgon|imorgon|tomorrow)\b", re.IGNORECASE)
_TODAY_RE = re.compile(r"\b(?:i\s*dag|idag|today)\b", re.IGNORECASE)
_DAY_AFTER_RE = re.compile(
    r"\b(?:i\s*övermorgon|iövermorgon|day\s+after\s+tomorrow)\b",
    re.IGNORECASE,
)

# Reminder trigger words
_REMINDER_RE = re.compile(r"\b(?:påminn|påminnelse|remind)\b", re.IGNORECASE)

# Event trigger words
_EVENT_KEYWORDS = ("möte", "meeting", "lunch", "middag", "frukost", "kalas")

# Activity verbs mapped to ActivityType
_ACTIVITY_KEYWORDS: dict[str, ActivityType] = {
    "träna": ActivityType.GYM,
    "tränar": ActivityType.GYM,
    "tränade": ActivityType.GYM,
    "träning": ActivityType.GYM,
    "gym": ActivityType.GYM,
    "spring": ActivityType.RUN,
    "springer": ActivityType.RUN,
    "sprang": ActivityType.RUN,
    "löpning": ActivityType.RUN,
    "löper": ActivityType.RUN,
    "promenad": ActivityType.WALK,
    "promenera": ActivityType.WALK,
    "promenerar": ActivityType.WALK,
    "walk": ActivityType.WALK,
    "studera": ActivityType.STUDY,
    "studerar": ActivityType.STUDY,
    "pluggar": ActivityType.STUDY,
    "plugga": ActivityType.STUDY,
    "study": ActivityType.STUDY,
}

_DURATION_HOUR_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:h|tim|timme|timmar|hours?)\b",
    re.IGNORECASE,
)
_DURATION_MIN_RE = re.compile(
    r"(\d+)\s*(?:min|minut|minutes?)\b",
    re.IGNORECASE,
)

_TITLE_PREFIX_REs = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^\s*jag\s+ska\s+",
        r"^\s*jag\s+vill\s+",
        r"^\s*jag\s+",
        r"^\s*påminn\s+mig\s+(?:om\s+)?(?:att\s+)?",
        r"^\s*påminn\s+(?:om\s+)?(?:att\s+)?",
        r"^\s*remind\s+me\s+to\s+",
        r"^\s*remind\s+me\s+",
        r"^\s*remind\s+",
    )
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_from_text(
    text: str,
    reference_date: date | None = None,
    llm_client: LLMClient | None = None,
) -> ExtractionResult:
    """Extract a structured :class:`ExtractionResult` from raw user text.

    If an LLM client is configured and enabled, its JSON output is parsed and
    returned.  Otherwise a deterministic rule-based extractor runs.  No data
    is written to the database in either case.
    """
    cleaned = text.strip() if text else ""
    if not cleaned:
        return ExtractionResult(
            raw_text="",
            confidence=0.0,
            questions=["No text was provided."],
        )

    client = llm_client if llm_client is not None else LLMClient()
    llm_data = client.extract_structured(EXTRACTION_SYSTEM_PROMPT, cleaned)
    if llm_data is not None:
        try:
            parsed = parse_extraction_result(llm_data)
            return parsed.model_copy(update={"raw_text": cleaned})
        except Exception:
            # Fall through to the rule-based extractor.
            pass

    return _rule_based_extract(cleaned, reference_date or date.today())


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------


def _resolve_relative_date(text: str, reference_date: date) -> date:
    """Return the date implied by relative-date words in *text*."""
    if _DAY_AFTER_RE.search(text):
        return reference_date + timedelta(days=2)
    if _TOMORROW_RE.search(text):
        return reference_date + timedelta(days=1)
    if _TODAY_RE.search(text):
        return reference_date
    return reference_date


def _extract_time(clause: str) -> time | None:
    match = _TIME_RE.search(clause)
    if not match:
        return None
    try:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
    except ValueError:
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None


def _extract_duration_minutes(clause: str) -> int | None:
    total: int | None = None
    h_match = _DURATION_HOUR_RE.search(clause)
    if h_match:
        try:
            hours = float(h_match.group(1).replace(",", "."))
            total = int(round(hours * 60))
        except ValueError:
            pass
    m_match = _DURATION_MIN_RE.search(clause)
    if m_match:
        try:
            mins = int(m_match.group(1))
            total = (total or 0) + mins
        except ValueError:
            pass
    return total


def _detect_activity_type(clause_lower: str) -> ActivityType | None:
    for keyword, activity_type in _ACTIVITY_KEYWORDS.items():
        if re.search(rf"\b{re.escape(keyword)}\w*\b", clause_lower):
            return activity_type
    return None


def _make_title(clause: str) -> str:
    """Strip date/time/duration markers and common Swedish/English prefixes."""
    s = clause
    s = _TIME_RE.sub("", s)
    s = _TOMORROW_RE.sub("", s)
    s = _TODAY_RE.sub("", s)
    s = _DAY_AFTER_RE.sub("", s)
    s = _DURATION_HOUR_RE.sub("", s)
    s = _DURATION_MIN_RE.sub("", s)
    for pattern in _TITLE_PREFIX_REs:
        s = pattern.sub("", s, count=1)
    s = re.sub(r"\s+", " ", s).strip(" .,;:!?")
    if not s:
        return ""
    return s[0].upper() + s[1:]


def _split_into_clauses(text: str) -> list[str]:
    """Split on sentence punctuation, then on ``och`` when reminder keyword is present.

    The "och" split is only applied to clauses containing a reminder trigger
    so that natural phrases like "rygg och biceps" are kept intact.
    """
    primary = [c.strip() for c in re.split(r"[,.;]", text) if c.strip()]
    result: list[str] = []
    for clause in primary:
        if _REMINDER_RE.search(clause) and re.search(r"\s+och\s+", clause, re.IGNORECASE):
            parts = re.split(r"\s+och\s+", clause, maxsplit=1, flags=re.IGNORECASE)
            for p in parts:
                p = p.strip()
                if p:
                    result.append(p)
        else:
            result.append(clause)
    return result


def _rule_based_extract(text: str, reference_date: date) -> ExtractionResult:
    global_date = _resolve_relative_date(text, reference_date)
    clauses = _split_into_clauses(text)

    activities: list[ExtractedActivity] = []
    events: list[ExtractedEvent] = []
    reminders: list[ExtractedReminder] = []
    questions: list[str] = []

    last_activity_index: int | None = None

    for clause in clauses:
        lower = clause.lower()

        clause_date = _resolve_relative_date(clause, reference_date)
        if clause_date == reference_date and not any(
            r.search(clause) for r in (_TOMORROW_RE, _TODAY_RE, _DAY_AFTER_RE)
        ):
            clause_date = global_date

        clause_time = _extract_time(clause)
        clause_dt: datetime | None = (
            datetime.combine(clause_date, clause_time) if clause_time else None
        )
        duration_minutes = _extract_duration_minutes(clause)

        is_reminder = bool(_REMINDER_RE.search(clause))
        is_event = any(kw in lower for kw in _EVENT_KEYWORDS)
        activity_type = _detect_activity_type(lower)

        title = _make_title(clause)

        if is_reminder:
            reminders.append(
                ExtractedReminder(
                    title=title or "Påminnelse",
                    remind_at=clause_dt,
                )
            )
            if clause_dt is None:
                questions.append(
                    "When should the reminder fire? No clear time was found."
                )
            continue

        if is_event:
            events.append(
                ExtractedEvent(title=title or None, start_time=clause_dt)
            )
            continue

        if activity_type is not None:
            # Refinement clause: e.g. "träningen ska vara 1h" extends the
            # previously mentioned activity with a duration.
            if (
                clause_dt is None
                and duration_minutes is not None
                and last_activity_index is not None
                and activities[last_activity_index].duration_minutes is None
            ):
                prev = activities[last_activity_index]
                activities[last_activity_index] = prev.model_copy(
                    update={"duration_minutes": duration_minutes}
                )
                continue

            activities.append(
                ExtractedActivity(
                    title=title or None,
                    activity_type=activity_type,
                    logged_at=clause_dt,
                    duration_minutes=duration_minutes,
                )
            )
            last_activity_index = len(activities) - 1
            continue

        # Pure duration refinement without an activity verb — apply to the
        # last activity if it lacks a duration.
        if (
            duration_minutes is not None
            and last_activity_index is not None
            and activities[last_activity_index].duration_minutes is None
        ):
            prev = activities[last_activity_index]
            activities[last_activity_index] = prev.model_copy(
                update={"duration_minutes": duration_minutes}
            )

    extracted_anything = bool(activities or events or reminders)
    confidence = 0.55 if extracted_anything else 0.0
    if not extracted_anything:
        questions.append(
            "Could not extract a task, event, activity, or reminder from the text."
        )

    return ExtractionResult(
        activities=activities,
        events=events,
        reminders=reminders,
        questions=questions,
        confidence=confidence,
        raw_text=text,
    )
