# 0004 — Replaying a LongMemEval history into memory

Status: accepted
Date: 2026-09-26

## Context

`evals/longmemeval.py` turns each LongMemEval instance into a sequence of
`write()` calls, then one `retrieve()`. Retrieval precision and recall compare
`Retrieval.sources` with the ids of the turns the dataset marks as evidence, so
the mapping from dataset to records decides whether those two sets address the
same things. Get it wrong and the numbers still compute.

The file is `longmemeval_s_cleaned.json` from the Hugging Face dataset
`xiaowu0162/longmemeval-cleaned`, revision
`98d7416c24c778c2fee6e6f3006e7a073259d48f`, sha256
`d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`. The
authors publish it in place of the original, which it replaces by removing
history sessions that interfered with answer correctness. Each instance lists
its sessions in `haystack_sessions`, their ids in `haystack_session_ids`, one
timestamp per session in `haystack_dates` (`2023/05/20 (Sat) 02:21`), and marks
evidence turns with `has_answer: true`. There is no per-turn timestamp.

The file holds 70 `single-session-user` and 78 `knowledge-update` questions.
Across all of them, three things shape the replay:

- **The dates hold to the day, not to the minute.** No session in either type
  is dated on a later day than its question, and across days every history
  lists its sessions in date order. Within a day they do not agree: all 78
  `knowledge-update` histories list their sessions out of clock order within a
  day, between 1 and 22 times each, while the 70 `single-session-user`
  histories are in clock order. 16 `knowledge-update` questions, one of them an
  abstention question, have 58 sessions timed after the question, from 1
  minute to 15 hours later, all on the question's own day.
- **Within a day the clock also contradicts the evidence, in two questions.**
  In `2133c1b5` the updated value is stated at 20:50 on a day the question is
  asked at 08:39. In `618f13b2` two evidence sessions on one day are timed in
  the opposite order to the update they record. Across days, the dates never
  contradict the order of two evidence sessions.
- **Some session ids repeat.** 5 histories contain the same session twice,
  identical in content, on different dates. Two records would share an id.

`RecentTurnsMemory` treats the last records written as the most recent, so the
order in which sessions are written decides what the baseline sees.

LongMemEval's own reader (`src/generation/run_generation.py` at commit
`d0c699faf593726d96a6c75768e0fd2016d1feb8`) sorts the sessions it shows the
model by their full timestamps ("sort sessions by their dates", line 225), and
shows every session whatever its date: `question_date` enters only as text in
the prompt (lines 91–96 and 280).

## Decision

The harness must refuse to start unless the file's sha256 matches the one
above.

For each instance:

- **Sessions are replayed in clock order**: a stable sort on the full
  timestamps in `haystack_dates`, as LongMemEval's reader sorts them, so
  sessions with equal timestamps keep their list order.
- **The question is treated as asked at the end of its day.** Sessions dated
  on or before the question's calendar day are written, which in this dataset
  is all of them, and the question is asked with `retrieve(question, at=<23:59
  on the question's day>, budget_tokens=...)`. The limit is inclusive: a
  session timed 23:59 on the question's day is written and can be recalled.
  The same `at` is passed to every strategy.
- **The session id is the dataset's own** `haystack_session_ids[i]`.
- **The turn index is the turn's position in its session as the dataset lists
  it**, counting from 0 and counting user and assistant turns alike. The record
  id is `make_record_id(session_id, turn_index)`.
- Every turn is written as `kind="message"` with its own role and content,
  unchanged, and `at` set to its session's timestamp.
- `end_session()` is called after every session.
- **Evidence** is the set of record ids of turns marked `has_answer: true`.
- The harness must raise if two records in one replay would share an id.

**Why the clock order within a day.** Between an evidence session and a filler
session there is no true order: the filler conversations have nothing to do
with the user's story. What the order within a day has to be is neutral toward
where the evidence sits. Counted on the 69 measured `knowledge-update`
questions (0005), the clock order puts the latest evidence session last on its
day in 15 of the 61 questions where that day holds other sessions, close to the
16.2 expected by chance; the list order does so in 23, which is not neutral and
favours any strategy that reads the end of the history. The clock order is
also LongMemEval's own. Between two evidence sessions there is a true order,
the order of the update, and the one question where the clock contradicts it,
`618f13b2`, is excluded in 0005.

Considered and rejected:

- **Stopping at the question's clock time.** It never writes anything timed
  after the question, but it cuts at a resolution the dates do not have: of the
  130 questions measured under this record, it would remove 47 sessions from 15
  histories and make `2133c1b5` unanswerable, although its answer is the one
  the benchmark expects.
- **The list order within a day**, with `at` set to the day so that write
  order and `at` agree. Since every list is in date order across days, this is
  simply the list order. It uses no clock time at all and would keep
  `618f13b2`, whose two evidence sessions the list orders correctly. It was
  rejected because it is not neutral, as above: on the same 69 questions the
  baseline would reach evidence in 21 instead of 14.
- **Positional session ids** (`s0`, `s1`, …). They would change with the
  replay order and lose the link to `answer_session_ids`. Dataset ids do not
  depend on where a session sits, so sorting leaves every id unchanged.

## Consequences

Recency means time, for every strategy, in both question types, and the memory
sees the same sessions in the same order as LongMemEval's own reader gives its
model.

What this record adds is an interpretation the dataset does not state: that a
question is asked at the end of its day. It follows from the dates holding at
that resolution and not below it. The method section must state it.

Within a day the order follows the clock, the least reliable part of the
dates. That is still a choice, and it moves the baseline: it reaches evidence
in 14 of 69 `knowledge-update` questions in clock order against 21 in list
order. 0009 declares recall in the list order as a secondary measure for every
strategy, so the effect of the choice is reported rather than hidden.

All turns in a session share one timestamp, so time cannot order turns within
a session; only write order can. A strategy that sorts by `at` must sort
stably.

Two kinds of question cannot be measured under this rule: one whose evidence
sessions are timed against the update they record, and a history with a
repeated session id, which cannot be replayed without inventing a second id
scheme. Both are excluded in 0005 rather than patched here.

The time cutoff in `retrieve()` is still passed and still enforced, but the
replay does not exercise it: no session in this dataset is dated after its
question's day. The invariant is covered by the memory tests, not by the
evaluation.
