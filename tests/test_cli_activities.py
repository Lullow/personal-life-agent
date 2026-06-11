"""CLI tests for activity commands."""

import pytest
from typer.testing import CliRunner

from life_agent.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def test_log_activity():
    result = runner.invoke(app, [
        "activity", "Gym rygg och biceps",
        "--type", "gym",
        "--minutes", "50",
    ])
    assert result.exit_code == 0
    assert "Gym rygg och biceps" in result.stdout


def test_log_activity_defaults():
    result = runner.invoke(app, ["activity", "Quick stretch"])
    assert result.exit_code == 0
    assert "Quick stretch" in result.stdout


def test_list_activities_empty():
    result = runner.invoke(app, ["activities"])
    assert result.exit_code == 0
    assert "No activities found" in result.stdout


def test_list_activities_after_log():
    runner.invoke(app, ["activity", "Morning run", "--type", "run", "--minutes", "30"])
    runner.invoke(app, ["activity", "Evening walk", "--type", "walk"])
    result = runner.invoke(app, ["activities"])
    assert result.exit_code == 0
    assert "Morning run" in result.stdout
    assert "Evening walk" in result.stdout
    assert "[1]" in result.stdout
    assert "[2]" in result.stdout


def test_activities_show_type_and_minutes():
    runner.invoke(app, ["activity", "Gym session", "--type", "gym", "--minutes", "60"])
    result = runner.invoke(app, ["activities"])
    assert "gym" in result.stdout
    assert "60min" in result.stdout
