"""Confirmation flow for natural-language add.

This service turns an :class:`ExtractionResult` into a human-readable proposal
and — only when explicitly authorised — persists the extracted items via the
existing services.  It enforces the project safety rule that natural language
must never write to the database without explicit confirmation.
"""

from life_agent.agent.safety import assert_confirmed
from life_agent.models.common import (
    ActivityStatus,
    ActivityType,
    EventCategory,
    Priority,
    ReminderTargetType,
    TaskCategory,
)
from life_agent.schemas.confirmation import (
    ConfirmationProposal,
    ConfirmationSaveResult,
    SavedItemSummary,
)
from life_agent.schemas.extraction import ExtractionResult
from life_agent.services.activity_service import add_activity
from life_agent.services.event_service import add_event
from life_agent.services.reminder_service import add_reminder
from life_agent.services.task_service import add_task


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def _count_saveable(result: ExtractionResult) -> tuple[int, int]:
    """Return (saveable, skipped) counts without saving anything."""
    saveable = 0
    skipped = 0

    for task in result.tasks:
        if _has_text(task.title):
            saveable += 1
        else:
            skipped += 1

    for event in result.events:
        if _has_text(event.title) and event.start_time is not None:
            saveable += 1
        else:
            skipped += 1

    for activity in result.activities:
        if _has_text(activity.title):
            saveable += 1
        else:
            skipped += 1

    for reminder in result.reminders:
        if _has_text(reminder.title) and reminder.remind_at is not None:
            saveable += 1
        else:
            skipped += 1

    return saveable, skipped


def build_confirmation_proposal(result: ExtractionResult) -> ConfirmationProposal:
    """Build a read-only proposal describing what would be saved."""
    saveable, skipped = _count_saveable(result)
    return ConfirmationProposal(
        extraction=result,
        saveable_count=saveable,
        skipped_count=skipped,
    )


def save_confirmed_extraction(
    result: ExtractionResult,
    confirmed: bool = True,
    db_path: str | None = None,
) -> ConfirmationSaveResult:
    """Persist extracted items, but only when *confirmed* is True.

    Items missing required fields are skipped with a useful reason rather than
    raising.  Calling this without confirmation raises ``PermissionError`` to
    enforce the safety rule.
    """
    assert_confirmed(confirmed)

    saved: list[SavedItemSummary] = []
    skipped: list[SavedItemSummary] = []

    # --- Tasks -----------------------------------------------------------
    for task in result.tasks:
        title = (task.title or "").strip()
        if not title:
            skipped.append(
                SavedItemSummary(
                    item_type="task",
                    title="(untitled)",
                    saved=False,
                    reason="missing title",
                )
            )
            continue
        add_task(
            title=title,
            due_date=task.due_date,
            priority=task.priority or Priority.MEDIUM,
            category=task.category or TaskCategory.OTHER,
            estimated_minutes=task.estimated_minutes,
            db_path=db_path,
        )
        saved.append(SavedItemSummary(item_type="task", title=title, saved=True))

    # --- Events ----------------------------------------------------------
    for event in result.events:
        title = (event.title or "").strip()
        if not title:
            skipped.append(
                SavedItemSummary(
                    item_type="event",
                    title="(untitled)",
                    saved=False,
                    reason="missing title",
                )
            )
            continue
        if event.start_time is None:
            skipped.append(
                SavedItemSummary(
                    item_type="event",
                    title=title,
                    saved=False,
                    reason="missing start_time",
                )
            )
            continue
        add_event(
            title=title,
            start_time=event.start_time,
            end_time=event.end_time,
            location=event.location,
            category=event.category or EventCategory.OTHER,
            db_path=db_path,
        )
        saved.append(SavedItemSummary(item_type="event", title=title, saved=True))

    # --- Activities ------------------------------------------------------
    for activity in result.activities:
        title = (activity.title or "").strip()
        if not title:
            skipped.append(
                SavedItemSummary(
                    item_type="activity",
                    title="(untitled)",
                    saved=False,
                    reason="missing title",
                )
            )
            continue
        add_activity(
            title=title,
            activity_type=activity.activity_type or ActivityType.OTHER,
            duration_minutes=activity.duration_minutes,
            notes=activity.notes,
            logged_at=activity.logged_at,
            status=ActivityStatus.PLANNED,
            db_path=db_path,
        )
        saved.append(SavedItemSummary(item_type="activity", title=title, saved=True))

    # --- Reminders -------------------------------------------------------
    for reminder in result.reminders:
        title = (reminder.title or "").strip()
        if not title:
            skipped.append(
                SavedItemSummary(
                    item_type="reminder",
                    title="(untitled)",
                    saved=False,
                    reason="missing title",
                )
            )
            continue
        if reminder.remind_at is None:
            skipped.append(
                SavedItemSummary(
                    item_type="reminder",
                    title=title,
                    saved=False,
                    reason="missing remind_at",
                )
            )
            continue
        add_reminder(
            title=title,
            remind_at=reminder.remind_at,
            target_type=reminder.target_type or ReminderTargetType.GENERAL,
            message=reminder.notes,
            db_path=db_path,
        )
        saved.append(
            SavedItemSummary(item_type="reminder", title=title, saved=True)
        )

    return ConfirmationSaveResult(saved=saved, skipped=skipped)
