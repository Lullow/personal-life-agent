"""Readable terminal output formatting for domain models and agendas."""

from life_agent.models import ActivityLog, CalendarEvent, Task
from life_agent.schemas.planner import TodayAgenda, WeekAgenda


def format_task_line(index: int, task: Task) -> str:
    due = str(task.due_date) if task.due_date else "-"
    return f"[{index}] {task.status} {task.priority} {task.category} {due} - {task.title}"


def format_event_line(index: int, event: CalendarEvent) -> str:
    start = event.start_time.strftime("%Y-%m-%d %H:%M")
    loc = f" ({event.location})" if event.location else ""
    return f"[{index}] {start} {event.category} - {event.title}{loc}"


def format_activity_line(index: int, activity: ActivityLog) -> str:
    mins = f"{activity.duration_minutes}min" if activity.duration_minutes else "-"
    return f"[{index}] {activity.activity_type} {mins} - {activity.title}"


def format_today_agenda(agenda: TodayAgenda) -> str:
    """Render today's events, tasks due today, and undated pending tasks."""
    lines: list[str] = [f"Today ({agenda.date.isoformat()}):"]

    if agenda.events:
        lines.append("")
        lines.append("Events:")
        for i, event in enumerate(agenda.events, start=1):
            lines.append("  " + format_event_line(i, event))

    if agenda.tasks_due_today:
        lines.append("")
        lines.append("Tasks due today:")
        for i, task in enumerate(agenda.tasks_due_today, start=1):
            lines.append("  " + format_task_line(i, task))

    if agenda.undated_tasks:
        lines.append("")
        lines.append("Other pending tasks:")
        for i, task in enumerate(agenda.undated_tasks, start=1):
            lines.append("  " + format_task_line(i, task))

    if not (agenda.events or agenda.tasks_due_today or agenda.undated_tasks):
        lines.append("")
        lines.append("Nothing on the agenda.")

    return "\n".join(lines)


def format_week_agenda(agenda: WeekAgenda) -> str:
    """Render a 7-day plan grouped by date.  Empty days are skipped."""
    lines: list[str] = [
        f"Week {agenda.start_date.isoformat()} -> {agenda.end_date.isoformat()}:"
    ]

    has_content = False
    for day in agenda.days:
        if not day.events and not day.tasks:
            continue
        has_content = True
        lines.append("")
        lines.append(f"{day.date.isoformat()}:")
        for i, event in enumerate(day.events, start=1):
            lines.append("  " + format_event_line(i, event))
        for i, task in enumerate(day.tasks, start=1):
            lines.append("  " + format_task_line(i, task))

    if not has_content:
        lines.append("")
        lines.append("Nothing scheduled.")

    return "\n".join(lines)


def format_deadlines(tasks: list[Task]) -> str:
    """Render pending tasks with due dates."""
    if not tasks:
        return "No upcoming deadlines."

    lines = ["Upcoming deadlines:"]
    for i, task in enumerate(tasks, start=1):
        lines.append(format_task_line(i, task))
    return "\n".join(lines)
