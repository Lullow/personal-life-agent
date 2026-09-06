"""CRUD repository functions for tasks, events, and activities."""

import sqlite3
import uuid
from datetime import date, datetime, timedelta

from life_agent.db.database import get_connection
from life_agent.models import ActivityLog, CalendarEvent, Reminder, Task
from life_agent.models.common import (
    ActivityStatus,
    ActivityType,
    EventCategory,
    Priority,
    ReminderStatus,
    ReminderTargetType,
    TaskCategory,
    TaskStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(value: datetime | date | None) -> str | None:
    """Serialise a datetime or date to an ISO-8601 string."""
    return value.isoformat() if value is not None else None


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def _timestamp_range(
    column: str,
    start: date | None,
    end: date | None,
) -> tuple[list[str], list[str]]:
    """SQL clauses bounding an ISO timestamp *column* to whole calendar days.

    Timestamps are stored as ISO-8601 text, which sorts chronologically, so a
    day range is a plain string comparison: ``>= "2026-03-01"`` includes every
    time on 1 March, and ``< "2026-04-01"`` includes all of 31 March.  Both
    bounds are inclusive days.
    """
    clauses: list[str] = []
    params: list[str] = []
    if start is not None:
        clauses.append(f"{column} >= ?")
        params.append(start.isoformat())
    if end is not None:
        clauses.append(f"{column} < ?")
        params.append((end + timedelta(days=1)).isoformat())
    return clauses, params


def _delete_row(table: str, row_id: str | int, db_path: str | None = None) -> bool:
    """Delete one row by id and report whether it existed.

    *table* is never user-supplied — callers pass one of the four literals
    below, so this cannot become an injection point.
    """
    if table not in {"tasks", "events", "activities", "reminders"}:
        raise ValueError(f"unknown table: {table}")
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _where(clauses: list[str]) -> str:
    return (" WHERE " + " AND ".join(clauses)) if clauses else ""


# ---------------------------------------------------------------------------
# Task repository
# ---------------------------------------------------------------------------

def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        priority=Priority(row["priority"]),
        status=TaskStatus(row["status"]),
        category=TaskCategory(row["category"]),
        estimated_minutes=row["estimated_minutes"],
        due_date=_parse_date(row["due_date"]),
        created_at=_parse_datetime(row["created_at"]),  # type: ignore[arg-type]
        updated_at=_parse_datetime(row["updated_at"]),
    )


def create_task(task: Task, db_path: str | None = None) -> Task:
    """Insert a new task and return it with a generated id."""
    task_id = task.id or str(uuid.uuid4())
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO tasks
               (id, title, description, priority, status, category,
                estimated_minutes, due_date, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task_id,
                task.title,
                task.description,
                str(task.priority),
                str(task.status),
                str(task.category),
                task.estimated_minutes,
                _iso(task.due_date),
                _iso(task.created_at),
                _iso(task.updated_at),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return task.model_copy(update={"id": task_id})


def list_tasks(
    db_path: str | None = None,
    *,
    due_from: date | None = None,
    due_to: date | None = None,
) -> list[Task]:
    """Return tasks ordered by creation time (newest first).

    *due_from* and *due_to* are inclusive bounds on ``due_date``; passing
    either drops tasks that have no due date at all.
    """
    clauses: list[str] = []
    params: list[str] = []
    if due_from is not None:
        clauses.append("due_date >= ?")
        params.append(due_from.isoformat())
    if due_to is not None:
        clauses.append("due_date <= ?")
        params.append(due_to.isoformat())

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            f"SELECT * FROM tasks{_where(clauses)} ORDER BY created_at DESC",
            params,
        ).fetchall()
        return [_row_to_task(r) for r in rows]
    finally:
        conn.close()


def get_task(task_id: str, db_path: str | None = None) -> Task | None:
    """Fetch a single task by id, or *None* if not found."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return _row_to_task(row) if row else None
    finally:
        conn.close()


def update_task_status(
    task_id: str,
    status: TaskStatus,
    db_path: str | None = None,
) -> Task | None:
    """Set a new status on a task and return the updated model."""
    now = _iso(datetime.now())
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (str(status), now, task_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_task(task_id, db_path)


# ---------------------------------------------------------------------------
# Event repository
# ---------------------------------------------------------------------------

def update_task_due_date(
    task_id: str,
    due_date: date | None,
    db_path: str | None = None,
) -> Task | None:
    """Change a task's due date and return the updated row."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE tasks SET due_date = ?, updated_at = ? WHERE id = ?",
            (_iso(due_date), _iso(datetime.now()), task_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_task(task_id, db_path)


def delete_task(task_id: str, db_path: str | None = None) -> bool:
    """Delete a task; return whether a row was removed."""
    return _delete_row("tasks", task_id, db_path)


def _row_to_event(row: sqlite3.Row) -> CalendarEvent:
    return CalendarEvent(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        category=EventCategory(row["category"]),
        start_time=_parse_datetime(row["start_time"]),  # type: ignore[arg-type]
        end_time=_parse_datetime(row["end_time"]),
        location=row["location"],
        created_at=_parse_datetime(row["created_at"]),  # type: ignore[arg-type]
    )


def create_event(event: CalendarEvent, db_path: str | None = None) -> CalendarEvent:
    """Insert a new event and return it with a generated id."""
    event_id = event.id or str(uuid.uuid4())
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO events
               (id, title, description, category, start_time, end_time,
                location, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                event.title,
                event.description,
                str(event.category),
                _iso(event.start_time),
                _iso(event.end_time),
                event.location,
                _iso(event.created_at),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return event.model_copy(update={"id": event_id})


def list_events(
    db_path: str | None = None,
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[CalendarEvent]:
    """Return events ordered by start time (soonest first).

    *start* and *end* are inclusive calendar-day bounds on ``start_time``.
    """
    clauses, params = _timestamp_range("start_time", start, end)
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            f"SELECT * FROM events{_where(clauses)} ORDER BY start_time ASC",
            params,
        ).fetchall()
        return [_row_to_event(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Activity repository
# ---------------------------------------------------------------------------

def get_event(event_id: str, db_path: str | None = None) -> CalendarEvent | None:
    """Fetch a single event by id, or *None* if not found."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        return _row_to_event(row) if row else None
    finally:
        conn.close()


def update_event_time(
    event_id: str,
    start_time: datetime,
    end_time: datetime | None = None,
    db_path: str | None = None,
) -> CalendarEvent | None:
    """Move an event to a new start (and optional end) time."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE events SET start_time = ?, end_time = ? WHERE id = ?",
            (_iso(start_time), _iso(end_time), event_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_event(event_id, db_path)


def delete_event(event_id: str, db_path: str | None = None) -> bool:
    """Delete an event; return whether a row was removed."""
    return _delete_row("events", event_id, db_path)


def _row_to_activity(row: sqlite3.Row) -> ActivityLog:
    return ActivityLog(
        id=row["id"],
        title=row["title"],
        activity_type=ActivityType(row["activity_type"]),
        status=ActivityStatus(row["status"]),
        duration_minutes=row["duration_minutes"],
        logged_at=_parse_datetime(row["logged_at"]),  # type: ignore[arg-type]
        notes=row["notes"],
        created_at=_parse_datetime(row["created_at"]),  # type: ignore[arg-type]
    )


def create_activity(activity: ActivityLog, db_path: str | None = None) -> ActivityLog:
    """Insert a new activity and return it with a generated id."""
    activity_id = activity.id or str(uuid.uuid4())
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO activities
               (id, title, activity_type, status, duration_minutes, logged_at,
                notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                activity_id,
                activity.title,
                str(activity.activity_type),
                str(activity.status),
                activity.duration_minutes,
                _iso(activity.logged_at),
                activity.notes,
                _iso(activity.created_at),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return activity.model_copy(update={"id": activity_id})


def list_activities(
    status: str | None = None,
    db_path: str | None = None,
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[ActivityLog]:
    """Return activities ordered by logged time (newest first).

    When *status* is provided, only activities with that status are returned.
    *start* and *end* are inclusive calendar-day bounds on ``logged_at``.
    """
    clauses, params = _timestamp_range("logged_at", start, end)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            f"SELECT * FROM activities{_where(clauses)} ORDER BY logged_at DESC",
            params,
        ).fetchall()
        return [_row_to_activity(r) for r in rows]
    finally:
        conn.close()


def list_planned_activities(db_path: str | None = None) -> list[ActivityLog]:
    """Return planned activities ordered by logged time (newest first)."""
    return list_activities(status=str(ActivityStatus.PLANNED), db_path=db_path)


def get_activity(activity_id: str, db_path: str | None = None) -> ActivityLog | None:
    """Fetch a single activity by id, or *None* if not found."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM activities WHERE id = ?", (activity_id,)
        ).fetchone()
        return _row_to_activity(row) if row else None
    finally:
        conn.close()


def update_activity_status(
    activity_id: str,
    status: str,
    db_path: str | None = None,
) -> ActivityLog | None:
    """Update an activity's status and return the refreshed model."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "UPDATE activities SET status = ? WHERE id = ?",
            (status, activity_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    finally:
        conn.close()
    return get_activity(activity_id, db_path)


# ---------------------------------------------------------------------------
# Reminder repository
# ---------------------------------------------------------------------------

def update_activity_time(
    activity_id: str,
    logged_at: datetime,
    db_path: str | None = None,
) -> ActivityLog | None:
    """Move an activity to a new point in time."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE activities SET logged_at = ? WHERE id = ?",
            (_iso(logged_at), activity_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_activity(activity_id, db_path)


def delete_activity(activity_id: str, db_path: str | None = None) -> bool:
    """Delete an activity; return whether a row was removed."""
    return _delete_row("activities", activity_id, db_path)


def _row_to_reminder(row: sqlite3.Row) -> Reminder:
    return Reminder(
        id=row["id"],
        title=row["title"],
        message=row["message"],
        remind_at=_parse_datetime(row["remind_at"]),  # type: ignore[arg-type]
        target_type=ReminderTargetType(row["target_type"]),
        target_id=row["target_id"],
        status=ReminderStatus(row["status"]),
        created_at=_parse_datetime(row["created_at"]),  # type: ignore[arg-type]
    )


def create_reminder(reminder: Reminder, db_path: str | None = None) -> Reminder:
    """Insert a new reminder.  The database assigns an integer ``id``."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """INSERT INTO reminders
               (title, message, remind_at, target_type, target_id, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                reminder.title,
                reminder.message,
                _iso(reminder.remind_at),
                str(reminder.target_type),
                reminder.target_id,
                str(reminder.status),
                _iso(reminder.created_at),
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()

    return reminder.model_copy(update={"id": new_id})


def list_reminders(
    status: str | None = None,
    db_path: str | None = None,
) -> list[Reminder]:
    """Return reminders ordered by ``remind_at`` (soonest first).

    When *status* is provided, only reminders with that status are returned.
    """
    conn = get_connection(db_path)
    try:
        if status is None:
            rows = conn.execute(
                "SELECT * FROM reminders ORDER BY remind_at ASC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE status = ? ORDER BY remind_at ASC",
                (status,),
            ).fetchall()
        return [_row_to_reminder(r) for r in rows]
    finally:
        conn.close()


def list_upcoming_reminders(db_path: str | None = None) -> list[Reminder]:
    """Return pending reminders ordered by ``remind_at`` ascending."""
    return list_reminders(status=str(ReminderStatus.PENDING), db_path=db_path)


def get_reminder(reminder_id: int, db_path: str | None = None) -> Reminder | None:
    """Fetch a single reminder by id, or *None* if not found."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
        ).fetchone()
        return _row_to_reminder(row) if row else None
    finally:
        conn.close()


def update_reminder_time(
    reminder_id: int,
    remind_at: datetime,
    db_path: str | None = None,
) -> Reminder | None:
    """Move a reminder to a new time."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE reminders SET remind_at = ? WHERE id = ?",
            (_iso(remind_at), reminder_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_reminder(reminder_id, db_path)


def delete_reminder(reminder_id: int, db_path: str | None = None) -> bool:
    """Delete a reminder; return whether a row was removed."""
    return _delete_row("reminders", reminder_id, db_path)


def update_reminder_status(
    reminder_id: int,
    status: str,
    db_path: str | None = None,
) -> Reminder | None:
    """Update a reminder's status and return the refreshed model."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "UPDATE reminders SET status = ? WHERE id = ?",
            (status, reminder_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    finally:
        conn.close()
    return get_reminder(reminder_id, db_path)
