"""Tests for the confirmation service."""

import tempfile
from datetime import date, datetime
from pathlib import Path

import pytest

from life_agent.db.repositories import (
    list_activities,
    list_events,
    list_reminders,
    list_tasks,
)
from life_agent.db.schema import init_db
from life_agent.schemas.extraction import (
    ExtractedActivity,
    ExtractedEvent,
    ExtractedReminder,
    ExtractedTask,
    ExtractionResult,
)
from life_agent.models.common import ActivityType
from life_agent.services.confirmation_service import (
    build_confirmation_proposal,
    save_confirmed_extraction,
)


@pytest.fixture()
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "confirm.db")
        init_db(path)
        yield path


def _full_result() -> ExtractionResult:
    return ExtractionResult(
        tasks=[ExtractedTask(title="Buy milk", due_date=date(2026, 6, 15))],
        events=[
            ExtractedEvent(title="Möte", start_time=datetime(2026, 6, 12, 14, 0))
        ],
        activities=[
            ExtractedActivity(
                title="Träna rygg",
                activity_type=ActivityType.GYM,
                duration_minutes=60,
                logged_at=datetime(2026, 6, 12, 12, 0),
            )
        ],
        reminders=[
            ExtractedReminder(title="Påminnelse", remind_at=datetime(2026, 6, 12, 9, 0))
        ],
        confidence=0.6,
    )


# ---------------------------------------------------------------------------
# build_confirmation_proposal
# ---------------------------------------------------------------------------

def test_build_proposal_counts_saveable_items():
    proposal = build_confirmation_proposal(_full_result())
    assert proposal.saveable_count == 4
    assert proposal.skipped_count == 0
    assert proposal.extraction.confidence == 0.6


def test_build_proposal_flags_incomplete_items():
    result = ExtractionResult(
        tasks=[ExtractedTask(title="   ")],  # blank title
        events=[ExtractedEvent(title="No time")],  # missing start_time
        reminders=[ExtractedReminder(title="No when")],  # missing remind_at
    )
    proposal = build_confirmation_proposal(result)
    assert proposal.saveable_count == 0
    assert proposal.skipped_count == 3


def test_build_proposal_does_not_write(db_path):
    build_confirmation_proposal(_full_result())
    assert list_tasks(db_path) == []
    assert list_events(db_path) == []
    assert list_activities(db_path) == []
    assert list_reminders(status=None, db_path=db_path) == []


# ---------------------------------------------------------------------------
# save_confirmed_extraction
# ---------------------------------------------------------------------------

def test_save_requires_confirmation():
    with pytest.raises(PermissionError):
        save_confirmed_extraction(_full_result(), confirmed=False)


def test_save_persists_all_item_types(db_path):
    result = save_confirmed_extraction(_full_result(), confirmed=True, db_path=db_path)
    assert result.saved_count == 4
    assert result.skipped_count == 0

    assert len(list_tasks(db_path)) == 1
    assert len(list_events(db_path)) == 1
    assert len(list_activities(db_path)) == 1
    assert len(list_reminders(status=None, db_path=db_path)) == 1


def test_save_preserves_activity_logged_at_and_duration(db_path):
    save_confirmed_extraction(_full_result(), confirmed=True, db_path=db_path)
    activities = list_activities(db_path)
    assert activities[0].duration_minutes == 60
    assert activities[0].logged_at == datetime(2026, 6, 12, 12, 0)


def test_save_skips_incomplete_items_with_reason(db_path):
    result = ExtractionResult(
        tasks=[ExtractedTask(title="Valid task")],
        events=[ExtractedEvent(title="No start time")],
        reminders=[ExtractedReminder(title="No remind_at")],
    )
    save_result = save_confirmed_extraction(result, confirmed=True, db_path=db_path)

    assert save_result.saved_count == 1
    assert save_result.skipped_count == 2
    reasons = {s.reason for s in save_result.skipped}
    assert "missing start_time" in reasons
    assert "missing remind_at" in reasons

    # Only the valid task should be persisted.
    assert len(list_tasks(db_path)) == 1
    assert list_events(db_path) == []
    assert list_reminders(status=None, db_path=db_path) == []


def test_save_empty_result_saves_nothing(db_path):
    save_result = save_confirmed_extraction(
        ExtractionResult(), confirmed=True, db_path=db_path
    )
    assert save_result.saved_count == 0
    assert save_result.skipped_count == 0
