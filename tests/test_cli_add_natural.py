"""CLI tests for the natural-language `add` command (confirmation flow)."""

import os

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
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def _db_path() -> str:
    return os.environ["DB_PATH"]


def _is_empty_db() -> bool:
    db = _db_path()
    return (
        list_tasks(db) == []
        and list_events(db) == []
        and list_activities(db_path=db) == []
        and list_reminders(status=None, db_path=db) == []
    )


def test_add_shows_proposal_and_prompt():
    result = runner.invoke(app, ["add", TRAINING_TEXT], input="n\n")
    assert result.exit_code == 0
    assert "Proposed to save:" in result.stdout
    assert "Save this?" in result.stdout


def test_add_yes_saves_items():
    result = runner.invoke(app, ["add", TRAINING_TEXT], input="yes\n")
    assert result.exit_code == 0
    assert "Saved" in result.stdout
    assert not _is_empty_db()


def test_add_y_saves_items():
    result = runner.invoke(app, ["add", TRAINING_TEXT], input="y\n")
    assert result.exit_code == 0
    db = _db_path()
    assert len(list_activities(db_path=db)) == 1
    assert len(list_reminders(status=None, db_path=db)) == 1


def test_add_no_saves_nothing():
    result = runner.invoke(app, ["add", TRAINING_TEXT], input="no\n")
    assert result.exit_code == 0
    assert "Cancelled" in result.stdout
    assert _is_empty_db()


def test_add_enter_saves_nothing():
    result = runner.invoke(app, ["add", TRAINING_TEXT], input="\n")
    assert result.exit_code == 0
    assert "Cancelled" in result.stdout
    assert _is_empty_db()


def test_add_yes_flag_skips_prompt_and_saves():
    result = runner.invoke(app, ["add", "--yes", TRAINING_TEXT])
    assert result.exit_code == 0
    assert "Saved" in result.stdout
    assert not _is_empty_db()


def test_add_saved_activity_appears_in_activities():
    runner.invoke(app, ["add", TRAINING_TEXT], input="y\n")
    listing = runner.invoke(app, ["activities"])
    assert listing.exit_code == 0
    assert "rygg" in listing.stdout.lower() or "biceps" in listing.stdout.lower()


def test_add_saved_reminder_appears_in_reminders():
    runner.invoke(app, ["add", TRAINING_TEXT], input="y\n")
    listing = runner.invoke(app, ["reminders"])
    assert listing.exit_code == 0
    assert "2026-06-12 09:00" in listing.stdout


def test_add_empty_text_exits_cleanly():
    result = runner.invoke(app, ["add", ""])
    assert result.exit_code == 1
    assert "No text provided" in result.stdout


def test_add_unrecognised_text_saves_nothing():
    result = runner.invoke(app, ["add", "Some random text with nothing structured"])
    assert result.exit_code == 0
    assert "Nothing to save" in result.stdout
    assert _is_empty_db()


def test_extract_still_saves_nothing():
    result = runner.invoke(app, ["extract", TRAINING_TEXT])
    assert result.exit_code == 0
    assert "Nothing was saved" in result.stdout
    assert _is_empty_db()


EVENT_TEXT = "Jag har möte på Odenplan kl 14 imorgon"


def test_add_event_phrase_asks_before_saving():
    result = runner.invoke(app, ["add", EVENT_TEXT], input="n\n")
    assert result.exit_code == 0
    assert "Proposed to save:" in result.stdout
    assert "Save this?" in result.stdout
    assert _is_empty_db()


def test_add_event_phrase_saves_event_on_yes():
    result = runner.invoke(app, ["add", EVENT_TEXT], input="y\n")
    assert result.exit_code == 0
    db = _db_path()
    events = list_events(db)
    assert len(events) == 1
    assert events[0].location == "Odenplan"


def test_add_event_phrase_enter_saves_nothing():
    result = runner.invoke(app, ["add", EVENT_TEXT], input="\n")
    assert result.exit_code == 0
    assert "Cancelled" in result.stdout
    assert _is_empty_db()


TASK_TEXT = "Jag behöver plugga machine learning på fredag"


def test_add_task_phrase_saves_task_on_yes():
    result = runner.invoke(app, ["add", TASK_TEXT], input="y\n")
    assert result.exit_code == 0
    db = _db_path()
    tasks = list_tasks(db)
    assert len(tasks) == 1
    assert str(tasks[0].category) == "study"
    assert tasks[0].due_date is not None


def test_add_still_requires_confirmation_in_llm_mode(monkeypatch):
    # Even with LLM mode enabled (and no key -> deterministic fallback), the
    # add command must still ask before writing anything.
    for var in (
        "LIFE_AGENT_LLM_API_KEY",
        "LIFE_AGENT_LLM_BASE_URL",
        "LIFE_AGENT_LLM_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LIFE_AGENT_EXTRACTION_MODE", "llm")

    result = runner.invoke(app, ["add", TRAINING_TEXT], input="n\n")
    assert result.exit_code == 0
    assert "Save this?" in result.stdout
    assert _is_empty_db()
