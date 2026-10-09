# 0014 — The strategy's clock is the latest time it has been given

Status: accepted
Date: 2026-10-03

## Context

A `kind="summary"` record carries the time consolidation ran, never the time
of the records it derives from (`CLAUDE.md`). `retrieve(at=T)` must never
surface a record with `at > T`. Both rules are enforced on `at`, and a
summary's `at` has to come from somewhere.

`end_session()` takes no argument, and `MemoryRecord.at` is supplied by the
caller so that a replay can run at any pace. The strategy therefore has no
clock of its own. The three sources it could have:

- **The wall clock.** In a replay every record is dated in 2023, and the
  question is asked at `retrieve(at=<23:59 on its day>)`. A summary stamped
  with today's date is later than every `T`, is never visible, and the
  strategy is measured as a baseline with S tokens less. Backwards is worse:
  stamping a summary with the time of the records it covers walks it past a
  cutoff it should not cross.
- **An argument or an injected clock.** `end_session(at=...)` changes the
  Protocol for all three strategies and for the agent. A clock callable is one
  more constructor argument, and in the harness it would be a second source of
  time that has to agree with the `at` on every record.
- **The records themselves.** Every record the strategy has been given carries
  the caller's time. In the agent that is `ConversationAgent`'s own clock,
  `self._clock()`, which is injectable and defaults to now. In the replay it
  is the session's timestamp in clock order and midnight of the session's day
  in list order (0004, 0009); the question's `T` is 23:59 on its day, and no
  session is dated after it.

Within a session all turns share one timestamp (0004). A caller could in
principle write records out of time order.

## Decision

**The strategy's clock is the largest `at` it has received in `write()`**, over
every record of every kind since it was constructed. A summary made in
`end_session()` is stamped with that value. The clock never moves backwards: a
record written with an earlier `at` than one already written does not change
it. The strategy never reads the wall clock, and `ConsolidatingMemory` takes no
clock argument.

In `retrieve(at=T)` a summary is filtered on its `at` exactly as a raw record
is: a summary with `at > T` is not visible, and neither is its text.

The memory tests cover both: a summary stamped with the latest `at`, not the
earliest, and a summary made after `T` absent from `retrieve(at=T)` while the
raw records before `T` are present.

Considered and rejected:

- **`datetime.now()`**, above. It also puts an untestable value into the
  record.
- **`end_session(at=...)`.** The Protocol is the contract; a change to it to
  serve one strategy's bookkeeping is the kind of change `CLAUDE.md` calls
  wrong however clean it looks.
- **A clock callable in the constructor.** It would work, and the agent has
  one to hand over. It was rejected because the harness would then hold two
  clocks, the records' `at` and the callable, and a disagreement between them
  is exactly the leak the time-cutoff rule exists to prevent. One source is
  safer than two that must agree.
- **The `at` of the last record written**, rather than the largest. The same
  in every replay, where `at` never decreases, and wrong for a caller that
  writes out of order.

## Consequences

The summary's `at` equals the `at` of the session it was made after. It is not
earlier than any record it derives from, so it is never backdated past a
cutoff that its sources would pass. It is also not later than the last record,
so a `retrieve(at=T)` that sees the session sees the summary made from it.
"The time consolidation ran" is, for this strategy, the latest moment it knows
of.

In the agent the clock is the agent's clock, so a test that injects a fixed
clock into `ConversationAgent` gets summaries stamped with it. Nothing in the
memory module reads time on its own.

A summary and the turns of its last session share an `at`. Order among them is
by meaning, not by time: 0012 shows the summary first. A strategy that sorted
by `at` would have to sort stably and place the summary deliberately.

In the replay the rule is not exercised beyond the one case: `at` is
non-decreasing and every session precedes `T`. The invariant is covered by the
memory tests, not by the evaluation, as 0004 says of the cutoff itself.
