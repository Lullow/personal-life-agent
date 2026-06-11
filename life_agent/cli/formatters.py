"""Readable terminal output formatting for domain models and agendas."""

from life_agent.models import ActivityLog, CalendarEvent, Reminder, Task
from life_agent.models.common import ActivityStatus
from life_agent.schemas.confirmation import (
    ConfirmationProposal,
    ConfirmationSaveResult,
)
from life_agent.schemas.extraction import ExtractionResult
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
    parts = [
        f"[{index}]",
        str(activity.status),
        str(activity.activity_type),
        mins,
    ]
    # Planned activities carry a meaningful scheduled time; show it.
    if activity.status == ActivityStatus.PLANNED:
        parts.append(activity.logged_at.strftime("%Y-%m-%d %H:%M"))
    parts.append(f"- {activity.title}")
    return " ".join(parts)


def format_completion_candidate(activity: ActivityLog) -> str:
    """Render the planned activity matched for completion."""
    when = activity.logged_at.strftime("%Y-%m-%d %H:%M")
    mins = f"{activity.duration_minutes}min" if activity.duration_minutes else "-"
    return (
        f"Matched planned activity:\n"
        f"  {activity.status} {activity.activity_type} {mins} {when} - {activity.title}"
    )


def format_reminder_line(reminder: Reminder) -> str:
    """Render a reminder, leading with its database id so it is easy to dismiss."""
    when = reminder.remind_at.strftime("%Y-%m-%d %H:%M")
    return f"#{reminder.id} {when} {reminder.status} {reminder.target_type} - {reminder.title}"


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


def format_extraction_result(result: ExtractionResult) -> str:
    """Render an extraction preview.  Caller appends the 'nothing saved' note."""
    lines: list[str] = ["Extraction preview:"]

    if result.activities:
        lines.append("")
        lines.append("Activities:")
        for i, activity in enumerate(result.activities, start=1):
            when = (
                activity.logged_at.strftime("%Y-%m-%d %H:%M")
                if activity.logged_at
                else "-"
            )
            dur = (
                f"{activity.duration_minutes}min"
                if activity.duration_minutes is not None
                else "-"
            )
            atype = activity.activity_type if activity.activity_type else "-"
            lines.append(f"  [{i}] {when} {atype} {dur} - {activity.title or '-'}")

    if result.events:
        lines.append("")
        lines.append("Events:")
        for i, event in enumerate(result.events, start=1):
            start = (
                event.start_time.strftime("%Y-%m-%d %H:%M")
                if event.start_time
                else "-"
            )
            loc = f" ({event.location})" if event.location else ""
            cat = f" {event.category}" if event.category else ""
            lines.append(f"  [{i}] {start}{cat} - {event.title or '-'}{loc}")

    if result.tasks:
        lines.append("")
        lines.append("Tasks:")
        for i, task in enumerate(result.tasks, start=1):
            due = task.due_date.isoformat() if task.due_date else "-"
            pri = task.priority if task.priority else "-"
            cat = task.category if task.category else "-"
            lines.append(f"  [{i}] {due} {pri} {cat} - {task.title or '-'}")

    if result.reminders:
        lines.append("")
        lines.append("Reminders:")
        for i, reminder in enumerate(result.reminders, start=1):
            when = (
                reminder.remind_at.strftime("%Y-%m-%d %H:%M")
                if reminder.remind_at
                else "-"
            )
            lines.append(f"  [{i}] {when} - {reminder.title or '-'}")

    if result.questions:
        lines.append("")
        lines.append("Questions:")
        for question in result.questions:
            lines.append(f"  - {question}")

    if result.confidence is not None:
        lines.append("")
        lines.append(f"Confidence: {result.confidence:.2f}")

    if not (
        result.tasks or result.events or result.activities or result.reminders
    ):
        lines.append("")
        lines.append("(no structured items extracted)")

    return "\n".join(lines)


def format_confirmation_proposal(proposal: ConfirmationProposal) -> str:
    """Render the proposal shown before asking the user to confirm."""
    lines = ["Proposed to save:"]
    body = format_extraction_result(proposal.extraction)
    # Reuse the extraction preview body, minus its own heading line.
    body_lines = body.split("\n")[1:]
    lines.extend(body_lines)
    lines.append("")
    lines.append(
        f"Will save {proposal.saveable_count} item(s); "
        f"skipping {proposal.skipped_count} incomplete item(s)."
    )
    return "\n".join(lines)


def format_save_result(result: ConfirmationSaveResult) -> str:
    """Render the outcome after a confirmed save."""
    lines: list[str] = []
    if result.saved:
        lines.append(f"Saved {result.saved_count} item(s):")
        for item in result.saved:
            lines.append(f"  + {item.item_type}: {item.title}")
    else:
        lines.append("Saved 0 items.")

    if result.skipped:
        lines.append("")
        lines.append(f"Skipped {result.skipped_count} item(s):")
        for item in result.skipped:
            reason = f" ({item.reason})" if item.reason else ""
            lines.append(f"  - {item.item_type}: {item.title}{reason}")

    return "\n".join(lines)
