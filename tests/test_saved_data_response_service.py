"""Tests for life_agent.services.saved_data_response_service.

These tests are pure-formatting tests: no database access required.
"""

from life_agent.schemas.saved_data_query import (
    QueryType,
    SavedDataAnswer,
    SavedDataQueryResult,
    SavedDataRecord,
)
from life_agent.services.saved_data_response_service import (
    build_saved_data_answer,
    format_saved_data_answer,
    format_saved_data_query_result,
)


# ---------------------------------------------------------------------------
# build_saved_data_answer
# ---------------------------------------------------------------------------


class TestBuildSavedDataAnswer:
    def test_returns_saved_data_answer(self):
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=True,
            records=[SavedDataRecord(record_type="reminder", title="X", when="2026-06-15 10:00")],
        )
        answer = build_saved_data_answer(result)
        assert isinstance(answer, SavedDataAnswer)

    def test_matching_reminder_is_grounded(self):
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=True,
            records=[SavedDataRecord(record_type="reminder", title="Handla mat", when="2026-06-15 10:00")],
        )
        answer = build_saved_data_answer(result)
        assert answer.grounded is True
        assert answer.matched is True

    def test_matching_reminder_record_count(self):
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=True,
            records=[SavedDataRecord(record_type="reminder", title="A", when="2026-06-15 10:00")],
        )
        answer = build_saved_data_answer(result)
        assert answer.record_count == 1

    def test_source_record_types_includes_reminder(self):
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=True,
            records=[SavedDataRecord(record_type="reminder", title="A", when="2026-06-15 10:00")],
        )
        answer = build_saved_data_answer(result)
        assert "reminder" in answer.source_record_types

    def test_multiple_record_types_sorted(self):
        result = SavedDataQueryResult(
            query_type=QueryType.PLANNED_TOMORROW,
            question="test",
            matched=True,
            records=[
                SavedDataRecord(record_type="event", title="Meeting", when="2026-06-15 14:00"),
                SavedDataRecord(record_type="reminder", title="Gym", when="2026-06-15 09:00"),
                SavedDataRecord(record_type="event", title="Lunch", when="2026-06-15 12:00"),
            ],
        )
        answer = build_saved_data_answer(result)
        assert answer.source_record_types == ["event", "reminder"]
        assert answer.record_count == 3

    def test_no_training_is_not_grounded(self):
        result = SavedDataQueryResult(
            query_type=QueryType.TRAINING_WEEK,
            question="test",
            matched=False,
            records=[],
            fallback_message="No training activities found this week (2026-06-09 – 2026-06-15).",
        )
        answer = build_saved_data_answer(result)
        assert answer.grounded is False
        assert answer.matched is False
        assert answer.record_count == 0
        assert answer.source_record_types == []

    def test_unknown_is_not_grounded(self):
        result = SavedDataQueryResult(
            query_type=QueryType.UNKNOWN,
            question="random",
            matched=False,
            fallback_message="I couldn't find a specific answer for that yet.",
        )
        answer = build_saved_data_answer(result)
        assert answer.grounded is False
        assert answer.matched is False

    def test_fallback_message_preserved(self):
        msg = "You have no pending reminders."
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=False,
            records=[],
            fallback_message=msg,
        )
        answer = build_saved_data_answer(result)
        assert answer.fallback_message == msg

    def test_limitations_populated_on_fallback(self):
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=False,
            records=[],
            fallback_message="You have no pending reminders.",
        )
        answer = build_saved_data_answer(result)
        assert len(answer.limitations) >= 1
        assert "no pending reminders" in answer.limitations[0].lower()

    def test_limitations_empty_when_matched(self):
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=True,
            records=[SavedDataRecord(record_type="reminder", title="A", when="2026-06-15 10:00")],
        )
        answer = build_saved_data_answer(result)
        assert answer.limitations == []

    def test_unmatched_with_records_is_grounded(self):
        """When records exist (e.g. listing all pending) the answer is still grounded."""
        result = SavedDataQueryResult(
            query_type=QueryType.REMINDER_LOOKUP,
            question="test",
            matched=False,
            records=[SavedDataRecord(record_type="reminder", title="Other", when="2026-06-16 09:00")],
            fallback_message="No reminder matched your query.",
        )
        answer = build_saved_data_answer(result)
        assert answer.grounded is True
        assert answer.matched is False
        assert answer.record_count == 1

    def test_query_type_is_string_value(self):
        result = SavedDataQueryResult(
            query_type=QueryType.PLANNED_TOMORROW,
            question="test",
            matched=False,
            records=[],
            fallback_message="Nothing planned.",
        )
        answer = build_saved_data_answer(result)
        assert answer.query_type == "planned_tomorrow"


# ---------------------------------------------------------------------------
# format_saved_data_answer
# ---------------------------------------------------------------------------


class TestFormatSavedDataAnswer:
    def test_returns_string(self):
        answer = SavedDataAnswer(
            query_type="reminder_lookup",
            text="You have a reminder for Handla mat at 2026-06-15 10:00.",
            grounded=True,
            matched=True,
            record_count=1,
            source_record_types=["reminder"],
        )
        text = format_saved_data_answer(answer)
        assert isinstance(text, str)
        assert "Handla mat" in text

    def test_returns_text_field(self):
        answer = SavedDataAnswer(
            query_type="unknown",
            text="I couldn't find a specific answer for that yet.",
            grounded=False,
            matched=False,
            record_count=0,
        )
        assert format_saved_data_answer(answer) == answer.text


# ---------------------------------------------------------------------------
# format_saved_data_query_result (backward compat)
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
