"""Local SQLite database layer for personal-life-agent."""

from life_agent.db.database import get_connection
from life_agent.db.repositories import (
    create_activity,
    create_event,
    create_task,
    get_activity,
    get_task,
    list_activities,
    list_events,
    list_planned_activities,
    list_tasks,
    update_activity_status,
    update_task_status,
)
from life_agent.db.schema import init_db

__all__ = [
    "create_activity",
    "create_event",
    "create_task",
    "get_activity",
    "get_connection",
    "get_task",
    "init_db",
    "list_activities",
    "list_events",
    "list_planned_activities",
    "list_tasks",
    "update_activity_status",
    "update_task_status",
]
