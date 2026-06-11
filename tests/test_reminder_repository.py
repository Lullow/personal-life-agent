"""Tests for the reminder repository."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from life_agent.db.repositories import (
    create_reminder,
    get_reminder,
    list_reminders,
    list_upcoming_reminders,
    update_reminder_status,
)
from life_agent.db.schema import init_db
from life_agent.models import Reminder
from life_agent.models.common import ReminderStatus, ReminderTargetType


@pytest.fixture()
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "reminders.db")
        init_db(path)
        yield path


def test_create_reminder_assigns_integer_id(db_path):
    reminder = Reminder(title="Träna", remind_at=datetime(2026, 6, 15, 9, 0))
    saved = create_reminder(reminder, db_path)
    assert isinstance(saved.id, int)
    assert saved.id >= 1
    assert saved.title == "Träna"
    assert saved.status == ReminderStatus.PENDING
    assert saved.target_type == ReminderTargetType.GENERAL


def test_create_reminder_assigns_sequential_ids(db_path):
    first = create_reminder(
        Reminder(title="First", remind_at=datetime(2026, 6, 15, 9, 0)), db_path
    )
    second = create_reminder(
        Reminder(title="Second", remind_at=datetime(2026, 6, 16, 9, 0)), db_path
    )
    assert second.id == first.id + 1


def test_list_reminders_sorted_by_remind_at(db_path):
    create_reminder(
        Reminder(title="Latest", remind_at=datetime(2026, 6, 20, 12, 0)), db_path
    )
    create_reminder(
        Reminder(title="Earliest", remind_at=datetime(2026, 6, 15, 8, 0)), db_path
    )
    create_reminder(
        Reminder(title="Middle", remind_at=datetime(2026, 6, 17, 18, 0)), db_path
    )

    titles = [r.title for r in list_reminders(db_path=db_path)]
    assert titles == ["Earliest", "Middle", "Latest"]


def test_list_reminders_filtered_by_status(db_path):
    pending = create_reminder(
        Reminder(title="Pending one", remind_at=datetime(2026, 6, 15, 9, 0)),
        db_path,
    )
    dismissed = create_reminder(
        Reminder(title="Dismissed one", remind_at=datetime(2026, 6, 15, 10, 0)),
        db_path,
    )
    update_reminder_status(dismissed.id, str(ReminderStatus.DISMISSED), db_path)

    pending_only = list_reminders(status=str(ReminderStatus.PENDING), db_path=db_path)
    dismissed_only = list_reminders(
        status=str(ReminderStatus.DISMISSED), db_path=db_path
    )

    assert [r.id for r in pending_only] == [pending.id]
    assert [r.id for r in dismissed_only] == [dismissed.id]


def test_list_upcoming_reminders_only_returns_pending(db_path):
    a = create_reminder(
        Reminder(title="A", remind_at=datetime(2026, 6, 15, 9, 0)), db_path
    )
    b = create_reminder(
        Reminder(title="B", remind_at=datetime(2026, 6, 16, 9, 0)), db_path
    )
    update_reminder_status(b.id, str(ReminderStatus.DISMISSED), db_path)

    upcoming = list_upcoming_reminders(db_path)
    assert [r.id for r in upcoming] == [a.id]


def test_update_reminder_status_changes_status(db_path):
    saved = create_reminder(
        Reminder(title="To dismiss", remind_at=datetime(2026, 6, 15, 9, 0)),
        db_path,
    )
    updated = update_reminder_status(
        saved.id, str(ReminderStatus.DISMISSED), db_path
    )
    assert updated is not None
    assert updated.status == ReminderStatus.DISMISSED


def test_update_reminder_status_returns_none_for_missing(db_path):
    assert update_reminder_status(9999, str(ReminderStatus.DISMISSED), db_path) is None


def test_get_reminder_roundtrip_preserves_fields(db_path):
    saved = create_reminder(
        Reminder(
            title="Doctor",
            remind_at=datetime(2026, 6, 15, 9, 30),
            target_type=ReminderTargetType.EVENT,
            target_id=42,
            message="Bring papers",
        ),
        db_path,
    )
    fetched = get_reminder(saved.id, db_path)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.title == "Doctor"
    assert fetched.message == "Bring papers"
    assert fetched.target_type == ReminderTargetType.EVENT
    assert fetched.target_id == 42
    assert fetched.remind_at == datetime(2026, 6, 15, 9, 30)
