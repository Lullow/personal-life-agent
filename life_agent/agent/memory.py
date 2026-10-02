"""Conversation memory, behind a swappable Protocol.

The conversation loop used to own a plain list of messages and truncate it.
That list is now one *strategy* among several, so the strategies can be
compared against each other in a measured evaluation rather than argued about.

Three things the loop must not decide for itself, and therefore live here:

* **what to remember** — :meth:`ConversationMemory.write` is the only way in;
* **what to recall** — :meth:`ConversationMemory.retrieve` returns messages
  ready for the model, together with the record ids they came from;
* **when to compact** — a strategy consolidates on its own schedule.  The
  agent never asks it to, because a shared trigger would make every strategy
  answer to one policy instead of to its own.

Two invariants hold for every implementation, and both are load-bearing:

* ``retrieve(at=T)`` never surfaces a record stamped later than ``T``.  The
  evaluation replays a history step by step and asks what the memory should
  believe at a point in time; a leak invalidates the numbers silently.
* a ``kind="outcome"`` record is a fact read out of the domain database, not
  something the model said.  It survives consolidation verbatim.

See the "Memory layer" section of ``CLAUDE.md``.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

# The window the baseline keeps, in user+assistant pairs.  Unchanged from the
# constant the conversation loop used to hold.
DEFAULT_HISTORY_TURNS = 10

# Room for recalled context in one call.  Generous on purpose: the agent's
# baseline is bounded by its turn window long before it reaches this.  The
# evaluation drops the window and fills this budget instead (ADR 0007).
DEFAULT_BUDGET_TOKENS = 8000

# BM25's two constants, at Lucene's defaults.  ADR 0011 fixes them: the
# evaluation's dry run shows recall for free, so they are not there to be tuned.
BM25_K1 = 1.2
BM25_B = 0.75

RecordKind = Literal["message", "outcome", "summary"]
Role = Literal["user", "assistant"]


def make_record_id(session_id: str, turn_index: int) -> str:
    """Build the id for the *turn_index*-th record of *session_id*.

    Deterministic by construction: replaying one history twice, or replaying it
    through two different strategies, produces the same ids both times.  That
    is what makes retrieval precision and recall comparable between the things
    being compared, so this must never grow a random component.
    """
    return f"{session_id}:{turn_index}"


@dataclass(frozen=True)
class MemoryRecord:
    """One thing worth remembering, stamped in time.

    ``at`` is supplied by the caller rather than read off the clock here, so
    the evaluation can replay a history at whatever pace it likes.  For a
    ``kind="summary"`` record it is the moment consolidation *ran* — never the
    time of the records it derives from, which would walk the summary back past
    a cutoff it should not cross.
    """

    id: str
    role: Role
    content: str
    kind: RecordKind
    at: datetime
    session_id: str
    derived_from: tuple[str, ...] = ()

    def as_message(self) -> dict[str, str]:
        """Render as a chat message, the shape the LLM client expects."""
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class Retrieval:
    """What one recall produced.

    ``messages`` is what the model sees, oldest first, and never includes the
    turn being sent — the loop appends that itself.  ``sources`` is what those
    messages were built from, which for a summarising strategy is the summary's
    own id rather than the ids it swallowed.  That is the honest answer: the
    summary is what reached the context.  Follow ``MemoryRecord.derived_from``
    to expand it.
    """

    messages: list[dict[str, str]]
    sources: tuple[str, ...]
    tokens_used: int


class TokenCounter(Protocol):
    """Counts tokens in a string, for budgeting and for cost reporting."""

    def count(self, text: str) -> int: ...


class ApproxTokenCounter:
    """A dependency-free estimate: roughly four characters to the token.

    Good enough to keep a context window from overflowing, and wrong enough
    that no reported cost figure should come from it — it under-counts
    Swedish, whose compounds split into more tokens than their length suggests.
    The evaluation injects a real tokenizer where the number is published.

    ``evals/longmemeval.py`` refuses one of these rather than warn: a cost
    table built on a four-character heuristic looks exactly like a real one.
    It also recounts every recall with its own tokenizer, which catches a
    strategy that fell back on this default.  See
    ``docs/adr/0003-approx-token-counter-as-the-default.md``.
    """

    _CHARS_PER_TOKEN = 4

    def count(self, text: str) -> int:
        if not text:
            return 0
        return max(1, -(-len(text) // self._CHARS_PER_TOKEN))


class ConversationMemory(Protocol):
    """What the conversation loop needs from a memory strategy."""

    def write(self, record: MemoryRecord) -> None:
        """Remember *record*, consolidating first if this strategy wants to."""
        ...

    def retrieve(
        self, query: str, *, at: datetime, budget_tokens: int
    ) -> Retrieval:
        """Recall context for *query*, as of *at*, within *budget_tokens*."""
        ...

    def end_session(self) -> None:
        """Mark a session boundary.  A strategy may consolidate here."""
        ...


class RecentTurnsMemory:
    """The last N turns and nothing else — the agent's default, and the baseline.

    It ignores *query* entirely: recency is its only notion of relevance.  It
    never consolidates, so it can neither compact an old conversation nor
    correct a fact it recorded earlier.  Both are on purpose.  This is the
    baseline the other two strategies have to beat, and the shape of its
    failures is part of the result.

    One difference from the buffer it replaced, which belongs in the method
    section of any write-up: **the window is applied when recalling, not when
    writing.**  The old code discarded a message the moment it fell out of the
    buffer, so nothing could later ask what it had thrown away.  This keeps
    every record and narrows at :meth:`retrieve`, which is what makes recall
    measurable — the evaluation can ask what the strategy *failed* to surface.
    The consequence is that this class models what a sliding window would have
    found, not what the previous implementation still had in memory.  The
    messages the model sees are identical; the claim being measured is not.
    See ``docs/adr/0002-window-truncates-at-retrieve.md``.

    ``max_turns=None`` removes the window, leaving the token budget as the only
    limit: the most recent messages that fit.  That is how the evaluation runs
    it, so that every strategy gets the same allowance
    (``docs/adr/0007-the-baseline-fills-the-budget.md``).  The agent keeps
    :data:`DEFAULT_HISTORY_TURNS`.
    """

    def __init__(
        self,
        *,
        max_turns: int | None = DEFAULT_HISTORY_TURNS,
        token_counter: TokenCounter | None = None,
    ) -> None:
        self._max_messages = None if max_turns is None else max_turns * 2
        self._counter = token_counter or ApproxTokenCounter()
        self._records: list[MemoryRecord] = []

    @property
    def records(self) -> list[MemoryRecord]:
        """Everything written so far, oldest first.  For tests and the eval."""
        return list(self._records)

    def write(self, record: MemoryRecord) -> None:
        self._records.append(record)

    def retrieve(
        self, query: str, *, at: datetime, budget_tokens: int
    ) -> Retrieval:
        visible = [r for r in self._records if r.at <= at]
        if self._max_messages is None:
            window = visible
        else:
            window = visible[-self._max_messages :] if self._max_messages else []

        # Fill backwards from the newest, so what survives a tight budget is
        # the most recent context rather than the oldest.
        chosen: list[MemoryRecord] = []
        used = 0
        for record in reversed(window):
            cost = self._counter.count(record.content)
            if chosen and used + cost > budget_tokens:
                break
            used += cost
            chosen.append(record)
        chosen.reverse()

        return Retrieval(
            messages=[r.as_message() for r in chosen],
            sources=tuple(r.id for r in chosen),
            tokens_used=used,
        )

    def end_session(self) -> None:
        """Nothing to do: the baseline has no compaction step."""
        return None


_TERM = re.compile(r"[^\W_]+")


def _terms(text: str) -> list[str]:
    """The terms BM25 matches on: runs of letters and digits, case folded."""
    return _TERM.findall(text.casefold())


class RetrievalMemory:
    """Recall by relevance to the query, over everything ever written.

    Every record is ranked against *query* with BM25: a score built from the
    words the two share, where a rare word counts for more than a common one
    and a long record is not favoured for its length.  Recall then fills the
    budget in rank order.  It keeps everything and corrects nothing, so when a
    fact has changed it can return the old value and the new one side by side.
    That is on purpose: it is what this strategy is expected to fail at.

    Three things are decided in
    ``docs/adr/0011-retrieval-ranks-turns-with-bm25.md`` and must not drift:

    * **The messages come back in the order they were written**, not by rank.
      Order is the only thing that tells the model which of two values is the
      newer one.
    * **The statistics come from the visible records only.**  How rare a word
      is, and how long an average record is, are computed at :meth:`retrieve`
      over the records at or before the cutoff, so a later record cannot move
      the ranking either.
    * **The budget is never exceeded.**  A record that does not fit is passed
      over and the walk down the ranking goes on.  Unlike the baseline, a
      single oversized record does not come back alone.

    The matching is lexical, with no stemming and no stopword list: "graduate"
    does not match "graduated".
    """

    def __init__(self, *, token_counter: TokenCounter | None = None) -> None:
        self._counter = token_counter or ApproxTokenCounter()
        self._records: list[MemoryRecord] = []
        # How often each term occurs in each record, in step with _records.
        self._term_counts: list[Counter[str]] = []

    @property
    def records(self) -> list[MemoryRecord]:
        """Everything written so far, oldest first.  For tests and the eval."""
        return list(self._records)

    def write(self, record: MemoryRecord) -> None:
        self._records.append(record)
        self._term_counts.append(Counter(_terms(record.content)))

    def retrieve(
        self, query: str, *, at: datetime, budget_tokens: int
    ) -> Retrieval:
        visible = [i for i, r in enumerate(self._records) if r.at <= at]
        scores = self._scores(query, visible)
        # Best match first; between equal scores, the record written later.
        ranked = sorted(
            (i for i in visible if scores[i] > 0),
            key=lambda i: (-scores[i], -i),
        )

        chosen: list[int] = []
        used = 0
        for i in ranked:
            cost = self._counter.count(self._records[i].content)
            if used + cost > budget_tokens:
                continue
            used += cost
            chosen.append(i)
        chosen.sort()

        records = [self._records[i] for i in chosen]
        return Retrieval(
            messages=[r.as_message() for r in records],
            sources=tuple(r.id for r in records),
            tokens_used=used,
        )

    def end_session(self) -> None:
        """Nothing to do: nothing is compacted, so a boundary changes nothing."""
        return None

    def _scores(self, query: str, visible: list[int]) -> dict[int, float]:
        """BM25 of every visible record against *query*, by record position."""
        scores = dict.fromkeys(visible, 0.0)
        if not visible:
            return scores
        lengths = {i: sum(self._term_counts[i].values()) for i in visible}
        average = sum(lengths.values()) / len(visible)
        # Sorted, so the floats are summed in one order whatever the hash seed.
        for term in sorted(set(_terms(query))):
            holders = [i for i in visible if term in self._term_counts[i]]
            if not holders:
                continue
            idf = math.log(
                1 + (len(visible) - len(holders) + 0.5) / (len(holders) + 0.5)
            )
            for i in holders:
                tf = self._term_counts[i][term]
                norm = 1 - BM25_B + BM25_B * lengths[i] / average
                scores[i] += idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * norm)
        return scores
