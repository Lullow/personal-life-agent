"""Mark a planned activity as completed from a natural-language phrase.

This is intentionally simple and deterministic: it recognises a small set of
Swedish/English "I'm done" phrases, finds the most relevant planned activity,
and — only after explicit confirmation — flips its status to ``completed``.

It never updates the database without confirmation.
"""

import re
from datetime import date, timedelta

from life_agent.agent.safety import assert_confirmed
from life_agent.db.repositories import list_planned_activities
from life_agent.models import ActivityLog
from life_agent.models.common import ActivityType
from life_agent.services.activity_service import mark_activity_completed

# Phrases that signal "an activity is finished".
_COMPLETION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"tränat\s+klart",
        r"tränat\s+färdigt",
        r"träning(?:en)?\s+är\s+klar",
        r"träning(?:en)?\s+är\s+färdig",
        r"klar\s+med\s+träning",
        r"färdig\s+med\s+träning",
        r"har\s+tränat",
        r"\bär\s+klar\b",
        r"\bär\s+färdig\b",
        r"\bklart\b",
        r"done\s+training",
        r"finished\s+(?:training|workout|my\s+workout)",
        r"done\s+with\s+(?:training|my\s+workout|the\s+workout)",
    )
]

# Hints that point at a particular activity type within a completion phrase.
_TYPE_HINTS: dict[ActivityType, tuple[str, ...]] = {
    ActivityType.GYM: ("träna", "tränat", "träning", "gym", "workout"),
    ActivityType.RUN: ("spring", "sprang", "löpning", "löpt", "run", "ran"),
    ActivityType.WALK: ("promenad", "promenerat", "gått", "walk", "walked"),
    ActivityType.STUDY: ("plugga", "pluggat", "studerat", "studied", "study"),
}


def is_completion_phrase(text: str) -> bool:
    """Return *True* if *text* looks like an activity-completion statement."""
    if not text:
        return False
    return any(p.search(text) for p in _COMPLETION_PATTERNS)


def _detect_type_hint(text: str) -> ActivityType | None:
    lower = text.lower()
    for activity_type, keywords in _TYPE_HINTS.items():
        if any(re.search(rf"\b{re.escape(k)}", lower) for k in keywords):
            return activity_type
    return None


def find_completion_candidate(
    text: str,
    reference_date: date | None = None,
    db_path: str | None = None,
) -> ActivityLog | None:
    """Find the planned activity that a completion phrase most likely refers to.

    Strategy:
      1. Prefer planned activities scheduled for *today*.
      2. Otherwise look within a small window (yesterday..tomorrow) and pick
         the one nearest to today.
      3. When the phrase hints at a type (e.g. "tränat" -> gym), prefer
         matching activities, but fall back to any planned activity.
    """
    today = reference_date or date.today()
    planned = list_planned_activities(db_path)
    if not planned:
        return None

    type_hint = _detect_type_hint(text)

    def _candidates(items: list[ActivityLog]) -> list[ActivityLog]:
        if type_hint is not None:
            typed = [a for a in items if a.activity_type == type_hint]
            if typed:
                return typed
        return items

    # 1. Today.
    today_items = [a for a in planned if a.logged_at.date() == today]
    today_items = _candidates(today_items)
    if today_items:
        today_items.sort(key=lambda a: a.logged_at)
        return today_items[0]

    # 2. Window: yesterday..tomorrow, nearest to today.
    window_start = today - timedelta(days=1)
    window_end = today + timedelta(days=1)
    window_items = [
        a for a in planned if window_start <= a.logged_at.date() <= window_end
    ]
    window_items = _candidates(window_items)
    if window_items:
        window_items.sort(
            key=lambda a: (abs((a.logged_at.date() - today).days), a.logged_at)
        )
        return window_items[0]

    return None


def complete_activity(
    activity_id: str,
    confirmed: bool = True,
    db_path: str | None = None,
) -> ActivityLog | None:
    """Mark the given activity as completed, only when *confirmed* is True."""
    assert_confirmed(confirmed)
    return mark_activity_completed(activity_id, db_path)
