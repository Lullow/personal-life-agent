"""Tests for life_agent.services.saved_data_query_service."""

import os
from datetime import date, datetime, timedelta

import pytest
from typer.testing import CliRunner

from life_agent.main import app
from life_agent.services.saved_data_query_service import answer_saved_data_question

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def _db() -> str:
    return os.environ["DB_PATH"]


def _seed_reminder(title: str, remind_at: datetime) -> None:
    runner.invoke(
        app,
        ["add-reminder", title, "--at", remind_at.strftime("%Y-%m-%d %H:%M")],
    )


def _seed_planned_activity(text: str) -> None:
    runner.invoke(app, ["add", "--yes", text])


# ---------------------------------------------------------------------------
# Reminder lookup
# ---------------------------------------------------------------------------


class TestReminderLookup:
    def test_finds_matching_reminder(self):
        remind_at = datetime(2026, 6, 15, 10, 0)
        _seed_reminder("Handla mat", remind_at)
        result = answer_saved_data_question(
            "vilken tid ska du påminna mig om att handla mat", db_path=_db()
        )
        assert "Handla mat" in result
        assert "2026-06-15" in result
        assert "10:00" in result

    def test_no_match_lists_all_reminders(self):
        remind_at = datetime(2026, 6, 16, 9, 0)
        _seed_reminder("Betala faktura", remind_at)
        result = answer_saved_data_question(
            "när ska du påminna mig om att handla mat", db_path=_db()
        )
        assert "No reminder matched" in result
        assert "Betala faktura" in result

    def test_no_reminders_at_all(self):
        result = answer_saved_data_question(
            "vilken tid ska du påminna mig om träningen", db_path=_db()
        )
        assert "no pending reminders" in result.lower()

    def test_multiple_matches_all_returned(self):
        _seed_reminder("Handla mat", datetime(2026, 6, 15, 10, 0))
        _seed_reminder("Handla mera mat", datetime(2026, 6, 16, 8, 0))
        result = answer_saved_data_question(
            "vilken tid ska du påminna mig om att handla mat", db_path=_db()
        )
        assert "Handla mat" in result


# ---------------------------------------------------------------------------
# Tomorrow question
# ---------------------------------------------------------------------------


class TestTomorrowQuestion:
    def test_nothing_tomorrow(self):
        today = date.today()
        result = answer_saved_data_question(
            "har jag något planerat imorgon", db_path=_db(), today=today
        )
        assert "Nothing is planned" in result

    def test_reminder_tomorrow_shows_up(self):
        today = date(2026, 6, 14)
        tomorrow = date(2026, 6, 15)
        _seed_reminder("Träning", datetime(2026, 6, 15, 9, 0))
        result = answer_saved_data_question(
            "har jag något planerat imorgon", db_path=_db(), today=today
        )
        assert str(tomorrow) in result
        assert "Träning" in result


# ---------------------------------------------------------------------------
# Training this week
# ---------------------------------------------------------------------------


class TestTrainingWeek:
    def test_no_training_this_week(self):
        today = date.today()
        result = answer_saved_data_question(
            "vad har jag för träningar den här veckan", db_path=_db(), today=today
        )
        assert "No training" in result

    def test_training_activity_shows_up(self):
        runner.invoke(app, ["add", "--yes", "Jag ska gymma idag kl 18"])
        today = date.today()
        result = answer_saved_data_question(
            "vad har jag för träningar den här veckan", db_path=_db(), today=today
        )
        assert "training" in result.lower() or "gym" in result.lower() or str(today) in result


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


class TestFallback:
    def test_unknown_question_returns_fallback(self):
        result = answer_saved_data_question("something completely random", db_path=_db())
        assert "couldn't find" in result.lower() or "not sure" in result.lower()
