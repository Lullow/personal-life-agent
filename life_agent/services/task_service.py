"""Task service — thin layer between CLI and repository."""

from datetime import date

from life_agent.db.repositories import (
    create_task,
    list_tasks,
    update_task_status,
)
from life_agent.models import Task
from life_agent.models.common import Priority, TaskCategory, TaskStatus


def add_task(
    title: str,
    due_date: date | None = None,
    priority: Priority = Priority.MEDIUM,
    category: TaskCategory = TaskCategory.OTHER,
    estimated_minutes: int | None = None,
    db_path: str | None = None,
) -> Task:
    task = Task(
        title=title,
        due_date=due_date,
        priority=priority,
        category=category,
        estimated_minutes=estimated_minutes,
    )
    return create_task(task, db_path)


def get_all_tasks(db_path: str | None = None) -> list[Task]:
    return list_tasks(db_path)


def mark_task_done(index: int, db_path: str | None = None) -> Task | None:
    """Mark the task at the given 1-based display index as done."""
    tasks = list_tasks(db_path)
    if index < 1 or index > len(tasks):
        return None
    task = tasks[index - 1]
    return update_task_status(task.id, TaskStatus.DONE, db_path)
