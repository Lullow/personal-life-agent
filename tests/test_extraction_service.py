"""Tests for the extraction service (rule-based fallback)."""

from datetime import date, datetime

from life_agent.models.common import (
    ActivityType,
    EventCategory,
    TaskCategory,
)
from life_agent.schemas.extraction import ExtractionResult
from life_agent.services.extraction_service import extract_from_text

# Reference date used across the deterministic tests below.
# 2026-06-11 is a Thursday (weekday() == 3), so:
#   "på fredag" -> 2026-06-12, "på söndag" -> 2026-06-14,
#   "på måndag" -> 2026-06-15.
REF = date(2026, 6, 11)


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


# ---------------------------------------------------------------------------
# Improved coverage: activities
# ---------------------------------------------------------------------------


def test_planned_gym_today_with_duration():
    result = extract_from_text(
        "Jag ska gymma bröst och triceps idag kl 18 i 45 minuter",
        reference_date=REF,
    )
    assert len(result.activities) == 1, result.activities
    activity = result.activities[0]
    assert activity.activity_type == ActivityType.GYM
    assert activity.logged_at == datetime(2026, 6, 11, 18, 0)
    assert activity.duration_minutes == 45
    assert activity.title is not None
    title_lower = activity.title.lower()
    assert "bröst" in title_lower or "triceps" in title_lower
    assert result.tasks == []
    assert result.events == []


def test_planned_gym_with_klockan_time():
    result = extract_from_text(
        "Jag ska gymma idag klockan 18",
        reference_date=REF,
    )
    assert len(result.activities) == 1
    assert result.activities[0].logged_at == datetime(2026, 6, 11, 18, 0)
    assert result.activities[0].activity_type == ActivityType.GYM


def test_vague_time_becomes_question_not_timestamp():
    result = extract_from_text(
        "Jag ska träna ben på söndag kväll",
        reference_date=REF,
    )
    assert len(result.activities) == 1
    activity = result.activities[0]
    assert activity.activity_type == ActivityType.GYM
    # "kväll" must not be invented into an exact time.
    assert activity.logged_at is None
    assert result.questions  # a clarifying question was recorded


# ---------------------------------------------------------------------------
# Improved coverage: events
# ---------------------------------------------------------------------------


def test_event_with_location_and_time():
    result = extract_from_text(
        "Jag har möte på Odenplan kl 14 imorgon",
        reference_date=REF,
    )
    assert len(result.events) == 1, result.events
    event = result.events[0]
    assert event.start_time == datetime(2026, 6, 12, 14, 0)
    assert event.location == "Odenplan"
    assert event.category == EventCategory.MEETING
    assert event.title is not None and "möte" in event.title.lower()


def test_dentist_event_on_weekday():
    result = extract_from_text(
        "Jag ska till tandläkaren på fredag kl 10",
        reference_date=REF,
    )
    assert len(result.events) == 1, result.events
    event = result.events[0]
    assert event.start_time == datetime(2026, 6, 12, 10, 0)
    assert event.category == EventCategory.HEALTH
    assert event.title is not None and "tandläkare" in event.title.lower()


def test_event_with_bare_time():
    result = extract_from_text(
        "Möte med skolan på måndag 13:30",
        reference_date=REF,
    )
    assert len(result.events) == 1, result.events
    event = result.events[0]
    assert event.start_time == datetime(2026, 6, 15, 13, 30)
    assert event.category == EventCategory.MEETING


# ---------------------------------------------------------------------------
# Improved coverage: tasks
# ---------------------------------------------------------------------------


def test_study_task_with_due_date():
    result = extract_from_text(
        "Jag behöver plugga machine learning på fredag",
        reference_date=REF,
    )
    assert len(result.tasks) == 1, result.tasks
    task = result.tasks[0]
    assert task.due_date == date(2026, 6, 12)
    assert task.category == TaskCategory.STUDY
    assert task.title is not None and "machine learning" in task.title.lower()
    assert result.activities == []
    assert result.events == []


def test_errand_task_with_due_date():
    result = extract_from_text(
        "Jag måste handla mat imorgon",
        reference_date=REF,
    )
    assert len(result.tasks) == 1, result.tasks
    task = result.tasks[0]
    assert task.due_date == date(2026, 6, 12)
    assert task.category == TaskCategory.ERRAND
    assert task.title is not None and "handla" in task.title.lower()


def test_kom_ihag_task_on_weekday():
    result = extract_from_text(
        "Kom ihåg att betala fakturan på måndag",
        reference_date=REF,
    )
    assert len(result.tasks) == 1, result.tasks
    task = result.tasks[0]
    assert task.due_date == date(2026, 6, 15)
    assert task.category == TaskCategory.ERRAND
    assert task.title is not None
    title_lower = task.title.lower()
    assert "betala" in title_lower or "faktura" in title_lower


# ---------------------------------------------------------------------------
# Improved coverage: reminders
# ---------------------------------------------------------------------------


def test_standalone_reminder_with_date_and_time():
    result = extract_from_text(
        "Påminn mig att handla mat imorgon kl 10",
        reference_date=REF,
    )
    assert len(result.reminders) == 1, result.reminders
    reminder = result.reminders[0]
    assert reminder.remind_at == datetime(2026, 6, 12, 10, 0)
    assert reminder.title is not None and "handla" in reminder.title.lower()
    # A "påminn" phrase is a reminder, not a task.
    assert result.tasks == []


def test_reminder_on_weekday_stays_general():
    result = extract_from_text(
        "Påminn mig på fredag kl 08",
        reference_date=REF,
    )
    assert len(result.reminders) == 1, result.reminders
    reminder = result.reminders[0]
    assert reminder.remind_at == datetime(2026, 6, 12, 8, 0)
    # target unclear -> stays general (None here, defaulted on save)
    assert reminder.target_type is None


# ---------------------------------------------------------------------------
# Improved coverage: weekday parsing determinism
# ---------------------------------------------------------------------------


def test_weekday_parsing_uses_reference_date():
    # From Thursday 2026-06-11, "på söndag" is 2026-06-14.
    from_thursday = extract_from_text(
        "Jag behöver plugga på söndag", reference_date=date(2026, 6, 11)
    )
    assert from_thursday.tasks[0].due_date == date(2026, 6, 14)

    # From Monday 2026-06-15, "på söndag" is the following Sunday 2026-06-21.
    from_monday = extract_from_text(
        "Jag behöver plugga på söndag", reference_date=date(2026, 6, 15)
    )
    assert from_monday.tasks[0].due_date == date(2026, 6, 21)


# ---------------------------------------------------------------------------
# Optional LLM mode (with a fake client — never a real network call)
# ---------------------------------------------------------------------------


class _FakeLLMClient:
    """Stand-in for LLMClient that returns a canned dict (or raises)."""

    def __init__(self, payload=None, *, enabled=True, error=None):
        self.payload = payload
        self.enabled = enabled
        self.error = error

    def extract_structured(self, system_prompt, user_text):
        if self.error is not None:
            raise self.error
        return self.payload


def test_llm_client_result_is_used_when_valid():
    payload = {
        "tasks": [{"title": "From the LLM", "category": "study"}],
        "events": [],
        "activities": [],
        "reminders": [],
        "questions": [],
        "confidence": 0.95,
    }
    result = extract_from_text(
        "anything", reference_date=REF, llm_client=_FakeLLMClient(payload)
    )
    assert len(result.tasks) == 1
    assert result.tasks[0].title == "From the LLM"
    assert result.confidence == 0.95
    # raw_text is always set from the input.
    assert result.raw_text == "anything"


def test_llm_invalid_output_falls_back_to_deterministic():
    # Invalid shape (tasks must be a list) -> validation fails -> fallback.
    bad_payload = {"tasks": "not-a-list"}
    result = extract_from_text(
        "Jag ska gymma idag kl 18",
        reference_date=REF,
        llm_client=_FakeLLMClient(bad_payload),
    )
    # Deterministic extractor still found the planned activity.
    assert len(result.activities) == 1
    assert result.activities[0].logged_at == datetime(2026, 6, 11, 18, 0)
    # A note explains the graceful fallback.
    assert any("deterministic extractor" in q for q in result.questions)


def test_llm_client_error_falls_back_to_deterministic():
    result = extract_from_text(
        "Jag ska gymma idag kl 18",
        reference_date=REF,
        llm_client=_FakeLLMClient(error=RuntimeError("boom")),
    )
    assert len(result.activities) == 1
    assert any("deterministic extractor" in q for q in result.questions)


def test_llm_mode_without_config_falls_back(monkeypatch):
    for var in (
        "LIFE_AGENT_LLM_API_KEY",
        "LIFE_AGENT_LLM_BASE_URL",
        "LIFE_AGENT_LLM_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)

    result = extract_from_text(
        "Jag ska gymma idag kl 18", reference_date=REF, mode="llm"
    )
    # Still works, using the deterministic extractor, with an explanatory note.
    assert len(result.activities) == 1
    assert any("not fully configured" in q for q in result.questions)


def test_default_mode_is_deterministic_without_env(monkeypatch):
    monkeypatch.delenv("LIFE_AGENT_EXTRACTION_MODE", raising=False)
    result = extract_from_text(
        "Jag ska gymma idag kl 18", reference_date=REF
    )
    assert len(result.activities) == 1
    # No fallback note when deterministic is the chosen mode.
    assert not any("deterministic extractor" in q for q in result.questions)
