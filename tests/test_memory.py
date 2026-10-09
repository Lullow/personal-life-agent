"""Tests for the memory layer.

Two kinds of test live here.  :class:`TestMemoryContract` is parametrised over
every strategy and asserts the rules that hold for all of them — it is the
harness the next two implementations plug into, and a strategy that cannot pass
it is not finished.  The rest test one strategy each:
:class:`RecentTurnsMemory`, including the window behaviour the conversation
loop used to implement itself, :class:`RetrievalMemory`, whose rules are
those of ADR 0011, :class:`ConsolidatingMemory`, whose rules are those of
ADRs 0012 to 0014, and :class:`FactGraphMemory`, whose rules are those of ADR
0018.  The consolidator is a fake that replies with a scripted summary and
keeps every call, so a test can read what it was shown; the fact graph's
extraction model is a fake of the same kind, and its facts are kept in the
process.
"""

import inspect
from datetime import datetime, timedelta

import pytest

import life_agent.agent.memory as memory_module
from life_agent.agent.fact_store import FactStoreError, InProcessFactStore
from life_agent.agent.memory import (
    CONSOLIDATION_ATTEMPTS,
    CONSOLIDATION_SYSTEM_PROMPT,
    EXTRACTION_ATTEMPTS,
    EXTRACTION_SYSTEM_PROMPT,
    FACT_TOKENS,
    SUMMARY_TARGET_TOKENS,
    ApproxTokenCounter,
    ConsolidatingMemory,
    FactGraphMemory,
    MemoryRecord,
    RecentTurnsMemory,
    RetrievalMemory,
    keep_last_tokens,
    make_fact_id,
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


class FakeExtractor:
    """Replies with the scripted *replies* in turn, then with no facts."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def chat_json(self, system_prompt, messages):
        self.calls.append((system_prompt, messages))
        if self.replies:
            return self.replies.pop(0)
        return {"facts": []}


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
    pytest.param(lambda: FactGraphMemory(FakeExtractor()), id="fact-graph"),
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


# ---------------------------------------------------------------------------
# FactGraphMemory — ADR 0018, with 0013 (derived_from) and 0014 (clock)
# ---------------------------------------------------------------------------

MAY = datetime(2026, 5, 1, 9, 0, 0)
JUNE = datetime(2026, 6, 1, 9, 0, 0)
JULY = datetime(2026, 7, 1, 9, 0, 0)


def fact_graph(*replies, counter=None, store=None):
    llm = FakeExtractor(*replies)
    return FactGraphMemory(llm, store=store, token_counter=counter), llm


def facts(*triples):
    """A reply: each triple is (relation, value) or (relation, value, turn), about the user."""
    return {"facts": [
        {"subject": "user", "relation": t[0], "value": t[1], "turn": t[2] if len(t) > 2 else 0}
        for t in triples
    ]}


def session(memory, session_id, *contents, at=NOW):
    """Write one session, user and assistant in turn, and end it."""
    for i, content in enumerate(contents):
        memory.write(record(i, content, role="user" if i % 2 == 0 else "assistant", at=at, session_id=session_id))
    memory.end_session()


def lines(memory, *, held_at=None):
    return [f.line for f in memory.facts if held_at is None or f.holds(held_at)]


class TestFactGraphMemory:
    # -- what the presentation shows --

    def test_what_held_before_a_replacement_can_still_be_asked_for(self):
        memory, _ = fact_graph(facts(("car", "Honda")), facts(("car", "Tesla")))
        session(memory, "may", "I drive a Honda", at=MAY)
        session(memory, "june", "I traded my car for a Tesla", at=JUNE)
        question = "What car do I drive?"

        in_may = memory.retrieve(question, at=MAY + timedelta(days=14), budget_tokens=1000)
        in_june = memory.retrieve(question, at=JUNE + timedelta(days=14), budget_tokens=1000)

        # Before the replacement the old value holds, after it the new one,
        # and neither time shows both.
        assert shown(in_may)[0] == "user / car = Honda"
        assert shown(in_june)[0] == "user / car = Tesla"
        # The old fact was marked, not deleted.
        old, new = memory.facts
        assert (old.value, old.replaced_by, old.replaced_at) == ("Honda", new.id, JUNE)
        assert (new.value, new.replaced_by) == ("Tesla", None)

    # -- extraction (0018) --

    def test_end_session_stores_each_fact_as_a_record(self):
        memory, llm = fact_graph(facts(("running_day", "Tuesday"), ("dog_name", "Miso", 1)))
        memory.write(record(0, "I run on Tuesdays"))
        memory.write(record(1, "And my dog is called Miso"))

        memory.end_session()

        first, second = [r for r in memory.records if r.kind == "summary"]
        assert (first.id, second.id) == (make_fact_id("s1", 0), make_fact_id("s1", 1))
        assert first.role == "assistant"
        assert first.content == "user / running_day = Tuesday"
        assert first.session_id == "s1"
        # 0013: every message the call read, not only the turn the model named.
        assert first.derived_from == second.derived_from == (make_record_id("s1", 0), make_record_id("s1", 1))
        assert [f.turn_id for f in memory.facts] == [make_record_id("s1", 0), make_record_id("s1", 1)]
        assert len(llm.calls) == 1

    def test_the_call_shows_the_facts_that_hold_and_the_numbered_transcript(self):
        memory, llm = fact_graph(facts(("running_day", "Tuesday"), ("dog_name", "Miso")), facts(("running_day", "Friday")))
        session(memory, "s1", "I run on Tuesdays", "Noted.")
        session(memory, "s2", "Now I run on Fridays", "OK.")
        session(memory, "s3", "hej")

        first, second, third = llm.calls
        assert first[0] == EXTRACTION_SYSTEM_PROMPT
        # One user message: the session is quoted data, not turns to continue.
        assert first[1] == [{
            "role": "user",
            "content": "Facts so far:\n(none)\n\nConversation:\n"
                       "[0] user: I run on Tuesdays\n\n[1] assistant: Noted.",
        }]
        assert second[1][0]["content"] == (
            "Facts so far:\nuser / running_day = Tuesday\nuser / dog_name = Miso\n\nConversation:\n"
            "[0] user: Now I run on Fridays\n\n[1] assistant: OK."
        )
        # A replaced fact is no longer shown to the call; the rest stay oldest first.
        assert third[1][0]["content"].startswith(
            "Facts so far:\nuser / dog_name = Miso\nuser / running_day = Friday\n\n"
        )

    def test_write_never_extracts(self):
        memory, llm = fact_graph()
        for i in range(50):
            memory.write(record(i, f"message {i}"))

        assert llm.calls == []
        assert memory.facts == []

    def test_nothing_happens_on_a_session_without_messages(self):
        memory, llm = fact_graph()
        memory.end_session()
        memory.write(record(0, "hej"))
        memory.end_session()
        memory.end_session()
        memory.write(record(1, "Saved 1 item(s)", role="assistant", kind="outcome"))
        memory.end_session()

        assert len(llm.calls) == 1

    def test_a_second_extraction_for_the_same_session_is_refused(self):
        memory, _ = fact_graph()
        memory.write(record(0, "one"))
        memory.end_session()
        memory.write(record(1, "two"))

        with pytest.raises(ValueError):
            memory.end_session()

    def test_an_outcome_never_enters_the_call_and_stays_verbatim(self):
        memory, llm = fact_graph(facts(("plan", "train tomorrow")))
        memory.write(record(0, "jag ska träna imorgon"))
        memory.write(record(1, "Saved 4 item(s)", role="assistant", kind="outcome"))
        memory.end_session()

        (_, messages), = llm.calls
        assert "Saved 4 item(s)" not in messages[0]["content"]
        assert memory.records[-1].derived_from == (make_record_id("s1", 0),)
        assert "Saved 4 item(s)" in shown(memory.retrieve("saved", at=NOW, budget_tokens=1000))

    def test_the_turn_a_fact_names_is_counted_among_the_messages_only(self):
        memory, _ = fact_graph(facts(("plan", "train tomorrow", 1)))
        memory.write(record(0, "hej"))
        memory.write(record(1, "Saved 4 item(s)", role="assistant", kind="outcome"))
        memory.write(record(2, "jag ska träna imorgon"))
        memory.end_session()

        # The call numbered two turns, and its turn 1 is the record s1:2.
        (fact,) = memory.facts
        assert (fact.turn, fact.turn_id) == (1, make_record_id("s1", 2))

    def test_an_entry_that_is_not_a_fact_is_dropped_and_counted(self):
        reply = {"facts": [
            {"subject": "user", "relation": "siblings", "value": 2, "turn": 0},
            {"subject": "user", "relation": "  city ", "value": " Lund ", "turn": 0},
            {"subject": "user", "relation": "", "value": "x", "turn": 0},
            {"subject": "user", "relation": "likes", "value": True, "turn": 0},
            {"subject": "user", "relation": "car", "value": "Honda", "turn": 7},
            {"subject": "user", "relation": "car", "value": "Honda", "turn": "0"},
            {"subject": "user", "relation": "car", "value": "Honda"},
            "user / car = Honda",
        ]}
        memory, _ = fact_graph(reply)
        session(memory, "s1", "hej")

        # A value sent as a number is taken as its text; names are stripped.
        assert lines(memory) == ["user / siblings = 2", "user / city = Lund"]
        (e,) = memory.extractions
        assert (e.stored, e.dropped) == (2, 6)

    # -- the replacement rule (0018) --

    def test_a_newer_fact_replaces_on_subject_and_relation_case_and_spacing_aside(self):
        memory, _ = fact_graph(
            facts(("wake_up time", "8:30")),
            {"facts": [{"subject": " User", "relation": "Wake_Up   Time", "value": "7:30", "turn": 0}]},
        )
        session(memory, "s1", "I get up at 8:30", at=MAY)
        session(memory, "s2", "I get up at 7:30 now", at=JUNE)

        assert lines(memory, held_at=JUNE) == ["User / Wake_Up   Time = 7:30"]
        assert [e.replaced for e in memory.extractions] == [0, 1]

    def test_another_relation_replaces_nothing(self):
        memory, _ = fact_graph(facts(("recent_5k_time", "27:12")), facts(("personal_best_time", "25:50")))
        session(memory, "s1", "I ran 5k in 27:12", at=MAY)
        session(memory, "s2", "My new best is 25:50", at=JUNE)

        # What the rule is expected to miss: the old value and the new one both hold.
        assert lines(memory, held_at=JUNE) == ["user / recent_5k_time = 27:12", "user / personal_best_time = 25:50"]

    def test_another_subject_replaces_nothing(self):
        memory, _ = fact_graph(
            facts(("car", "Honda")),
            {"facts": [{"subject": "Anna", "relation": "car", "value": "Tesla", "turn": 0}]},
        )
        session(memory, "s1", "I drive a Honda", at=MAY)
        session(memory, "s2", "Anna drives a Tesla", at=JUNE)

        assert lines(memory, held_at=JUNE) == ["user / car = Honda", "Anna / car = Tesla"]

    def test_two_facts_of_one_session_never_replace_each_other(self):
        memory, _ = fact_graph(facts(("pet", "dog"), ("pet", "cat")), facts(("pet", "parrot")))
        session(memory, "s1", "I have a dog and a cat", at=MAY)

        assert lines(memory, held_at=MAY) == ["user / pet = dog", "user / pet = cat"]

        session(memory, "s2", "Now I have a parrot", at=JUNE)

        # A later session's fact replaces every fact that held under the name.
        assert lines(memory, held_at=JUNE) == ["user / pet = parrot"]
        assert [f.replaced_by for f in memory.facts] == [make_fact_id("s2", 0), make_fact_id("s2", 0), None]

    def test_a_fact_said_again_is_not_stored_and_the_older_one_stands(self):
        memory, _ = fact_graph(facts(("pet", "dog")), facts(("PET", " Dog")))
        session(memory, "s1", "I have a dog", at=MAY)
        session(memory, "s2", "My dog is asleep", at=JUNE)

        (fact,) = memory.facts
        assert (fact.id, fact.at, fact.replaced_by) == (make_fact_id("s1", 0), MAY, None)
        assert [e.said_again for e in memory.extractions] == [0, 1]

    def test_a_fact_said_again_is_not_replaced_by_its_own_session(self):
        said_again_first = facts(("pet", "dog"), ("pet", "cat"))
        said_again_last = facts(("pet", "cat"), ("pet", "dog"))

        for reply in (said_again_first, said_again_last):
            memory, _ = fact_graph(facts(("pet", "dog")), reply)
            session(memory, "s1", "I have a dog", at=MAY)
            session(memory, "s2", "I still have the dog, and a cat now", at=JUNE)

            # Whatever the order of the reply: the dog stands and the cat is new.
            assert lines(memory, held_at=JUNE) == ["user / pet = dog", "user / pet = cat"]

    def test_a_fact_twice_in_one_reply_is_stored_once(self):
        memory, _ = fact_graph(facts(("pet", "dog"), ("pet", "Dog"), ("city", "Lund")))
        session(memory, "s1", "I have a dog")

        assert [(f.id, f.line) for f in memory.facts] == [
            (make_fact_id("s1", 0), "user / pet = dog"),
            (make_fact_id("s1", 1), "user / city = Lund"),
        ]
        assert memory.extractions[0].said_again == 1

    def test_an_old_value_said_after_it_was_replaced_is_a_new_fact(self):
        memory, _ = fact_graph(facts(("car", "Honda")), facts(("car", "Tesla")), facts(("car", "Honda")))
        session(memory, "s1", "a Honda", at=MAY)
        session(memory, "s2", "a Tesla", at=JUNE)
        session(memory, "s3", "a Honda again", at=JULY)

        assert [(f.value, f.replaced_by) for f in memory.facts] == [
            ("Honda", make_fact_id("s2", 0)), ("Tesla", make_fact_id("s3", 0)), ("Honda", None),
        ]

    # -- time (0014, 0018) --

    def test_a_fact_is_stamped_with_the_largest_time_seen_not_its_turns(self):
        memory, _ = fact_graph(facts(("pet", "dog", 1)))
        memory.write(record(0, "later", at=LATER))
        memory.write(record(1, "I have a dog", at=NOW))
        memory.end_session()

        assert memory.facts[0].at == LATER

    def test_a_fact_made_after_the_cutoff_is_invisible(self):
        memory, _ = fact_graph(facts(("pet", "dog")))
        memory.write(record(0, "my pet is a dog", at=NOW))
        memory.write(record(1, "after", at=LATER))
        memory.end_session()

        at_now = memory.retrieve("pet", at=NOW, budget_tokens=1000)
        at_later = memory.retrieve("pet", at=LATER, budget_tokens=1000)

        assert shown(at_now) == ["my pet is a dog"]
        assert shown(at_later) == ["user / pet = dog", "my pet is a dog", "after"]

    def test_a_replacement_made_after_the_cutoff_has_not_happened_yet(self):
        memory, _ = fact_graph(facts(("car", "Honda")), facts(("car", "Tesla")))
        session(memory, "s1", "my car is a Honda", at=MAY)
        session(memory, "s2", "my car is a Tesla now", at=JUNE)

        result = memory.retrieve("car", at=MAY, budget_tokens=1000)

        # Nothing stamped after May is in the context: not the new fact, not
        # its turn, and the old fact is still shown as holding.
        assert shown(result) == ["user / car = Honda", "my car is a Honda"]
        assert result.sources == (make_fact_id("s1", 0), make_record_id("s1", 0))

    # -- what retrieve shows (0018) --

    def test_the_facts_come_first_as_one_assistant_message_then_the_window(self):
        memory, _ = fact_graph(facts(("pet", "dog"), ("city", "Lund", 1)))
        session(memory, "s1", "my pet is a dog", "nice")
        memory.write(record(0, "what about my pet and my city?", session_id="s2"))

        result = memory.retrieve("pet city nice", at=NOW, budget_tokens=1000)

        assert result.messages == [
            {"role": "assistant", "content": "user / pet = dog\nuser / city = Lund"},
            {"role": "user", "content": "my pet is a dog"},
            {"role": "assistant", "content": "nice"},
            {"role": "user", "content": "what about my pet and my city?"},
        ]
        assert result.sources == (
            make_fact_id("s1", 0),
            make_fact_id("s1", 1),
            make_record_id("s1", 0),
            make_record_id("s1", 1),
            make_record_id("s2", 0),
        )

    def test_the_facts_are_shown_in_the_order_stored_not_by_rank(self):
        memory, _ = fact_graph(facts(("city", "Lund")), facts(("gym_price", "30")))
        session(memory, "s1", "I live in Lund", at=MAY)
        session(memory, "s2", "the gym price went up to 30", at=JUNE)

        ranking = memory.ranking("gym price in Lund", at=JUNE)
        result = memory.retrieve("gym price in Lund", at=JUNE, budget_tokens=1000)

        # The later fact is the better match, and still comes last: order is
        # the only thing that says which of two lines is the newer.
        assert [f.relation for f in ranking] == ["gym_price", "city"]
        assert shown(result)[0] == "user / city = Lund\nuser / gym_price = 30"

    def test_a_fact_is_ranked_on_its_line_and_the_turn_it_names(self):
        memory, _ = fact_graph(facts(("friend_meetup_count", "twice", 1)))
        session(memory, "s1", "hej", "Good to hear you met Alex again")

        by_turn = memory.retrieve("How many times have I met Alex?", at=NOW, budget_tokens=1000)
        by_line = memory.retrieve("meetup", at=NOW, budget_tokens=1000)

        # The line shares no word with the first question; the turn does. The
        # turn's text is never shown as part of the fact.
        assert shown(by_turn)[0] == "user / friend_meetup_count = twice"
        assert shown(by_line)[0] == "user / friend_meetup_count = twice"

    def test_a_fact_that_shares_no_term_with_the_query_is_never_shown(self):
        memory, _ = fact_graph(facts(("pet", "dog")))
        session(memory, "s1", "I have a dog")

        result = memory.retrieve("saffron", at=NOW, budget_tokens=1000)

        # No facts message: what the baseline would return.
        assert shown(result) == ["I have a dog"]
        assert result.sources == (make_record_id("s1", 0),)

    def test_a_replaced_fact_is_never_shown(self):
        memory, _ = fact_graph(facts(("car", "Honda")), facts(("car", "Tesla")))
        session(memory, "s1", "car", at=MAY)
        session(memory, "s2", "car", at=JUNE)

        result = memory.retrieve("car Honda", at=JUNE, budget_tokens=1000)

        assert shown(result)[0] == "user / car = Tesla"
        assert make_fact_id("s1", 0) not in result.sources

    def test_equal_scores_go_to_the_fact_stored_later(self):
        memory, _ = fact_graph(facts(("a", "bike")), facts(("b", "bike")))
        session(memory, "s1", "x", at=MAY)
        session(memory, "s2", "x", at=JUNE)

        assert [f.relation for f in memory.ranking("bike", at=JUNE)] == ["b", "a"]

    def test_the_statistics_come_from_the_facts_that_hold_at_the_cutoff(self):
        memory, _ = fact_graph(
            facts(("a", "alpha"), ("b", "gamma", 1)),
            facts(("c", "gamma"), ("d", "gamma"), ("e", "gamma"), ("f", "gamma")),
        )
        session(memory, "s1", "x", "y", at=MAY)
        session(memory, "s2", "z", at=JUNE)

        # Seen from May the two words are equally rare, so the tie goes to the
        # later fact.  Counting June's facts would make "gamma" common and put
        # "alpha" first.
        assert [f.relation for f in memory.ranking("alpha gamma", at=MAY)] == ["b", "a"]

    # -- the budget, in tokens (0018) --

    def test_f_is_a_thousand_tokens(self):
        assert FACT_TOKENS == 1000

    def test_the_facts_message_never_counts_more_than_f(self, monkeypatch):
        monkeypatch.setattr(memory_module, "FACT_TOKENS", 40)
        memory, _ = fact_graph(facts(*[(f"pet_{i}", "dog") for i in range(10)]), counter=CharCounter())
        session(memory, "s1", "dog")

        result = memory.retrieve("dog", at=NOW, budget_tokens=1000)

        # Each line is 18 characters and the line break one more: two fit in 40.
        assert len(shown(result)[0]) <= 40
        assert shown(result)[0].count("\n") == 1

    def test_f_is_counted_over_the_message_as_a_whole(self, monkeypatch):
        class PerLine:
            """A counter under which a message costs more than its lines: 10 a line, 5 a line break."""

            def count(self, text: str) -> int:
                return 0 if not text else 10 * len(text.split("\n")) + 5 * text.count("\n")

        monkeypatch.setattr(memory_module, "FACT_TOKENS", 30)
        memory, _ = fact_graph(facts(("a", "dog"), ("b", "dog"), ("c", "dog")), counter=PerLine())
        session(memory, "s1", "dog")

        result = memory.retrieve("dog", at=NOW, budget_tokens=1000)

        # Three lines are 30 as a sum and 40 as one message, so only two are shown.
        assert shown(result)[0].count("\n") == 1
        assert result.tokens_used == 25 + 10

    def test_a_fact_too_large_is_passed_over_and_the_walk_goes_on(self, monkeypatch):
        monkeypatch.setattr(memory_module, "FACT_TOKENS", 30)
        memory, _ = fact_graph(facts(("pet", "dog " * 20), ("pet_name", "dog")), counter=CharCounter())
        session(memory, "s1", "x")

        result = memory.retrieve("dog", at=NOW, budget_tokens=1000)

        # The long fact ranks first and does not fit; the short one is still taken.
        assert memory.ranking("dog", at=NOW)[0].relation == "pet"
        assert shown(result)[0] == "user / pet_name = dog"

    def test_the_window_fills_what_the_facts_left(self):
        memory, _ = fact_graph(facts(("p", "dog")), counter=CharCounter())
        memory.write(record(0, "aaaa dog"))
        memory.write(record(1, "bbbbbbbbbbbb"))
        memory.write(record(2, "cccc"))
        memory.end_session()

        result = memory.retrieve("dog", at=NOW, budget_tokens=20)

        # 14 for the facts message, 4 for the newest, then 12 does not fit and
        # the walk ends there, as the baseline's does (ADR 0007).
        assert shown(result) == ["user / p = dog", "cccc"]
        assert result.tokens_used == 18

    def test_tokens_used_is_what_the_messages_count(self):
        memory, _ = fact_graph(facts(("pet", "dog"), ("city", "Lund")), counter=CharCounter())
        session(memory, "s1", "my pet in the city", "nice")

        result = memory.retrieve("pet city", at=NOW, budget_tokens=1000)

        # The harness recounts every recall this way and refuses a difference.
        assert result.tokens_used == sum(len(m["content"]) for m in result.messages)

    def test_the_facts_never_take_more_than_the_budget(self):
        memory, _ = fact_graph(facts(*[(f"pet_{i}", "dog") for i in range(10)]), counter=CharCounter())
        session(memory, "s1", "dog")

        result = memory.retrieve("dog", at=NOW, budget_tokens=20)

        assert result.tokens_used <= 20

    def test_with_facts_shown_an_oversized_record_is_not_admitted(self):
        memory, _ = fact_graph(facts(("pet", "dog")), counter=CharCounter())
        session(memory, "s1", "dog " * 100)

        result = memory.retrieve("dog", at=NOW, budget_tokens=20)

        assert shown(result) == ["user / pet = dog"]

    # -- deterministic ids --

    def test_ids_and_derived_from_are_the_same_in_two_replays(self):
        def replay():
            memory, _ = fact_graph(facts(("car", "Honda"), ("pet", "dog")), facts(("car", "Tesla")))
            session(memory, "s1", "one", "two", at=MAY)
            session(memory, "s2", "three", at=JUNE)
            result = memory.retrieve("one two three car pet", at=JUNE, budget_tokens=1000)
            return (
                [(f.id, f.turn_id, f.replaced_by) for f in memory.facts],
                [(r.id, r.derived_from) for r in memory.records if r.kind == "summary"],
                result.sources,
            )

        first, second = replay(), replay()

        assert first == second
        assert first[0] == [
            ("fact:s1:0", "s1:0", "fact:s2:0"),
            ("fact:s1:1", "s1:0", None),
            ("fact:s2:0", "s2:0", None),
        ]

    def test_a_fact_id_collides_with_no_other_id(self):
        assert make_fact_id("s1", 0) not in (make_record_id("s1", 0), make_summary_id("s1"))

    # -- failures (0016, 0018) --

    def test_a_failed_call_is_tried_again(self):
        memory, llm = fact_graph(None, {"notes": "x"}, facts(("pet", "dog")))
        session(memory, "s1", "I have a dog")

        # None and a reply without a list of facts are both failures.
        assert len(llm.calls) == EXTRACTION_ATTEMPTS
        assert lines(memory) == ["user / pet = dog"]
        assert not memory.extractions[0].failed

    def test_when_every_attempt_fails_the_session_is_skipped_and_counted(self):
        memory, llm = fact_graph(None, {"facts": "none"}, None)
        session(memory, "s1", "I have a dog")

        # No fact, nothing lost, and the skip is on record.
        assert len(llm.calls) == EXTRACTION_ATTEMPTS
        assert memory.facts == []
        assert shown(memory.retrieve("dog", at=NOW, budget_tokens=1000)) == ["I have a dog"]
        (e,) = memory.extractions
        assert (e.session_id, e.stored, e.failed) == ("s1", 0, True)

    def test_a_skipped_session_replaces_nothing_and_is_not_carried_on(self):
        memory, llm = fact_graph(facts(("car", "Honda")), None, None, None, facts(("city", "Lund")))
        session(memory, "s1", "a Honda", at=MAY)
        session(memory, "s2", "the looping session", at=JUNE)
        session(memory, "s3", "I live in Lund", at=JUNE)

        last = llm.calls[-1][1][0]["content"]
        assert "the looping session" not in last
        assert lines(memory, held_at=JUNE) == ["user / car = Honda", "user / city = Lund"]
        assert memory.records[-1].derived_from == (make_record_id("s3", 0),)
        assert [e.failed for e in memory.extractions] == [False, True, False]

    def test_a_session_with_nothing_to_list_is_not_a_failure(self):
        memory, llm = fact_graph({"facts": []})
        session(memory, "s1", "what is the capital of France?")

        assert len(llm.calls) == 1
        (e,) = memory.extractions
        assert (e.stored, e.failed) == (0, False)

    def test_a_store_that_fails_is_raised(self):
        class BrokenStore(InProcessFactStore):
            def add(self, facts, replaced):
                raise FactStoreError("the database is gone")

        memory, _ = fact_graph(facts(("pet", "dog")), store=BrokenStore())
        memory.write(record(0, "I have a dog"))

        # The machine's failure, not the model's: the harness marks the
        # question an error instead of counting a skipped session.
        with pytest.raises(FactStoreError):
            memory.end_session()

    def test_the_facts_go_to_the_store_it_was_given(self):
        store = InProcessFactStore()
        memory, _ = fact_graph(facts(("pet", "dog")), store=store)
        session(memory, "s1", "I have a dog")

        assert [f.line for f in store.facts()] == ["user / pet = dog"]


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
