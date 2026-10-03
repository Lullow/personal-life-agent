# 0016 — A session the consolidator cannot summarise is skipped, not fatal

Status: accepted
Date: 2026-10-03
Supersedes: 0015, its failure rule only

## Context

0015's failure rule: a consolidation call that fails is tried twice more, and
if all three attempts fail the strategy raises, the harness marks the question
`error`, and it is run again under 0008. 0008 drops a question that fails
twice from every strategy's figures, so that every row rests on the same
questions.

The second smoke test, one question per type on commit 2db15dd, showed what a
failure is here. On `c8c3f81d` the consolidator failed three times on the
session `sharegpt_pRqHb1o_0`, with 3,239 input tokens each time. The reply,
read raw through a diagnosing wrapper, was 30,280 characters and 4,399 words:
valid notes for the first part, then `"Isis Unveiled" \t, \t"Isis Unveiled"
\t: \t"Isis Unveiled"` repeated until the output ran out, so the JSON string
was never closed. On `07741c45` the list-order replay failed the same way on
`sharegpt_5G145hp_0`, and the clock-order replay had one failure that passed
on the second attempt. Both histories hit a loop somewhere; the one that
failed three times failed on the same input each time.

The model is run at temperature 0, which is what makes the loop return on
every attempt and on every rerun. The three attempts at a looping call take
about three minutes, since each runs to the 60-second timeout or to the end of
the model's output.

Under 0015's rule the question would be marked `error`, run again, fail again,
and be dropped from the table for all three strategies. The other two
strategies had answered it. A question lost that way is lost to the model the
third strategy consolidates with, not to anything the question asks.

The strategy owns consolidation (`CLAUDE.md`): what it does when a call fails
is its design, and the design is what is measured.

## Decision

0015 stands in every part but its failure rule, which this record replaces.

**A failed call is tried twice more**, as before; a call that returns `None`
or whose `summary` is not a non-empty string has failed.

**If the first call fails all three attempts, the session is skipped.** No
summary is made for it. The notes stay as they were; the next session's call
reads them unchanged. The session's turns stay in the store as raw records
and are recalled by the window like any other. `derived_from` is not extended
with them, so "evidence consolidated" (0013) counts them as not read. The
strategy records the skip, and the harness logs per question how many
sessions were skipped, `consolidations_failed`, next to how many were asked
again and cut. The harness reports the total per question type.

**If the second call, the ask-again of 0015, fails all three attempts, the
first reply is used**, cut to S as 0015 cuts, and recorded as asked again and
cut. The first reply was valid notes, only too long.

The strategy no longer raises on a failed call. A question is an `error` only
when its answer or grading fails, as 0008 says.

Considered and rejected:

- **Raising, as 0015 did.** It drops the question from every strategy's
  figures for a failure that is the consolidator's alone, and the smoke test
  suggests it is not rare.
- **A higher temperature on the second and third attempts**, to break the
  loop. It needs a temperature argument the client does not have, makes the
  attempts differ from the first in more than their timing, and still needs
  a rule for when all three fail.
- **Carrying the failed session into the next call.** The content that made
  the model loop would be in the next call as well, and a loop there would
  take the next session with it.
- **`max_tokens` to end a loop sooner.** The failed attempt would be shorter
  but still failed; 0015 already rejected it for the valid case.
- **Repairing the unterminated JSON** and keeping the notes before the loop.
  Where the loop begins is not known, and the cut of 0015 would keep whatever
  junk sits inside the first S tokens.

## Consequences

Every question stays in the table. What the consolidator could not do is a
figure, `consolidations_failed`, not a missing row.

A skipped session is a gap in the notes that the strategy cannot close later.
On a `knowledge-update` question whose update sits in a skipped session, the
notes keep the old value, and the breakdown of 0013 shows the session as not
consolidated. That is the strategy failing, measured as such.

The skip is deterministic given the model's output, so the figure is as
reproducible as the summaries are, which is to say not quite (0012).

A looping call costs about three minutes and a few cents, three times. The
run is longer by that for every skipped session; the harness's workers cover
it.

The gpt-4o check of 0010, if made, would show whether the loop is this
model's habit or the prompt's.
