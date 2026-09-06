"""CLI tests for the natural-language `complete` command."""

import os
from datetime import datetime

import pytest
from typer.testing import CliRunner

from life_agent.db.repositories import create_activity, list_activities
from life_agent.main import app
from life_agent.models import ActivityLog
from life_agent.models.common import ActivityStatus, ActivityType

runner = CliRunner()

COMPLETE_TEXT = "Jag har tränat klart"


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def _db_path() -> str:
    return os.environ["DB_PATH"]


def _seed_planned_today():
    """A planned gym session at 18:00 today, the shape `complete` looks for."""
    create_activity(
        ActivityLog(
            title="Träna gym",
            activity_type=ActivityType.GYM,
            status=ActivityStatus.PLANNED,
            logged_at=datetime.now().replace(hour=18, minute=0, second=0, microsecond=0),
        ),
        _db_path(),
    )


def _statuses() -> list[ActivityStatus]:
    return [a.status for a in list_activities(db_path=_db_path())]


# ---------------------------------------------------------------------------
# Planned vs completed status
# ---------------------------------------------------------------------------

def test_manual_activity_log_defaults_to_completed():
    result = runner.invoke(app, ["activity", "Gym 50 min", "--type", "gym", "--minutes", "50"])
    assert result.exit_code == 0
    assert _statuses() == [ActivityStatus.COMPLETED]


def test_activities_listing_shows_status():
    _seed_planned_today()
    result = runner.invoke(app, ["activities"])
    assert result.exit_code == 0
    assert "planned" in result.stdout


# ---------------------------------------------------------------------------
# complete command
# ---------------------------------------------------------------------------

def test_complete_shows_matched_activity():
    _seed_planned_today()
    result = runner.invoke(app, ["complete", COMPLETE_TEXT], input="n\n")
    assert result.exit_code == 0
    assert "Matched planned activity" in result.stdout
    assert "Mark this activity as completed?" in result.stdout


def test_complete_yes_marks_completed():
    _seed_planned_today()
    result = runner.invoke(app, ["complete", COMPLETE_TEXT], input="yes\n")
    assert result.exit_code == 0
    assert "Completed:" in result.stdout
    assert _statuses() == [ActivityStatus.COMPLETED]


def test_complete_y_marks_completed():
    _seed_planned_today()
    result = runner.invoke(app, ["complete", COMPLETE_TEXT], input="y\n")
    assert result.exit_code == 0
    assert _statuses() == [ActivityStatus.COMPLETED]


def test_complete_no_changes_nothing():
    _seed_planned_today()
    result = runner.invoke(app, ["complete", COMPLETE_TEXT], input="no\n")
    assert result.exit_code == 0
    assert "Cancelled" in result.stdout
    assert _statuses() == [ActivityStatus.PLANNED]


def test_complete_enter_changes_nothing():
    _seed_planned_today()
    result = runner.invoke(app, ["complete", COMPLETE_TEXT], input="\n")
    assert result.exit_code == 0
    assert "Cancelled" in result.stdout
    assert _statuses() == [ActivityStatus.PLANNED]


def test_complete_yes_flag_skips_prompt():
    _seed_planned_today()
    result = runner.invoke(app, ["complete", "--yes", COMPLETE_TEXT])
    assert result.exit_code == 0
    assert _statuses() == [ActivityStatus.COMPLETED]


def test_complete_no_planned_activity_shows_message():
    result = runner.invoke(app, ["complete", COMPLETE_TEXT])
    assert result.exit_code == 0
    assert "No planned activity found" in result.stdout


def test_complete_non_completion_phrase_is_ignored():
    _seed_planned_today()
    result = runner.invoke(app, ["complete", "Möte på Odenplan kl 14"])
    assert result.exit_code == 0
    assert "doesn't look like a completion phrase" in result.stdout
    assert _statuses() == [ActivityStatus.PLANNED]


def test_complete_empty_text_exits_cleanly():
    result = runner.invoke(app, ["complete", ""])
    assert result.exit_code == 1
    assert "No text provided" in result.stdout


