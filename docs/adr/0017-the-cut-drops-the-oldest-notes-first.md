# 0017 — The cut drops the oldest notes first

Status: accepted
Date: 2026-10-03
Supersedes: 0015, its cut rule only

## Context

0015 holds the summary to S = 1000 tokens: a reply over S is asked for once
more with its word count, and a second reply over S is cut after the last
sentence end at which what remains counts at most S. The cut was meant as a
backstop that the ask-again would make rare.

The third and fourth smoke tests, one question per type each on commits
2db15dd and 3ab6342, show it is not rare. On `07741c45`, 49 sessions: 38 asked
again, 32 cut. On the next run of the same two questions: 40 asked again and
33 cut of 52 on `c8c3f81d`, 36 and 33 of 49 on `07741c45`. The model keeps to
750 words in about a third of the sessions, shortens when told the number in
a few more, and in about two thirds the cut does the work.

The model writes the notes in the order of the conversations: the oldest
session's facts first, the session just added last. The rows are in
`evals/results/consolidating-20261003-214031-smoke.jsonl` and
`consolidating-0016-smoke.jsonl`; the summary text is in each row.

A cut from the end therefore removes, two sessions in three, part of what the
session just added, before the next session's call ever sees it. What
survives is weighted toward the earliest sessions. The third hypothesis in
`docs/vg-project.md` is about a fact that has changed, and the change is in a
later session than the first value. A design that drops the newest first
disfavours the hypothesis by construction, in the part of the pipeline that
was meant to be a formality.

The baseline forgets the oldest first: its window keeps the newest turns that
fit (0007). A rolling summary in the usual sense does the same.

Nothing has been measured under 0015's cut beyond the smoke tests.

## Decision

0015 stands in every part but its cut rule, which this record replaces.

**When the second reply is still over S, the cut drops the beginning.** The
notes keep their last part: from the first sentence start at which what
follows counts at most S tokens, to the end. A sentence start is the position
after a `.`, `!`, `?` or line break, with leading whitespace dropped. If no
sentence start leaves a part within S, the last words that fit are kept.
Nothing is added to mark the cut.

The ask-again of 0015 is unchanged, and so is everything the cut feeds: the
summary record, its `derived_from`, `retrieve()`, the counts
`summary_reasked` and `summary_truncated`, and the skip rule of 0016.

Considered and rejected:

- **Keeping the cut from the end**, as 0015 said, and reporting it. The row
  would measure a strategy that forgets the newest first, which is neither
  the design described nor a fair test of the hypothesis.
- **Asking the model to put the newest facts first**, so that the end cut
  takes the oldest. It makes the notes' order a second thing the model has
  to be held to, and the smoke tests show it is not held to the first.
- **Cutting from both ends, or by sentence weight.** There is no measure of a
  sentence's worth that is not the answer key.
- **Asking again more than once**, so that the cut is rarer. 0015 rejected
  it; the fourth smoke test shows the second ask shortens in only a few
  sessions, so a third would mostly be another call.

## Consequences

When the cut falls, the newest session's facts survive it and the oldest go.
The notes are then a recency-weighted memory with a model's compression on
top, which is what a rolling summary is. On a `knowledge-update` question the
newer value has the better chance; on a `single-session-user` question about
a fact stated early, the fact survives only as long as the model keeps
restating it compactly. Both are the hypothesis's own terms.

A cut summary is still one the model did not make, and the cut is still
counted. With two sessions in three cut, `summary_truncated` will be high for
nearly every question, and the report says so: the size is held by code more
often than by the model.

The direction of forgetting is now the same for the three strategies' limits:
the window, the ranking's tie rule (0011, later record first) and the cut all
favour the newer record.

The smoke tests under 0015's cut are kept as evidence and are not figures of
the comparison.
