"""Tests for the chat service intent classifier and response helpers."""

import os

import pytest
from typer.testing import CliRunner

from life_agent.main import app
from life_agent.services.chat_service import (
    ChatIntent,
    classify_intent,
    get_deadlines_response,
    get_reminders_response,
    get_today_response,
    get_week_response,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    runner.invoke(app, ["init"])


def _db_path() -> str:
    return os.environ["DB_PATH"]


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["/help", "help", "/h"])
def test_help_intent(text):
    assert classify_intent(text) == ChatIntent.HELP


@pytest.mark.parametrize("text", ["/quit", "/exit", "quit", "exit"])
def test_quit_intent(text):
    assert classify_intent(text) == ChatIntent.QUIT


# ---------------------------------------------------------------------------
# Today planner
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "vad har jag idag",
        "Vad har jag idag?",
        "vad händer idag",
        "dagens plan",
        "visa idag",
        "today",
    ],
)
def test_today_intent(text):
    assert classify_intent(text) == ChatIntent.TODAY


# ---------------------------------------------------------------------------
# Week planner
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "vad händer i veckan",
        "visa veckan",
        "veckoplan",
        "veckans plan",
    ],
)
def test_week_intent(text):
    assert classify_intent(text) == ChatIntent.WEEK


# ---------------------------------------------------------------------------
# Deadlines
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "visa deadlines",
        "vad har jag för deadlines",
        "deadlines",
    ],
)
def test_deadlines_intent(text):
    assert classify_intent(text) == ChatIntent.DEADLINES


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "visa påminnelser",
        "mina reminders",
        "mina påminnelser",
        "påminnelser",
    ],
)
def test_reminders_intent(text):
    assert classify_intent(text) == ChatIntent.REMINDERS


# ---------------------------------------------------------------------------
# Add items (planning)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "jag ska träna rygg och biceps kl 12 imorgon",
        "påminn mig att handla mat imorgon kl 10",
        "jag behöver plugga machine learning på fredag",
        "jag måste handla mat imorgon",
        "jag har möte på Odenplan kl 14 imorgon",
        "kom ihåg att betala fakturan",
        "jag ska gymma idag kl 18",
    ],
)
def test_add_items_intent(text):
    assert classify_intent(text) == ChatIntent.ADD_ITEMS


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "jag har tränat klart",
        "träningen är klar",
        "klar med träningen",
    ],
)
def test_complete_intent(text):
    assert classify_intent(text) == ChatIntent.COMPLETE


# ---------------------------------------------------------------------------
# Unknown
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "hej allihopa",
        "what is the meaning of life",
        "asdf",
        "",
        "   ",
    ],
)
def test_unknown_intent(text):
    assert classify_intent(text) == ChatIntent.UNKNOWN


# ---------------------------------------------------------------------------
# Read-only response helpers
# ---------------------------------------------------------------------------


def test_get_today_response_returns_string():
    result = get_today_response(db_path=_db_path())
    assert isinstance(result, str)
    assert "Today" in result


def test_get_week_response_returns_string():
    result = get_week_response(db_path=_db_path())
    assert isinstance(result, str)
    assert "Week" in result


def test_get_deadlines_response_returns_string():
    result = get_deadlines_response(db_path=_db_path())
    assert isinstance(result, str)


def test_get_reminders_response_empty():
    result = get_reminders_response(db_path=_db_path())
    assert "No pending reminders" in result
