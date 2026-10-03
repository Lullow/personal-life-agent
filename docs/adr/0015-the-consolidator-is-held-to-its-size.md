# 0015 — The consolidator is held to its size, by a stricter prompt and then by code

Status: accepted
Date: 2026-10-03
Supersedes: 0012
Superseded by: 0016, for the failure rule only

## Context

0012 fixed `ConsolidatingMemory`: a rolling summary rewritten by
`gpt-4o-mini-2024-07-18` after every session, target size S = 1000 tokens
asked for as 750 words, S a target and not a cap, the newest summary first in
the context and the most recent raw turns in what it left of the 8000-token
budget. It said that nothing enforced the size and that a summary longer than
the budget would be reported as over budget rather than truncated.

The first smoke test, one question per type on commit 11da1c2, showed the
model does not keep to the words. On `c8c3f81d`, 52 sessions, the output grew
by about 165 tokens a session, 443 tokens after the first and 8,883 after the
last; the summary shown to the answering model held 8,453 tokens. That is
larger than the whole budget: the window was empty, `sources` held one id,
and the row was over budget. The answer was right. The consolidation cost
$0.19 for the question, against $0.05 in 0010's model, and a call took about
35 seconds. The rows are in `evals/results/consolidating-20261003-192859-smoke.jsonl`.

A check on the first six sessions of the same history, measuring only the
size: under 0012's prompt the notes went from 630 to 2,165 tokens and kept
ten links; under a prompt that states the limit first, forbids links and
markdown, and says what to drop first, from 121 to 664 tokens with no links,
and a call took 8 seconds instead of 37. The stricter prompt still grew by
about 100 tokens a session. No prompt guarantees the size.

The comparison is made at the same token budget (`docs/vg-project.md`, 0007).
A strategy whose summary alone exceeds the budget is measured at a larger
budget than the other two, on every long history, by construction. That is a
wrong measurement, which is what the stop rule in `docs/vg-project.md` lets a
record be reopened for. Nothing was measured under 0012 beyond the smoke test.

The reading of the answers in step 4 needs the text the model saw.
`evals/write_run_reading.py` rebuilds a context by replaying the strategy,
which for this strategy would need the model again and would not give the
same text (0012: the summaries are not reproducible).

Everything else 0012 rested on still holds: the budget rules (0006, 0007), the
messages without dates (0008), 0010's cost model and its binding to
`gpt-4o-mini`, the strategy owning consolidation, outcomes never summarised,
the consolidation call unable to produce a tool call, the question asked after
the last `end_session()` (0004), the 5,874 sessions in the 122 histories, 39
to 55 per history, the largest session at 17,141 tokens and the largest
history at 103,557, the 128,000-token context of the model, and its prices of
$0.15 and $0.60 per million tokens, read on OpenRouter on 2026-10-03.
`LLMClient.chat_json` sends temperature 0 and JSON mode, sets no `max_tokens`,
and returns `None` on any failure.

## Decision

The design of 0012 stands in every part not restated here. What changes is the
prompt, what happens when the notes come back too long, and what the row
records.

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
Hard limit: the notes are at most 750 words. Write plain prose or short lines:
no links, no markdown, no lists of products or sources. You are given the
notes so far and the transcript of one more conversation. Rewrite the notes so
that they also cover this conversation, within the limit: keep what is about
the user (names, numbers, dates, places, plans, preferences, what they asked
for) and drop detail about anything else first. When a fact has changed, write
the current value in place of the old one. Keep the notes in the language of
the conversation. Reply with a JSON object: {"summary": "<the notes>"}.
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

**The size S is 1000 tokens, and it is a cap.** The prompt asks for 750
words, about 1000 tokens at this dataset's 1.3 tokens per word without links.
After the call the strategy counts the reply with its token counter. If it is
more than S:

1. **It asks once more.** A second call, same system prompt, with this user
   message, where `{words}` is the reply's word count and `{notes}` the reply:

   ```
   These notes are {words} words, over the limit of 750. Rewrite them to at
   most 750 words: keep what is about the user and the current value of every
   fact, and drop detail about anything else first. Reply with a JSON object:
   {"summary": "<the notes>"}.

   Notes:
   {notes}
   ```

   The second reply replaces the first whether or not it is shorter.

2. **If it is still more than S, the strategy cuts it** after the last
   sentence end, a `.`, `!`, `?` or line break, at which what remains counts
   at most S tokens; if no sentence end leaves anything, after the last word
   that does. Nothing is added to mark the cut.

The summary stored is therefore never more than S tokens, and the window
always has at least `B − S` tokens of the budget `B`.

The reply's `summary` string becomes a new record: `kind="summary"`,
`role="assistant"`, the text as returned or as cut, `session_id` of the session
that ended, `id = f"summary:{session_id}"`, `at` from 0014, and `derived_from`
the flat tuple of every `kind="message"` id the summary covers. Earlier
summaries are kept, not replaced; the strategy raises if a summary id would
repeat.

**What `retrieve(query, at=T, budget_tokens=B)` returns.** As 0012: the newest
summary with `at <= T` as an assistant message first, then the raw records
with `at <= T` filled backwards from the newest as the baseline fills (0007),
into `B` minus the summary's tokens, in the order they were written, nothing
added. `sources` is the summary's id and then the raw ids. Raw records are
kept after consolidation. Without a visible summary the strategy returns what
the baseline would.

**Failures.** A call that returns `None`, or whose `summary` is not a
non-empty string, is tried twice more; this applies to the second call as
well. If all three attempts of either call fail, the strategy raises; the
records written stay as they are and no summary is made. The harness marks
the question `error` and it is run again before any figure is reported (0008).

**What the row records**, beyond 0012 and 0013: the text of the summary shown
to the answering model, its tokens, and for the clock-order replay how many
consolidations asked a second time and how many cut, `summary_reasked` and
`summary_truncated`. The harness reports both as totals against the number of
consolidations, per question type. The second call is logged under
`consolidate` like the first and is the strategy's cost; in the list-order
replay under `consolidate-list-order`, which is not.

**Cost and 0010.** Each session reads the previous notes, the session and the
instruction and writes the next notes, at most S; a session that asks again
reads and writes once more. That is 0010's model with the second call added
when it happens, and S is now at most what the model assumed. 0010 stands.

The dry run's placeholder summary counts at most S tokens, so the dry run
neither asks again nor cuts.

The harness registers the strategy as `consolidating`. The prompts, S and the
cut rule are fixed here, before the strategy's first run under this record.
The dry run shows recall without a model call (0013), so they are not changed
after it. One smoke test, one question per type, is made to see that the size
holds and that the JSON comes back in shape; it changes nothing unless the
shape is wrong.

Considered and rejected:

- **Keeping 0012 and reporting over budget**, as it said. On the first
  question the context was the summary alone, 8,453 tokens; on 48 to 55
  sessions that is every long history. The row would measure a different
  strategy at a different budget.
- **The stricter prompt alone.** It cut the growth to a third and the time to a
  fifth in the six-session check, and still grew every session. At 48
  sessions that is several thousand tokens, and the finding above again.
- **`max_tokens` on the call.** `chat_json` asks for JSON; a reply the provider
  stops at a token limit is unfinished JSON, parses to `None`, is tried
  twice more with the same result, and the session fails. Holding the size
  that way needs a plain-text path in the client and a parser for what comes
  back, for the one call that uses it.
- **Cutting at once, without asking again.** The cut takes the end of the
  notes, and a model that writes in the order of the conversation puts the
  newest facts there, which on a `knowledge-update` question are the ones
  that matter. The second call gives the model the chance to shorten by
  choosing; the cut is the backstop and is counted.
- **Asking again more than once.** Each ask is a call on every session that
  overruns; one is enough to show whether the model can shorten when told the
  number, and the cut holds the size whatever it does.
- **A smaller S, so that the model's overrun lands near 1000.** It would tune
  S to one model's habit and move the window the other way.

## Consequences

The size holds, so the strategy is measured at the same budget as the other
two, and the window is never empty on account of the summary. What the model
does when told the number is measured, not assumed: `summary_reasked` and
`summary_truncated` say how often the cap was reached and how often the model
could not shorten.

A cut summary is one the model did not make. Where `summary_truncated` is
high, the row measures the model's notes with their end removed, and the
report must say so next to the figure. Where it is low, the second call did
the work and the cut is a formality.

The prompt forbids links and markdown and tells the model what to drop first.
That is a stronger steer than 0012's, and it is the same for every question;
it is not tuned to any answer, since no answer had been produced under it.
The consolidator now reads the raw turns under one instruction and the
answering model reads the notes under another (0008), and the two were
written together on the same day.

The row carries the summary text, so the answers can be read in step 4
against what the model saw, and so the rows are larger by about S tokens
each.

The second call makes the cost per session depend on the model's habit. The
dry run cannot show it; the smoke test and the run do, and the run's figures
are what the report gives, with the second calls inside the strategy's cost.

In the six-session check the stricter prompt's calls took 8 seconds. At that
rate the 6,347 consolidation calls take about 14 hours in one thread and
under two with eight questions in flight, which is what the harness is run
with.

The summaries are still not reproducible (0012), and the consolidation model
is still a weaker one than the answering model (0010). The gpt-4o check 0010
sets aside is unchanged: $4.47 at S = 1000, made only if M3's hard stop has
already been met.

The agent still cannot be switched to this strategy with one configuration
line; that wiring waits, as 0012 said.

If OpenRouter withdraws the dated model before the comparison is finished, a
new record supersedes this one, and the strategy is measured again.
