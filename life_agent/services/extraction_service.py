"""Extract structured items from unstructured user text.

This module never writes to the database.  It either calls an LLM (when one
is configured) or falls back to a deterministic rule-based extractor that
recognises common Swedish and English planning phrases used in this project.

The fallback understands the patterns the MVP needs and bails out cleanly on
anything else:

* relative dates: ``idag``, ``imorgon``, ``i övermorgon``
* weekdays: ``på måndag`` … ``på söndag`` (resolved to the next occurrence)
* times: ``kl 9``, ``kl 09``, ``kl 09:00``, ``klockan 18``, bare ``13:30``
* durations: ``1h``, ``45 min``, ``45 minuter``
* tasks: ``jag behöver…``, ``jag måste…``, ``kom ihåg att…``
* events: ``möte``, ``tandläkaren``, with ``på <Plats>`` locations
* reminders: ``påminn mig…``
* planned activities: ``jag ska träna/gymma…``

Vague times such as ``kväll`` are never turned into an exact timestamp; instead
a clarifying question is recorded.
"""

import re
from datetime import date, datetime, time, timedelta

from life_agent.agent.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT_TEMPLATE,
)
from life_agent.config import EXTRACTION_MODE_LLM, get_settings
from life_agent.llm.client import LLMClient
from life_agent.llm.structured_output import safe_parse_extraction_result
from life_agent.models.common import (
    ActivityType,
    EventCategory,
    Priority,
    TaskCategory,
)
from life_agent.schemas.extraction import (
    ExtractedActivity,
    ExtractedEvent,
    ExtractedReminder,
    ExtractedTask,
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

# Bare "HH:MM" time without a "kl" prefix, e.g. "13:30"
_BARE_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")

# Relative-date keywords
_TOMORROW_RE = re.compile(r"\b(?:i\s*morgon|imorgon|tomorrow)\b", re.IGNORECASE)
_TODAY_RE = re.compile(r"\b(?:i\s*dag|idag|today)\b", re.IGNORECASE)
_DAY_AFTER_RE = re.compile(
    r"\b(?:i\s*övermorgon|iövermorgon|day\s+after\s+tomorrow)\b",
    re.IGNORECASE,
)

# Weekday name -> Python weekday() index (Monday == 0)
_WEEKDAYS: dict[str, int] = {
    "måndag": 0,
    "tisdag": 1,
    "onsdag": 2,
    "torsdag": 3,
    "fredag": 4,
    "lördag": 5,
    "söndag": 6,
}
_WEEKDAY_FIND_RE = re.compile(
    r"\b(måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag)(?:en|ar|s)?\b",
    re.IGNORECASE,
)
# Strips an optional "på "/"i " plus the weekday name when building titles.
_WEEKDAY_STRIP_RE = re.compile(
    r"\b(?:på\s+|i\s+)?(?:måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag)"
    r"(?:en|ar|s)?\b",
    re.IGNORECASE,
)

# Vague time-of-day words.  These never become an exact timestamp.
_VAGUE_TIME_RE = re.compile(
    r"\b(morgonen|morgon|förmiddag(?:en)?|eftermiddag(?:en)?|"
    r"kväll(?:en)?|natt(?:en)?)\b",
    re.IGNORECASE,
)

# Reminder trigger words
_REMINDER_RE = re.compile(r"\b(?:påminn|påminnelse|remind)\b", re.IGNORECASE)

# Task trigger words (intent to do something with a possible deadline)
_TASK_INTENT_RE = re.compile(
    r"\b(?:behöver|måste|kom\s+ihåg|glöm\s+inte)\b",
    re.IGNORECASE,
)
_STUDY_TASK_RE = re.compile(
    r"(?:plugga|studera|läs(?:a|er)?|tenta|kurs|prov|matematik|matte|"
    r"machine\s+learning)",
    re.IGNORECASE,
)
_ERRAND_TASK_RE = re.compile(
    r"\b(?:handla|köp(?:a|er)?|betala|faktura(?:n|or)?|hämta|posta|boka|"
    r"ringa|tvätta|städa)\b",
    re.IGNORECASE,
)

# Event trigger words
_EVENT_KEYWORDS = (
    "möte",
    "meeting",
    "lunch",
    "middag",
    "frukost",
    "kalas",
    "fika",
    "tandläkare",
    "läkare",
    "doktor",
    "frisör",
)

# Location after "på " when the following word is capitalised (a place name).
_LOCATION_RE = re.compile(r"\bpå\s+([A-ZÅÄÖ][\wÅÄÖåäö-]*)")

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
    r"(\d+(?:[.,]\d+)?)\s*(?:timmar|timme|tim|hours?|h)\b",
    re.IGNORECASE,
)
_DURATION_MIN_RE = re.compile(
    r"(\d+)\s*(?:minuter|minutes|minute|minut|min)\b",
    re.IGNORECASE,
)

_TITLE_PREFIX_REs = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^\s*jag\s+ska\s+komma\s+ihåg\s+(?:att\s+)?",
        r"^\s*jag\s+behöver\s+(?:att\s+)?",
        r"^\s*jag\s+måste\s+",
        r"^\s*jag\s+ska\s+",
        r"^\s*jag\s+vill\s+",
        r"^\s*jag\s+har\s+",
        r"^\s*jag\s+",
        r"^\s*kom\s+ihåg\s+(?:att\s+)?",
        r"^\s*glöm\s+inte\s+(?:att\s+)?",
        r"^\s*påminn\s+mig\s+(?:om\s+|att\s+)*",
        r"^\s*påminn\s+(?:om\s+|att\s+)*",
        r"^\s*remind\s+me\s+to\s+",
        r"^\s*remind\s+me\s+",
        r"^\s*remind\s+",
    )
]

# Leading/trailing tokens that carry no title meaning on their own.
_EDGE_STOPWORDS = {"i", "på", "om", "kl", "klockan", "att", "till", "med", "-"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_from_text(
    text: str,
    reference_date: date | None = None,
    llm_client: LLMClient | None = None,
    mode: str | None = None,
) -> ExtractionResult:
    """Extract a structured :class:`ExtractionResult` from raw user text.

    Mode selection (in priority order):

    1. An explicit ``llm_client`` argument forces LLM extraction (used in tests
       with a fake client).
    2. Otherwise the *mode* argument, falling back to
       ``Settings.extraction_mode`` (``deterministic`` by default).

    In ``llm`` mode the configured client is asked for JSON, which is validated
    into an :class:`ExtractionResult`.  If the client is unavailable or returns
    invalid data, extraction degrades gracefully to the deterministic
    rule-based extractor and records a short note in ``questions``.  No data is
    written to the database in any case, and extraction is always read-only.
    """
    cleaned = text.strip() if text else ""
    if not cleaned:
        return ExtractionResult(
            raw_text="",
            confidence=0.0,
            questions=["No text was provided."],
        )

    reference = reference_date or date.today()

    explicit_client = llm_client is not None
    resolved_mode = EXTRACTION_MODE_LLM if explicit_client else (
        mode or get_settings().extraction_mode
    )

    if resolved_mode == EXTRACTION_MODE_LLM:
        return _llm_extract_with_fallback(cleaned, reference, llm_client)

    return _rule_based_extract(cleaned, reference)


def _llm_extract_with_fallback(
    cleaned: str,
    reference: date,
    llm_client: LLMClient | None,
) -> ExtractionResult:
    """Try LLM extraction, then degrade to the deterministic extractor."""
    client = llm_client if llm_client is not None else LLMClient.from_settings()

    if not getattr(client, "enabled", True):
        note = (
            "LLM mode is enabled but not fully configured "
            "(set LIFE_AGENT_LLM_BASE_URL, LIFE_AGENT_LLM_API_KEY, and "
            "LIFE_AGENT_LLM_MODEL); used the deterministic extractor instead."
        )
        return _deterministic_with_note(cleaned, reference, note)

    user_prompt = EXTRACTION_USER_PROMPT_TEMPLATE.format(
        today=reference.isoformat(), text=cleaned
    )
    try:
        raw = client.extract_structured(EXTRACTION_SYSTEM_PROMPT, user_prompt)
    except Exception:
        raw = None

    parsed = safe_parse_extraction_result(raw) if raw is not None else None
    if parsed is not None:
        return parsed.model_copy(update={"raw_text": cleaned})

    note = (
        "LLM extraction did not return valid data; "
        "used the deterministic extractor instead."
    )
    return _deterministic_with_note(cleaned, reference, note)


def _deterministic_with_note(
    cleaned: str, reference: date, note: str
) -> ExtractionResult:
    result = _rule_based_extract(cleaned, reference)
    return result.model_copy(update={"questions": [*result.questions, note]})


# ---------------------------------------------------------------------------
# Rule-based fallback — date / time helpers
# ---------------------------------------------------------------------------


def _resolve_date(text: str, reference_date: date) -> date | None:
    """Return the explicit date implied by *text*, or ``None`` if none.

    Relative keywords win over weekdays.  A weekday resolves to its next
    occurrence strictly in the future (a same-weekday match jumps a week) so
    that "på fredag" never means "today" when today is already Friday.
    """
    if _DAY_AFTER_RE.search(text):
        return reference_date + timedelta(days=2)
    if _TOMORROW_RE.search(text):
        return reference_date + timedelta(days=1)
    if _TODAY_RE.search(text):
        return reference_date
    match = _WEEKDAY_FIND_RE.search(text)
    if match:
        target = _WEEKDAYS[match.group(1).lower()]
        days_ahead = (target - reference_date.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return reference_date + timedelta(days=days_ahead)
    return None


def _extract_time(clause: str) -> time | None:
    """Return a time from "kl HH[:MM]"/"klockan HH" or a bare "HH:MM"."""
    match = _TIME_RE.search(clause)
    if match:
        hour_str, minute_str = match.group(1), match.group(2)
    else:
        bare = _BARE_TIME_RE.search(clause)
        if not bare:
            return None
        hour_str, minute_str = bare.group(1), bare.group(2)
    try:
        hour = int(hour_str)
        minute = int(minute_str) if minute_str else 0
    except ValueError:
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None


def _detect_vague_time(clause: str) -> str | None:
    """Return a vague time-of-day word, ignoring relative-date keywords."""
    s = _TOMORROW_RE.sub(" ", clause)
    s = _TODAY_RE.sub(" ", s)
    s = _DAY_AFTER_RE.sub(" ", s)
    match = _VAGUE_TIME_RE.search(s)
    return match.group(1).lower() if match else None


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


def _extract_location(clause: str) -> str | None:
    """Return a place name following "på " (e.g. "på Odenplan" -> Odenplan)."""
    match = _LOCATION_RE.search(clause)
    if not match:
        return None
    word = match.group(1)
    if word.lower() in _WEEKDAYS:
        return None
    return word


def _task_category(clause: str) -> TaskCategory:
    if _STUDY_TASK_RE.search(clause):
        return TaskCategory.STUDY
    if _ERRAND_TASK_RE.search(clause):
        return TaskCategory.ERRAND
    return TaskCategory.OTHER


def _event_category(clause_lower: str) -> EventCategory:
    if "möte" in clause_lower or "meeting" in clause_lower:
        return EventCategory.MEETING
    if any(k in clause_lower for k in ("tandläkare", "läkare", "doktor", "frisör")):
        return EventCategory.HEALTH
    return EventCategory.OTHER


def _make_title(clause: str, location: str | None = None) -> str:
    """Strip date/time/duration/location markers and common prefixes."""
    s = clause
    s = _TIME_RE.sub(" ", s)
    s = _BARE_TIME_RE.sub(" ", s)
    s = _TOMORROW_RE.sub(" ", s)
    s = _TODAY_RE.sub(" ", s)
    s = _DAY_AFTER_RE.sub(" ", s)
    s = _DURATION_HOUR_RE.sub(" ", s)
    s = _DURATION_MIN_RE.sub(" ", s)
    s = _WEEKDAY_STRIP_RE.sub(" ", s)
    s = _VAGUE_TIME_RE.sub(" ", s)
    if location:
        s = re.sub(
            rf"\bpå\s+{re.escape(location)}\b", " ", s, flags=re.IGNORECASE
        )
    for pattern in _TITLE_PREFIX_REs:
        s = pattern.sub("", s, count=1)
    s = re.sub(r"\s+", " ", s).strip(" .,;:!?")

    tokens = s.split()
    while tokens and tokens[0].lower() in _EDGE_STOPWORDS:
        tokens.pop(0)
    while tokens and tokens[-1].lower() in _EDGE_STOPWORDS:
        tokens.pop()
    s = " ".join(tokens)
    if not s:
        return ""
    return s[0].upper() + s[1:]


def _split_into_clauses(text: str) -> list[str]:
    """Split on sentence punctuation, then on ``och`` when a reminder is present.

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


# ---------------------------------------------------------------------------
# Rule-based fallback — main extractor
# ---------------------------------------------------------------------------


def _rule_based_extract(text: str, reference_date: date) -> ExtractionResult:
    global_date = _resolve_date(text, reference_date)
    clauses = _split_into_clauses(text)

    tasks: list[ExtractedTask] = []
    events: list[ExtractedEvent] = []
    activities: list[ExtractedActivity] = []
    reminders: list[ExtractedReminder] = []
    questions: list[str] = []

    last_activity_index: int | None = None

    for clause in clauses:
        lower = clause.lower()

        explicit_date = _resolve_date(clause, reference_date)
        if explicit_date is None:
            explicit_date = global_date
        date_for_dt = explicit_date or reference_date

        clause_time = _extract_time(clause)
        clause_dt: datetime | None = (
            datetime.combine(date_for_dt, clause_time) if clause_time else None
        )
        duration_minutes = _extract_duration_minutes(clause)
        vague_time = _detect_vague_time(clause) if clause_time is None else None

        is_reminder = bool(_REMINDER_RE.search(clause))
        is_task = (not is_reminder) and bool(
            _TASK_INTENT_RE.search(clause) or _ERRAND_TASK_RE.search(clause)
        )
        is_event = (
            not is_reminder
            and not is_task
            and any(kw in lower for kw in _EVENT_KEYWORDS)
        )
        activity_type = _detect_activity_type(lower)

        # --- Reminders ---------------------------------------------------
        if is_reminder:
            title = _make_title(clause)
            reminders.append(
                ExtractedReminder(title=title or "Påminnelse", remind_at=clause_dt)
            )
            if clause_dt is None:
                questions.append(
                    "When should the reminder fire? No clear time was found."
                )
            continue

        # --- Tasks -------------------------------------------------------
        if is_task:
            title = _make_title(clause)
            tasks.append(
                ExtractedTask(
                    title=title or None,
                    due_date=explicit_date,
                    priority=Priority.MEDIUM,
                    category=_task_category(clause),
                )
            )
            if not title:
                questions.append(
                    "What is the task about? No clear title was found."
                )
            continue

        # --- Events ------------------------------------------------------
        if is_event:
            location = _extract_location(clause)
            title = _make_title(clause, location=location)
            events.append(
                ExtractedEvent(
                    title=title or None,
                    start_time=clause_dt,
                    location=location,
                    category=_event_category(lower),
                )
            )
            if clause_dt is None:
                questions.append(
                    "What time is the event? No clear time was found."
                )
            continue

        # --- Activities --------------------------------------------------
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

            title = _make_title(clause)
            activities.append(
                ExtractedActivity(
                    title=title or None,
                    activity_type=activity_type,
                    logged_at=clause_dt,
                    duration_minutes=duration_minutes,
                )
            )
            last_activity_index = len(activities) - 1
            if clause_dt is None and vague_time:
                questions.append(
                    f"What time on the planned day? '{vague_time}' is vague."
                )
            continue

        # --- Pure duration refinement ------------------------------------
        if (
            duration_minutes is not None
            and last_activity_index is not None
            and activities[last_activity_index].duration_minutes is None
        ):
            prev = activities[last_activity_index]
            activities[last_activity_index] = prev.model_copy(
                update={"duration_minutes": duration_minutes}
            )

    extracted_anything = bool(tasks or events or activities or reminders)
    confidence = 0.55 if extracted_anything else 0.0
    if not extracted_anything:
        questions.append(
            "Could not extract a task, event, activity, or reminder from the text."
        )

    return ExtractionResult(
        tasks=tasks,
        activities=activities,
        events=events,
        reminders=reminders,
        questions=questions,
        confidence=confidence,
        raw_text=text,
    )
