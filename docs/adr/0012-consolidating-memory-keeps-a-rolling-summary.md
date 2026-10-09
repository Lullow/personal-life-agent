# 0012 — ConsolidatingMemory keeps a rolling summary, rewritten by gpt-4o-mini after every session

Status: accepted
Date: 2026-10-03
Superseded by: 0015

## Context

M3 builds `ConsolidatingMemory`, the third strategy: a rolling summary plus a
recent window (`CLAUDE.md`). The third hypothesis in `docs/vg-project.md` is
that it handles changed facts better, because the summary replaces the old
value, and that it loses detail and pays for extra calls. `docs/vg-project.md`
requires three rules to be recorded before it is measured: which model
consolidates, how a summary counts toward recall, and where the strategy's
clock comes from during a replay. This record fixes the design and the model;
0013 and 0014 fix the other two.

What is already fixed constrains the design:

- Every strategy fills the same 8000-token budget, counted over the content of
  what it returns (0006, 0007). The baseline always admits the newest record
  and then fills backwards until the next one does not fit (0007).
- The model sees the recalled messages as chat turns without dates (0008), so
  whatever the summary is, it has to be a chat message with a role.
- 0010 estimated the whole comparison with a model of consolidation: a rolling
  summary of S tokens rewritten after every session by
  `gpt-4o-mini-2024-07-18`, each call reading the session's turns, the previous
  summary and 300 tokens of instruction and writing S tokens, with S from 500
  to 2000. 0010 binds M3 to that model and requires M3 to check the actual
  design against it before measuring.
- The strategy owns consolidation: `write()` and `end_session()` decide for
  themselves, and the harness never triggers it (`CLAUDE.md`). A record with
  `kind="outcome"` is never summarised or paraphrased. The consolidation call
  runs outside the turn and must not be able to produce a tool call.
- The harness asks the question after the last `end_session()` of the history
  (0004). At that moment no session is open.

Measured on the 122 histories of 0010 with `o200k_base`: 5,874 sessions, 39 to
55 per history; the largest session holds 17,141 tokens and the largest
history 103,557. `gpt-4o-mini-2024-07-18` takes 128,000 tokens of context. On
2026-10-03 OpenRouter prices it at $0.15 per million input tokens and $0.60
per million output tokens, unchanged since 0010.

`LLMClient.chat_json` sends temperature 0 and JSON mode, sets no `max_tokens`,
and returns `None` on any failure without saying why (0008).

M2 found the answering model not fully deterministic at temperature 0. A
strategy whose context is written by a model inherits that.

## Decision

**The model.** `openai/gpt-4o-mini-2024-07-18` through OpenRouter, named by its
dated id and never by an alias, through the same `chat_json` as every other
call: temperature 0, JSON mode. It is the model 0010 assumed, so 0010 stands.
The model id is written into every result row.

**When.** The strategy consolidates in `end_session()`, once, and only if at
least one `kind="message"` record was written since the last consolidation.
`write()` never consolidates. Nothing happens on an empty session.

**What.** One call rewrites the notes. It receives the system prompt below and
one user message holding the previous summary, or `(none)` the first time, and
the transcript of the session that just ended: every `kind="message"` record
written since the last consolidation, in write order, as `user:` and
`assistant:` lines. `kind="outcome"` records never enter the call. The system
prompt is:

```
You keep the assistant's notes about its earlier conversations with the user.
You are given the notes so far and the transcript of one more conversation.
Rewrite the notes so that they also cover this conversation. Keep concrete
facts: names, numbers, dates, places, plans, preferences, and what the user
asked for. When a fact has changed, write the current value in place of the
old one. Keep the notes in the language of the conversation, and write them so
that they can be read on their own, in at most 750 words. Reply with a JSON
object: {"summary": "<the notes>"}.
```

The user message is:

```
Notes so far:
{previous summary, or "(none)"}

Conversation to add:
user: {content}

assistant: {content}

...
```

The reply's `summary` string becomes a new record: `kind="summary"`,
`role="assistant"`, the text exactly as returned, `session_id` of the session
that ended, `id = f"summary:{session_id}"`, `at` from 0014, and
`derived_from` the flat tuple of every `kind="message"` id the summary covers:
the previous summary's `derived_from` followed by this session's ids. Earlier
summaries are kept, not replaced; the strategy raises if a summary id would
repeat.

**The target size S is 1000 tokens.** The prompt asks for 750 words, about
1000 tokens at this dataset's 1.3 tokens per word. S is a target, not a cap:
the strategy does not truncate, and `max_tokens` is not set. The size of every
summary that reaches a context is reported, mean and maximum. The only hard
limit is the budget, below.

**What `retrieve(query, at=T, budget_tokens=B)` returns.** The newest summary
with `at <= T`, as an assistant message, first. Then the raw records
(`kind="message"` and `kind="outcome"`) with `at <= T`, filled backwards from
the newest as the baseline fills (0007), into `B` minus the summary's tokens,
stopping at the first record that does not fit. The raw records come after the
summary in the order they were written. No label, date or separator is added.
`sources` lists the summary's id and then the raw ids, in the same order.
Raw records are kept after consolidation; the summary does not remove them
from the store. When no summary is visible at `T`, the strategy returns what
the baseline would.

**Failures.** A call that returns `None` is tried twice more. If all three
fail, the strategy raises; the records written stay as they are and no summary
is made. The harness marks the question `error` and it is run again before any
figure is reported (0008).

**Cost.** The harness builds the strategy with a `RecordingLLMClient` labelled
`consolidate`, wrapping a client for the model above. Each `LLMCall` records
the model it was made with, and every cost figure prices a call at its own
model. The strategy's cost for a question is its answer call plus its
`consolidate` calls in the clock-order replay; consolidation tokens are
reported under their own label as well as in the total (0010). The list-order
replay of 0009 is made with the client relabelled `consolidate-list-order`, on
the 10 `knowledge-update` pilot questions only, and is not counted as the
strategy's.

**Against 0010's model.** Each call reads the previous summary, the session and
the instruction, and writes the next summary, as the model says; the
instruction is shorter than its 300 tokens. At N = 61 and S = 1000
`evals/estimate_cost.py` puts consolidation at $7.06 and the whole comparison
at $14.89, 15% of the cap. 0010 holds and is not superseded.

The harness registers the strategy as `consolidating`. The prompt, S and the
fill rule are fixed here, before the strategy's first dry run; the dry run
shows this strategy's recall without a model call (0013), so they are not
changed after it.

Considered and rejected:

- **`gpt-4o-2024-08-06` as the consolidator**, which would remove the confound
  0010 names. At N = 61 it fits the cap only with S = 500, at 85%, and leaves
  nothing to measure again with. 0010 rejected it on those numbers; they have
  not changed.
- **Dropping the raw turns once they are summarised**, showing only the
  summary and the open session. The harness asks after the last
  `end_session()`, so the model would see the summary and nothing else, and
  on `single-session-user` the strategy would be measured on its summary
  alone. It is also not what a recent window means.
- **Keeping the old value next to the new one** in the notes, with a note that
  it changed. It would answer questions about the earlier value, which
  replacing cannot. But it is the other design: a summary that keeps every
  value is a compressed `RetrievalMemory`, and the hypothesis under test is
  the one that replaces.
- **One summary per session, all of them shown.** Nothing would ever replace an
  old value, so the third hypothesis would fail by construction, and the
  summaries would outgrow the budget on long histories.
- **Consolidating in `write()`** when the raw turns pass a size. It would make
  the consolidation points depend on message length rather than on the
  session boundary the agent already marks, and it is not 0010's model.
- **Passing the session as chat turns** instead of as quoted transcript. The
  model would be continuing the conversation it is meant to summarise, and a
  filler session's instruction ("act as a Linux terminal", 0008) would be an
  instruction to the consolidator.
- **Showing the summary in the system prompt.** It would change the prompt of
  0008 for one strategy, which 0011 kept unchanged for the same reason.
- **Enforcing S** by truncating the text or by `max_tokens`. Either cuts the
  notes mid-sentence and destroys the thing being measured; the reported size
  shows whether the model kept to the target.

## Consequences

The strategy has S tokens less for raw turns than the baseline does; the
summary is the only representation of anything older than the window. On a
`single-session-user` question whose evidence is long past, the answer is
right only if the fact survived up to 54 rewrites. That loss is the price the
hypothesis names, and it is measured, not assumed.

On a `knowledge-update` question the summary holds, at best, one value. The
window may still hold the other if the change was recent. A question that
asks for the earlier value is answered right only from the window. 0009's
breakdown, recomputed under 0013, shows which.

The last session is both summarised and in the window, so recent facts appear
twice. That is expected of a recent window over a rolling summary and costs
budget, not correctness.

The summary is shown as something the assistant said. The notes are written to
be read on their own, so the answering model reads them as a message from
itself about earlier conversations. That is a convention this record chooses,
and the same for every question.

The transcript is quoted, so an instruction inside a filler session is less
likely to be obeyed by the consolidator than by the answering model (0008).
But the notes could carry one forward in their text. The answers are read by
hand for this before any figure is reported, as in M1 and M2.

The context is written by a weaker model than the one that answers. 0010
names it as the confound of the third hypothesis and sets aside a check,
consolidating the first five `knowledge-update` histories with
`gpt-4o-2024-08-06` as well, $4.47 at S = 1000. The check is made only if M3's
hard stop has already been met.

The summaries are not reproducible. Two runs of the same history produce
different notes, and the list-order replay re-consolidates, so its difference
from the primary figures mixes the order with the model's variation. The recall
figures of 0013 do not depend on the text and are not affected; the answers
are.

6,347 consolidation calls, 5,874 in clock order and 473 in list order, against
244 calls in each of M2's two runs. The harness is sequential and would take between
five and eighteen hours; it is run with several questions in flight at once,
each with its own call log, and started so that it can run overnight.

The model may not keep to 750 words. Nothing enforces it, and a summary longer
than the budget would leave no room for the window; the harness reports such a
question as over budget rather than truncate (0007).

`kind="outcome"` records are never summarised and never dropped from the
store, but they are recalled by the window like any raw turn, so one older
than the window is not in the context. The agent is forbidden from answering
from memory and looks facts up in the database, which is where an outcome came
from.

The agent cannot yet be switched to this strategy with one configuration line:
the strategy needs a model client, and the agent does not hand its client to
its memory. That wiring is not needed for the measurement and waits (scope
rule in `docs/vg-project.md`).

If OpenRouter withdraws the dated model before the comparison is finished, it
cannot be finished as specified here. A new record supersedes this one, and
the strategy is measured again.
