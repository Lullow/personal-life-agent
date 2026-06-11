"""CLI tests for task commands."""

import pytest
from typer.testing import CliRunner

from life_agent.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def test_init_command():
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Database initialised" in result.stdout


def test_add_task():
    result = runner.invoke(app, ["add-task", "Buy groceries"])
    assert result.exit_code == 0
    assert "Buy groceries" in result.stdout


def test_add_task_with_options():
    result = runner.invoke(app, [
        "add-task", "Plugga machine learning",
        "--due", "2026-06-15",
        "--priority", "high",
        "--category", "study",
    ])
    assert result.exit_code == 0
    assert "Plugga machine learning" in result.stdout


def test_list_tasks_empty():
    result = runner.invoke(app, ["tasks"])
    assert result.exit_code == 0
    assert "No tasks found" in result.stdout


def test_list_tasks_after_add():
    runner.invoke(app, ["add-task", "Task A"])
    runner.invoke(app, ["add-task", "Task B"])
    result = runner.invoke(app, ["tasks"])
    assert result.exit_code == 0
    assert "Task A" in result.stdout
    assert "Task B" in result.stdout
    assert "[1]" in result.stdout
    assert "[2]" in result.stdout


def test_tasks_show_priority_and_category():
    runner.invoke(app, [
        "add-task", "Study linear algebra",
        "--priority", "high",
        "--category", "study",
        "--due", "2026-06-15",
    ])
    result = runner.invoke(app, ["tasks"])
    assert "high" in result.stdout
    assert "study" in result.stdout
    assert "2026-06-15" in result.stdout


def test_done_marks_task():
    runner.invoke(app, ["add-task", "Finish report"])
    result = runner.invoke(app, ["done", "1"])
    assert result.exit_code == 0
    assert "Done:" in result.stdout
    assert "Finish report" in result.stdout

    listing = runner.invoke(app, ["tasks"])
    assert "done" in listing.stdout


def test_done_invalid_index():
    result = runner.invoke(app, ["done", "99"])
    assert result.exit_code == 1
    assert "No task found" in result.stdout


def test_add_task_invalid_date():
    result = runner.invoke(app, ["add-task", "Bad date", "--due", "not-a-date"])
    assert result.exit_code == 1
    assert "Invalid date format" in result.stdout
