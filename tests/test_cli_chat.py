"""CLI tests for the interactive chat command."""

import os

import pytest
from typer.testing import CliRunner

from life_agent.db.repositories import list_activities, list_reminders
from life_agent.main import app
from life_agent.models.common import ActivityStatus

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def _db_path() -> str:
    return os.environ["DB_PATH"]


def _chat(messages: str) -> str:
    """Run the chat command, feeding *messages* as stdin lines.

    We always append a /quit so the loop exits cleanly.
    """
    if not messages.endswith("\n"):
        messages += "\n"
    if "/quit" not in messages and "/exit" not in messages:
        messages += "/quit\n"
    result = runner.invoke(app, ["chat"], input=messages)
    assert result.exit_code == 0, result.stdout
    return result.stdout


# ---------------------------------------------------------------------------
# Greeting and basics
# ---------------------------------------------------------------------------


def test_chat_shows_greeting():
    output = _chat("/quit\n")
    assert "Hello" in output or "personal life agent" in output


def test_chat_help_shows_useful_info():
    output = _chat("/help\n")
    assert "/help" in output
    assert "/quit" in output
    assert "vad har jag idag" in output


def test_chat_quit_exits_cleanly():
    output = _chat("/quit\n")
    assert "Bye!" in output


def test_chat_exit_exits_cleanly():
    output = _chat("/exit\n")
    assert "Bye!" in output


# ---------------------------------------------------------------------------
# Read-only planner queries
# ---------------------------------------------------------------------------


def test_chat_today():
    output = _chat("vad har jag idag\n")
    assert "Today" in output


def test_chat_week():
    output = _chat("vad händer i veckan\n")
    assert "Week" in output


def test_chat_deadlines():
    output = _chat("visa deadlines\n")
    # Empty or "No upcoming deadlines" — both are valid.
    assert "deadline" in output.lower()


def test_chat_reminders():
    output = _chat("visa påminnelser\n")
    assert "reminder" in output.lower() or "påminnelse" in output.lower()


# ---------------------------------------------------------------------------
# Planning (add_items) with confirmation
# ---------------------------------------------------------------------------


PLAN_TEXT = (
    "jag ska träna rygg och biceps kl 12 imorgon, "
    "träningen ska vara 1h och påminn mig kl 09"
)


def test_chat_plan_shows_proposal():
    output = _chat(f"{PLAN_TEXT}\nn\n")
    assert "Proposed to save:" in output
    assert "Save this?" in output


def test_chat_plan_yes_saves():
    output = _chat(f"{PLAN_TEXT}\ny\n")
    assert "Saved" in output
    db = _db_path()
    assert len(list_activities(db_path=db)) == 1
    assert len(list_reminders(status=None, db_path=db)) == 1


def test_chat_plan_no_saves_nothing():
    output = _chat(f"{PLAN_TEXT}\nn\n")
    assert "Cancelled" in output
    db = _db_path()
    assert list_activities(db_path=db) == []
    assert list_reminders(status=None, db_path=db) == []


def test_chat_plan_enter_saves_nothing():
    output = _chat(f"{PLAN_TEXT}\n\n")
    assert "Cancelled" in output
    db = _db_path()
    assert list_activities(db_path=db) == []


# ---------------------------------------------------------------------------
# Completion with confirmation
# ---------------------------------------------------------------------------


def _seed_planned_today():
    runner.invoke(app, ["add", "--yes", "Jag ska träna gym kl 18 idag"])


def test_chat_complete_asks_before_updating():
    _seed_planned_today()
    output = _chat("jag har tränat klart\nn\n")
    assert "Matched planned activity" in output
    assert "Mark this activity as completed?" in output


def test_chat_complete_yes_marks_completed():
    _seed_planned_today()
    output = _chat("jag har tränat klart\ny\n")
    assert "Completed:" in output
    statuses = [a.status for a in list_activities(db_path=_db_path())]
    assert statuses == [ActivityStatus.COMPLETED]


def test_chat_complete_no_changes_nothing():
    _seed_planned_today()
    output = _chat("jag har tränat klart\nn\n")
    assert "Cancelled" in output
    statuses = [a.status for a in list_activities(db_path=_db_path())]
    assert statuses == [ActivityStatus.PLANNED]


def test_chat_complete_enter_changes_nothing():
    _seed_planned_today()
    output = _chat("jag har tränat klart\n\n")
    assert "Cancelled" in output
    statuses = [a.status for a in list_activities(db_path=_db_path())]
    assert statuses == [ActivityStatus.PLANNED]


def test_chat_complete_no_planned_activity():
    output = _chat("jag har tränat klart\n")
    assert "No planned activity found" in output


# ---------------------------------------------------------------------------
# Unknown input
# ---------------------------------------------------------------------------


def test_chat_unknown_shows_helpful_fallback():
    output = _chat("hej allihopa\n")
    assert "not sure" in output.lower()


# ---------------------------------------------------------------------------
# Existing commands still work
# ---------------------------------------------------------------------------


def test_existing_version_command_still_works():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0


def test_existing_add_command_still_requires_confirmation():
    result = runner.invoke(
        app, ["add", "Jag ska gymma idag kl 18"], input="n\n"
    )
    assert result.exit_code == 0
    assert "Save this?" in result.stdout
    assert list_activities(db_path=_db_path()) == []


def test_existing_extract_command_still_read_only():
    result = runner.invoke(app, ["extract", "Jag ska gymma idag kl 18"])
    assert result.exit_code == 0
    assert "Nothing was saved" in result.stdout
    assert list_activities(db_path=_db_path()) == []
