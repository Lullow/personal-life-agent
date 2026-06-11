"""CLI tests for the extract command."""

import pytest
from typer.testing import CliRunner

from life_agent.db.repositories import (
    list_activities,
    list_events,
    list_reminders,
    list_tasks,
)
from life_agent.main import app

runner = CliRunner()

TRAINING_TEXT = (
    "Jag ska träna rygg och biceps kl 12 imorgon, "
    "träningen ska vara 1h och påminn mig kl 09."
)


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    db = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db))
    runner.invoke(app, ["init"])
    # Make the db path available to tests that want to read the repos directly.
    return str(db)


def _db_path() -> str:
    import os
    return os.environ["DB_PATH"]


def test_extract_runs_and_shows_structured_output():
    result = runner.invoke(app, ["extract", TRAINING_TEXT])
    assert result.exit_code == 0, result.stdout
    assert "Extraction preview" in result.stdout
    assert "Activities:" in result.stdout
    assert "Reminders:" in result.stdout


def test_extract_output_says_nothing_was_saved():
    result = runner.invoke(app, ["extract", TRAINING_TEXT])
    assert result.exit_code == 0
    assert "Nothing was saved" in result.stdout


def test_extract_does_not_write_to_database():
    runner.invoke(app, ["extract", TRAINING_TEXT])

    db = _db_path()
    assert list_tasks(db) == []
    assert list_events(db) == []
    assert list_activities(db) == []
    assert list_reminders(status=None, db_path=db) == []


def test_extract_preserves_existing_database_state():
    # Seed a single task, then run extract — it must not be affected.
    runner.invoke(app, ["add-task", "Pre-existing task"])
    before = list_tasks(_db_path())
    assert len(before) == 1

    runner.invoke(app, ["extract", TRAINING_TEXT])

    after = list_tasks(_db_path())
    assert len(after) == 1
    assert after[0].title == "Pre-existing task"


def test_extract_handles_empty_input():
    result = runner.invoke(app, ["extract", ""])
    assert result.exit_code == 1
    assert "No text provided" in result.stdout


def test_extract_output_contains_confidence():
    result = runner.invoke(app, ["extract", TRAINING_TEXT])
    assert result.exit_code == 0
    assert "Confidence:" in result.stdout


def test_extract_unrecognised_input_shows_no_items_message():
    result = runner.invoke(app, ["extract", "Some random text with nothing structured"])
    assert result.exit_code == 0
    assert "no structured items extracted" in result.stdout
    assert "Nothing was saved" in result.stdout
