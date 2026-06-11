"""CLI tests for event commands."""

import pytest
from typer.testing import CliRunner

from life_agent.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def test_add_event():
    result = runner.invoke(app, [
        "add-event", "Möte på Odenplan",
        "--start", "2026-06-15 12:00",
        "--location", "Odenplan",
    ])
    assert result.exit_code == 0
    assert "Möte på Odenplan" in result.stdout


def test_add_event_without_location():
    result = runner.invoke(app, [
        "add-event", "Standup",
        "--start", "2026-06-16 09:00",
    ])
    assert result.exit_code == 0
    assert "Standup" in result.stdout


def test_list_events_empty():
    result = runner.invoke(app, ["events"])
    assert result.exit_code == 0
    assert "No events found" in result.stdout


def test_list_events_after_add():
    runner.invoke(app, [
        "add-event", "Morning standup",
        "--start", "2026-06-16 09:00",
    ])
    runner.invoke(app, [
        "add-event", "Lunch meeting",
        "--start", "2026-06-16 12:00",
        "--location", "Café",
    ])
    result = runner.invoke(app, ["events"])
    assert result.exit_code == 0
    assert "Morning standup" in result.stdout
    assert "Lunch meeting" in result.stdout
    assert "[1]" in result.stdout
    assert "[2]" in result.stdout


def test_events_show_location():
    runner.invoke(app, [
        "add-event", "Möte",
        "--start", "2026-06-15 14:00",
        "--location", "Odenplan",
    ])
    result = runner.invoke(app, ["events"])
    assert "Odenplan" in result.stdout


def test_add_event_invalid_start():
    result = runner.invoke(app, [
        "add-event", "Bad time",
        "--start", "not-a-datetime",
    ])
    assert result.exit_code == 1
    assert "Invalid datetime format" in result.stdout
