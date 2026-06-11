"""Read-only planner that combines tasks and events into agendas.

The planner never modifies the database. It loads tasks and events from the
repository layer and arranges them for display.
"""

from datetime import date, timedelta

from life_agent.db.repositories import list_events, list_tasks
from life_agent.models import CalendarEvent, Task
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


def get_today_agenda(
    today: date | None = None,
    db_path: str | None = None,
) -> TodayAgenda:
    """Return today's events, tasks due today, and undated pending tasks."""
    target = today or date.today()

    events = _sort_events_by_start(
        [e for e in list_events(db_path) if e.start_time.date() == target]
    )

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
    )


def get_week_agenda(
    start: date | None = None,
    days: int = 7,
    db_path: str | None = None,
) -> WeekAgenda:
    """Return a 7-day plan starting at *start* (defaults to today).

    Each day shows its events (sorted by start time) and pending tasks due
    on that day (sorted by priority).
    """
    if days < 1:
        raise ValueError("days must be at least 1")

    start_date = start or date.today()
    end_date = start_date + timedelta(days=days - 1)

    all_events = list_events(db_path)
    active = _active_tasks(db_path)

    day_plans: list[DayPlan] = []
    for offset in range(days):
        d = start_date + timedelta(days=offset)
        day_events = _sort_events_by_start(
            [e for e in all_events if e.start_time.date() == d]
        )
        day_tasks = _sort_tasks_by_priority(
            [t for t in active if t.due_date == d]
        )
        day_plans.append(DayPlan(date=d, events=day_events, tasks=day_tasks))

    return WeekAgenda(start_date=start_date, end_date=end_date, days=day_plans)


def get_upcoming_deadlines(db_path: str | None = None) -> list[Task]:
    """Return pending tasks that have a due date, sorted by date then priority."""
    deadline_tasks = [t for t in _active_tasks(db_path) if t.due_date is not None]
    deadline_tasks.sort(key=lambda t: (t.due_date, _priority_rank(t.priority)))
    return deadline_tasks
