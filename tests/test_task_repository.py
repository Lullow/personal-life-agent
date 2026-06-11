"""Tests for task repository functions."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from life_agent.db.repositories import (
    create_task,
    get_task,
    list_tasks,
    update_task_status,
)
from life_agent.db.schema import init_db
from life_agent.models import Task, TaskStatus
from life_agent.models.common import Priority, TaskCategory


@pytest.fixture()
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "test.db")
        init_db(path)
        yield path


def test_create_task(db_path):
    task = Task(title="Buy groceries", category=TaskCategory.ERRAND)
    saved = create_task(task, db_path)
    assert saved.id is not None
    assert saved.title == "Buy groceries"
    assert saved.category == TaskCategory.ERRAND
    assert saved.priority == Priority.MEDIUM
    assert saved.status == TaskStatus.PENDING


def test_get_task(db_path):
    task = Task(title="Read chapter 5", estimated_minutes=60)
    saved = create_task(task, db_path)
    fetched = get_task(saved.id, db_path)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.title == "Read chapter 5"
    assert fetched.estimated_minutes == 60


def test_get_task_returns_none_for_missing_id(db_path):
    assert get_task("nonexistent-id", db_path) is None


def test_list_tasks(db_path):
    create_task(Task(title="Task A"), db_path)
    create_task(Task(title="Task B"), db_path)
    tasks = list_tasks(db_path)
    assert len(tasks) == 2
    titles = {t.title for t in tasks}
    assert titles == {"Task A", "Task B"}


def test_update_task_status(db_path):
    task = Task(title="Finish report")
    saved = create_task(task, db_path)
    updated = update_task_status(saved.id, TaskStatus.DONE, db_path)
    assert updated is not None
    assert updated.status == TaskStatus.DONE
    assert updated.updated_at is not None


def test_task_roundtrip_preserves_fields(db_path):
    task = Task(
        title="Dentist appointment",
        description="Annual checkup",
        priority=Priority.HIGH,
        category=TaskCategory.HEALTH,
        estimated_minutes=30,
        due_date=date(2026, 7, 1),
    )
    saved = create_task(task, db_path)
    fetched = get_task(saved.id, db_path)
    assert fetched is not None
    assert fetched.description == "Annual checkup"
    assert fetched.priority == Priority.HIGH
    assert fetched.category == TaskCategory.HEALTH
    assert fetched.estimated_minutes == 30
    assert fetched.due_date == date(2026, 7, 1)
    assert fetched.created_at is not None
