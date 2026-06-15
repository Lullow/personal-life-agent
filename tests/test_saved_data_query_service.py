"""Tests for life_agent.services.saved_data_query_service."""

import os
from datetime import date, datetime, timedelta

import pytest
from typer.testing import CliRunner

from life_agent.main import app
from life_agent.schemas.saved_data_query import QueryType, SavedDataQueryResult, SavedDataRecord
from life_agent.services.saved_data_query_service import (
    answer_saved_data_question,
    detect_saved_data_query_type,
    query_saved_data,
)
from life_agent.services.saved_data_response_service import (
    format_saved_data_query_result,
)

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
# detect_saved_data_query_type
# ---------------------------------------------------------------------------


class TestDetectSavedDataQueryType:
    @pytest.mark.parametrize(
        "text",
        [
            "vilken tid ska du påminna mig om att handla mat",
            "när ska du påminna mig om träningen",
        ],
    )
    def test_returns_reminder_lookup(self, text: str):
        assert detect_saved_data_query_type(text) == "reminder_lookup"

    @pytest.mark.parametrize(
        "text",
        [
            "har jag något planerat imorgon",
            "vad händer imorgon",
        ],
    )
    def test_returns_planned_tomorrow(self, text: str):
        assert detect_saved_data_query_type(text) == "planned_tomorrow"

    @pytest.mark.parametrize(
        "text",
        [
            "vad har jag för träningar den här veckan",
            "träningar i veckan",
        ],
    )
    def test_returns_training_week(self, text: str):
        assert detect_saved_data_query_type(text) == "training_week"

    @pytest.mark.parametrize(
        "text",
        [
            "vad är nästa grej",
            "vad händer härnäst",
            "nästa påminnelse",
        ],
    )
    def test_returns_next_upcoming(self, text: str):
        assert detect_saved_data_query_type(text) == "next_upcoming"

    @pytest.mark.parametrize(
        "text",
        [
            "vad borde jag fokusera på idag",
            "vad är viktigast idag",
            "dagens fokus",
        ],
    )
    def test_returns_daily_focus(self, text: str):
        assert detect_saved_data_query_type(text) == "daily_focus"

    @pytest.mark.parametrize(
        "text",
        [
            "hello there",
            "jag ska gymma idag kl 18",
            "påminn mig att handla mat imorgon kl 10",
            "jag har tränat klart",
            "",
        ],
    )
    def test_returns_unknown_for_non_queries(self, text: str):
        assert detect_saved_data_query_type(text) == "unknown"

    def test_no_database_access(self):
        """detect_saved_data_query_type is pure text — no db_path needed."""
        result = detect_saved_data_query_type("vad är nästa grej")
        assert result == "next_upcoming"


# ---------------------------------------------------------------------------
# Structured: query_saved_data returns SavedDataQueryResult
# ---------------------------------------------------------------------------


class TestQuerySavedDataReturnsStructured:
    def test_returns_saved_data_query_result(self):
        result = query_saved_data("vilken tid ska du påminna mig om att handla mat", db_path=_db())
        assert isinstance(result, SavedDataQueryResult)

    def test_records_are_saved_data_record_instances(self):
        _seed_reminder("Handla mat", datetime(2026, 6, 15, 10, 0))
        result = query_saved_data(
            "vilken tid ska du påminna mig om att handla mat", db_path=_db()
        )
        assert all(isinstance(r, SavedDataRecord) for r in result.records)


# ---------------------------------------------------------------------------
# Structured: Reminder lookup
# ---------------------------------------------------------------------------


class TestStructuredReminderLookup:
    def test_query_type_is_reminder_lookup(self):
        result = query_saved_data(
            "vilken tid ska du påminna mig om att handla mat", db_path=_db()
        )
        assert result.query_type == QueryType.REMINDER_LOOKUP

    def test_matched_true_when_reminder_found(self):
        _seed_reminder("Handla mat", datetime(2026, 6, 15, 10, 0))
        result = query_saved_data(
            "vilken tid ska du påminna mig om att handla mat", db_path=_db()
        )
        assert result.matched is True

    def test_matched_false_when_no_reminders(self):
        result = query_saved_data(
            "vilken tid ska du påminna mig om att handla mat", db_path=_db()
        )
        assert result.matched is False

    def test_record_contains_title_and_when(self):
        _seed_reminder("Handla mat", datetime(2026, 6, 15, 10, 0))
        result = query_saved_data(
            "vilken tid ska du påminna mig om att handla mat", db_path=_db()
        )
        assert len(result.records) >= 1
        rec = result.records[0]
        assert rec.record_type == "reminder"
        assert "Handla mat" in rec.title
        assert "2026-06-15" in (rec.when or "")
        assert "10:00" in (rec.when or "")

    def test_no_match_still_includes_pending_records(self):
        _seed_reminder("Betala faktura", datetime(2026, 6, 16, 9, 0))
        result = query_saved_data(
            "när ska du påminna mig om att handla mat", db_path=_db()
        )
        assert result.matched is False
        assert len(result.records) >= 1
        assert result.records[0].title == "Betala faktura"


# ---------------------------------------------------------------------------
# Structured: Planned tomorrow
# ---------------------------------------------------------------------------


class TestStructuredPlannedTomorrow:
    def test_query_type_is_planned_tomorrow(self):
        result = query_saved_data(
            "har jag något planerat imorgon", db_path=_db(), today=date(2026, 6, 14)
        )
        assert result.query_type == QueryType.PLANNED_TOMORROW

    def test_matched_false_when_nothing_tomorrow(self):
        result = query_saved_data(
            "har jag något planerat imorgon", db_path=_db(), today=date(2026, 6, 14)
        )
        assert result.matched is False
        assert result.records == []

    def test_matched_true_with_reminder_tomorrow(self):
        _seed_reminder("Träning", datetime(2026, 6, 15, 9, 0))
        result = query_saved_data(
            "har jag något planerat imorgon", db_path=_db(), today=date(2026, 6, 14)
        )
        assert result.matched is True
        assert len(result.records) >= 1
        assert any("Träning" in r.title for r in result.records)


# ---------------------------------------------------------------------------
# Structured: Training this week
# ---------------------------------------------------------------------------


class TestStructuredTrainingWeek:
    def test_query_type_is_training_week(self):
        today = date.today()
        result = query_saved_data(
            "vad har jag för träningar den här veckan", db_path=_db(), today=today
        )
        assert result.query_type == QueryType.TRAINING_WEEK

    def test_matched_false_when_no_training(self):
        today = date.today()
        result = query_saved_data(
            "vad har jag för träningar den här veckan", db_path=_db(), today=today
        )
        assert result.matched is False
        assert result.records == []

    def test_matched_true_with_gym_activity(self):
        runner.invoke(app, ["add", "--yes", "Jag ska gymma idag kl 18"])
        today = date.today()
        result = query_saved_data(
            "vad har jag för träningar den här veckan", db_path=_db(), today=today
        )
        assert result.matched is True
        assert len(result.records) >= 1
        assert result.records[0].record_type == "activity"


# ---------------------------------------------------------------------------
# Structured: Unknown question
# ---------------------------------------------------------------------------


class TestStructuredUnknown:
    def test_query_type_is_unknown(self):
        result = query_saved_data("something completely random", db_path=_db())
        assert result.query_type == QueryType.UNKNOWN

    def test_matched_is_false(self):
        result = query_saved_data("something completely random", db_path=_db())
        assert result.matched is False

    def test_fallback_message_present(self):
        result = query_saved_data("something completely random", db_path=_db())
        assert result.fallback_message is not None
        assert len(result.fallback_message) > 0


# ---------------------------------------------------------------------------
# format_saved_data_query_result
# ---------------------------------------------------------------------------


class TestFormatResult:
    def test_formats_matched_reminder(self):
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=True,
            records=[
                SavedDataRecord(
                    record_type="reminder",
                    title="Handla mat",
                    when="2026-06-15 10:00",
                    status="pending",
                )
            ],
        )
        text = format_saved_data_query_result(result)
        assert "Handla mat" in text
        assert "2026-06-15 10:00" in text

    def test_formats_unmatched_reminder(self):
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=False,
            records=[
                SavedDataRecord(
                    record_type="reminder",
                    title="Betala faktura",
                    when="2026-06-16 09:00",
                    status="pending",
                )
            ],
            fallback_message="No reminder matched your query.",
        )
        text = format_saved_data_query_result(result)
        assert "No reminder matched" in text
        assert "Betala faktura" in text

    def test_formats_unknown_fallback(self):
        result = SavedDataQueryResult(
            query_type=QueryType.UNKNOWN,
            question="random",
            matched=False,
            fallback_message="I couldn't find a specific answer for that yet.",
        )
        text = format_saved_data_query_result(result)
        assert "couldn't find" in text.lower()


# ---------------------------------------------------------------------------
# Structured: Next upcoming
# ---------------------------------------------------------------------------


class TestStructuredNextUpcoming:
    def test_query_type_is_next_upcoming(self):
        result = query_saved_data("vad är nästa grej", db_path=_db())
        assert result.query_type == QueryType.NEXT_UPCOMING

    def test_matched_false_when_nothing_upcoming(self):
        result = query_saved_data("vad händer härnäst", db_path=_db())
        assert result.matched is False
        assert result.records == []
        assert result.fallback_message is not None

    def test_matched_true_with_future_reminder(self):
        _seed_reminder("Handla mat", datetime(2099, 1, 15, 10, 0))
        result = query_saved_data(
            "vad är nästa grej", db_path=_db(), today=date(2099, 1, 14)
        )
        assert result.matched is True
        assert len(result.records) >= 1
        assert result.records[0].record_type == "reminder"
        assert "Handla mat" in result.records[0].title

    def test_chooses_earliest_item(self):
        _seed_reminder("Later", datetime(2099, 3, 1, 12, 0))
        _seed_reminder("Sooner", datetime(2099, 2, 1, 8, 0))
        result = query_saved_data(
            "vad händer härnäst", db_path=_db(), today=date(2099, 1, 1)
        )
        assert result.matched is True
        assert len(result.records) == 1
        assert "Sooner" in result.records[0].title

    def test_ignores_past_items(self):
        _seed_reminder("Old", datetime(2020, 1, 1, 10, 0))
        result = query_saved_data(
            "vad är nästa grej", db_path=_db(), today=date(2026, 6, 15)
        )
        assert result.matched is False

    def test_returns_all_earliest_ties(self):
        _seed_reminder("A", datetime(2099, 2, 1, 10, 0))
        _seed_reminder("B", datetime(2099, 2, 1, 10, 0))
        result = query_saved_data(
            "nästa påminnelse", db_path=_db(), today=date(2099, 1, 1)
        )
        assert result.matched is True
        assert len(result.records) == 2

    def test_detects_nasta_paminnelse(self):
        result = query_saved_data("nästa påminnelse", db_path=_db())
        assert result.query_type == QueryType.NEXT_UPCOMING

    def test_detects_vad_har_jag_narmast(self):
        result = query_saved_data("vad har jag närmast", db_path=_db())
        assert result.query_type == QueryType.NEXT_UPCOMING


# ---------------------------------------------------------------------------
# Structured: Daily focus
# ---------------------------------------------------------------------------


def _seed_event(title: str, start: datetime) -> None:
    runner.invoke(
        app,
        ["add-event", title, "--start", start.strftime("%Y-%m-%d %H:%M")],
    )


def _seed_task(title: str, due: date | None = None) -> None:
    args = ["add-task", title]
    if due is not None:
        args += ["--due", str(due)]
    runner.invoke(app, args)


class TestStructuredDailyFocus:
    def test_query_type_is_daily_focus(self):
        result = query_saved_data(
            "vad borde jag fokusera på idag", db_path=_db(), today=date(2026, 6, 15)
        )
        assert result.query_type == QueryType.DAILY_FOCUS

    def test_matched_false_when_nothing_today(self):
        result = query_saved_data(
            "dagens fokus", db_path=_db(), today=date(2099, 1, 1)
        )
        assert result.matched is False
        assert result.records == []
        assert result.fallback_message is not None

    def test_matched_true_with_event_today(self):
        today = date(2026, 6, 15)
        _seed_event("Meeting", datetime(2026, 6, 15, 14, 0))
        result = query_saved_data(
            "vad är viktigast idag", db_path=_db(), today=today
        )
        assert result.matched is True
        assert any(r.record_type == "event" and "Meeting" in r.title for r in result.records)

    def test_matched_true_with_task_due_today(self):
        today = date(2026, 6, 15)
        _seed_task("Study ML", due=today)
        result = query_saved_data(
            "dagens fokus", db_path=_db(), today=today
        )
        assert result.matched is True
        assert any(r.record_type == "task" and "Study ML" in r.title for r in result.records)

    def test_matched_true_with_reminder_today(self):
        today = date(2026, 6, 15)
        _seed_reminder("Call doctor", datetime(2026, 6, 15, 9, 0))
        result = query_saved_data(
            "vad ska jag prioritera idag", db_path=_db(), today=today
        )
        assert result.matched is True
        assert any(r.record_type == "reminder" for r in result.records)

    def test_includes_records_with_details(self):
        today = date(2026, 6, 15)
        _seed_event("Meeting", datetime(2026, 6, 15, 14, 0))
        result = query_saved_data(
            "dagens fokus", db_path=_db(), today=today
        )
        assert result.records[0].details is not None

    def test_events_appear_before_tasks(self):
        today = date(2026, 6, 15)
        _seed_task("Study ML", due=today)
        _seed_event("Meeting", datetime(2026, 6, 15, 14, 0))
        result = query_saved_data(
            "dagens fokus", db_path=_db(), today=today
        )
        types = [r.record_type for r in result.records]
        assert types.index("event") < types.index("task")

    def test_undated_tasks_included_when_no_dated_tasks(self):
        _seed_task("Clean house")
        result = query_saved_data(
            "dagens fokus", db_path=_db(), today=date(2099, 1, 1)
        )
        assert result.matched is True
        assert any(r.record_type == "task" and "Clean house" in r.title for r in result.records)

    def test_undated_tasks_excluded_when_dated_tasks_exist(self):
        today = date(2026, 6, 15)
        _seed_task("Dated task", due=today)
        _seed_task("Undated task")
        result = query_saved_data(
            "dagens fokus", db_path=_db(), today=today
        )
        titles = [r.title for r in result.records]
        assert "Dated task" in titles
        assert "Undated task" not in titles

    def test_detects_fokusera_phrase(self):
        result = query_saved_data("vad ska jag fokusera på", db_path=_db())
        assert result.query_type == QueryType.DAILY_FOCUS

    def test_detects_viktigast_idag(self):
        result = query_saved_data("vad är viktigast idag", db_path=_db())
        assert result.query_type == QueryType.DAILY_FOCUS


# ---------------------------------------------------------------------------
# Existing string API: answer_saved_data_question (backward compat)
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


class TestFallback:
    def test_unknown_question_returns_fallback(self):
        result = answer_saved_data_question("something completely random", db_path=_db())
        assert "couldn't find" in result.lower() or "not sure" in result.lower()
