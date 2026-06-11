"""CLI tests for reminder commands."""

import re

import pytest
from typer.testing import CliRunner

from life_agent.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def _added_reminder_id(stdout: str) -> int:
    match = re.search(r"Added reminder #(\d+)", stdout)
    assert match is not None, f"could not find reminder id in: {stdout!r}"
    return int(match.group(1))


def test_add_reminder():
    result = runner.invoke(app, [
        "add-reminder", "Träning rygg och biceps",
        "--at", "2026-06-15 09:00",
    ])
    assert result.exit_code == 0
    assert "Träning rygg och biceps" in result.stdout
    assert "#" in result.stdout


def test_add_reminder_invalid_datetime():
    result = runner.invoke(app, [
        "add-reminder", "Bad reminder",
        "--at", "not-a-datetime",
    ])
    assert result.exit_code == 1
    assert "Invalid datetime format" in result.stdout


def test_reminders_empty():
    result = runner.invoke(app, ["reminders"])
    assert result.exit_code == 0
    assert "No pending reminders" in result.stdout


def test_reminders_sorted_by_remind_at():
    runner.invoke(app, ["add-reminder", "Late one", "--at", "2026-06-20 12:00"])
    runner.invoke(app, ["add-reminder", "Early one", "--at", "2026-06-15 08:00"])
    runner.invoke(app, ["add-reminder", "Middle one", "--at", "2026-06-17 18:00"])

    result = runner.invoke(app, ["reminders"])
    assert result.exit_code == 0

    early_idx = result.stdout.index("Early one")
    middle_idx = result.stdout.index("Middle one")
    late_idx = result.stdout.index("Late one")
    assert early_idx < middle_idx < late_idx


def test_dismiss_reminder_changes_status():
    add = runner.invoke(app, ["add-reminder", "Stretch", "--at", "2026-06-15 09:00"])
    reminder_id = _added_reminder_id(add.stdout)

    result = runner.invoke(app, ["dismiss-reminder", str(reminder_id)])
    assert result.exit_code == 0
    assert f"#{reminder_id}" in result.stdout
    assert "Dismissed" in result.stdout

    listing = runner.invoke(app, ["reminders"])
    assert "Stretch" not in listing.stdout
    assert "No pending reminders" in listing.stdout


def test_dismiss_reminder_missing_id():
    result = runner.invoke(app, ["dismiss-reminder", "9999"])
    assert result.exit_code == 1
    assert "No reminder found" in result.stdout


def test_reminders_show_id_status_and_target_type():
    add = runner.invoke(app, [
        "add-reminder", "Möte på Odenplan",
        "--at", "2026-06-15 12:00",
    ])
    reminder_id = _added_reminder_id(add.stdout)

    result = runner.invoke(app, ["reminders"])
    assert result.exit_code == 0
    assert f"#{reminder_id}" in result.stdout
    assert "pending" in result.stdout
    assert "general" in result.stdout
    assert "Möte på Odenplan" in result.stdout
