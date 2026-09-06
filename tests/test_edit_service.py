"""Tests for resolving, rescheduling, and deleting saved items."""

import tempfile
from datetime import date, datetime
from pathlib import Path

import pytest

from life_agent.db.repositories import (
    create_activity,
    create_event,
    create_reminder,
    create_task,
    list_events,
    list_tasks,
)
from life_agent.db.schema import init_db
from life_agent.models import ActivityLog, CalendarEvent, Reminder, Task
from life_agent.models.common import ActivityType
from life_agent.services.edit_service import (
    delete_item,
    find_items,
    reschedule_item,
)


@pytest.fixture()
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "edit.db")
        init_db(path)
        yield path


@pytest.fixture()
def seeded(db_path):
    create_event(
        CalendarEvent(
            title="Lämna grabben på förskolan",
            start_time=datetime(2026, 9, 7, 9, 30),
        ),
        db_path,
    )
    create_task(Task(title="Lämna grabben på förskolan", due_date=date(2026, 9, 7)), db_path)
    create_activity(
        ActivityLog(
            title="Träna rygg",
            activity_type=ActivityType.GYM,
            logged_at=datetime(2026, 9, 7, 10, 0),
        ),
        db_path,
    )
    create_reminder(
        Reminder(title="Handla mat", remind_at=datetime(2026, 9, 8, 10, 0)), db_path
    )
    return db_path


class TestFinding:
    def test_matches_part_of_a_title_case_insensitively(self, seeded):
        assert len(find_items("GRABBEN", db_path=seeded)) == 2

    def test_narrows_by_item_type(self, seeded):
        found = find_items("grabben", item_type="event", db_path=seeded)

        assert [m.item_type for m in found] == ["event"]
        assert found[0].when == datetime(2026, 9, 7, 9, 30)

    def test_narrows_by_day_when_the_day_matches(self, seeded):
        create_task(Task(title="Handla mat", due_date=date(2026, 9, 9)), seeded)

        found = find_items("handla", day=date(2026, 9, 8), db_path=seeded)

        assert [m.item_type for m in found] == ["reminder"]

    def test_a_wrong_day_is_dropped_rather_than_returning_nothing(self, seeded):
        """The agent guesses the day too, and a wrong guess must not hide a row."""
        found = find_items("handla", day=date(2026, 9, 7), db_path=seeded)

        assert [m.title for m in found] == ["Handla mat"]
        assert found[0].day == date(2026, 9, 8)

    def test_a_wrong_kind_is_dropped_too(self, seeded):
        found = find_items("handla", item_type="activity", db_path=seeded)

        assert [m.item_type for m in found] == ["reminder"]

    def test_finds_across_all_four_kinds(self, seeded):
        kinds = {m.item_type for m in find_items(item_type=None, title="", db_path=seeded) or []}
        # An empty description matches nothing on purpose.
        assert kinds == set()
        assert {m.item_type for m in find_items("a", db_path=seeded)} >= {
            "event",
            "task",
            "activity",
            "reminder",
        }

    def test_an_empty_description_matches_nothing(self, seeded):
        assert find_items(db_path=seeded) == []
        assert find_items("   ", db_path=seeded) == []

    def test_describe_names_the_kind_and_the_time(self, seeded):
        match = find_items("grabben", item_type="event", db_path=seeded)[0]

        assert match.describe() == (
            "event: Lämna grabben på förskolan (2026-09-07 09:30)"
        )


class TestChanging:
    def test_reschedule_moves_an_event(self, seeded):
        match = find_items("grabben", item_type="event", db_path=seeded)[0]

        reschedule_item(match, datetime(2026, 9, 7, 8, 45), db_path=seeded)

        moved = [e for e in list_events(seeded) if e.id == match.item_id][0]
        assert moved.start_time == datetime(2026, 9, 7, 8, 45)

    def test_reschedule_a_task_keeps_only_the_date(self, seeded):
        match = find_items("grabben", item_type="task", db_path=seeded)[0]

        reschedule_item(match, datetime(2026, 9, 9, 8, 45), db_path=seeded)

        moved = [t for t in list_tasks(seeded) if t.id == match.item_id][0]
        assert moved.due_date == date(2026, 9, 9)

    def test_delete_removes_only_the_matched_row(self, seeded):
        match = find_items("grabben", item_type="task", db_path=seeded)[0]

        assert delete_item(match, db_path=seeded) is True

        assert list_tasks(seeded) == []
        assert len(list_events(seeded)) == 1

    def test_deleting_twice_reports_the_second_as_a_miss(self, seeded):
        match = find_items("grabben", item_type="task", db_path=seeded)[0]
        delete_item(match, db_path=seeded)

        assert delete_item(match, db_path=seeded) is False


class TestConfirmationIsRequired:
    def test_delete_without_confirmation_raises(self, seeded):
        match = find_items("grabben", item_type="task", db_path=seeded)[0]

        with pytest.raises(PermissionError):
            delete_item(match, confirmed=False, db_path=seeded)

        assert len(list_tasks(seeded)) == 1

    def test_reschedule_without_confirmation_raises(self, seeded):
        match = find_items("grabben", item_type="event", db_path=seeded)[0]

        with pytest.raises(PermissionError):
            reschedule_item(
                match, datetime(2026, 9, 7, 8, 45), confirmed=False, db_path=seeded
            )

        assert list_events(seeded)[0].start_time == datetime(2026, 9, 7, 9, 30)


class TestInflectedDescriptions:
    """The agent says what the user said; the titles are written differently."""

    @pytest.mark.parametrize(
        "description",
        ["lämningen", "Lämningen på förskolan", "lämna grabben"],
    )
    def test_finds_the_dropoff(self, seeded, description):
        assert find_items(description, item_type="event", db_path=seeded)

    @pytest.mark.parametrize("description", ["ryggpasset", "rygg", "träna rygg"])
    def test_finds_the_training(self, seeded, description):
        found = find_items(description, item_type="activity", db_path=seeded)

        assert [m.title for m in found] == ["Träna rygg"]

    def test_unrelated_words_still_miss(self, seeded):
        assert find_items("tandläkaren", db_path=seeded) == []

    def test_the_best_match_wins_over_a_weaker_one(self, seeded):
        create_activity(
            ActivityLog(
                title="Träna biceps",
                activity_type=ActivityType.GYM,
                logged_at=datetime(2026, 9, 9, 11, 0),
            ),
            seeded,
        )

        found = find_items("träna rygg", item_type="activity", db_path=seeded)

        assert [m.title for m in found] == ["Träna rygg"]

    def test_a_genuinely_ambiguous_word_returns_both(self, seeded):
        create_activity(
            ActivityLog(
                title="Träna biceps",
                activity_type=ActivityType.GYM,
                logged_at=datetime(2026, 9, 9, 11, 0),
            ),
            seeded,
        )

        found = find_items("träna", item_type="activity", db_path=seeded)

        assert {m.title for m in found} == {"Träna rygg", "Träna biceps"}
