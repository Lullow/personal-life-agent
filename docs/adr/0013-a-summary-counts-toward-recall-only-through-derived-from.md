# 0013 — A summary counts toward recall only through what it derives from

Status: accepted
Date: 2026-10-03

## Context

0009 defines recall and precision per turn: `R` is the set of ids in
`Retrieval.sources`, `E` the ids of the turns the dataset marks as evidence,
and recall is |R ∩ E| / |E|. It left one thing open: "How a summary's id
counts, given what it was derived from, is decided in M3, before
`ConsolidatingMemory` is measured."

Under 0012, `ConsolidatingMemory` returns one summary record first and then a
window of raw turns. The summary's id is `summary:{session_id}`, which is in
`E` for no question. Its `derived_from` is the flat tuple of every message id
the notes cover, which after the last session is the whole history. The
`Retrieval` docstring already says what `sources` means for a summarising
strategy: the summary's own id, because the summary is what reached the
context, with `derived_from` there to expand it.

The two figures that could be computed from this say different things. Whether
an evidence turn is in `sources` says it reached the model verbatim. Whether
it is in a summary's `derived_from` says the consolidator read it; it does not
say the fact survived the rewrite, and the third hypothesis is about exactly
that gap.

Recall of this strategy does not depend on the text of the summary, only on
its length, which decides how many raw turns fit beside it. A dry run with a
placeholder of about S tokens therefore shows recall close to the real run's,
without a model call, as it did for `RetrievalMemory` (0011).

## Decision

**Recall and precision stay as 0009 defines them**, computed over `sources` as
the strategy returns them. The summary's id matches no evidence, so evidence
that reached the model only through the summary counts as missed, and the
summary counts against precision as one recalled item. The `knowledge-update`
breakdown of 0009 is computed on the same `sources`.

**One secondary figure, "evidence consolidated", for this strategy.** For a
question, `C` is the union of `derived_from` over the summary records in
`sources`, and

- **evidence consolidated** = |C ∩ E| / |E|, reported as a mean per question
  type next to recall;
- **evidence consolidated or reached** = whether (C ∪ R) ∩ E is non-empty,
  reported as a count next to "evidence reached";
- the `knowledge-update` breakdown of 0009 is computed a second time with
  C ∪ R in place of R, and reported as a second table.

The harness reads `derived_from` from the strategy's own records after
`retrieve()`; the row logs the figures, not the id sets.

For `RecentTurnsMemory` and `RetrievalMemory` the figure is not computed: they
return no summaries, and it would equal recall.

The figures are declared here, before this strategy's first dry run, so that
the way a summary counts cannot be chosen after its effect is seen.

Considered and rejected:

- **Counting a summary as every id in its `derived_from`** in the primary
  figure. After the last session the summary derives from the whole history,
  so recall would be 1 on every question whatever the notes say, and the
  figure would stop measuring anything. It would also make the strategy's
  precision incomparable with the other rows, which count turns.
- **Counting the summary as nothing and leaving it there.** It is the primary
  rule above, but alone it would report this strategy's recall as the recall
  of its window, and the window is the part of the strategy that is not under
  test. The secondary figure is what separates "the consolidator never saw
  it" from "it saw it and lost it".
- **Searching the summary's text for the gold answer.** It is a different
  measure, over text rather than ids, it reads the reference answer into the
  recall figure, and a paraphrased or restated fact would be scored by string
  luck.
- **Recall per session** for this strategy, as 0009 already rejected.

## Consequences

The row's recall will be low by construction on every long-term question, and
much lower than `RetrievalMemory`'s, since only the window counts. Read on its
own it would say the strategy finds nothing. It has to be read next to
"evidence consolidated", which will be high by construction, since the
consolidator reads every session. The distance between the two is what the
strategy does; accuracy says what it was worth.

On `knowledge-update` the second breakdown will put almost every question in
`both`: the consolidator reads both evidence sessions. Correctness within that
group is then the direct test of the third hypothesis, with the window's
contribution visible in the first breakdown.

Precision falls by one item per question, the summary, against about 38 for
the baseline. That is within the noise 0009 expects of precision and is noted,
not corrected.

The figures are computable in the dry run, so, as 0011 required of BM25's
parameters, 0012's prompt, S and fill rule are not changed after the first dry
run.

`derived_from` is a tuple of up to a few thousand strings per summary, and the
flat form repeats the earlier ids in every later summary. For one history in
one process that is a few megabytes; for the agent's persistence in step 4 it
would be a reason to store the chain and expand it on read. The row does not
store it.
