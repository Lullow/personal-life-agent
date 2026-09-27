"""Tests for the memory layer.

Two kinds of test live here.  :class:`TestMemoryContract` is parametrised over
every strategy and asserts the rules that hold for all of them — it is the
harness the next two implementations plug into, and a strategy that cannot pass
it is not finished.  The rest test :class:`RecentTurnsMemory` specifically,
including the window behaviour the conversation loop used to implement itself.
"""

from datetime import datetime, timedelta

import pytest

from life_agent.agent.memory import (
    ApproxTokenCounter,
    MemoryRecord,
    RecentTurnsMemory,
    make_record_id,
)

NOW = datetime(2026, 9, 6, 12, 0, 0)
LATER = NOW + timedelta(hours=1)

# Every strategy, built fresh.  Add the next two here and the contract below
# starts applying to them without a line of new test code.
STRATEGIES = [
    pytest.param(lambda: RecentTurnsMemory(max_turns=10), id="recent-turns"),
    pytest.param(lambda: RecentTurnsMemory(max_turns=None), id="recent-turns-no-window"),
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

        result = memory.retrieve("q", at=NOW, budget_tokens=1000)

        contents = [m["content"] for m in result.messages]
        assert "before" in contents
        assert "after" not in contents

    def test_the_cutoff_is_inclusive_of_its_own_instant(self, memory):
        memory.write(record(0, "exactly now", at=NOW))

        result = memory.retrieve("q", at=NOW, budget_tokens=1000)

        assert [m["content"] for m in result.messages] == ["exactly now"]

    def test_an_outcome_survives_a_session_boundary(self, memory):
        memory.write(record(0, "jag ska träna imorgon"))
        memory.write(
            record(1, "Saved 4 item(s)", role="assistant", kind="outcome")
        )

        memory.end_session()

        result = memory.retrieve("vad sparade jag?", at=LATER, budget_tokens=1000)
        # Verbatim: the database had the last word, and a strategy that
        # paraphrases it during consolidation has broken that.
        assert "Saved 4 item(s)" in [m["content"] for m in result.messages]

    def test_sources_accompany_the_messages(self, memory):
        memory.write(record(0, "hej"))

        result = memory.retrieve("q", at=NOW, budget_tokens=1000)

        assert result.messages
        assert result.sources
        assert len(set(result.sources)) == len(result.sources)

    def test_recall_reports_what_it_spent(self, memory):
        memory.write(record(0, "a message with some length to it"))

        result = memory.retrieve("q", at=NOW, budget_tokens=1000)

        assert result.tokens_used > 0

    def test_a_budget_is_not_exceeded(self, memory):
        for i in range(10):
            memory.write(record(i, f"message number {i} with padding"))

        result = memory.retrieve("q", at=NOW, budget_tokens=5)

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


class TestApproxTokenCounter:
    def test_empty_text_costs_nothing(self):
        assert ApproxTokenCounter().count("") == 0

    def test_any_text_costs_at_least_one(self):
        assert ApproxTokenCounter().count("a") == 1

    def test_cost_grows_with_length(self):
        counter = ApproxTokenCounter()
        assert counter.count("x" * 400) > counter.count("x" * 40)
