"""Read-only service for answering simple questions about saved data.

This service never writes to the database.  It queries existing repositories
and returns either a structured ``SavedDataQueryResult`` or a plain-text
answer.

Four categories are supported:

1. **Reminder lookup** — "vilken tid ska du påminna mig om att handla mat"
   Searches pending reminders by keyword and reports the scheduled time.

2. **Planned tomorrow** — "har jag något planerat imorgon"
   Aggregates events, tasks, activities, and reminders for tomorrow.

3. **Training this week** — "vad har jag för träningar den här veckan"
   Lists gym/sport activities within the current week.

4. **Next upcoming** — "vad är nästa grej" / "vad händer härnäst"
   Finds the single earliest future saved item across all data sources.

5. **Daily focus** — "vad borde jag fokusera på idag" / "dagens fokus"
   Prioritised list of today's events, tasks, reminders, and activities.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from life_agent.schemas.saved_data_query import (
    QueryType,
    SavedDataQueryResult,
    SavedDataRecord,
)
from life_agent.services.saved_data_response_service import (
    format_saved_data_query_result,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def answer_saved_data_question(
    message: str,
    db_path: str | None = None,
    *,
    today: date | None = None,
) -> str:
    """Return a plain-text answer for *message*, or a polite fallback."""
    result = query_saved_data(message, db_path=db_path, today=today)
    return format_saved_data_query_result(result)


def detect_saved_data_query_type(message: str) -> str:
    """Classify *message* into a saved-data query type string.

    Returns one of the :class:`QueryType` values:
    ``"reminder_lookup"``, ``"planned_tomorrow"``, ``"training_week"``,
    ``"next_upcoming"``, ``"daily_focus"``, or ``"unknown"``.

    This function is pure text classification — no database access, no I/O.
    Both :func:`query_saved_data` and ``AgentRouter`` use it so that
    detection logic is defined in a single place.
    """
    msg = message.strip()

    if _is_reminder_question(msg):
        return QueryType.REMINDER_LOOKUP
    if _is_tomorrow_question(msg):
        return QueryType.PLANNED_TOMORROW
    if _is_training_week_question(msg):
        return QueryType.TRAINING_WEEK
    if _is_next_upcoming_question(msg):
        return QueryType.NEXT_UPCOMING
    if _is_daily_focus_question(msg):
        return QueryType.DAILY_FOCUS
    return QueryType.UNKNOWN


def query_saved_data(
    message: str,
    db_path: str | None = None,
    *,
    today: date | None = None,
) -> SavedDataQueryResult:
    """Classify *message* and return a structured query result."""
    msg = message.strip()
    _today = today or date.today()
    qtype = detect_saved_data_query_type(msg)

    if qtype == QueryType.REMINDER_LOOKUP:
        return _query_reminder(msg, db_path=db_path)
    if qtype == QueryType.PLANNED_TOMORROW:
        return _query_tomorrow(msg, _today, db_path=db_path)
    if qtype == QueryType.TRAINING_WEEK:
        return _query_training_week(msg, _today, db_path=db_path)
    if qtype == QueryType.NEXT_UPCOMING:
        return _query_next_upcoming(msg, _today, db_path=db_path)
    if qtype == QueryType.DAILY_FOCUS:
        return _query_daily_focus(msg, _today, db_path=db_path)

    return SavedDataQueryResult(
        query_type=QueryType.UNKNOWN,
        question=msg,
        matched=False,
        fallback_message="I couldn't find a specific answer for that yet.",
    )


# ---------------------------------------------------------------------------
# Classifiers
# ---------------------------------------------------------------------------

_REMINDER_Q_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bvilken\s+tid\b",
        r"\bnär\s+ska\s+du\s+påminna\b",
        r"\bnär\s+påminner\b",
        r"\bvad\s+är\s+tiden\b",
        r"\bpåminnelse\s+om\b",
        r"\bpåminna\s+mig\s+om\b",
    )
]

_TOMORROW_Q_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bhar\s+jag\s+något\s+planerat\s+imorgon\b",
        r"\bvad\s+händer\s+imorgon\b",
        r"\bvad\s+har\s+jag\s+imorgon\b",
        r"\bimorgon\b.*\bplanerat\b",
    )
]

_TRAINING_WEEK_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bvad\s+har\s+jag\s+för\s+träning",
        r"\bträningar?\s+den\s+här\s+veckan\b",
        r"\bträningar?\s+i\s+veckan\b",
        r"\bträna\b.*\bveckan\b",
        r"\bgym\b.*\bveckan\b",
    )
]


_NEXT_UPCOMING_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bnästa\s+grej\b",
        r"\bnästa\s+påminnelse\b",
        r"\bnästa\s+händelse\b",
        r"\bnästa\s+uppgift\b",
        r"\bnästa\s+aktivitet\b",
        r"\bvad\s+är\s+nästa\b",
        r"\bvad\s+händer\s+härnäst\b",
        r"\bvad\s+har\s+jag\s+närmast\b",
        r"\bvad\s+är\s+min\s+nästa\b",
        r"\bhärnäst\b",
        r"\bnärmast\b",
    )
]


def _is_reminder_question(msg: str) -> bool:
    return any(p.search(msg) for p in _REMINDER_Q_PATTERNS)


def _is_tomorrow_question(msg: str) -> bool:
    return any(p.search(msg) for p in _TOMORROW_Q_PATTERNS)


def _is_training_week_question(msg: str) -> bool:
    return any(p.search(msg) for p in _TRAINING_WEEK_PATTERNS)


_DAILY_FOCUS_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bfokusera\s+på\s+idag\b",
        r"\bviktigast\s+idag\b",
        r"\bprioritera\s+idag\b",
        r"\bdagens\s+fokus\b",
        r"\bmin\s+viktigaste\b.*\bidag\b",
        r"\bvad\s+borde\s+jag\b.*\bidag\b",
        r"\bvad\s+ska\s+jag\s+fokusera\b",
    )
]


def _is_next_upcoming_question(msg: str) -> bool:
    return any(p.search(msg) for p in _NEXT_UPCOMING_PATTERNS)


def _is_daily_focus_question(msg: str) -> bool:
    return any(p.search(msg) for p in _DAILY_FOCUS_PATTERNS)


# ---------------------------------------------------------------------------
# Structured query helpers
# ---------------------------------------------------------------------------


def _query_reminder(msg: str, *, db_path: str | None) -> SavedDataQueryResult:
    from life_agent.db.repositories import list_reminders
    from life_agent.models.common import ReminderStatus

    pending = list_reminders(status=ReminderStatus.PENDING, db_path=db_path)

    if not pending:
        return SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question=msg,
            matched=False,
            fallback_message="You have no pending reminders.",
        )

    keywords = _extract_keywords(msg)
    matches = [
        r for r in pending
        if r.title and any(kw in r.title.lower() for kw in keywords)
    ]

    if not matches:
        records = [
            SavedDataRecord(
                record_type="reminder",
                title=r.title or "(untitled)",
                when=_fmt_dt(r.remind_at),
                status="pending",
            )
            for r in pending
        ]
        return SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question=msg,
            matched=False,
            records=records,
            fallback_message="No reminder matched your query.",
        )

    records = [
        SavedDataRecord(
            record_type="reminder",
            title=r.title or "(untitled)",
            when=_fmt_dt(r.remind_at),
            status="pending",
        )
        for r in matches
    ]
    return SavedDataQueryResult(
        query_type=QueryType.REMINDER_LOOKUP,
        question=msg,
        matched=True,
        records=records,
    )


def _query_tomorrow(
    msg: str, today: date, *, db_path: str | None
) -> SavedDataQueryResult:
    tomorrow = today + timedelta(days=1)
    records: list[SavedDataRecord] = []

    from life_agent.db.repositories import (
        list_activities,
        list_events,
        list_reminders,
        list_tasks,
    )
    from life_agent.models.common import ReminderStatus, TaskStatus

    for event in list_events(db_path=db_path):
        if event.start_time and event.start_time.date() == tomorrow:
            records.append(SavedDataRecord(
                record_type="event",
                title=event.title,
                when=_fmt_dt(event.start_time),
            ))

    for task in list_tasks(db_path=db_path):
        if task.status != TaskStatus.DONE and task.due_date == tomorrow:
            records.append(SavedDataRecord(
                record_type="task",
                title=task.title,
                when=str(tomorrow),
                status=task.status,
            ))

    for act in list_activities(db_path=db_path):
        if act.logged_at and act.logged_at.date() == tomorrow:
            records.append(SavedDataRecord(
                record_type="activity",
                title=act.title,
                when=_fmt_dt(act.logged_at),
            ))

    for rem in list_reminders(status=ReminderStatus.PENDING, db_path=db_path):
        if rem.remind_at and rem.remind_at.date() == tomorrow:
            records.append(SavedDataRecord(
                record_type="reminder",
                title=rem.title or "(untitled)",
                when=_fmt_dt(rem.remind_at),
                status="pending",
            ))

    return SavedDataQueryResult(
        query_type=QueryType.PLANNED_TOMORROW,
        question=msg,
        matched=len(records) > 0,
        records=records,
        fallback_message=None if records else f"Nothing is planned for tomorrow ({tomorrow}).",
    )


def _query_training_week(
    msg: str, today: date, *, db_path: str | None
) -> SavedDataQueryResult:
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    from life_agent.db.repositories import list_activities
    from life_agent.models.common import ActivityType

    training_types = {ActivityType.GYM, ActivityType.RUN, ActivityType.SPORT}
    all_acts = list_activities(db_path=db_path)
    training = [
        a for a in all_acts
        if a.activity_type in training_types
        and a.logged_at
        and week_start <= a.logged_at.date() <= week_end
    ]

    records = [
        SavedDataRecord(
            record_type="activity",
            title=a.title,
            when=str(a.logged_at.date()),
            status=a.status if hasattr(a, "status") else None,
            details=a.activity_type if isinstance(a.activity_type, str) else a.activity_type.value,
        )
        for a in training
    ]

    return SavedDataQueryResult(
        query_type=QueryType.TRAINING_WEEK,
        question=msg,
        matched=len(records) > 0,
        records=records,
        fallback_message=None if records else f"No training activities found this week ({week_start} – {week_end}).",
    )


def _query_next_upcoming(
    msg: str, today: date, *, db_path: str | None
) -> SavedDataQueryResult:
    """Find the single earliest future item across all data sources."""
    now = datetime.combine(today, datetime.min.time())
    candidates: list[tuple[datetime, SavedDataRecord]] = []

    from life_agent.db.repositories import (
        list_activities,
        list_events,
        list_reminders,
        list_tasks,
    )
    from life_agent.models.common import ActivityStatus, ReminderStatus, TaskStatus

    for rem in list_reminders(status=ReminderStatus.PENDING, db_path=db_path):
        if rem.remind_at and rem.remind_at >= now:
            candidates.append((
                rem.remind_at,
                SavedDataRecord(
                    record_type="reminder",
                    title=rem.title or "(untitled)",
                    when=_fmt_dt(rem.remind_at),
                    status="pending",
                ),
            ))

    for event in list_events(db_path=db_path):
        if event.start_time and event.start_time >= now:
            candidates.append((
                event.start_time,
                SavedDataRecord(
                    record_type="event",
                    title=event.title,
                    when=_fmt_dt(event.start_time),
                ),
            ))

    for task in list_tasks(db_path=db_path):
        if task.status != TaskStatus.DONE and task.due_date and task.due_date >= today:
            dt = datetime.combine(task.due_date, datetime.min.time())
            candidates.append((
                dt,
                SavedDataRecord(
                    record_type="task",
                    title=task.title,
                    when=str(task.due_date),
                    status=task.status,
                ),
            ))

    for act in list_activities(db_path=db_path):
        if (
            act.status == ActivityStatus.PLANNED
            and act.logged_at
            and act.logged_at >= now
        ):
            candidates.append((
                act.logged_at,
                SavedDataRecord(
                    record_type="activity",
                    title=act.title,
                    when=_fmt_dt(act.logged_at),
                    status="planned",
                ),
            ))

    if not candidates:
        return SavedDataQueryResult(
            query_type=QueryType.NEXT_UPCOMING,
            question=msg,
            matched=False,
            fallback_message="No upcoming saved items found.",
        )

    candidates.sort(key=lambda c: c[0])
    earliest_dt = candidates[0][0]
    records = [rec for dt, rec in candidates if dt == earliest_dt]

    return SavedDataQueryResult(
        query_type=QueryType.NEXT_UPCOMING,
        question=msg,
        matched=True,
        records=records,
    )


_MAX_UNDATED_TASKS = 3


def _query_daily_focus(
    msg: str, today: date, *, db_path: str | None
) -> SavedDataQueryResult:
    """Collect today's focus items in priority order."""
    records: list[SavedDataRecord] = []

    from life_agent.db.repositories import (
        list_activities,
        list_events,
        list_reminders,
        list_tasks,
    )
    from life_agent.models.common import ActivityStatus, ReminderStatus, TaskStatus

    for event in list_events(db_path=db_path):
        if event.start_time and event.start_time.date() == today:
            records.append(SavedDataRecord(
                record_type="event",
                title=event.title,
                when=_fmt_dt(event.start_time),
                details="scheduled today",
            ))

    dated_task_count = 0
    for task in list_tasks(db_path=db_path):
        if task.status != TaskStatus.DONE and task.due_date == today:
            records.append(SavedDataRecord(
                record_type="task",
                title=task.title,
                when=str(today),
                status=task.status,
                details="due today",
            ))
            dated_task_count += 1

    for rem in list_reminders(status=ReminderStatus.PENDING, db_path=db_path):
        if rem.remind_at and rem.remind_at.date() == today:
            records.append(SavedDataRecord(
                record_type="reminder",
                title=rem.title or "(untitled)",
                when=_fmt_dt(rem.remind_at),
                status="pending",
                details="scheduled today",
            ))

    for act in list_activities(db_path=db_path):
        if (
            act.status == ActivityStatus.PLANNED
            and act.logged_at
            and act.logged_at.date() == today
        ):
            records.append(SavedDataRecord(
                record_type="activity",
                title=act.title,
                when=_fmt_dt(act.logged_at),
                status="planned",
                details="scheduled today",
            ))

    if dated_task_count == 0:
        undated = [
            t for t in list_tasks(db_path=db_path)
            if t.status != TaskStatus.DONE and t.due_date is None
        ]
        for task in undated[:_MAX_UNDATED_TASKS]:
            records.append(SavedDataRecord(
                record_type="task",
                title=task.title,
                status=task.status,
                details="pending",
            ))

    return SavedDataQueryResult(
        query_type=QueryType.DAILY_FOCUS,
        question=msg,
        matched=len(records) > 0,
        records=records,
        fallback_message=None if records else f"No saved focus items found for today ({today}).",
    )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "jag", "du", "ska", "att", "om", "på", "för", "den", "det", "en", "ett",
    "när", "vad", "har", "är", "tid", "vilken", "påminna", "påminner",
    "mig", "något", "planerat", "imorgon", "idag", "den", "här", "veckan",
    "träningar", "träning", "gym",
})


def _extract_keywords(msg: str) -> list[str]:
    """Return meaningful lowercase words from *msg*, filtering stop words."""
    words = re.findall(r"[a-zäöå]+", msg.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 2]


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "(unknown time)"
    return dt.strftime("%Y-%m-%d %H:%M")
