"""Tests for the planner service."""

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from life_agent.db.repositories import (
    create_event,
    create_task,
    update_task_status,
)
from life_agent.db.schema import init_db
from life_agent.models import CalendarEvent, Task
from life_agent.models.common import Priority, TaskCategory, TaskStatus
from life_agent.services.planner_service import (
    get_today_agenda,
    get_upcoming_deadlines,
    get_week_agenda,
)


@pytest.fixture()
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "planner.db")
        init_db(path)
        yield path


# ---------------------------------------------------------------------------
# get_today_agenda
# ---------------------------------------------------------------------------

def test_today_events_sorted_by_start_time(db_path):
    today = date(2026, 6, 11)
    create_event(
        CalendarEvent(title="Late meeting", start_time=datetime(2026, 6, 11, 15, 0)),
        db_path,
    )
    create_event(
        CalendarEvent(title="Standup", start_time=datetime(2026, 6, 11, 9, 0)),
        db_path,
    )
    create_event(
        CalendarEvent(title="Lunch", start_time=datetime(2026, 6, 11, 12, 30)),
        db_path,
    )
    # Add an event for a different day — must be excluded.
    create_event(
        CalendarEvent(title="Tomorrow", start_time=datetime(2026, 6, 12, 10, 0)),
        db_path,
    )

    agenda = get_today_agenda(today=today, db_path=db_path)
    titles = [e.title for e in agenda.events]
    assert titles == ["Standup", "Lunch", "Late meeting"]


def test_today_excludes_done_tasks(db_path):
    today = date(2026, 6, 11)
    pending = create_task(
        Task(title="Pay invoice", due_date=today, priority=Priority.MEDIUM),
        db_path,
    )
    finished = create_task(
        Task(title="Already done", due_date=today, priority=Priority.HIGH),
        db_path,
    )
    update_task_status(finished.id, TaskStatus.DONE, db_path)

    agenda = get_today_agenda(today=today, db_path=db_path)
    titles_today = [t.title for t in agenda.tasks_due_today]
    assert pending.title in titles_today
    assert finished.title not in titles_today


def test_today_includes_undated_pending_tasks_separately(db_path):
    today = date(2026, 6, 11)
    create_task(
        Task(title="Due today", due_date=today, priority=Priority.MEDIUM),
        db_path,
    )
    create_task(
        Task(title="No due date", priority=Priority.HIGH),
        db_path,
    )

    agenda = get_today_agenda(today=today, db_path=db_path)
    assert [t.title for t in agenda.tasks_due_today] == ["Due today"]
    assert [t.title for t in agenda.undated_tasks] == ["No due date"]


def test_today_tasks_due_today_sorted_by_priority(db_path):
    today = date(2026, 6, 11)
    create_task(Task(title="Low", due_date=today, priority=Priority.LOW), db_path)
    create_task(Task(title="High", due_date=today, priority=Priority.HIGH), db_path)
    create_task(Task(title="Medium", due_date=today, priority=Priority.MEDIUM), db_path)

    agenda = get_today_agenda(today=today, db_path=db_path)
    assert [t.title for t in agenda.tasks_due_today] == ["High", "Medium", "Low"]


def test_today_empty_when_nothing_scheduled(db_path):
    agenda = get_today_agenda(today=date(2026, 6, 11), db_path=db_path)
    assert agenda.events == []
    assert agenda.tasks_due_today == []
    assert agenda.undated_tasks == []


# ---------------------------------------------------------------------------
# get_week_agenda
# ---------------------------------------------------------------------------

def test_week_agenda_spans_seven_days(db_path):
    start = date(2026, 6, 11)
    agenda = get_week_agenda(start=start, db_path=db_path)
    assert agenda.start_date == start
    assert agenda.end_date == start + timedelta(days=6)
    assert len(agenda.days) == 7
    assert [d.date for d in agenda.days] == [
        start + timedelta(days=i) for i in range(7)
    ]


def test_week_groups_items_by_day_and_excludes_outside_range(db_path):
    start = date(2026, 6, 11)
    create_event(
        CalendarEvent(title="In week", start_time=datetime(2026, 6, 13, 9, 0)),
        db_path,
    )
    create_event(
        CalendarEvent(title="Out of week", start_time=datetime(2026, 6, 20, 9, 0)),
        db_path,
    )
    create_task(
        Task(title="Mid-week task", due_date=date(2026, 6, 14), category=TaskCategory.STUDY),
        db_path,
    )

    agenda = get_week_agenda(start=start, db_path=db_path)
    found_events = [e.title for d in agenda.days for e in d.events]
    found_tasks = [t.title for d in agenda.days for t in d.tasks]
    assert "In week" in found_events
    assert "Out of week" not in found_events
    assert "Mid-week task" in found_tasks


def test_week_excludes_done_tasks(db_path):
    start = date(2026, 6, 11)
    pending = create_task(
        Task(title="Pending", due_date=date(2026, 6, 12)),
        db_path,
    )
    done = create_task(
        Task(title="Completed", due_date=date(2026, 6, 12)),
        db_path,
    )
    update_task_status(done.id, TaskStatus.DONE, db_path)

    agenda = get_week_agenda(start=start, db_path=db_path)
    found_tasks = [t.title for d in agenda.days for t in d.tasks]
    assert pending.title in found_tasks
    assert done.title not in found_tasks


# ---------------------------------------------------------------------------
# get_upcoming_deadlines
# ---------------------------------------------------------------------------

def test_deadlines_sorted_by_due_date_then_priority(db_path):
    create_task(
        Task(title="Later high", due_date=date(2026, 6, 20), priority=Priority.HIGH),
        db_path,
    )
    create_task(
        Task(title="Sooner low", due_date=date(2026, 6, 12), priority=Priority.LOW),
        db_path,
    )
    create_task(
        Task(title="Same day low", due_date=date(2026, 6, 15), priority=Priority.LOW),
        db_path,
    )
    create_task(
        Task(title="Same day high", due_date=date(2026, 6, 15), priority=Priority.HIGH),
        db_path,
    )
    create_task(
        Task(title="Same day medium", due_date=date(2026, 6, 15), priority=Priority.MEDIUM),
        db_path,
    )

    deadlines = get_upcoming_deadlines(db_path)
    titles = [t.title for t in deadlines]
    assert titles == [
        "Sooner low",
        "Same day high",
        "Same day medium",
        "Same day low",
        "Later high",
    ]


def test_deadlines_excludes_done_and_undated(db_path):
    create_task(Task(title="Undated"), db_path)
    pending = create_task(
        Task(title="Pending with due", due_date=date(2026, 6, 15)),
        db_path,
    )
    done = create_task(
        Task(title="Finished", due_date=date(2026, 6, 15)),
        db_path,
    )
    update_task_status(done.id, TaskStatus.DONE, db_path)

    deadlines = get_upcoming_deadlines(db_path)
    titles = [t.title for t in deadlines]
    assert titles == [pending.title]


def test_deadlines_empty_when_no_dated_pending_tasks(db_path):
    create_task(Task(title="Undated only"), db_path)
    assert get_upcoming_deadlines(db_path) == []
