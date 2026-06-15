"""Tests for life_agent.services.saved_data_response_service.

These tests are pure-formatting tests: no database access required.
"""

from life_agent.schemas.saved_data_query import (
    QueryType,
    SavedDataQueryResult,
    SavedDataRecord,
)
from life_agent.services.saved_data_response_service import (
    format_saved_data_query_result,
)


# ---------------------------------------------------------------------------
# Reminder lookup formatting
# ---------------------------------------------------------------------------


class TestFormatReminderLookup:
    def test_matched_single_reminder(self):
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="vilken tid ska du påminna mig om att handla mat",
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
        assert text.startswith("You have a reminder")

    def test_matched_multiple_reminders(self):
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=True,
            records=[
                SavedDataRecord(record_type="reminder", title="A", when="2026-06-15 10:00"),
                SavedDataRecord(record_type="reminder", title="B", when="2026-06-16 08:00"),
            ],
        )
        text = format_saved_data_query_result(result)
        assert "A" in text
        assert "B" in text

    def test_no_records_with_fallback(self):
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=False,
            records=[],
            fallback_message="You have no pending reminders.",
        )
        text = format_saved_data_query_result(result)
        assert "no pending reminders" in text.lower()

    def test_unmatched_lists_pending(self):
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


# ---------------------------------------------------------------------------
# Planned tomorrow formatting
# ---------------------------------------------------------------------------


class TestFormatPlannedTomorrow:
    def test_with_reminder_record(self):
        result = SavedDataQueryResult(
            query_type=QueryType.PLANNED_TOMORROW,
            question="har jag något planerat imorgon",
            matched=True,
            records=[
                SavedDataRecord(
                    record_type="reminder",
                    title="Träning",
                    when="2026-06-15 09:00",
                    status="pending",
                )
            ],
        )
        text = format_saved_data_query_result(result)
        assert "Planned for tomorrow" in text
        assert "Träning" in text
        assert "2026-06-15" in text

    def test_no_records_fallback(self):
        result = SavedDataQueryResult(
            query_type=QueryType.PLANNED_TOMORROW,
            question="har jag något planerat imorgon",
            matched=False,
            records=[],
            fallback_message="Nothing is planned for tomorrow (2026-06-16).",
        )
        text = format_saved_data_query_result(result)
        assert "Nothing is planned" in text

    def test_multiple_record_types(self):
        result = SavedDataQueryResult(
            query_type=QueryType.PLANNED_TOMORROW,
            question="test",
            matched=True,
            records=[
                SavedDataRecord(record_type="event", title="Meeting", when="2026-06-15 14:00"),
                SavedDataRecord(record_type="task", title="Study", when="2026-06-15"),
            ],
        )
        text = format_saved_data_query_result(result)
        assert "Event" in text
        assert "Task" in text


# ---------------------------------------------------------------------------
# Training this week formatting
# ---------------------------------------------------------------------------


class TestFormatTrainingWeek:
    def test_no_records_fallback(self):
        result = SavedDataQueryResult(
            query_type=QueryType.TRAINING_WEEK,
            question="vad har jag för träningar den här veckan",
            matched=False,
            records=[],
            fallback_message="No training activities found this week (2026-06-09 – 2026-06-15).",
        )
        text = format_saved_data_query_result(result)
        assert "No training" in text

    def test_with_activity_record(self):
        result = SavedDataQueryResult(
            query_type=QueryType.TRAINING_WEEK,
            question="test",
            matched=True,
            records=[
                SavedDataRecord(
                    record_type="activity",
                    title="Gym session",
                    when="2026-06-12",
                    details="gym",
                )
            ],
        )
        text = format_saved_data_query_result(result)
        assert "Training this week" in text
        assert "Gym session" in text
        assert "2026-06-12" in text


# ---------------------------------------------------------------------------
# Unknown formatting
# ---------------------------------------------------------------------------


class TestFormatUnknown:
    def test_uses_fallback_message(self):
        result = SavedDataQueryResult(
            query_type=QueryType.UNKNOWN,
            question="random",
            matched=False,
            fallback_message="I couldn't find a specific answer for that yet.",
        )
        text = format_saved_data_query_result(result)
        assert "couldn't find" in text.lower()

    def test_missing_fallback_uses_default(self):
        result = SavedDataQueryResult(
            query_type=QueryType.UNKNOWN,
            question="random",
            matched=False,
        )
        text = format_saved_data_query_result(result)
        assert "couldn't find" in text.lower()
