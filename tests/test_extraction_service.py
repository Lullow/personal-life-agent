"""Tests for the extraction service (rule-based fallback)."""

from datetime import date, datetime

from life_agent.models.common import ActivityType
from life_agent.schemas.extraction import ExtractionResult
from life_agent.services.extraction_service import extract_from_text


# Canonical Swedish example from the spec.
TRAINING_TEXT = (
    "Jag ska träna rygg och biceps kl 12 imorgon, "
    "träningen ska vara 1h och påminn mig kl 09."
)


def test_extraction_returns_extraction_result():
    result = extract_from_text(
        TRAINING_TEXT, reference_date=date(2026, 6, 11)
    )
    assert isinstance(result, ExtractionResult)
    assert result.raw_text == TRAINING_TEXT


def test_training_example_extracts_activity():
    result = extract_from_text(
        TRAINING_TEXT, reference_date=date(2026, 6, 11)
    )
    assert len(result.activities) == 1, result.activities
    activity = result.activities[0]
    assert activity.activity_type == ActivityType.GYM
    assert activity.logged_at == datetime(2026, 6, 12, 12, 0)
    assert activity.duration_minutes == 60
    assert activity.title is not None
    title_lower = activity.title.lower()
    assert "rygg" in title_lower or "biceps" in title_lower


def test_training_example_extracts_reminder():
    result = extract_from_text(
        TRAINING_TEXT, reference_date=date(2026, 6, 11)
    )
    assert len(result.reminders) == 1, result.reminders
    reminder = result.reminders[0]
    assert reminder.remind_at == datetime(2026, 6, 12, 9, 0)
    assert reminder.title is not None and reminder.title.strip() != ""


def test_training_example_does_not_create_tasks_or_events():
    result = extract_from_text(
        TRAINING_TEXT, reference_date=date(2026, 6, 11)
    )
    assert result.tasks == []
    assert result.events == []


def test_reference_date_makes_extraction_deterministic():
    a = extract_from_text(TRAINING_TEXT, reference_date=date(2026, 6, 11))
    b = extract_from_text(TRAINING_TEXT, reference_date=date(2026, 6, 11))
    assert a.activities[0].logged_at == b.activities[0].logged_at
    assert a.reminders[0].remind_at == b.reminders[0].remind_at


def test_idag_resolves_to_reference_date():
    result = extract_from_text(
        "Jag ska träna gym kl 18 idag",
        reference_date=date(2026, 6, 11),
    )
    assert len(result.activities) == 1
    assert result.activities[0].logged_at == datetime(2026, 6, 11, 18, 0)


def test_event_keyword_extracts_calendar_event():
    result = extract_from_text(
        "Möte på Odenplan kl 14 imorgon",
        reference_date=date(2026, 6, 11),
    )
    assert len(result.events) == 1
    event = result.events[0]
    assert event.start_time == datetime(2026, 6, 12, 14, 0)
    assert event.title is not None
    assert "möte" in event.title.lower()


def test_reminder_with_kl_extracts_remind_at():
    result = extract_from_text(
        "Påminn mig kl 07 imorgon",
        reference_date=date(2026, 6, 11),
    )
    assert len(result.reminders) == 1
    assert result.reminders[0].remind_at == datetime(2026, 6, 12, 7, 0)


def test_empty_text_returns_empty_result_with_question():
    result = extract_from_text("")
    assert result.tasks == []
    assert result.events == []
    assert result.activities == []
    assert result.reminders == []
    assert result.questions  # at least one clarifying question


def test_whitespace_only_text_handled_cleanly():
    result = extract_from_text("   \n  ")
    assert result.tasks == []
    assert result.events == []
    assert result.activities == []
    assert result.reminders == []


def test_unrecognised_text_yields_no_items_and_questions():
    result = extract_from_text(
        "Some text without any structure",
        reference_date=date(2026, 6, 11),
    )
    assert result.activities == []
    assert result.events == []
    assert result.reminders == []
    assert result.questions
    assert (result.confidence or 0.0) == 0.0


def test_extraction_confidence_for_useful_input():
    result = extract_from_text(
        TRAINING_TEXT, reference_date=date(2026, 6, 11)
    )
    assert result.confidence is not None
    assert result.confidence > 0.0
