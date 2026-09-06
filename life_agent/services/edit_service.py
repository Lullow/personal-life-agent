"""Find, reschedule, and delete saved items from a description.

The agent never handles database ids.  It says what the user meant — a piece of
a title, optionally a kind and a day — and this module resolves that to actual
rows.  Resolution is deterministic code, the resolved row is shown to the user
in full, and nothing changes without an explicit confirmation, so a wrong match
is caught by a person rather than by a prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from life_agent.agent.safety import assert_confirmed
from life_agent.db.repositories import (
    delete_activity,
    delete_event,
    delete_reminder,
    delete_task,
    list_activities,
    list_events,
    list_reminders,
    list_tasks,
    update_activity_time,
    update_event_time,
    update_reminder_time,
    update_task_due_date,
)

ITEM_TYPES: tuple[str, ...] = ("task", "event", "activity", "reminder")


@dataclass(frozen=True)
class ItemMatch:
    """One saved row, identified well enough to change or remove it."""

    item_type: str
    item_id: str | int
    title: str
    when: datetime | None
    day: date | None

    def describe(self) -> str:
        if self.when is not None:
            stamp = self.when.strftime("%Y-%m-%d %H:%M")
        elif self.day is not None:
            stamp = self.day.isoformat()
        else:
            stamp = "no date"
        return f"{self.item_type}: {self.title} ({stamp})"


def _all_items(db_path: str | None) -> list[ItemMatch]:
    items: list[ItemMatch] = []

    for task in list_tasks(db_path):
        items.append(
            ItemMatch("task", task.id, task.title, None, task.due_date)
        )
    for event in list_events(db_path):
        items.append(
            ItemMatch(
                "event",
                event.id,
                event.title,
                event.start_time,
                event.start_time.date(),
            )
        )
    for activity in list_activities(db_path=db_path):
        items.append(
            ItemMatch(
                "activity",
                activity.id,
                activity.title,
                activity.logged_at,
                activity.logged_at.date(),
            )
        )
    for reminder in list_reminders(db_path=db_path):
        items.append(
            ItemMatch(
                "reminder",
                reminder.id,
                reminder.title,
                reminder.remind_at,
                reminder.remind_at.date(),
            )
        )
    return items


_WORD_SPLIT = re.compile(r"[^0-9a-zåäöéü]+", re.IGNORECASE)
_STEM_LENGTH = 4


def _words(text: str) -> list[str]:
    return [w for w in _WORD_SPLIT.split(text.lower()) if w]


def _same_word(a: str, b: str) -> bool:
    """Whether two words are the same word, allowing for Swedish inflection.

    The agent describes what the user said — "ryggpasset", "lämningen" — while
    the stored titles read "Träna rygg" and "Lämna grabben på förskolan".
    Neither pair is a prefix of the other ("lämna" and "lämningen" part company
    at the fifth character), so what counts is a shared opening of four
    characters.  That is a stemmer's worth of accuracy for none of its weight.
    """
    if a == b:
        return True
    if min(len(a), len(b)) < _STEM_LENGTH:
        return False
    shared = 0
    for left, right in zip(a, b):
        if left != right:
            break
        shared += 1
    return shared >= _STEM_LENGTH


def _score(needle_words: list[str], title: str) -> int:
    """How many of the description's words appear in *title*."""
    title_words = _words(title)
    return sum(1 for n in needle_words if any(_same_word(n, t) for t in title_words))


def find_items(
    title: str | None = None,
    item_type: str | None = None,
    day: date | None = None,
    db_path: str | None = None,
) -> list[ItemMatch]:
    """Return the saved items that best match a description.

    Only the best-scoring group is returned: a description that clearly points
    at one row resolves to that row, while a genuinely ambiguous one ("träna",
    when two sessions are saved) comes back as several for the user to pick
    between.  An empty description matches nothing — removing "everything" is
    not something the agent gets to propose.
    """
    needle = (title or "").strip().lower()
    if not needle and item_type is None and day is None:
        return []

    matches = _all_items(db_path)
    if item_type is not None:
        matches = [m for m in matches if m.item_type == item_type]
    if day is not None:
        matches = [m for m in matches if m.day == day]

    if needle:
        needle_words = _words(needle)
        scored = [(_score(needle_words, m.title), m) for m in matches]
        scored = [(score, m) for score, m in scored if score > 0 or needle in m.title.lower()]
        if not scored:
            return []
        best = max(score for score, _ in scored)
        matches = [m for score, m in scored if score == best]

    matches.sort(key=lambda m: (m.day is None, m.day or date.min, m.title))
    return matches


def delete_item(
    match: ItemMatch,
    confirmed: bool = True,
    db_path: str | None = None,
) -> bool:
    """Delete the matched row.  Raises without an explicit confirmation."""
    assert_confirmed(confirmed)

    deleters = {
        "task": delete_task,
        "event": delete_event,
        "activity": delete_activity,
        "reminder": delete_reminder,
    }
    deleter = deleters.get(match.item_type)
    if deleter is None:
        return False
    return deleter(match.item_id, db_path)


def reschedule_item(
    match: ItemMatch,
    new_time: datetime,
    confirmed: bool = True,
    db_path: str | None = None,
):
    """Move the matched row to *new_time*, or ``None`` if it could not move.

    A task carries only a due date, so for a task the clock time is dropped
    rather than silently stored somewhere it will not be read back.
    """
    assert_confirmed(confirmed)

    if match.item_type == "event":
        return update_event_time(match.item_id, new_time, None, db_path)
    if match.item_type == "activity":
        return update_activity_time(match.item_id, new_time, db_path)
    if match.item_type == "reminder":
        return update_reminder_time(match.item_id, new_time, db_path)
    if match.item_type == "task":
        return update_task_due_date(match.item_id, new_time.date(), db_path)
    return None
