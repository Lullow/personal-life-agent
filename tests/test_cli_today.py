"""CLI tests for today / week / deadlines commands."""

from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from life_agent.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def _add_task(title, due=None, priority="medium", category="other"):
    args = ["add-task", title, "--priority", priority, "--category", category]
    if due is not None:
        args.extend(["--due", due])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout


def _add_event(title, start, location=None):
    args = ["add-event", title, "--start", start]
    if location is not None:
        args.extend(["--location", location])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout


# ---------------------------------------------------------------------------
# today
# ---------------------------------------------------------------------------

def test_today_empty():
    result = runner.invoke(app, ["today"])
    assert result.exit_code == 0
    assert "Today" in result.stdout
    assert "Nothing on the agenda" in result.stdout


def test_today_shows_events_tasks_and_undated():
    today_iso = date.today().isoformat()
    _add_event("Standup", f"{today_iso} 09:00")
    _add_event("Lunch meeting", f"{today_iso} 12:00", location="Café")
    _add_task("Pay invoice", due=today_iso, priority="high")
    _add_task("Random idea")

    result = runner.invoke(app, ["today"])
    assert result.exit_code == 0
    assert "Standup" in result.stdout
    assert "Lunch meeting" in result.stdout
    assert "Pay invoice" in result.stdout
    assert "Random idea" in result.stdout
    assert "Events:" in result.stdout
    assert "Tasks due today:" in result.stdout
    assert "Other pending tasks:" in result.stdout


def test_today_hides_done_tasks():
    today_iso = date.today().isoformat()
    _add_task("Finish slides", due=today_iso)
    runner.invoke(app, ["done", "1"])

    result = runner.invoke(app, ["today"])
    assert result.exit_code == 0
    assert "Tasks due today:" not in result.stdout


# ---------------------------------------------------------------------------
# week
# ---------------------------------------------------------------------------

def test_week_empty():
    result = runner.invoke(app, ["week"])
    assert result.exit_code == 0
    assert "Week" in result.stdout
    assert "Nothing scheduled" in result.stdout


def test_week_shows_items_within_range_and_excludes_outside():
    in_range = (date.today() + timedelta(days=2)).isoformat()
    out_of_range = (date.today() + timedelta(days=20)).isoformat()

    _add_event("In-range meeting", f"{in_range} 10:00")
    _add_event("Faraway meeting", f"{out_of_range} 10:00")
    _add_task("In-range task", due=in_range, priority="high")
    _add_task("Faraway task", due=out_of_range)

    result = runner.invoke(app, ["week"])
    assert result.exit_code == 0
    assert "In-range meeting" in result.stdout
    assert "In-range task" in result.stdout
    assert "Faraway meeting" not in result.stdout
    assert "Faraway task" not in result.stdout


# ---------------------------------------------------------------------------
# deadlines
# ---------------------------------------------------------------------------

def test_deadlines_empty():
    result = runner.invoke(app, ["deadlines"])
    assert result.exit_code == 0
    assert "No upcoming deadlines" in result.stdout


def test_deadlines_sorted_output():
    soon = (date.today() + timedelta(days=1)).isoformat()
    later = (date.today() + timedelta(days=10)).isoformat()

    _add_task("Far high", due=later, priority="high")
    _add_task("Soon low", due=soon, priority="low")

    result = runner.invoke(app, ["deadlines"])
    assert result.exit_code == 0
    assert "Soon low" in result.stdout
    assert "Far high" in result.stdout
    soon_idx = result.stdout.index("Soon low")
    far_idx = result.stdout.index("Far high")
    assert soon_idx < far_idx


def test_deadlines_ignores_undated_and_done():
    soon = (date.today() + timedelta(days=2)).isoformat()
    _add_task("Has deadline", due=soon)
    _add_task("Undated")
    _add_task("Will be done", due=soon)
    # Mark the "Will be done" task (it's the most recently created, so it's [1])
    runner.invoke(app, ["done", "1"])

    result = runner.invoke(app, ["deadlines"])
    assert result.exit_code == 0
    assert "Has deadline" in result.stdout
    assert "Undated" not in result.stdout
    assert "Will be done" not in result.stdout
