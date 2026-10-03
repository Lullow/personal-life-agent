"""Tests for the memory layer.

Two kinds of test live here.  :class:`TestMemoryContract` is parametrised over
every strategy and asserts the rules that hold for all of them — it is the
harness the next two implementations plug into, and a strategy that cannot pass
it is not finished.  The rest test one strategy each:
:class:`RecentTurnsMemory`, including the window behaviour the conversation
loop used to implement itself, :class:`RetrievalMemory`, whose rules are
those of ADR 0011, and :class:`ConsolidatingMemory`, whose rules are those of
ADRs 0012 to 0014.  The consolidator is a fake that replies with a scripted
summary and keeps every call, so a test can read what it was shown.
"""

import inspect
from datetime import datetime, timedelta

import pytest

import life_agent.agent.memory as memory_module
from life_agent.agent.memory import (
    CONSOLIDATION_ATTEMPTS,
    CONSOLIDATION_SYSTEM_PROMPT,
    SUMMARY_TARGET_TOKENS,
    ApproxTokenCounter,
    ConsolidatingMemory,
    MemoryRecord,
    RecentTurnsMemory,
    RetrievalMemory,
    keep_last_tokens,
    make_record_id,
    make_summary_id,
)

NOW = datetime(2026, 9, 6, 12, 0, 0)
LATER = NOW + timedelta(hours=1)


class FakeConsolidator:
    """Replies with the scripted *replies* in turn, then with numbered notes."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def chat_json(self, system_prompt, messages):
        self.calls.append((system_prompt, messages))
        if self.replies:
            return self.replies.pop(0)
        return {"summary": f"notes after {len(self.calls)} call(s)"}


class CharCounter:
    def count(self, text: str) -> int:
        return len(text)


# Every strategy, built fresh.  Add the last one here and the contract below
# starts applying to it without a line of new test code.  Each query shares a
# word with the record it expects back: a strategy that recalls by relevance
# owes nothing to a query that matches nothing.
STRATEGIES = [
    pytest.param(lambda: RecentTurnsMemory(max_turns=10), id="recent-turns"),
    pytest.param(lambda: RecentTurnsMemory(max_turns=None), id="recent-turns-no-window"),
    pytest.param(lambda: RetrievalMemory(), id="retrieval"),
    pytest.param(lambda: ConsolidatingMemory(FakeConsolidator()), id="consolidating"),
]


@pytest.fixture(params=STRATEGIES)
def memory(request):
    return request.param()


def record(
    index: int,
    content: str,
    *,
    role="user",
    kind="message",
    at=NOW,
    session_id="s1",
) -> MemoryRecord:
    return MemoryRecord(
        id=make_record_id(session_id, index),
        role=role,
        content=content,
        kind=kind,
        at=at,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Record ids
# ---------------------------------------------------------------------------


class TestRecordIds:
    def test_id_is_derived_from_position(self):
        assert make_record_id("s1", 0) == "s1:0"

    def test_same_history_gives_the_same_ids_twice(self):
        first = [make_record_id("s1", i) for i in range(5)]
        second = [make_record_id("s1", i) for i in range(5)]

        # Precision and recall are only comparable between strategies because
        # of this.  A random component here would quietly destroy the metric.
        assert first == second

    def test_sessions_do_not_collide(self):
        assert make_record_id("s1", 0) != make_record_id("s2", 0)


# ---------------------------------------------------------------------------
# The contract every strategy owes
# ---------------------------------------------------------------------------


class TestMemoryContract:
    def test_empty_memory_recalls_nothing(self, memory):
        result = memory.retrieve("anything", at=NOW, budget_tokens=1000)

        assert result.messages == []
        assert result.sources == ()
        assert result.tokens_used == 0

    def test_a_record_stamped_after_the_cutoff_is_invisible(self, memory):
        memory.write(record(0, "before", at=NOW))
        memory.write(record(1, "after", at=LATER))

        result = memory.retrieve("before or after", at=NOW, budget_tokens=1000)

        contents = [m["content"] for m in result.messages]
        assert "before" in contents
        assert "after" not in contents

    def test_the_cutoff_is_inclusive_of_its_own_instant(self, memory):
        memory.write(record(0, "exactly now", at=NOW))

        result = memory.retrieve("now", at=NOW, budget_tokens=1000)

        assert [m["content"] for m in result.messages] == ["exactly now"]

    def test_an_outcome_survives_a_session_boundary(self, memory):
        memory.write(record(0, "jag ska träna imorgon"))
        memory.write(
            record(1, "Saved 4 item(s)", role="assistant", kind="outcome")
        )

        memory.end_session()

        result = memory.retrieve("what was saved?", at=LATER, budget_tokens=1000)
        # Verbatim: the database had the last word, and a strategy that
        # paraphrases it during consolidation has broken that.
        assert "Saved 4 item(s)" in [m["content"] for m in result.messages]

    def test_sources_accompany_the_messages(self, memory):
        memory.write(record(0, "hej"))

        result = memory.retrieve("hej", at=NOW, budget_tokens=1000)

        assert result.messages
        assert result.sources
        assert len(set(result.sources)) == len(result.sources)

    def test_recall_reports_what_it_spent(self, memory):
        memory.write(record(0, "a message with some length to it"))

        result = memory.retrieve("message", at=NOW, budget_tokens=1000)

        assert result.tokens_used > 0

    def test_a_budget_is_not_exceeded(self, memory):
        for i in range(10):
            memory.write(record(i, f"message number {i} with padding"))

        result = memory.retrieve("message", at=NOW, budget_tokens=5)

        # One oversized record may still come back alone — returning nothing
        # would be worse — but anything beyond that has to fit.
        assert len(result.messages) <= 1 or result.tokens_used <= 5


# ---------------------------------------------------------------------------
# RecentTurnsMemory — the baseline, and what it is meant to be bad at
# ---------------------------------------------------------------------------


class TestRecentTurnsMemory:
    def test_messages_come_back_oldest_first(self):
        memory = RecentTurnsMemory()
        memory.write(record(0, "first"))
        memory.write(record(1, "second", role="assistant"))

        result = memory.retrieve("q", at=NOW, budget_tokens=1000)

        assert [m["content"] for m in result.messages] == ["first", "second"]

    def test_the_window_keeps_the_most_recent_pairs(self):
        memory = RecentTurnsMemory(max_turns=2)
        for i in range(6):
            memory.write(record(i * 2, f"m{i}"))
            memory.write(record(i * 2 + 1, f"r{i}", role="assistant"))

        result = memory.retrieve("q", at=NOW, budget_tokens=10_000)

        assert [m["content"] for m in result.messages] == ["m4", "r4", "m5", "r5"]

    def test_older_records_are_kept_but_not_recalled(self):
        memory = RecentTurnsMemory(max_turns=1)
        memory.write(record(0, "old"))
        memory.write(record(1, "new", role="assistant"))
        memory.write(record(2, "newer"))

        result = memory.retrieve("q", at=NOW, budget_tokens=10_000)

        # Dropped from recall, not from the store: the eval needs to be able to
        # ask what the strategy failed to surface.
        assert "old" not in [m["content"] for m in result.messages]
        assert "old" in [r.content for r in memory.records]

    def test_the_query_makes_no_difference(self):
        memory = RecentTurnsMemory()
        memory.write(record(0, "träning"))
        memory.write(record(1, "matlagning"))

        for query in ("träning", "matlagning", ""):
            result = memory.retrieve(query, at=NOW, budget_tokens=1000)
            assert len(result.messages) == 2

    def test_a_tight_budget_keeps_the_newest(self):
        memory = RecentTurnsMemory()
        memory.write(record(0, "x" * 400))
        memory.write(record(1, "y" * 400, role="assistant"))

        result = memory.retrieve("q", at=NOW, budget_tokens=120)

        assert [m["content"] for m in result.messages] == ["y" * 400]

    def test_one_oversized_record_still_comes_back(self):
        memory = RecentTurnsMemory()
        memory.write(record(0, "z" * 4000))

        result = memory.retrieve("q", at=NOW, budget_tokens=1)

        assert len(result.messages) == 1

    def test_the_default_window_is_ten_turns(self):
        memory = RecentTurnsMemory()
        for i in range(30):
            memory.write(record(i, f"m{i}"))

        result = memory.retrieve("q", at=NOW, budget_tokens=10_000)

        # The agent's own configuration, which ADR 0007 leaves unchanged.
        assert [m["content"] for m in result.messages] == [f"m{i}" for i in range(10, 30)]

    def test_without_a_window_only_the_budget_limits(self):
        memory = RecentTurnsMemory(max_turns=None)
        for i in range(30):
            memory.write(record(i, "x" * 40))

        everything = memory.retrieve("q", at=NOW, budget_tokens=10_000)
        tight = memory.retrieve("q", at=NOW, budget_tokens=100)

        # ADR 0007: the evaluation fills the budget instead of keeping the
        # 20-message window.  Each record costs 10 approximate tokens.
        assert len(everything.messages) == 30
        assert tight.sources == tuple(make_record_id("s1", i) for i in range(20, 30))
        assert tight.tokens_used == 100

    def test_end_session_is_a_no_op(self):
        memory = RecentTurnsMemory()
        memory.write(record(0, "hej"))
        memory.end_session()

        assert [r.content for r in memory.records] == ["hej"]


# ---------------------------------------------------------------------------
# RetrievalMemory — BM25 over every record, shown in the order it was said
# ---------------------------------------------------------------------------


class TestRetrievalMemory:
    def test_the_record_that_shares_words_with_the_query_is_recalled(self):
        memory = RetrievalMemory()
        memory.write(record(0, "My cat is called Miso"))
        memory.write(record(1, "The weather is nice today"))

        # Room for either record, 6 and 7 approximate tokens, but not for both.
        result = memory.retrieve("What is my cat called?", at=NOW, budget_tokens=7)

        assert [m["content"] for m in result.messages] == ["My cat is called Miso"]

    def test_a_rare_word_counts_for_more_than_a_common_one(self):
        memory = RetrievalMemory()
        memory.write(record(0, "Lisbon was sunny"))
        memory.write(record(1, "talk about weather"))
        memory.write(record(2, "talk about dinner"))
        memory.write(record(3, "talk about sports"))

        result = memory.retrieve("about Lisbon", at=NOW, budget_tokens=5)

        assert result.sources == (make_record_id("s1", 0),)

    def test_messages_come_back_in_the_order_they_were_written(self):
        memory = RetrievalMemory()
        memory.write(record(0, "the gym costs 20"))
        memory.write(record(1, "see you tomorrow", role="assistant"))
        memory.write(record(2, "my gym membership price went up to 30"))

        result = memory.retrieve("gym membership price", at=NOW, budget_tokens=1000)

        # The later record is the better match, and still comes last: order is
        # the only thing that tells the model which value is the newer one.
        assert [m["content"] for m in result.messages] == [
            "the gym costs 20",
            "my gym membership price went up to 30",
        ]
        assert result.sources == (make_record_id("s1", 0), make_record_id("s1", 2))

    def test_a_record_that_shares_no_word_is_never_recalled(self):
        memory = RetrievalMemory()
        memory.write(record(0, "see you tomorrow"))

        result = memory.retrieve("gym membership price", at=NOW, budget_tokens=1000)

        assert result.messages == []
        assert result.tokens_used == 0

    def test_a_record_too_large_is_passed_over_and_the_walk_goes_on(self):
        memory = RetrievalMemory()
        memory.write(record(0, "cat " * 200))
        memory.write(record(1, "my cat"))

        result = memory.retrieve("cat", at=NOW, budget_tokens=50)

        # The long record ranks first and costs 200 approximate tokens.
        assert [m["content"] for m in result.messages] == ["my cat"]
        assert result.tokens_used <= 50

    def test_an_oversized_record_does_not_come_back_alone(self):
        memory = RetrievalMemory()
        memory.write(record(0, "cat " * 200))

        result = memory.retrieve("cat", at=NOW, budget_tokens=50)

        # Unlike the baseline: every strategy gets the same allowance, so this
        # one never spends more than it.
        assert result.messages == []

    def test_equal_scores_go_to_the_record_written_later(self):
        memory = RetrievalMemory()
        memory.write(record(0, "blue bike"))
        memory.write(record(1, "blue bike"))

        result = memory.retrieve("bike", at=NOW, budget_tokens=3)

        assert result.sources == (make_record_id("s1", 1),)

    def test_a_later_record_does_not_move_the_ranking(self):
        memory = RetrievalMemory()
        memory.write(record(0, "alpha"))
        memory.write(record(1, "gamma"))
        for i in range(2, 6):
            memory.write(record(i, "gamma", at=LATER))

        result = memory.retrieve("alpha gamma", at=NOW, budget_tokens=2)

        # Seen from NOW the two words are equally rare, so the tie goes to the
        # later record.  Counting the records stamped LATER would make "gamma"
        # common and hand the single place to "alpha".
        assert result.sources == (make_record_id("s1", 1),)

    def test_matching_ignores_case_and_punctuation(self):
        memory = RetrievalMemory()
        memory.write(record(0, "Träna RYGG!"))

        for query in ("rygg", "TRÄNA", "träna, rygg?"):
            result = memory.retrieve(query, at=NOW, budget_tokens=1000)
            assert result.sources == (make_record_id("s1", 0),)

    def test_an_inflected_word_does_not_match(self):
        memory = RetrievalMemory()
        memory.write(record(0, "graduated"))

        result = memory.retrieve("graduate", at=NOW, budget_tokens=1000)

        # No stemming: the matching is lexical, and the report says so.
        assert result.messages == []

    def test_assistant_turns_are_recalled_too(self):
        memory = RetrievalMemory()
        memory.write(record(0, "the recipe needs saffron", role="assistant"))

        result = memory.retrieve("saffron", at=NOW, budget_tokens=1000)

        assert result.messages == [
            {"role": "assistant", "content": "the recipe needs saffron"}
        ]

    def test_an_outcome_is_recalled_only_when_it_matches(self):
        memory = RetrievalMemory()
        memory.write(record(0, "Saved 4 item(s)", role="assistant", kind="outcome"))

        missed = memory.retrieve("träna imorgon", at=NOW, budget_tokens=1000)
        found = memory.retrieve("saved", at=NOW, budget_tokens=1000)

        # Kept verbatim, but ranked like any other record.
        assert missed.messages == []
        assert [m["content"] for m in found.messages] == ["Saved 4 item(s)"]

    def test_end_session_is_a_no_op(self):
        memory = RetrievalMemory()
        memory.write(record(0, "hej"))
        memory.end_session()

        assert [r.content for r in memory.records] == ["hej"]


# ---------------------------------------------------------------------------
# ConsolidatingMemory — ADRs 0012 (design), 0013 (derived_from), 0014 (clock)
# ---------------------------------------------------------------------------


def consolidating(*replies, counter=None):
    llm = FakeConsolidator(*replies)
    return ConsolidatingMemory(llm, token_counter=counter), llm


def shown(result):
    return [m["content"] for m in result.messages]


class TestConsolidatingMemory:
    def test_end_session_turns_the_pending_messages_into_a_summary(self):
        memory, llm = consolidating({"summary": "the user runs on Tuesdays"})
        memory.write(record(0, "I run on Tuesdays"))
        memory.write(record(1, "Noted.", role="assistant"))

        memory.end_session()

        summary = memory.records[-1]
        assert summary.kind == "summary"
        assert summary.role == "assistant"
        assert summary.content == "the user runs on Tuesdays"
        assert summary.id == make_summary_id("s1")
        assert summary.session_id == "s1"
        assert summary.derived_from == (make_record_id("s1", 0), make_record_id("s1", 1))
        assert len(llm.calls) == 1

    def test_the_call_quotes_the_transcript_under_the_notes_so_far(self):
        memory, llm = consolidating({"summary": "first notes"})
        memory.write(record(0, "I run on Tuesdays"))
        memory.write(record(1, "Noted.", role="assistant"))
        memory.end_session()
        memory.write(record(0, "Now I run on Fridays", session_id="s2"))
        memory.end_session()

        first, second = llm.calls
        assert first[0] == CONSOLIDATION_SYSTEM_PROMPT
        assert first[1] == [{
            "role": "user",
            "content": "Notes so far:\n(none)\n\nConversation to add:\n"
                       "user: I run on Tuesdays\n\nassistant: Noted.",
        }]
        # One user message: the session is quoted data, not turns to continue.
        assert second[1] == [{
            "role": "user",
            "content": "Notes so far:\nfirst notes\n\nConversation to add:\n"
                       "user: Now I run on Fridays",
        }]

    def test_write_never_consolidates(self):
        memory, llm = consolidating()
        for i in range(50):
            memory.write(record(i, f"message {i}"))

        assert llm.calls == []
        assert all(r.kind == "message" for r in memory.records)

    def test_nothing_happens_on_a_session_without_messages(self):
        memory, llm = consolidating()
        memory.end_session()
        memory.write(record(0, "hej"))
        memory.end_session()
        memory.end_session()
        memory.write(record(1, "Saved 1 item(s)", role="assistant", kind="outcome"))
        memory.end_session()

        assert len(llm.calls) == 1

    # -- what retrieve shows (0012) --

    def test_the_summary_comes_first_then_the_window_in_write_order(self):
        memory, _ = consolidating({"summary": "notes"})
        memory.write(record(0, "one"))
        memory.write(record(1, "two", role="assistant"))
        memory.end_session()
        memory.write(record(0, "three", session_id="s2"))

        result = memory.retrieve("anything", at=NOW, budget_tokens=1000)

        assert result.messages == [
            {"role": "assistant", "content": "notes"},
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
        ]
        assert result.sources == (
            make_summary_id("s1"),
            make_record_id("s1", 0),
            make_record_id("s1", 1),
            make_record_id("s2", 0),
        )

    def test_raw_records_are_kept_after_consolidation(self):
        memory, _ = consolidating({"summary": "notes"})
        memory.write(record(0, "one"))
        memory.end_session()

        assert [r.kind for r in memory.records] == ["message", "summary"]
        assert "one" in shown(memory.retrieve("one", at=NOW, budget_tokens=1000))

    def test_the_window_fills_what_the_summary_left(self):
        memory, _ = consolidating({"summary": "x" * 10}, counter=CharCounter())
        memory.write(record(0, "aaaa"))
        memory.write(record(1, "bbbbbbbb"))
        memory.write(record(2, "cccc"))
        memory.end_session()

        result = memory.retrieve("anything", at=NOW, budget_tokens=20)

        # 10 for the notes, 4 for the newest, then 8 does not fit and the walk
        # ends there: an older record that would fit is not taken (ADR 0007).
        assert shown(result) == ["x" * 10, "cccc"]
        assert result.tokens_used == 14

    def test_the_newest_summary_is_the_one_shown(self):
        memory, _ = consolidating({"summary": "first"}, {"summary": "second"})
        memory.write(record(0, "one"))
        memory.end_session()
        memory.write(record(0, "two", session_id="s2"))
        memory.end_session()

        result = memory.retrieve("anything", at=NOW, budget_tokens=1000)

        assert shown(result)[0] == "second"
        assert "first" not in shown(result)

    def test_without_a_summary_the_strategy_is_the_baseline(self):
        memory, _ = consolidating(counter=CharCounter())
        memory.write(record(0, "x" * 100))

        result = memory.retrieve("anything", at=NOW, budget_tokens=10)

        # The newest record is always admitted, as RecentTurnsMemory does.
        assert shown(result) == ["x" * 100]

    def test_with_a_summary_an_oversized_record_is_not_admitted(self):
        memory, _ = consolidating({"summary": "notes"}, counter=CharCounter())
        memory.write(record(0, "x" * 100))
        memory.end_session()

        result = memory.retrieve("anything", at=NOW, budget_tokens=10)

        assert shown(result) == ["notes"]
        assert result.tokens_used == 5

    def test_the_query_makes_no_difference(self):
        memory, _ = consolidating({"summary": "notes"})
        memory.write(record(0, "the gym"))
        memory.end_session()

        a = memory.retrieve("gym", at=NOW, budget_tokens=1000)
        b = memory.retrieve("saffron", at=NOW, budget_tokens=1000)

        assert a == b

    # -- outcomes --

    def test_an_outcome_never_enters_the_call_and_stays_verbatim(self):
        memory, llm = consolidating({"summary": "notes"})
        memory.write(record(0, "jag ska träna imorgon"))
        memory.write(record(1, "Saved 4 item(s)", role="assistant", kind="outcome"))
        memory.end_session()

        (_, messages), = llm.calls
        assert "Saved 4 item(s)" not in messages[0]["content"]
        assert memory.records[-1].derived_from == (make_record_id("s1", 0),)
        assert "Saved 4 item(s)" in shown(memory.retrieve("saved", at=NOW, budget_tokens=1000))

    # -- derived_from is flat (0013) --

    def test_derived_from_accumulates_across_sessions(self):
        memory, _ = consolidating()
        memory.write(record(0, "one"))
        memory.write(record(1, "two", role="assistant"))
        memory.end_session()
        memory.write(record(0, "three", session_id="s2"))
        memory.end_session()

        assert memory.records[-1].derived_from == (
            make_record_id("s1", 0),
            make_record_id("s1", 1),
            make_record_id("s2", 0),
        )

    def test_ids_and_derived_from_are_the_same_in_two_replays(self):
        def replay():
            memory, _ = consolidating()
            memory.write(record(0, "one"))
            memory.end_session()
            memory.write(record(0, "two", session_id="s2"))
            memory.end_session()
            return [(r.id, r.derived_from) for r in memory.records if r.kind == "summary"]

        assert replay() == replay()

    def test_a_second_summary_for_the_same_session_is_refused(self):
        memory, _ = consolidating()
        memory.write(record(0, "one"))
        memory.end_session()
        memory.write(record(1, "two"))

        with pytest.raises(ValueError):
            memory.end_session()

    # -- the clock (0014) --

    def test_the_summary_is_stamped_with_the_largest_time_seen(self):
        memory, _ = consolidating()
        memory.write(record(0, "later", at=LATER))
        memory.write(record(1, "earlier", at=NOW))
        memory.end_session()

        # The largest, not the last written: the clock never moves backwards.
        assert memory.records[-1].at == LATER

    def test_a_summary_made_after_the_cutoff_is_invisible(self):
        memory, _ = consolidating({"summary": "notes"})
        memory.write(record(0, "before", at=NOW))
        memory.write(record(1, "after", at=LATER))
        memory.end_session()

        at_now = memory.retrieve("anything", at=NOW, budget_tokens=1000)
        at_later = memory.retrieve("anything", at=LATER, budget_tokens=1000)

        assert shown(at_now) == ["before"]
        assert shown(at_later) == ["notes", "before", "after"]

    def test_the_module_reads_no_clock_of_its_own(self):
        source = inspect.getsource(memory_module)
        assert "now()" not in source and "today()" not in source

    # -- failures --

    def test_a_failed_call_is_tried_again(self):
        memory, llm = consolidating(None, None, {"summary": "third time"})
        memory.write(record(0, "one"))

        memory.end_session()

        assert len(llm.calls) == CONSOLIDATION_ATTEMPTS
        assert memory.records[-1].content == "third time"

    def test_when_every_attempt_fails_the_session_is_skipped(self):
        memory, llm = consolidating(None, None, None)
        memory.write(record(0, "one"))

        memory.end_session()

        # ADR 0016: no summary, nothing lost, and the skip is on record.
        assert len(llm.calls) == CONSOLIDATION_ATTEMPTS
        assert [r.kind for r in memory.records] == ["message"]
        assert shown(memory.retrieve("one", at=NOW, budget_tokens=1000)) == ["one"]
        (c,) = memory.consolidations
        assert (c.session_id, c.tokens, c.failed) == ("s1", 0, True)

    def test_a_skipped_session_is_not_carried_into_the_next_call(self):
        memory, llm = consolidating(None, None, None, {"summary": "notes of s2"})
        memory.write(record(0, "the looping session"))
        memory.end_session()
        memory.write(record(0, "a later session", session_id="s2"))
        memory.end_session()

        last = llm.calls[-1][1][0]["content"]
        assert "the looping session" not in last
        assert "Notes so far:\n(none)" in last
        summary = memory.records[-1]
        assert summary.content == "notes of s2"
        assert summary.derived_from == (make_record_id("s2", 0),)

    def test_a_skipped_session_leaves_the_notes_as_they_were(self):
        memory, _ = consolidating({"summary": "first notes"}, None, None, None)
        memory.write(record(0, "one"))
        memory.end_session()
        memory.write(record(0, "two", session_id="s2"))
        memory.end_session()

        result = memory.retrieve("anything", at=NOW, budget_tokens=1000)

        assert shown(result) == ["first notes", "one", "two"]
        assert [c.failed for c in memory.consolidations] == [False, True]

    def test_a_reply_without_a_string_summary_is_a_failure(self):
        memory, llm = consolidating({"summary": 5}, {"notes": "x"}, {"summary": "  "})
        memory.write(record(0, "one"))

        memory.end_session()

        assert len(llm.calls) == CONSOLIDATION_ATTEMPTS
        assert memory.consolidations[0].failed

    # -- the size holds (0015) --

    def test_a_summary_within_s_is_taken_as_it_is(self):
        memory, llm = consolidating({"summary": "short notes."}, counter=CharCounter())
        memory.write(record(0, "one"))
        memory.end_session()

        (c,) = memory.consolidations
        assert len(llm.calls) == 1
        assert (c.tokens, c.reasked, c.truncated) == (len("short notes."), False, False)

    def test_a_summary_over_s_is_asked_for_once_more_with_its_word_count(self, monkeypatch):
        monkeypatch.setattr(memory_module, "SUMMARY_TARGET_TOKENS", 20)
        long = "one two three four five six seven eight nine ten."  # 50 chars
        memory, llm = consolidating({"summary": long}, {"summary": "ten words cut."}, counter=CharCounter())
        memory.write(record(0, "hej"))
        memory.end_session()

        assert len(llm.calls) == 2
        second = llm.calls[1][1][0]["content"]
        assert second.startswith("These notes are 10 words, over the limit of 750.")
        assert second.endswith("Notes:\n" + long)
        assert memory.records[-1].content == "ten words cut."
        (c,) = memory.consolidations
        assert (c.reasked, c.truncated) == (True, False)

    def test_a_second_reply_still_over_s_is_cut_from_the_start(self, monkeypatch):
        monkeypatch.setattr(memory_module, "SUMMARY_TARGET_TOKENS", 25)
        long = "Oldest fact. Older fact! Newer fact? Newest fact."
        memory, llm = consolidating({"summary": long}, {"summary": long}, counter=CharCounter())
        memory.write(record(0, "hej"))
        memory.end_session()

        # ADR 0017: the oldest go first; the session just added survives.
        assert len(llm.calls) == 2
        assert memory.records[-1].content == "Newer fact? Newest fact."
        (c,) = memory.consolidations
        assert (c.tokens, c.reasked, c.truncated) == (len("Newer fact? Newest fact."), True, True)

    def test_the_second_reply_replaces_the_first_even_when_longer(self, monkeypatch):
        monkeypatch.setattr(memory_module, "SUMMARY_TARGET_TOKENS", 20)
        memory, _ = consolidating({"summary": "a" * 30}, {"summary": "c" * 30 + ". " + "b" * 15},
                                  counter=CharCounter())
        memory.write(record(0, "hej"))
        memory.end_session()

        assert memory.records[-1].content == "b" * 15

    def test_a_failed_second_call_falls_back_on_the_first_reply_cut(self, monkeypatch):
        monkeypatch.setattr(memory_module, "SUMMARY_TARGET_TOKENS", 12)
        memory, llm = consolidating({"summary": "Too long. By far."}, None, None, None, counter=CharCounter())
        memory.write(record(0, "hej"))

        memory.end_session()

        # ADR 0016: the first reply was valid notes, only too long.
        assert len(llm.calls) == 1 + CONSOLIDATION_ATTEMPTS
        assert memory.records[-1].content == "By far."
        (c,) = memory.consolidations
        assert (c.reasked, c.truncated, c.failed) == (True, True, False)

    def test_the_summary_never_takes_more_than_s_of_the_budget(self, monkeypatch):
        monkeypatch.setattr(memory_module, "SUMMARY_TARGET_TOKENS", 10)
        memory, _ = consolidating({"summary": "x" * 50}, {"summary": "y" * 50}, counter=CharCounter())
        for i in range(5):
            memory.write(record(i, "mmmm"))
        memory.end_session()

        result = memory.retrieve("anything", at=NOW, budget_tokens=30)

        # 10 at most for the notes, so at least 20 of 30 are left for the window.
        assert result.tokens_used <= 30
        assert len(result.messages) >= 1 + 4

    def test_s_is_a_thousand_tokens(self):
        assert SUMMARY_TARGET_TOKENS == 1000


class TestKeepLastTokens:
    counter = CharCounter()

    def test_text_within_the_limit_is_unchanged(self):
        assert keep_last_tokens("short.", 10, self.counter) == "short."

    def test_the_cut_falls_at_the_first_sentence_start_that_fits(self):
        text = "One. Two! Three? Four."
        assert keep_last_tokens(text, 15, self.counter) == "Three? Four."

    def test_a_line_break_is_a_sentence_end(self):
        text = "first\nsecond line\nthird line"
        assert keep_last_tokens(text, 22, self.counter) == "second line\nthird line"

    def test_without_a_sentence_start_the_cut_keeps_the_last_words(self):
        text = "alpha beta gamma delta"
        assert keep_last_tokens(text, 12, self.counter) == "gamma delta"

    def test_nothing_fits_gives_nothing(self):
        assert keep_last_tokens("abcdefgh", 3, self.counter) == ""


class TestApproxTokenCounter:
    def test_empty_text_costs_nothing(self):
        assert ApproxTokenCounter().count("") == 0

    def test_any_text_costs_at_least_one(self):
        assert ApproxTokenCounter().count("a") == 1

    def test_cost_grows_with_length(self):
        counter = ApproxTokenCounter()
        assert counter.count("x" * 400) > counter.count("x" * 40)
