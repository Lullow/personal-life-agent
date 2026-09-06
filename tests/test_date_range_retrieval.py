"""Tests for date-range retrieval: repositories, planner, and read tools.

These cover the gap the first real agent session exposed — a training session
saved for tomorrow was invisible in every view the agent could reach.
"""

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from life_agent.db.repositories import (
    create_activity,
    create_event,
    create_task,
    list_activities,
    list_events,
    list_tasks,
)
from life_agent.db.schema import init_db
from life_agent.models import ActivityLog, CalendarEvent, Task
from life_agent.models.common import ActivityStatus, ActivityType
from life_agent.services.chat_service import get_day_response, get_range_response
from life_agent.services.planner_service import get_day_agenda, get_range_agenda

MARCH = date(2026, 3, 15)
JUNE = date(2026, 6, 11)


@pytest.fixture()
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "ranges.db")
        init_db(path)
        yield path


def _event(db_path, title: str, when: datetime) -> None:
    create_event(CalendarEvent(title=title, start_time=when), db_path)


def _activity(db_path, title: str, when: datetime, status=ActivityStatus.PLANNED) -> None:
    create_activity(
        ActivityLog(
            title=title,
            activity_type=ActivityType.GYM,
            status=status,
            logged_at=when,
        ),
        db_path,
    )


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


class TestRepositoryRanges:
    def test_events_are_bounded_by_whole_days(self, db_path):
        _event(db_path, "Late on the first", datetime(2026, 3, 1, 23, 30))
        _event(db_path, "Early on the last", datetime(2026, 3, 31, 0, 15))
        _event(db_path, "February", datetime(2026, 2, 28, 12, 0))
        _event(db_path, "April", datetime(2026, 4, 1, 8, 0))

        titles = [
            e.title
            for e in list_events(db_path, start=date(2026, 3, 1), end=date(2026, 3, 31))
        ]

        assert titles == ["Late on the first", "Early on the last"]

    def test_activities_are_bounded_by_whole_days(self, db_path):
        _activity(db_path, "March session", datetime(2026, 3, 15, 18, 0))
        _activity(db_path, "April session", datetime(2026, 4, 2, 18, 0))

        found = list_activities(
            db_path=db_path, start=date(2026, 3, 1), end=date(2026, 3, 31)
        )

        assert [a.title for a in found] == ["March session"]

    def test_activity_range_combines_with_status(self, db_path):
        _activity(db_path, "Planned", datetime(2026, 3, 15, 18, 0))
        _activity(
            db_path, "Done", datetime(2026, 3, 16, 18, 0), status=ActivityStatus.COMPLETED
        )

        found = list_activities(
            status=str(ActivityStatus.PLANNED),
            db_path=db_path,
            start=date(2026, 3, 1),
            end=date(2026, 3, 31),
        )

        assert [a.title for a in found] == ["Planned"]

    def test_tasks_bounded_by_due_date(self, db_path):
        create_task(Task(title="Due in range", due_date=date(2026, 3, 10)), db_path)
        create_task(Task(title="Due later", due_date=date(2026, 5, 10)), db_path)
        create_task(Task(title="No due date"), db_path)

        titles = [
            t.title
            for t in list_tasks(
                db_path, due_from=date(2026, 3, 1), due_to=date(2026, 3, 31)
            )
        ]

        assert titles == ["Due in range"]

    def test_unfiltered_calls_are_unchanged(self, db_path):
        _event(db_path, "Whenever", datetime(2026, 3, 1, 9, 0))
        create_task(Task(title="Someday"), db_path)
        _activity(db_path, "Session", datetime(2026, 3, 1, 18, 0))

        assert len(list_events(db_path)) == 1
        assert len(list_tasks(db_path)) == 1
        assert len(list_activities(db_path=db_path)) == 1


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class TestDayAgenda:
    def test_activities_appear_on_the_day_they_belong_to(self, db_path):
        _activity(db_path, "Träna rygg", datetime(2026, 6, 12, 18, 0))

        assert get_day_agenda(JUNE, db_path).activities == []
        tomorrow = get_day_agenda(date(2026, 6, 12), db_path)
        assert [a.title for a in tomorrow.activities] == ["Träna rygg"]

    def test_activities_are_ordered_by_time(self, db_path):
        _activity(db_path, "Evening", datetime(2026, 6, 11, 18, 0))
        _activity(db_path, "Morning", datetime(2026, 6, 11, 7, 0))

        assert [a.title for a in get_day_agenda(JUNE, db_path).activities] == [
            "Morning",
            "Evening",
        ]

    def test_a_day_with_only_an_activity_is_not_empty(self, db_path):
        _activity(db_path, "Träna rygg", datetime(2026, 6, 11, 18, 0))

        assert "Nothing on the agenda" not in get_day_response(JUNE, db_path)
        assert "Träna rygg" in get_day_response(JUNE, db_path)


class TestRangeAgenda:
    def test_range_covers_every_day_inclusive(self, db_path):
        agenda = get_range_agenda(date(2026, 3, 1), date(2026, 3, 31), db_path)

        assert len(agenda.days) == 31
        assert agenda.days[0].date == date(2026, 3, 1)
        assert agenda.days[-1].date == date(2026, 3, 31)

    def test_range_reaches_back_into_history(self, db_path):
        _activity(db_path, "March session", datetime(2026, 3, 15, 18, 0))

        text = get_range_response(date(2026, 3, 1), date(2026, 3, 31), db_path)

        assert "March session" in text

    def test_range_excludes_what_falls_outside(self, db_path):
        _event(db_path, "April meeting", datetime(2026, 4, 2, 9, 0))

        text = get_range_response(date(2026, 3, 1), date(2026, 3, 31), db_path)

        assert "April meeting" not in text
        assert "Nothing scheduled" in text

    def test_backwards_range_is_rejected(self, db_path):
        with pytest.raises(ValueError):
            get_range_agenda(date(2026, 3, 31), date(2026, 3, 1), db_path)

    def test_week_agenda_is_a_seven_day_range(self, db_path):
        from life_agent.services.planner_service import get_week_agenda

        agenda = get_week_agenda(JUNE, db_path=db_path)

        assert agenda.start_date == JUNE
        assert agenda.end_date == JUNE + timedelta(days=6)
        assert len(agenda.days) == 7
