# 0010 — The number of questions per type

Status: accepted
Date: 2026-09-27

## Context

0005 took 10 questions per type for the M1 pilot and left the number for the
comparison to be fixed from the measured cost. `docs/vg-project.md` fixes it
from the estimated total cost of the whole comparison, consolidation included,
at most 61 per type, and caps the whole measurement at 1000 SEK. The pool in
0005 holds 61 `single-session-user` and 69 `knowledge-update` questions.

The pilot measured one strategy. The harness counted $0.4045 for the pilot's
20 questions; with the measured framing, $0.4135; OpenRouter billed $0.4134.
The framing is what 0006 leaves uncounted: `scripts/check_token_count.py`
found the provider's input count higher by 4 tokens per message and 3 per call.
That makes $0.0207 per question and strategy: $0.0202 to answer and $0.0004 to
grade. Every strategy fills the same budget (0007), so the answer call costs
about the same whichever strategy recalled for it.

Two of the three strategies are not built, and one of them decides the total.
`ConsolidatingMemory` has to read every history through a model, and the 122
histories at N = 61 hold 101,567 tokens in 48.1 sessions on average.
`RetrievalMemory` may embed them. Both are designed later, in M2 and M3, so
their cost can only be estimated with a model of them.

Prices on OpenRouter on 2026-09-27, per million input and output tokens:
`gpt-4o-2024-08-06` at $2.50 and $10.00, `gpt-4o-mini-2024-07-18` at $0.15 and
$0.60, `text-embedding-3-small` at $0.02 for input. The ECB reference rate on
2026-09-25 was 9.9009 SEK per dollar, which makes 1000 SEK a cap of $101.00.

The stop rule in `docs/vg-project.md` measures everything again that was
measured under a superseded record. The budget has to leave room for that.

## Decision

**N = 61 per type**: all 61 `single-session-user` questions and the first 61
`knowledge-update` questions, in the order of
`evals/longmemeval_questions.json`. Every strategy runs on these 122. The M1
pilot's 20 are the first ten of each.

The estimate rests on three assumptions, and `evals/estimate_cost.py`
recomputes every figure in this record from them:

- **Consolidation uses `gpt-4o-mini-2024-07-18`.** This binds M3: its record on
  the consolidation model has to stay within the budget below, or supersede
  this one.
- **`RetrievalMemory` embeds every turn** with `text-embedding-3-small`. Of the
  two indexes M2 may choose, it is the one that costs something, so M2's choice
  cannot move N.
- **The cap is converted at the ECB rate above.** The report states what the
  credits actually cost in SEK.

**Consolidation is estimated with a model of it, not with its design.** The
model is a rolling summary rewritten after every session: each call reads the
session's turns, the previous summary of S tokens and 300 tokens of
instruction, and writes S tokens, with S from 500 to 2000. The list-order
replay of 0009 adds a second consolidation of the ten `knowledge-update` pilot
questions. Before `ConsolidatingMemory` is measured, M3 checks its actual
design against this model. If the design's estimated cost at N = 61 does not
fit the cap, a new record supersedes this one.

With those assumptions the comparison costs **$12.51 to $19.65**, 124 to 195
SEK, 12 to 19% of the cap, what has been spent so far included.

Considered and rejected:

- **`gpt-4o-2024-08-06` for consolidation**, the model that answers. It would
  remove the confound below. At N = 61 it fits only with S = 500, at 85% of the
  cap; at S = 1000 it is 124%. A superseded record would leave nothing to
  measure again with.
- **A smaller N with `gpt-4o-2024-08-06`**: at N = 45 and S = 1000 it takes 94%,
  at N = 30 65%, and at N = 30 with S = 2000 107%. N = 30 doubles how far one
  question moves a share, and still fails if the summary grows.
- **BM25 as the assumed index.** It costs nothing, but assuming it would let
  M2's choice of embeddings move the estimate. At N = 61 embedding every
  history costs $0.25, so the dearer assumption costs almost nothing.

## Consequences

The comparison uses the whole `single-session-user` pool and leaves the last 8
of the 69 `knowledge-update` questions unmeasured. At N = 61 one question moves
a share by 0.016, against 0.1 in the pilot.

More than four fifths of the cap is left for the reruns 0008 requires and for
measuring again under a superseding record.

**The consolidation model is a confound for H3.** `ConsolidatingMemory`'s
summaries come from a weaker model than the one that answers. If it loses
detail, the loss cannot be put down to consolidation as a policy alone. The
report states this as a limitation. A possible check, if M3 has the time:
consolidate five histories with `gpt-4o-2024-08-06` as well, and compare. The
five are the first five `knowledge-update` questions in the 0005 order, named
here so that they are not picked after the results are seen. The check costs
$3.01 to $7.40 with the answers and their grading.

The consolidation estimate is only a model. A design that consolidates less
often costs less; one that keeps a longer summary, or reads more per call,
costs more. The check in M3 is what makes the estimate hold.

Tokens remain the unit cost is reported in (0006), and `gpt-4o-mini` counts
with the same `o200k_base`. But its tokens are priced far below the answer
model's, so a sum of the two hides where the money went. The report gives
consolidation tokens under their own label as well as in the strategy's total.

Embedding calls are not chat calls, and 0006 does not say how they are counted.
M2's record on the index has to.

Prices and the rate are external facts, read on the dates above. A change in
either moves the estimate, not N, unless it threatens the cap.
