"""Manual eval set for the conversation agent.

Run this by hand whenever the prompt or the tool set changes, and read the
output with your own eyes — the point is the wording and the judgement, not a
pass/fail number.  The expected-tool column only tells you where to look first.

    .venv/bin/python evals/agent_eval.py

It calls the configured model for real, and it costs a few cents.  It never
touches your database: every case runs against a temporary one seeded below,
with a fixed reference date, so the same sentence gives a comparable answer
today and next month.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from life_agent.agent.conversation import ConversationAgent  # noqa: E402
from life_agent.db.repositories import (  # noqa: E402
    create_activity,
    create_event,
    create_task,
)
from life_agent.db.schema import init_db  # noqa: E402
from life_agent.models import ActivityLog, CalendarEvent, Task  # noqa: E402
from life_agent.models.common import ActivityStatus, ActivityType  # noqa: E402

TODAY = date(2026, 9, 6)
TOMORROW = date(2026, 9, 7)

# Each case is (turns, expected_tool_of_the_last_turn, what you are looking at).
CASES: list[tuple[list[str], str | None, str]] = [
    (
        ["Jag har möte på Odenplan kl 12 imorgon, behöver plugga machine "
         "learning, handla mat och träna på kvällen."],
        "save_extracted_items",
        "Four items: the meeting keeps 12:00 and Odenplan; the rest sort sensibly.",
    ),
    (
        ["Kan du hjälpa mig spara ryggpasset imorgon kl 18"],
        "save_extracted_items",
        "Saves without asking about optional fields; 18:00 on the 7th.",
    ),
    (
        ["Lämna grabben på förskolan kl 09:30 imorgon"],
        "save_extracted_items",
        "An event at 09:30 — a clock time must never become a dateless task.",
    ),
    (
        ["Jag vill att du påminner mig om att träna imorgon, jag ska köra rygg"],
        "ask_clarifying_question",
        "No time given, so it asks rather than inventing midnight.",
    ),
    (
        ["påminn mig att handla mat imorgon kl 10"],
        "save_extracted_items",
        "The time is there, so it saves without asking.",
    ),
    (
        ["vad har jag idag?"],
        "list_day",
        "list_day with 2026-09-06, and the reply answers rather than announces.",
    ),
    (
        ["Vad har jag på agendan imorgon?"],
        "list_day",
        "list_day with 2026-09-07 — never today's schedule for tomorrow's question.",
    ),
    (
        ["vad har jag idag?", "och imorgon då?"],
        "list_day",
        "The follow-up resolves to the 7th from conversation history alone.",
    ),
    (
        ["hur mycket har jag tränat den senaste veckan?"],
        "list_range",
        "A count in the reply, not a table for the reader to add up.",
    ),
    (
        ["När ska jag träna imorgon?"],
        "list_day",
        "Answers with the actual time from the data, or says it is not there.",
    ),
    (
        ["jag har tränat klart"],
        "complete_activity",
        "Proposes completion; must not claim it is already done.",
    ),
    (
        ["flytta ryggpasset imorgon till 08:00"],
        "reschedule_item",
        "Resolves 'ryggpasset' to the saved 'Träna rygg' despite the inflection.",
    ),
    (
        ["ta bort studietiden"],
        "delete_item",
        "Resolves and proposes; nothing is removed without confirmation.",
    ),
    (
        ["vad har jag idag?",
         "okej, så jag ska alltså träna idag, sen har jag inte något planerat "
         "för resten av dagen? Tänker att kl 12:00-14:00 blir pluggtid. "
         "och imorgon då?"],
        "save_extracted_items",
        "Saves only the study block — the training is the user reading back "
        "the agenda — and says it will look up tomorrow next.",
    ),
    (
        ["hej, hur funkar du egentligen?"],
        None,
        "Plain conversation, no tool, no invented capabilities.",
    ),
]


def seed(db_path: str) -> None:
    """A small, fixed world: one training today, one tomorrow, one study block."""
    init_db(db_path)
    create_activity(
        ActivityLog(
            title="Träna rygg",
            activity_type=ActivityType.GYM,
            status=ActivityStatus.PLANNED,
            logged_at=datetime(2026, 9, 6, 11, 0),
            duration_minutes=60,
        ),
        db_path,
    )
    create_activity(
        ActivityLog(
            title="Träna rygg",
            activity_type=ActivityType.GYM,
            status=ActivityStatus.PLANNED,
            logged_at=datetime(2026, 9, 7, 10, 0),
            duration_minutes=60,
        ),
        db_path,
    )
    create_event(
        CalendarEvent(
            title="Studietid",
            start_time=datetime(2026, 9, 6, 12, 0),
            end_time=datetime(2026, 9, 6, 14, 0),
        ),
        db_path,
    )
    create_task(Task(title="Handla mat", due_date=TOMORROW), db_path)


def describe(turn) -> list[str]:
    lines = [f"    reply: {turn.reply}"]
    if turn.extraction is not None:
        for e in turn.extraction.events:
            lines.append(f"    EVENT    {e.title!r} {e.start_time} loc={e.location!r}")
        for t in turn.extraction.tasks:
            lines.append(f"    TASK     {t.title!r} due={t.due_date}")
        for a in turn.extraction.activities:
            lines.append(f"    ACTIVITY {a.title!r} at={a.logged_at}")
        for r in turn.extraction.reminders:
            lines.append(f"    REMINDER {r.title!r} at={r.remind_at}")
    if turn.data.get("match"):
        lines.append(f"    matched: {turn.data['match'].describe()}")
    if turn.data.get("new_time"):
        lines.append(f"    new time: {turn.data['new_time']}")
    if turn.text:
        lines.append("    " + turn.text.replace("\n", "\n    "))
    return lines


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "eval.db")
        seed(db_path)

        probe = ConversationAgent(db_path=db_path, reference_date=TODAY)
        if probe._get_client() is None:
            print("No LLM configured. Set LIFE_AGENT_LLM_* in .env first.")
            return 1

        agreed = 0
        for turns, expected, looking_for in CASES:
            agent = ConversationAgent(db_path=db_path, reference_date=TODAY)
            for message in turns:
                turn = agent.send(message)

            actual = turn.decision.tool_name
            ok = actual == expected
            agreed += ok
            mark = "  " if ok else "!!"

            print(f"{mark} {' / '.join(turns)}")
            print(f"    looking for: {looking_for}")
            print(f"    tool: {actual}  (expected {expected})  kind={turn.kind}")
            print("\n".join(describe(turn)))
            print()

        print(f"{agreed}/{len(CASES)} cases picked the expected tool.")
        print("The tool column is a hint. Read the replies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
