"""Read-only planner that combines tasks and events into agendas.

The planner never modifies the database. It loads tasks, events, and
activities from the repository layer and arranges them for display.

Every view is a date range: :func:`get_day_agenda` and :func:`get_range_agenda`
take explicit dates, and ``get_today_agenda`` / ``get_week_agenda`` are the
today-shaped defaults over them.
"""

from datetime import date, timedelta

from life_agent.db.repositories import list_activities, list_events, list_tasks
from life_agent.models import ActivityLog, CalendarEvent, Task
from life_agent.models.common import Priority, TaskStatus
from life_agent.schemas.planner import DayPlan, TodayAgenda, WeekAgenda

_PRIORITY_RANK: dict[Priority, int] = {
    Priority.HIGH: 0,
    Priority.MEDIUM: 1,
    Priority.LOW: 2,
}


def _priority_rank(priority: Priority) -> int:
    return _PRIORITY_RANK.get(priority, 99)


def _active_tasks(db_path: str | None) -> list[Task]:
    return [t for t in list_tasks(db_path) if t.status == TaskStatus.PENDING]


def _sort_events_by_start(events: list[CalendarEvent]) -> list[CalendarEvent]:
    return sorted(events, key=lambda e: e.start_time)


def _sort_tasks_by_priority(tasks: list[Task]) -> list[Task]:
    return sorted(tasks, key=lambda t: _priority_rank(t.priority))


def _sort_activities_by_time(activities: list[ActivityLog]) -> list[ActivityLog]:
    return sorted(activities, key=lambda a: a.logged_at)


def _activities_between(
    start: date, end: date, db_path: str | None
) -> list[ActivityLog]:
    return _sort_activities_by_time(
        list_activities(db_path=db_path, start=start, end=end)
    )


def get_day_agenda(
    day: date | None = None,
    db_path: str | None = None,
) -> TodayAgenda:
    """Return one day's events, tasks due that day, activities, and undated tasks."""
    target = day or date.today()

    events = _sort_events_by_start(list_events(db_path, start=target, end=target))

    active = _active_tasks(db_path)
    tasks_due_today = _sort_tasks_by_priority(
        [t for t in active if t.due_date == target]
    )
    undated_tasks = _sort_tasks_by_priority(
        [t for t in active if t.due_date is None]
    )

    return TodayAgenda(
        date=target,
        events=events,
        tasks_due_today=tasks_due_today,
        undated_tasks=undated_tasks,
        activities=_activities_between(target, target, db_path),
    )


def get_today_agenda(
    today: date | None = None,
    db_path: str | None = None,
) -> TodayAgenda:
    """Return today's agenda (:func:`get_day_agenda` for the current date)."""
    return get_day_agenda(today, db_path)


def get_range_agenda(
    start: date,
    end: date,
    db_path: str | None = None,
) -> WeekAgenda:
    """Return a day-by-day plan for the inclusive range *start*..*end*.

    Each day shows its events (sorted by start time), pending tasks due that
    day (sorted by priority), and activities logged or planned that day.  This
    is how the agent answers both "imorgon" and "vad gjorde jag i mars".
    """
    if end < start:
        raise ValueError("end must not be before start")

    all_events = list_events(db_path, start=start, end=end)
    all_activities = _activities_between(start, end, db_path)
    active = _active_tasks(db_path)

    day_plans: list[DayPlan] = []
    day = start
    while day <= end:
        day_plans.append(
            DayPlan(
                date=day,
                events=_sort_events_by_start(
                    [e for e in all_events if e.start_time.date() == day]
                ),
                tasks=_sort_tasks_by_priority(
                    [t for t in active if t.due_date == day]
                ),
                activities=[a for a in all_activities if a.logged_at.date() == day],
            )
        )
        day += timedelta(days=1)

    return WeekAgenda(start_date=start, end_date=end, days=day_plans)


def get_week_agenda(
    start: date | None = None,
    days: int = 7,
    db_path: str | None = None,
) -> WeekAgenda:
    """Return a *days*-long plan starting at *start* (defaults to today)."""
    if days < 1:
        raise ValueError("days must be at least 1")

    start_date = start or date.today()
    return get_range_agenda(start_date, start_date + timedelta(days=days - 1), db_path)


def get_upcoming_deadlines(db_path: str | None = None) -> list[Task]:
    """Return pending tasks that have a due date, sorted by date then priority."""
    deadline_tasks = [t for t in _active_tasks(db_path) if t.due_date is not None]
    deadline_tasks.sort(key=lambda t: (t.due_date, _priority_rank(t.priority)))
    return deadline_tasks
