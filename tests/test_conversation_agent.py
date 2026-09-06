"""Tests for the LLM-first conversation loop.

No network: every test drives :class:`ConversationAgent` with a fake client
that returns a canned JSON payload.  What is asserted is the part the model is
not trusted with — tool validation, confirmation flags, and the fact that a
proposal never touches the database on its own.
"""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from life_agent.agent.conversation import (
    AMBIGUOUS_TEXT,
    BAD_ARGUMENTS_TEXT,
    BAD_DATE_TEXT,
    LLM_UNAVAILABLE_TEXT,
    NOT_FOUND_TEXT,
    ConversationAgent,
)
from life_agent.db.repositories import list_activities, list_events, list_tasks
from life_agent.db.schema import init_db

REF = date(2026, 9, 6)

ODENPLAN = (
    "Jag har möte på Odenplan kl 12 imorgon, behöver plugga machine "
    "learning, handla mat och träna på kvällen."
)

ODENPLAN_PAYLOAD = {
    "tool": "save_extracted_items",
    "arguments": {
        "events": [
            {
                "title": "Möte på Odenplan",
                "category": "meeting",
                "start_time": "2026-09-07T12:00:00",
                "location": "Odenplan",
            }
        ],
        "tasks": [
            {"title": "Plugga machine learning", "category": "study"},
            {"title": "Handla mat", "category": "errand"},
        ],
        "activities": [{"title": "Träna", "activity_type": "gym"}],
    },
    "reply": "Jag har förberett fyra saker, vill du spara dem?",
}


class FakeLLMClient:
    """Returns canned payloads and records what it was asked."""

    def __init__(self, payload=None, payloads=None, error=None):
        self._payloads = list(payloads) if payloads is not None else None
        self._payload = payload
        self._error = error
        self.calls: list[list[dict[str, str]]] = []
        self.system_prompts: list[str] = []

    def chat_json(self, system_prompt, messages):
        self.calls.append(list(messages))
        self.system_prompts.append(system_prompt)
        if self._error is not None:
            raise self._error
        if self._payloads is not None:
            return self._payloads.pop(0) if self._payloads else None
        return self._payload


@pytest.fixture()
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "agent.db")
        init_db(path)
        yield path


def _agent(payload=None, *, db_path=None, payloads=None, error=None, **kwargs):
    return ConversationAgent(
        llm_client=FakeLLMClient(payload=payload, payloads=payloads, error=error),
        db_path=db_path,
        reference_date=REF,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# The target sentence
# ---------------------------------------------------------------------------


class TestSaveProposal:
    def test_planning_message_needs_confirmation(self, db_path):
        turn = _agent(ODENPLAN_PAYLOAD, db_path=db_path).send(ODENPLAN)

        assert turn.kind == "needs_confirmation"
        assert turn.data["flow"] == "save"
        assert turn.proposal.saveable_count == 4
        assert turn.proposal.skipped_count == 0
        assert turn.reply == ODENPLAN_PAYLOAD["reply"]

    def test_arguments_are_parsed_into_the_extraction_schema(self, db_path):
        turn = _agent(ODENPLAN_PAYLOAD, db_path=db_path).send(ODENPLAN)

        event = turn.extraction.events[0]
        assert event.location == "Odenplan"
        assert event.start_time.isoformat() == "2026-09-07T12:00:00"
        assert [t.title for t in turn.extraction.tasks] == [
            "Plugga machine learning",
            "Handla mat",
        ]
        assert turn.extraction.activities[0].title == "Träna"

    def test_proposal_writes_nothing(self, db_path):
        _agent(ODENPLAN_PAYLOAD, db_path=db_path).send(ODENPLAN)

        assert list_events(db_path) == []
        assert list_tasks(db_path) == []
        assert list_activities(db_path) == []

    def test_save_is_always_flagged_for_confirmation(self, db_path):
        """The registry decides, not the model's own JSON."""
        payload = dict(ODENPLAN_PAYLOAD)
        turn = _agent(payload, db_path=db_path).send(ODENPLAN)

        assert turn.decision.tool_name == "save_extracted_items"
        assert turn.decision.action_type == "write"
        assert turn.decision.requires_confirmation is True
        assert turn.decision.is_mutating is True

    def test_nothing_saveable_falls_back_to_a_reply(self, db_path):
        payload = {
            "tool": "save_extracted_items",
            # An event with no start_time cannot be saved.
            "arguments": {"events": [{"title": "Möte"}]},
            "reply": "När är mötet?",
        }
        turn = _agent(payload, db_path=db_path).send("jag har ett möte")

        assert turn.kind == "reply"
        assert turn.proposal.saveable_count == 0

    def test_unparseable_arguments_do_not_crash(self, db_path):
        payload = {
            "tool": "save_extracted_items",
            "arguments": {"tasks": "not a list"},
            "reply": "",
        }
        turn = _agent(payload, db_path=db_path).send("something")

        assert turn.kind == "reply"
        assert turn.reply == BAD_ARGUMENTS_TEXT
        assert list_tasks(db_path) == []


# ---------------------------------------------------------------------------
# Tool validation
# ---------------------------------------------------------------------------


class TestToolValidation:
    def test_hallucinated_tool_is_not_executed(self, db_path):
        payload = {
            "tool": "delete_everything",
            "arguments": {},
            "reply": "Done!",
        }
        turn = _agent(payload, db_path=db_path).send("radera allt")

        assert turn.kind == "reply"
        assert turn.decision.tool_name is None
        assert turn.decision.is_mutating is False

    def test_a_tool_name_that_only_sounds_plausible_is_rejected(self, db_path):
        payload = {"tool": "query_saved_data", "arguments": {}, "reply": "hm"}
        turn = _agent(payload, db_path=db_path).send("vad har jag sparat")

        assert turn.kind == "reply"
        assert turn.decision.tool_name is None

    def test_null_tool_is_plain_conversation(self, db_path):
        payload = {"tool": None, "arguments": {}, "reply": "Hej! Hur är läget?"}
        turn = _agent(payload, db_path=db_path).send("hej")

        assert turn.kind == "reply"
        assert turn.reply == "Hej! Hur är läget?"
        assert turn.decision.tool_name is None

    def test_read_tool_is_dispatched_immediately(self, db_path):
        payload = {"tool": "list_reminders", "arguments": {}, "reply": "Här är de."}
        turn = _agent(payload, db_path=db_path).send("visa mina påminnelser")

        assert turn.kind == "display"
        assert turn.decision.action_type == "read"
        assert turn.decision.requires_confirmation is False
        assert "reminders" in turn.text.lower()

    def test_a_day_assuming_tool_does_not_exist(self, db_path):
        """A tool that picks the day for you is how "imorgon" got today's plan."""
        payload = {"tool": "list_today", "arguments": {}, "reply": "Här är idag."}
        turn = _agent(payload, db_path=db_path).send("vad har jag idag")

        assert turn.kind == "reply"
        assert turn.decision.tool_name is None

    def test_clarifying_question_is_only_a_reply(self, db_path):
        payload = {
            "tool": "ask_clarifying_question",
            "arguments": {},
            "reply": "Vilken tid?",
        }
        turn = _agent(payload, db_path=db_path).send("boka något imorgon")

        assert turn.kind == "reply"
        assert turn.decision.action_type == "clarify"


# ---------------------------------------------------------------------------
# Degradation
# ---------------------------------------------------------------------------


class TestDegradation:
    def test_no_payload_reports_the_model_is_unreachable(self, db_path):
        turn = _agent(None, db_path=db_path).send("hej")

        assert turn.kind == "reply"
        assert turn.reply == LLM_UNAVAILABLE_TEXT

    def test_client_error_is_caught(self, db_path):
        turn = _agent(error=RuntimeError("boom"), db_path=db_path).send("hej")

        assert turn.reply == LLM_UNAVAILABLE_TEXT

    def test_missing_client_is_not_an_error(self, monkeypatch, db_path):
        agent = ConversationAgent(db_path=db_path, reference_date=REF)
        monkeypatch.setattr(agent, "_get_client", lambda: None)

        assert agent.send("hej").reply == LLM_UNAVAILABLE_TEXT

    def test_empty_message_is_ignored(self, db_path):
        agent = _agent(ODENPLAN_PAYLOAD, db_path=db_path)
        turn = agent.send("   ")

        assert turn.kind == "reply"
        assert agent.history == []


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------


class TestHistory:
    def test_turn_is_recorded(self, db_path):
        agent = _agent(
            payloads=[{"tool": None, "arguments": {}, "reply": "Hej!"}],
            db_path=db_path,
        )
        agent.send("hej")

        assert agent.history == [
            {"role": "user", "content": "hej"},
            {"role": "assistant", "content": "Hej!"},
        ]

    def test_history_is_sent_back_to_the_model(self, db_path):
        client = FakeLLMClient(
            payloads=[
                {"tool": None, "arguments": {}, "reply": "Hej!"},
                {"tool": None, "arguments": {}, "reply": "Imorgon då?"},
            ]
        )
        agent = ConversationAgent(
            llm_client=client, db_path=db_path, reference_date=REF
        )
        agent.send("hej")
        agent.send("och imorgon?")

        assert [m["content"] for m in client.calls[1]] == [
            "hej",
            "Hej!",
            "och imorgon?",
        ]

    def test_history_is_capped(self, db_path):
        agent = _agent(
            payloads=[{"tool": None, "arguments": {}, "reply": f"r{i}"} for i in range(6)],
            db_path=db_path,
            max_history_turns=2,
        )
        for i in range(6):
            agent.send(f"m{i}")

        assert len(agent.history) == 4
        assert agent.history[0]["content"] == "m4"

    def test_recorded_outcome_joins_the_history(self, db_path):
        agent = _agent(
            payloads=[{"tool": None, "arguments": {}, "reply": "ok"}], db_path=db_path
        )
        agent.send("hej")
        agent.record_outcome("Saved 4 item(s)")

        assert agent.history[-1] == {
            "role": "assistant",
            "content": "Saved 4 item(s)",
        }


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


def test_system_prompt_carries_the_reference_date(db_path):
    prompt = _agent(db_path=db_path).system_prompt()

    assert "2026-09-06" in prompt
    assert "Sunday" in prompt


# ---------------------------------------------------------------------------
# Date-parameterised read tools
# ---------------------------------------------------------------------------


def _plan_activity(db_path, title, when):
    from life_agent.db.repositories import create_activity
    from life_agent.models import ActivityLog
    from life_agent.models.common import ActivityStatus, ActivityType

    create_activity(
        ActivityLog(
            title=title,
            activity_type=ActivityType.GYM,
            status=ActivityStatus.PLANNED,
            logged_at=when,
        ),
        db_path,
    )


class TestDateReadTools:
    def test_list_day_answers_for_the_requested_day(self, db_path):
        from datetime import datetime

        _plan_activity(db_path, "Träna rygg", datetime(2026, 9, 7, 18, 0))
        payload = {
            "tool": "list_day",
            "arguments": {"date": "2026-09-07"},
            "reply": "Jag kollar imorgon åt dig.",
        }

        turn = _agent(payload, db_path=db_path).send("vad har jag imorgon?")

        assert turn.kind == "display"
        assert turn.decision.tool_name == "list_day"
        assert "2026-09-07" in turn.text
        assert "Träna rygg" in turn.text

    def test_list_day_without_a_date_asks_instead_of_guessing(self, db_path):
        payload = {"tool": "list_day", "arguments": {}, "reply": ""}

        turn = _agent(payload, db_path=db_path).send("vad har jag då?")

        assert turn.kind == "reply"
        assert turn.reply == BAD_DATE_TEXT
        assert turn.decision.tool_name is None

    def test_list_day_with_an_unusable_date_asks_instead_of_guessing(self, db_path):
        payload = {"tool": "list_day", "arguments": {"date": "imorgon"}, "reply": ""}

        turn = _agent(payload, db_path=db_path).send("vad har jag imorgon?")

        assert turn.kind == "reply"
        assert turn.reply == BAD_DATE_TEXT

    def test_list_range_reaches_into_history(self, db_path):
        from datetime import datetime

        _plan_activity(db_path, "Marspass", datetime(2026, 3, 15, 18, 0))
        payload = {
            "tool": "list_range",
            "arguments": {"from": "2026-03-01", "to": "2026-03-31"},
            "reply": "Jag tittar på mars.",
        }

        turn = _agent(payload, db_path=db_path).send("vad gjorde jag i mars?")

        assert turn.kind == "display"
        assert "Marspass" in turn.text

    def test_list_range_with_one_bound_covers_that_single_day(self, db_path):
        payload = {
            "tool": "list_range",
            "arguments": {"from": "2026-03-15"},
            "reply": "Jag kollar.",
        }

        turn = _agent(payload, db_path=db_path).send("vad hände den 15:e mars?")

        assert turn.kind == "display"
        assert "2026-03-15 -> 2026-03-15" in turn.text

    def test_list_range_survives_reversed_bounds(self, db_path):
        payload = {
            "tool": "list_range",
            "arguments": {"from": "2026-03-31", "to": "2026-03-01"},
            "reply": "Jag kollar.",
        }

        turn = _agent(payload, db_path=db_path).send("mars?")

        assert turn.kind == "display"
        assert "2026-03-01 -> 2026-03-31" in turn.text


# ---------------------------------------------------------------------------
# Answering from retrieved data (the second call on a read)
# ---------------------------------------------------------------------------


class TestReadAnswers:
    def test_the_answer_replaces_the_lead_in(self, db_path):
        from datetime import datetime

        _plan_activity(db_path, "Träna rygg", datetime(2026, 9, 7, 10, 0))
        client = FakeLLMClient(
            payloads=[
                {
                    "tool": "list_day",
                    "arguments": {"date": "2026-09-07"},
                    "reply": "Jag kollar imorgon åt dig.",
                },
                {"reply": "Du tränar rygg kl 10:00."},
            ]
        )
        agent = ConversationAgent(
            llm_client=client, db_path=db_path, reference_date=REF
        )

        turn = agent.send("när ska jag träna imorgon?")

        assert turn.kind == "display"
        assert turn.reply == "Du tränar rygg kl 10:00."
        assert "Träna rygg" in turn.text

    def test_the_retrieved_data_is_handed_to_the_model(self, db_path):
        from datetime import datetime

        _plan_activity(db_path, "Träna rygg", datetime(2026, 9, 7, 10, 0))
        client = FakeLLMClient(
            payloads=[
                {"tool": "list_day", "arguments": {"date": "2026-09-07"}, "reply": "Kollar."},
                {"reply": "Kl 10."},
            ]
        )
        ConversationAgent(
            llm_client=client, db_path=db_path, reference_date=REF
        ).send("när tränar jag?")

        assert len(client.calls) == 2
        assert "Träna rygg" in client.calls[1][-1]["content"]
        assert "READ" not in client.system_prompts[0]

    def test_a_failed_second_call_keeps_the_lead_in(self, db_path):
        client = FakeLLMClient(
            payloads=[
                {"tool": "list_day", "arguments": {"date": "2026-09-07"}, "reply": "Kollar."}
            ]
        )
        agent = ConversationAgent(
            llm_client=client, db_path=db_path, reference_date=REF
        )

        turn = agent.send("vad har jag imorgon?")

        assert turn.kind == "display"
        assert turn.reply == "Kollar."


# ---------------------------------------------------------------------------
# Changing and removing saved items
# ---------------------------------------------------------------------------


def _save_event(db_path, title, when):
    from life_agent.db.repositories import create_event
    from life_agent.models import CalendarEvent

    create_event(CalendarEvent(title=title, start_time=when), db_path)


class TestEditFlows:
    def test_delete_resolves_to_one_row_and_asks(self, db_path):
        from datetime import datetime

        _save_event(db_path, "Lämna grabben på förskolan", datetime(2026, 9, 7, 9, 30))
        payload = {
            "tool": "delete_item",
            "arguments": {"title": "grabben", "item_type": "event"},
            "reply": "Jag tar bort den.",
        }

        turn = _agent(payload, db_path=db_path).send("ta bort lämningen")

        assert turn.kind == "needs_confirmation"
        assert turn.data["flow"] == "delete"
        assert turn.data["match"].title == "Lämna grabben på förskolan"
        assert turn.decision.action_type == "delete"
        assert turn.decision.requires_confirmation is True

    def test_nothing_is_removed_by_the_proposal_itself(self, db_path):
        from datetime import datetime

        from life_agent.db.repositories import list_events

        _save_event(db_path, "Lämna grabben", datetime(2026, 9, 7, 9, 30))
        payload = {
            "tool": "delete_item",
            "arguments": {"title": "grabben"},
            "reply": "Jag tar bort den.",
        }

        _agent(payload, db_path=db_path).send("ta bort lämningen")

        assert len(list_events(db_path)) == 1

    def test_an_unmatched_description_says_so(self, db_path):
        payload = {
            "tool": "delete_item",
            "arguments": {"title": "tandläkaren"},
            "reply": "Jag tar bort den.",
        }

        turn = _agent(payload, db_path=db_path).send("ta bort tandläkaren")

        assert turn.kind == "reply"
        assert turn.reply == NOT_FOUND_TEXT
        assert turn.decision.tool_name is None

    def test_several_matches_are_listed_for_the_user_to_pick(self, db_path):
        from datetime import datetime

        _save_event(db_path, "Träna rygg", datetime(2026, 9, 7, 10, 0))
        _save_event(db_path, "Träna biceps", datetime(2026, 9, 9, 11, 0))
        payload = {
            "tool": "delete_item",
            "arguments": {"title": "träna"},
            "reply": "Jag tar bort den.",
        }

        turn = _agent(payload, db_path=db_path).send("ta bort träningen")

        assert turn.kind == "reply"
        assert turn.reply == AMBIGUOUS_TEXT
        assert "Träna rygg" in turn.text
        assert "Träna biceps" in turn.text

    def test_reschedule_carries_the_new_time(self, db_path):
        from datetime import datetime

        _save_event(db_path, "Lämna grabben", datetime(2026, 9, 7, 9, 30))
        payload = {
            "tool": "reschedule_item",
            "arguments": {"title": "grabben", "new_time": "2026-09-07T08:45:00"},
            "reply": "Jag flyttar den.",
        }

        turn = _agent(payload, db_path=db_path).send("flytta lämningen till 08:45")

        assert turn.kind == "needs_confirmation"
        assert turn.data["flow"] == "reschedule"
        assert turn.data["new_time"] == datetime(2026, 9, 7, 8, 45)
        assert turn.decision.action_type == "update"
        assert turn.decision.requires_confirmation is True

    def test_reschedule_without_a_usable_time_asks(self, db_path):
        from datetime import datetime

        _save_event(db_path, "Lämna grabben", datetime(2026, 9, 7, 9, 30))
        payload = {
            "tool": "reschedule_item",
            "arguments": {"title": "grabben", "new_time": "kvart i nio"},
            "reply": "",
        }

        turn = _agent(payload, db_path=db_path).send("flytta lämningen")

        assert turn.kind == "reply"
        assert turn.reply == BAD_DATE_TEXT
