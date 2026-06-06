"""Tests for the Task model."""

from datetime import date

import pytest
from pydantic import ValidationError

from life_agent.models import Priority, Task, TaskCategory, TaskStatus


def test_valid_task_creation():
    task = Task(title="Review notes", estimated_minutes=30, due_date=date(2026, 6, 10))
    assert task.title == "Review notes"
    assert task.priority == Priority.MEDIUM
    assert task.status == TaskStatus.PENDING
    assert task.category == TaskCategory.OTHER
    assert task.estimated_minutes == 30
    assert task.due_date == date(2026, 6, 10)
    assert task.created_at is not None


def test_task_requires_non_empty_title():
    with pytest.raises(ValidationError):
        Task(title="")

    with pytest.raises(ValidationError):
        Task(title="   ")


def test_task_rejects_negative_estimated_minutes():
    with pytest.raises(ValidationError):
        Task(title="Walk the dog", estimated_minutes=-5)
