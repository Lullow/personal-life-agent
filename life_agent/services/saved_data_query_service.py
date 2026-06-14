"""Read-only service for answering simple questions about saved data.

This service never writes to the database.  It queries existing repositories
and returns a plain-text answer.

Three categories are supported:

1. **Reminder lookup** — "vilken tid ska du påminna mig om att handla mat"
   Searches pending reminders by keyword and reports the scheduled time.

2. **Planned tomorrow** — "har jag något planerat imorgon"
   Aggregates events, tasks, activities, and reminders for tomorrow.

3. **Training this week** — "vad har jag för träningar den här veckan"
   Lists gym/sport activities within the current week.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta


def answer_saved_data_question(
    message: str,
    db_path: str | None = None,
    *,
    today: date | None = None,
) -> str:
    """Return a plain-text answer for *message*, or a polite fallback."""
    msg = message.strip()
    _today = today or date.today()

    if _is_reminder_question(msg):
        return _answer_reminder_question(msg, db_path=db_path)

    if _is_tomorrow_question(msg):
        return _answer_tomorrow_question(_today, db_path=db_path)

    if _is_training_week_question(msg):
        return _answer_training_week_question(_today, db_path=db_path)

    return "I couldn't find a specific answer for that yet."


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


def _is_reminder_question(msg: str) -> bool:
    return any(p.search(msg) for p in _REMINDER_Q_PATTERNS)


def _is_tomorrow_question(msg: str) -> bool:
    return any(p.search(msg) for p in _TOMORROW_Q_PATTERNS)


def _is_training_week_question(msg: str) -> bool:
    return any(p.search(msg) for p in _TRAINING_WEEK_PATTERNS)


# ---------------------------------------------------------------------------
# Answer helpers
# ---------------------------------------------------------------------------

def _answer_reminder_question(msg: str, *, db_path: str | None) -> str:
    from life_agent.db.repositories import list_reminders
    from life_agent.models.common import ReminderStatus

    pending = list_reminders(status=ReminderStatus.PENDING, db_path=db_path)
    if not pending:
        return "You have no pending reminders."

    keywords = _extract_keywords(msg)

    matches = [
        r for r in pending
        if r.title and any(kw in r.title.lower() for kw in keywords)
    ]

    if not matches:
        lines = [f"  • {r.title} at {_fmt_dt(r.remind_at)}" for r in pending]
        return "No reminder matched your query. Pending reminders:\n" + "\n".join(lines)

    parts = []
    for r in matches:
        parts.append(f"You have a reminder for {r.title} at {_fmt_dt(r.remind_at)}.")
    return "\n".join(parts)


def _answer_tomorrow_question(today: date, *, db_path: str | None) -> str:
    tomorrow = today + timedelta(days=1)
    lines: list[str] = []

    from life_agent.db.repositories import list_activities, list_events, list_reminders, list_tasks
    from life_agent.models.common import ReminderStatus, TaskStatus

    for event in list_events(db_path=db_path):
        if event.start_time and event.start_time.date() == tomorrow:
            lines.append(f"  • Event: {event.title} at {_fmt_dt(event.start_time)}")

    for task in list_tasks(db_path=db_path):
        if task.status != TaskStatus.DONE and task.due_date == tomorrow:
            lines.append(f"  • Task: {task.title} (due {tomorrow})")

    for act in list_activities(db_path=db_path):
        if act.logged_at and act.logged_at.date() == tomorrow:
            lines.append(f"  • Activity: {act.title}")

    for rem in list_reminders(status=ReminderStatus.PENDING, db_path=db_path):
        if rem.remind_at and rem.remind_at.date() == tomorrow:
            lines.append(f"  • Reminder: {rem.title} at {_fmt_dt(rem.remind_at)}")

    if not lines:
        return f"Nothing is planned for tomorrow ({tomorrow})."
    return f"Planned for tomorrow ({tomorrow}):\n" + "\n".join(lines)


def _answer_training_week_question(today: date, *, db_path: str | None) -> str:
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

    if not training:
        return f"No training activities found this week ({week_start} – {week_end})."

    lines = [f"  • {a.title} on {a.logged_at.date()}" for a in training]
    return f"Training this week ({week_start} – {week_end}):\n" + "\n".join(lines)


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
