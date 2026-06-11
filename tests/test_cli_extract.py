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
    assert list_activities(db_path=db) == []
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


def test_extract_event_phrase_shows_event():
    result = runner.invoke(app, ["extract", "Jag har möte på Odenplan kl 14 imorgon"])
    assert result.exit_code == 0, result.stdout
    assert "Events:" in result.stdout
    assert "Odenplan" in result.stdout
    assert "Nothing was saved" in result.stdout


def test_extract_task_phrase_shows_task():
    result = runner.invoke(
        app, ["extract", "Jag behöver plugga machine learning på fredag"]
    )
    assert result.exit_code == 0, result.stdout
    assert "Tasks:" in result.stdout
    assert "Nothing was saved" in result.stdout


def test_extract_reminder_phrase_shows_reminder():
    result = runner.invoke(
        app, ["extract", "Påminn mig att handla mat imorgon kl 10"]
    )
    assert result.exit_code == 0, result.stdout
    assert "Reminders:" in result.stdout
    assert "Nothing was saved" in result.stdout


def test_extract_gym_phrase_shows_planned_activity():
    result = runner.invoke(
        app, ["extract", "Jag ska gymma bröst och triceps idag kl 18 i 45 minuter"]
    )
    assert result.exit_code == 0, result.stdout
    assert "Activities:" in result.stdout
    assert "gym" in result.stdout.lower()
    assert "Nothing was saved" in result.stdout


def test_extract_event_phrase_writes_nothing():
    runner.invoke(app, ["extract", "Jag har möte på Odenplan kl 14 imorgon"])
    db = _db_path()
    assert list_tasks(db) == []
    assert list_events(db) == []
    assert list_activities(db_path=db) == []
    assert list_reminders(status=None, db_path=db) == []


def test_extract_llm_mode_without_key_falls_back_gracefully(monkeypatch):
    # Enable LLM mode but provide no provider config: must not crash, must
    # fall back to deterministic extraction and stay read-only.
    for var in (
        "LIFE_AGENT_LLM_API_KEY",
        "LIFE_AGENT_LLM_BASE_URL",
        "LIFE_AGENT_LLM_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LIFE_AGENT_EXTRACTION_MODE", "llm")

    result = runner.invoke(app, ["extract", "Jag ska gymma idag kl 18"])
    assert result.exit_code == 0, result.stdout
    assert "Extraction preview" in result.stdout
    assert "Activities:" in result.stdout
    assert "Nothing was saved" in result.stdout

    db = _db_path()
    assert list_activities(db_path=db) == []
