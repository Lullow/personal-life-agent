"""Readable terminal output formatting for domain models."""

from life_agent.models import ActivityLog, CalendarEvent, Task


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
