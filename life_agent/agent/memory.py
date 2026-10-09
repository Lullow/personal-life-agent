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

from life_agent.agent.fact_store import Fact, FactStore, InProcessFactStore, normalise

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

# The fact graph's F, in tokens (ADR 0018): the most the facts message may
# count, the message as a whole and not the sum of its lines.
FACT_TOKENS = 1000

# An extraction call that fails is tried this many times in all, as a
# consolidation call is (ADR 0016, 0018).
EXTRACTION_ATTEMPTS = 3

# ADR 0018, copied from the record's code block: round three of the spike,
# word for word.  Fixed before the strategy's first run, and here rather than
# in prompts.py for the consolidator's reasons: it is the memory strategy's,
# it runs outside the turn, one JSON object comes back and nothing dispatches
# on it.
EXTRACTION_SYSTEM_PROMPT = (
    "You keep the assistant's memory of facts about the user. You are given the\n"
    "facts so far and the transcript of one more conversation between the user\n"
    "and the assistant, every turn numbered in brackets. List what the user says\n"
    "in this conversation about themselves and about the people, places and\n"
    "things in their life: what they have, like, do, plan and have done, with the\n"
    "names, numbers, dates and places. Leave out general knowledge, the\n"
    "assistant's advice, and what the user only asks about.\n"
    'Each fact is one triple with the turn it comes from. subject: "user", or the\n'
    "name of the person or thing the fact is about. relation: what is said about\n"
    "the subject, as a short name in English, lower_snake_case (blood_type,\n"
    "dentist_name, number_of_siblings). value: the value, as short as the\n"
    "conversation allows, in the language of the conversation. turn: the number\n"
    "of the turn.\n"
    "A fact with the subject and relation of a fact so far replaces it. So when\n"
    "the user gives a newer value for one of the facts so far, use exactly its\n"
    "subject and relation; and give a fact about another person, thing or\n"
    "occasion a relation of its own, one that says which: a second allergy is not\n"
    "a newer value for the first. When the conversation gives two values for the\n"
    "same thing, give only the current one. Reply with a JSON object:\n"
    '{"facts": [{"subject": "...", "relation": "...", "value": "...", "turn": 0}]}.\n'
    'With nothing to list, reply {"facts": []}.'
)

# A sentence end, after which a cut may fall (ADR 0017).
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


def make_fact_id(session_id: str, n: int) -> str:
    """Build the id of the *n*-th fact stored from *session_id* (ADR 0018).

    Deterministic for the same reason as :func:`make_record_id`, and shaped
    like :func:`make_summary_id` so that it collides with neither.
    """
    return f"fact:{session_id}:{n}"


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


def _bm25(query: str, term_counts: dict[int, Counter[str]]) -> dict[int, float]:
    """BM25 of every document against *query* (ADR 0011), by the keys of *term_counts*.

    The statistics, how rare a term is and how long an average document is,
    come from the documents given and from no others.
    """
    scores = dict.fromkeys(term_counts, 0.0)
    if not term_counts:
        return scores
    lengths = {i: sum(counts.values()) for i, counts in term_counts.items()}
    average = sum(lengths.values()) / len(term_counts)
    # Sorted, so the floats are summed in one order whatever the hash seed.
    for term in sorted(set(_terms(query))):
        holders = [i for i, counts in term_counts.items() if term in counts]
        if not holders:
            continue
        idf = math.log(
            1 + (len(term_counts) - len(holders) + 0.5) / (len(holders) + 0.5)
        )
        for i in holders:
            tf = term_counts[i][term]
            norm = 1 - BM25_B + BM25_B * lengths[i] / average
            scores[i] += idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * norm)
    return scores


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
        return _bm25(query, {i: self._term_counts[i] for i in visible})


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


def keep_last_tokens(text: str, limit: int, counter: TokenCounter) -> str:
    """Drop the beginning of *text* so that what is left counts at most *limit*.

    The cut falls at a sentence start: the position after a ``.``, ``!``,
    ``?`` or line break, leading whitespace dropped (ADR 0017).  The notes are
    written oldest first, so this forgets the oldest first, as the baseline's
    window does.  If no sentence start leaves a part that fits, the last words
    that fit are kept.  Works with any counter, since it only ever counts: the
    candidates are tried from the start, so the first that fits is the longest.
    """
    if counter.count(text) <= limit:
        return text
    for m in _SENTENCE_END.finditer(text):
        candidate = text[m.end():].strip()
        if candidate and counter.count(candidate) <= limit:
            return candidate
    words = text.split()
    for n in range(1, len(words)):
        candidate = " ".join(words[n:])
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

    Its rules are decided in ADRs 0015–0017, 0013 and 0014 and must not drift:

    * **Consolidation happens in** :meth:`end_session` **and nowhere else.**  One
      call reads the notes so far and the session's ``kind="message"`` records
      as quoted transcript and writes the next notes.  An ``outcome`` never
      enters the call and is never paraphrased.  Raw records are kept: the
      summary is a view over them, not a replacement.
    * **The summary never counts more than S tokens.**  A reply over S is
      asked for once more with its word count; a second reply over S is cut
      from the start, at a sentence start, so the oldest notes go first (ADR
      0017).  Both are recorded in :attr:`consolidations`, since a cut summary
      is one the model did not make.  Under ADR 0012, which only asked, the
      model wrote eight times S; under 0015 the cut fell two sessions in three.
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
            text = keep_last_tokens(text, SUMMARY_TARGET_TOKENS, self._counter)

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


def extraction_message(held: list[Fact], turns: list[MemoryRecord]) -> str:
    """The user message of an extraction call, as ADR 0018 states it.

    The facts that hold come first, oldest first, for the model to reuse their
    names.  The session follows as quoted transcript, as the consolidator gets
    it, with every turn numbered so that a fact can name the turn it comes from.
    """
    facts = "\n".join(fact.line for fact in held)
    transcript = "\n\n".join(f"[{n}] {r.role}: {r.content}" for n, r in enumerate(turns))
    return f"Facts so far:\n{facts or '(none)'}\n\nConversation:\n{transcript}"


def _well_formed(entries: list, turns: int) -> tuple[list[tuple[str, str, str, int]], int]:
    """The entries of a reply that are facts (ADR 0018), and how many were dropped.

    An entry is a fact when its subject, relation and value are non-empty
    strings and its turn is the number of a turn in the call.
    """
    kept: list[tuple[str, str, str, int]] = []
    dropped = 0
    for entry in entries:
        fact = entry if isinstance(entry, dict) else {}
        value = fact.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)  # a count sent as a number is still a value
        texts = (fact.get("subject"), fact.get("relation"), value)
        turn = fact.get("turn")
        if not (
            all(isinstance(t, str) and t.strip() for t in texts)
            and isinstance(turn, int)
            and not isinstance(turn, bool)
            and 0 <= turn < turns
        ):
            dropped += 1
            continue
        subject, relation, value = (t.strip() for t in texts)
        kept.append((subject, relation, value, turn))
    return kept, dropped


def _name(subject: str, relation: str) -> tuple[str, str]:
    """What a fact is replaced on (ADR 0018): its subject and relation, case and spacing aside."""
    return normalise(subject), normalise(relation)


@dataclass(frozen=True)
class Extraction:
    """What one :meth:`FactGraphMemory.end_session` did, for the evaluation's row.

    ``said_again`` counts the facts not stored because a fact that held, or an
    earlier one of the same reply, already said them; ``dropped`` the entries
    that were not facts.  ``failed`` means the session was skipped: every
    attempt failed, nothing was stored and nothing was replaced.
    """

    session_id: str
    stored: int = 0
    said_again: int = 0
    dropped: int = 0
    replaced: int = 0
    failed: bool = False


class FactGraphMemory:
    """Timestamped facts, replaced on the name, over a recent window.

    After every session one call lists what the user said about themselves as
    (subject, relation, value) triples.  Each is stored once, with the time it
    was extracted, and a newer fact with the subject and relation of an older
    one replaces it.  Where :class:`ConsolidatingMemory` rewrites one text held
    to S tokens, this store is held to no size, and the facts shown are chosen
    for each question.  What it pays is a model call per session, and a rule
    that replaces on the name alone: two unrelated facts under one general name
    replace each other too.

    Its rules are decided in ADR 0018, with 0013 and 0014, and must not drift:

    * **Extraction happens in** :meth:`end_session` **and nowhere else.**  One
      call reads the facts that hold and the session's ``kind="message"``
      records as quoted transcript.  An ``outcome`` never enters the call and
      is never paraphrased.  Raw records are kept, in the process.
    * **The code replaces, not the model.**  A fact replaces every fact from
      an earlier session that holds and has its subject and relation, case and
      spacing aside.  Two facts of one session never replace each other.
    * **A fact said again is not stored.**  The older one stands, with its
      time and where it came from, and no fact of that session replaces it.
    * **A replaced fact is kept**, marked with the fact that replaced it and
      with that fact's time, so what held at an earlier time can be asked for.
      It is never shown once replaced, marked or unmarked.
    * **The clock is the latest** ``at`` **seen in** :meth:`write` (ADR 0014).
      A fact is stamped with it when it is extracted, never with the time of
      its turn.
    * **Recall is the facts message first, then the window.**  The facts that
      hold at the cutoff are ranked against the query with ADR 0011's BM25,
      each on its line and the turn the model named for it.  Those that fit in
      F tokens are shown as one assistant message, a line each, in the order
      they were stored.  The raw records that fit in the rest of the budget
      follow, filled as the baseline fills.  Without a fact to show the
      strategy returns what the baseline would.
    * **A session the model cannot handle is skipped** (ADR 0016), never
      fatal, and the skip is recorded in :attr:`extractions`.  A store that
      fails is the machine's failure, and is raised.
    * **Each fact is a** ``kind="summary"`` **record** whose ``derived_from``
      is every message its extraction read, so "evidence consolidated" means
      what ADR 0013 says: the call read it.
    * **The facts live in a store of their own**, behind
      :class:`~life_agent.agent.fact_store.FactStore`: Neo4j in a measured
      run, a list in the process for the tests and the dry run.
    """

    def __init__(
        self,
        llm: Consolidator,
        *,
        store: FactStore | None = None,
        token_counter: TokenCounter | None = None,
    ) -> None:
        self._llm = llm
        self._store = store if store is not None else InProcessFactStore()
        self._counter = token_counter or ApproxTokenCounter()
        # The raw records, in the order they arrived, and their text by id.
        self._records: list[MemoryRecord] = []
        self._content: dict[str, str] = {}
        # The messages written since the last extraction.
        self._pending: list[MemoryRecord] = []
        # By session, the ids of the messages its extraction read.
        self._read: dict[str, tuple[str, ...]] = {}
        self._clock: datetime | None = None
        self._extractions: list[Extraction] = []

    @property
    def records(self) -> list[MemoryRecord]:
        """The raw records, oldest first, then every fact as a record, in the order stored.  For tests and the eval."""
        return list(self._records) + [self._as_record(fact) for fact in self._store.facts()]

    @property
    def facts(self) -> list[Fact]:
        """Every fact stored, replaced ones included, in the order stored.  For tests and the eval."""
        return self._store.facts()

    @property
    def extractions(self) -> list[Extraction]:
        """One entry per session extracted or skipped, in order."""
        return list(self._extractions)

    def write(self, record: MemoryRecord) -> None:
        self._records.append(record)
        self._content[record.id] = record.content
        if self._clock is None or record.at > self._clock:
            self._clock = record.at
        if record.kind == "message":
            self._pending.append(record)

    def retrieve(
        self, query: str, *, at: datetime, budget_tokens: int
    ) -> Retrieval:
        held = self._store.held(at)
        # Walking down the ranking, a fact is taken if the message with its
        # line added still counts at most F, and passed over if not.  The
        # message never takes more than the budget either.
        limit = min(FACT_TOKENS, budget_tokens)
        taken: list[int] = []
        text = ""
        for i in self._ranked(query, held):
            trial = sorted(taken + [i])
            trial_text = "\n".join(held[j].line for j in trial)
            if self._counter.count(trial_text) <= limit:
                taken, text = trial, trial_text
        used = self._counter.count(text) if taken else 0

        # The baseline's fill (ADR 0007), into what the facts left, as
        # ConsolidatingMemory fills beside its summary.
        window: list[MemoryRecord] = []
        for record in reversed([r for r in self._records if r.at <= at]):
            cost = self._counter.count(record.content)
            if (taken or window) and used + cost > budget_tokens:
                break
            used += cost
            window.append(record)
        window.reverse()

        facts_message = [{"role": "assistant", "content": text}] if taken else []
        return Retrieval(
            messages=facts_message + [r.as_message() for r in window],
            sources=tuple(held[i].id for i in taken) + tuple(r.id for r in window),
            tokens_used=used,
        )

    def ranking(self, query: str, *, at: datetime) -> list[Fact]:
        """The facts that hold at *at*, best match for *query* first.  For tests and the eval.

        A fact that shares no term with *query* is left out, as it is never shown.
        """
        held = self._store.held(at)
        return [held[i] for i in self._ranked(query, held)]

    def end_session(self) -> None:
        """Extract the facts of the session that just ended, and replace what they replace.

        Nothing happens when no message was written since the last time.  If
        every attempt fails the session is skipped: no fact is stored, nothing
        is replaced, the turns stay as raw records, and the skip is recorded
        in :attr:`extractions`.
        """
        if not self._pending:
            return None
        turns = self._pending
        session_id = turns[-1].session_id
        if session_id in self._read:
            raise ValueError(f"the facts of session {session_id!r} are already extracted")
        assert self._clock is not None  # a pending record has set it

        held = self._store.held(self._clock)
        entries = self._ask(extraction_message(held, turns))
        self._pending = []
        if entries is None:
            self._extractions.append(Extraction(session_id, failed=True))
            return None

        triples, dropped = _well_formed(entries, len(turns))
        # 1. A fact that holds, or an earlier one of this reply, said again:
        #    not stored, and the older fact is not replaced by this session.
        held_ids: dict[tuple[str, str, str], list[str]] = {}
        for fact in held:
            held_ids.setdefault((*_name(fact.subject, fact.relation), normalise(fact.value)), []).append(fact.id)
        new: list[Fact] = []
        seen: set[tuple[str, str, str]] = set()
        confirmed: set[str] = set()
        said_again = 0
        for subject, relation, value, turn in triples:
            triple = (*_name(subject, relation), normalise(value))
            if triple in held_ids or triple in seen:
                confirmed.update(held_ids.get(triple, ()))
                said_again += 1
                continue
            seen.add(triple)
            new.append(
                Fact(
                    id=make_fact_id(session_id, len(new)),
                    subject=subject,
                    relation=relation,
                    value=value,
                    session_id=session_id,
                    turn=turn,
                    turn_id=turns[turn].id,
                    at=self._clock,
                )
            )
        # 2. Every other fact is stored, and replaces what held under its
        #    name.  Every fact that held is from an earlier session; where two
        #    facts of this one share a name, an old fact is marked with the
        #    first of them in the reply.
        replaced: dict[str, str] = {}
        for fact in new:
            for old in held:
                if old.id not in confirmed and _name(old.subject, old.relation) == _name(fact.subject, fact.relation):
                    replaced.setdefault(old.id, fact.id)

        self._store.add(new, replaced)
        self._read[session_id] = tuple(r.id for r in turns)
        self._extractions.append(
            Extraction(session_id, stored=len(new), said_again=said_again, dropped=dropped, replaced=len(replaced))
        )
        return None

    def _ranked(self, query: str, held: list[Fact]) -> list[int]:
        """Positions in *held* by BM25 against *query*, best first; between equal scores, the fact stored later.

        A fact is ranked on its line followed by the text of the turn the
        model named for it, and the statistics come from those texts alone.
        """
        term_counts = {
            i: Counter(_terms(f"{fact.line} {self._content.get(fact.turn_id, '')}"))
            for i, fact in enumerate(held)
        }
        scores = _bm25(query, term_counts)
        return sorted((i for i in scores if scores[i] > 0), key=lambda i: (-scores[i], -i))

    def _as_record(self, fact: Fact) -> MemoryRecord:
        return MemoryRecord(
            id=fact.id,
            role="assistant",
            content=fact.line,
            kind="summary",
            at=fact.at,
            session_id=fact.session_id,
            derived_from=self._read.get(fact.session_id, ()),
        )

    def _ask(self, message: str) -> list | None:
        """One extraction call, tried up to EXTRACTION_ATTEMPTS times; the reply's entries, or None when all failed."""
        messages = [{"role": "user", "content": message}]
        for _ in range(EXTRACTION_ATTEMPTS):
            reply = self._llm.chat_json(EXTRACTION_SYSTEM_PROMPT, messages)
            if reply is not None and isinstance(reply.get("facts"), list):
                return reply["facts"]
        return None
