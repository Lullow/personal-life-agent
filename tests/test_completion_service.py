"""Tests for the activity completion service."""

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from life_agent.db.repositories import create_activity, get_activity
from life_agent.db.schema import init_db
from life_agent.models import ActivityLog
from life_agent.models.common import ActivityStatus, ActivityType
from life_agent.services.completion_service import (
    complete_activity,
    find_completion_candidate,
    is_completion_phrase,
)


@pytest.fixture()
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "completion.db")
        init_db(path)
        yield path


def _planned(title, when, activity_type=ActivityType.GYM):
    return ActivityLog(
        title=title,
        activity_type=activity_type,
        status=ActivityStatus.PLANNED,
        logged_at=when,
    )


# ---------------------------------------------------------------------------
# Phrase detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "phrase",
    [
        "Jag har tränat klart",
        "träningen är klar",
        "klar med träningen",
        "Jag har tränat",
    ],
)
def test_is_completion_phrase_true(phrase):
    assert is_completion_phrase(phrase) is True


@pytest.mark.parametrize(
    "phrase",
    [
        "Jag ska träna rygg kl 12 imorgon",
        "Möte på Odenplan kl 14",
        "",
    ],
)
def test_is_completion_phrase_false(phrase):
    assert is_completion_phrase(phrase) is False


# ---------------------------------------------------------------------------
# Candidate matching
# ---------------------------------------------------------------------------

def test_finds_planned_activity_today(db_path):
    today = date(2026, 6, 11)
    create_activity(_planned("Träna rygg", datetime(2026, 6, 11, 12, 0)), db_path)

    candidate = find_completion_candidate(
        "Jag har tränat klart", reference_date=today, db_path=db_path
    )
    assert candidate is not None
    assert candidate.title == "Träna rygg"


def test_prefers_today_over_window(db_path):
    today = date(2026, 6, 11)
    create_activity(_planned("Yesterday gym", datetime(2026, 6, 10, 12, 0)), db_path)
    create_activity(_planned("Today gym", datetime(2026, 6, 11, 12, 0)), db_path)

    candidate = find_completion_candidate(
        "Jag har tränat klart", reference_date=today, db_path=db_path
    )
    assert candidate is not None
    assert candidate.title == "Today gym"


def test_falls_back_to_window_when_nothing_today(db_path):
    today = date(2026, 6, 11)
    create_activity(_planned("Tomorrow gym", datetime(2026, 6, 12, 9, 0)), db_path)

    candidate = find_completion_candidate(
        "Jag har tränat klart", reference_date=today, db_path=db_path
    )
    assert candidate is not None
    assert candidate.title == "Tomorrow gym"


def test_ignores_activities_outside_window(db_path):
    today = date(2026, 6, 11)
    create_activity(_planned("Far away", datetime(2026, 6, 20, 9, 0)), db_path)

    candidate = find_completion_candidate(
        "Jag har tränat klart", reference_date=today, db_path=db_path
    )
    assert candidate is None


def test_no_planned_activity_returns_none(db_path):
    today = date(2026, 6, 11)
    # Completed activity should not be a candidate.
    create_activity(
        ActivityLog(
            title="Already done",
            status=ActivityStatus.COMPLETED,
            logged_at=datetime(2026, 6, 11, 12, 0),
        ),
        db_path,
    )
    candidate = find_completion_candidate(
        "Jag har tränat klart", reference_date=today, db_path=db_path
    )
    assert candidate is None


def test_type_hint_prefers_matching_activity(db_path):
    today = date(2026, 6, 11)
    create_activity(
        _planned("Morning run", datetime(2026, 6, 11, 8, 0), ActivityType.RUN), db_path
    )
    gym = create_activity(
        _planned("Gym session", datetime(2026, 6, 11, 18, 0), ActivityType.GYM), db_path
    )

    candidate = find_completion_candidate(
        "Jag har tränat klart", reference_date=today, db_path=db_path
    )
    assert candidate is not None
    assert candidate.id == gym.id


# ---------------------------------------------------------------------------
# Completing
# ---------------------------------------------------------------------------

def test_complete_activity_requires_confirmation(db_path):
    saved = create_activity(_planned("Träna", datetime(2026, 6, 11, 12, 0)), db_path)
    with pytest.raises(PermissionError):
        complete_activity(saved.id, confirmed=False, db_path=db_path)
    # Status unchanged.
    assert get_activity(saved.id, db_path).status == ActivityStatus.PLANNED


def test_complete_activity_marks_completed(db_path):
    saved = create_activity(_planned("Träna", datetime(2026, 6, 11, 12, 0)), db_path)
    updated = complete_activity(saved.id, confirmed=True, db_path=db_path)
    assert updated is not None
    assert updated.status == ActivityStatus.COMPLETED
    assert get_activity(saved.id, db_path).status == ActivityStatus.COMPLETED
