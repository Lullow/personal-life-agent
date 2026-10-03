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

# The consolidator's size S, in tokens (ADR 0015).  The prompt asks for it in
# words; the strategy holds it in tokens, by asking once more and then by
# cutting, so the summary never takes more than this of the budget.  ADR 0012
# had it as a target only, and the model wrote eight times that.
SUMMARY_TARGET_TOKENS = 1000

# A consolidation call that returns None is tried this many times in all,
# as an answer call is (ADR 0008, 0015).
CONSOLIDATION_ATTEMPTS = 3

# ADR 0015, copied from the record's code blocks.  Fixed before the strategy's
# first run under that record, like BM25's constants: the dry run shows this
# strategy's recall without a model call (ADR 0013), so the prompt is not
# there to be tuned either.  It lives here and not in prompts.py because it is
# the memory strategy's, not the agent's, and it runs outside the turn: the
# reply is one string, and nothing dispatches on it.
CONSOLIDATION_SYSTEM_PROMPT = (
    "You keep the assistant's notes about its earlier conversations with the user.\n"
    "Hard limit: the notes are at most 750 words. Write plain prose or short lines:\n"
    "no links, no markdown, no lists of products or sources. You are given the\n"
    "notes so far and the transcript of one more conversation. Rewrite the notes so\n"
    "that they also cover this conversation, within the limit: keep what is about\n"
    "the user (names, numbers, dates, places, plans, preferences, what they asked\n"
    "for) and drop detail about anything else first. When a fact has changed, write\n"
    "the current value in place of the old one. Keep the notes in the language of\n"
    'the conversation. Reply with a JSON object: {"summary": "<the notes>"}.'
)

# The second call, when the first reply counts more than S (ADR 0015).
CONSOLIDATION_REASK_MESSAGE = (
    "These notes are {words} words, over the limit of 750. Rewrite them to at\n"
    "most 750 words: keep what is about the user and the current value of every\n"
    "fact, and drop detail about anything else first. Reply with a JSON object:\n"
    '{{"summary": "<the notes>"}}.\n'
    "\n"
    "Notes:\n"
    "{notes}"
)

# Where a cut may fall: after a sentence end or a line break (ADR 0015).
_SENTENCE_END = re.compile(r"[.!?]|\n")

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


def make_summary_id(session_id: str) -> str:
    """Build the id of the summary made when *session_id* ended (ADR 0012).

    Deterministic for the same reason as :func:`make_record_id`, and shaped so
    that it can never collide with one: a turn id ends in a number, this one
    starts with a word no session is named.
    """
    return f"summary:{session_id}"


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


class Consolidator(Protocol):
    """The one call :class:`ConsolidatingMemory` makes: the loop's JSON contract."""

    def chat_json(
        self, system_prompt: str, messages: list[dict[str, str]]
    ) -> dict | None: ...


class ConsolidationError(RuntimeError):
    """Kept for callers that catch it; since ADR 0016 the strategy skips a
    session it cannot summarise instead of raising."""


def consolidation_message(previous: str | None, turns: list[MemoryRecord]) -> str:
    """The user message of a consolidation call, as ADR 0015 states it.

    The session goes in as quoted transcript, not as chat turns: the model is
    to summarise the conversation, not continue it, and an instruction inside
    a turn stays something the user once said.
    """
    transcript = "\n\n".join(f"{r.role}: {r.content}" for r in turns)
    return f"Notes so far:\n{previous or '(none)'}\n\nConversation to add:\n{transcript}"


def cut_to_tokens(text: str, limit: int, counter: TokenCounter) -> str:
    """Cut *text* after the last sentence end at which it counts at most *limit*.

    A sentence end is ``.``, ``!``, ``?`` or a line break (ADR 0015).  If no
    sentence end leaves anything, the cut falls after the last word that fits.
    Works with any counter, since it only ever counts: the candidates are
    tried from the end, so the first that fits is the longest.
    """
    if counter.count(text) <= limit:
        return text
    ends = [m.end() for m in _SENTENCE_END.finditer(text)]
    for end in reversed(ends):
        candidate = text[:end].rstrip()
        if candidate and counter.count(candidate) <= limit:
            return candidate
    words = text.split()
    for n in range(len(words) - 1, 0, -1):
        candidate = " ".join(words[:n])
        if counter.count(candidate) <= limit:
            return candidate
    return ""


@dataclass(frozen=True)
class Consolidation:
    """What one :meth:`ConsolidatingMemory.end_session` did, for the evaluation's row.

    ``failed`` means the session was skipped (ADR 0016): no summary was made,
    the notes stayed as they were, and ``tokens`` is 0.
    """

    session_id: str
    tokens: int
    reasked: bool
    truncated: bool
    failed: bool = False


class ConsolidatingMemory:
    """A rolling summary, rewritten after every session, over a recent window.

    This is the strategy the third hypothesis is about: when a fact changes,
    the notes are meant to carry the new value in place of the old one, where
    :class:`RetrievalMemory` would return both.  What it pays is a model call
    per session and a window S tokens smaller than the baseline's.

    Its rules are decided in ADRs 0015, 0016, 0013 and 0014 and must not drift:

    * **Consolidation happens in** :meth:`end_session` **and nowhere else.**  One
      call reads the notes so far and the session's ``kind="message"`` records
      as quoted transcript and writes the next notes.  An ``outcome`` never
      enters the call and is never paraphrased.  Raw records are kept: the
      summary is a view over them, not a replacement.
    * **The summary never counts more than S tokens.**  A reply over S is
      asked for once more with its word count; a second reply over S is cut
      after the last sentence end that fits.  Both are recorded in
      :attr:`consolidations`, since a cut summary is one the model did not
      make.  Under ADR 0012, which only asked, the model wrote eight times S.
    * **A session the consolidator cannot summarise is skipped** (ADR 0016),
      never fatal: the model loops at temperature 0 on some inputs, and the
      loop returns on every attempt.  The skip is recorded too.
    * **Recall is the newest visible summary first, then the window.**  The
      summary is an assistant message; the raw records that fit in the rest of
      the budget follow in the order they were written, filled backwards from
      the newest as the baseline fills.  Without a visible summary the strategy
      returns what the baseline would.
    * **The clock is the latest** ``at`` **seen in** :meth:`write`.  A summary is
      stamped with it, never with the wall clock, which in a replay would put
      it past every cutoff, and never backdated.
    * **``derived_from`` is flat**: every message id the notes cover, so the
      evaluation can tell "the consolidator never saw it" from "it saw it and
      lost it" without walking a chain (ADR 0013).
    """

    def __init__(
        self, llm: Consolidator, *, token_counter: TokenCounter | None = None
    ) -> None:
        self._llm = llm
        self._counter = token_counter or ApproxTokenCounter()
        # Everything, raw records and summaries alike, in the order it arrived.
        self._records: list[MemoryRecord] = []
        # The messages written since the last consolidation.
        self._pending: list[MemoryRecord] = []
        self._latest_summary: MemoryRecord | None = None
        self._clock: datetime | None = None
        self._consolidations: list[Consolidation] = []

    @property
    def records(self) -> list[MemoryRecord]:
        """Everything written or summarised so far, oldest first.  For tests and the eval."""
        return list(self._records)

    @property
    def consolidations(self) -> list[Consolidation]:
        """One entry per summary made, in order: its size, and whether it was asked again or cut."""
        return list(self._consolidations)

    def write(self, record: MemoryRecord) -> None:
        self._records.append(record)
        if self._clock is None or record.at > self._clock:
            self._clock = record.at
        if record.kind == "message":
            self._pending.append(record)

    def retrieve(
        self, query: str, *, at: datetime, budget_tokens: int
    ) -> Retrieval:
        summaries = [r for r in self._records if r.kind == "summary" and r.at <= at]
        raw = [r for r in self._records if r.kind != "summary" and r.at <= at]
        summary = summaries[-1] if summaries else None
        used = self._counter.count(summary.content) if summary else 0

        # The baseline's fill (ADR 0007), into what the summary left.  With a
        # summary in hand the first raw record that does not fit ends the walk;
        # without one the newest record is always admitted, as the baseline does.
        window: list[MemoryRecord] = []
        for record in reversed(raw):
            cost = self._counter.count(record.content)
            if (summary or window) and used + cost > budget_tokens:
                break
            used += cost
            window.append(record)
        window.reverse()

        shown = ([summary] if summary else []) + window
        return Retrieval(
            messages=[r.as_message() for r in shown],
            sources=tuple(r.id for r in shown),
            tokens_used=used,
        )

    def end_session(self) -> None:
        """Rewrite the notes to cover the session that just ended.

        Nothing happens when no message was written since the last time.  If
        every attempt fails the session is skipped (ADR 0016): the records stay
        as they are, the notes stay as they were, and the skip is recorded in
        :attr:`consolidations`, so a half-made summary never reaches a context
        and a failure never goes uncounted.
        """
        if not self._pending:
            return None
        session_id = self._pending[-1].session_id
        summary_id = make_summary_id(session_id)
        if any(r.id == summary_id for r in self._records):
            raise ValueError(f"a summary for session {session_id!r} already exists")

        previous = self._latest_summary
        text = self._ask(consolidation_message(previous.content if previous else None, self._pending))
        if text is None:
            # ADR 0016: the session is skipped.  The notes stay as they were,
            # the turns stay raw, and derived_from is not extended with them.
            self._consolidations.append(Consolidation(session_id, 0, False, False, failed=True))
            self._pending = []
            return None
        # ADR 0015: over S, ask once more with the number; still over, cut.
        # ADR 0016: an ask-again that fails falls back on the first reply.
        reasked = truncated = False
        if self._counter.count(text) > SUMMARY_TARGET_TOKENS:
            reasked = True
            text = self._ask(CONSOLIDATION_REASK_MESSAGE.format(words=len(text.split()), notes=text)) or text
        if self._counter.count(text) > SUMMARY_TARGET_TOKENS:
            truncated = True
            text = cut_to_tokens(text, SUMMARY_TARGET_TOKENS, self._counter)

        assert self._clock is not None  # a pending record has set it
        summary = MemoryRecord(
            id=summary_id,
            role="assistant",
            content=text,
            kind="summary",
            at=self._clock,
            session_id=session_id,
            derived_from=(previous.derived_from if previous else ())
            + tuple(r.id for r in self._pending),
        )
        self._records.append(summary)
        self._latest_summary = summary
        self._consolidations.append(
            Consolidation(session_id, self._counter.count(text), reasked, truncated)
        )
        self._pending = []
        return None

    def _ask(self, message: str) -> str | None:
        """One consolidation call, tried up to CONSOLIDATION_ATTEMPTS times; None when all failed."""
        messages = [{"role": "user", "content": message}]
        for _ in range(CONSOLIDATION_ATTEMPTS):
            reply = self._llm.chat_json(CONSOLIDATION_SYSTEM_PROMPT, messages)
            if reply is not None and isinstance(reply.get("summary"), str) and reply["summary"].strip():
                return reply["summary"]
        return None
