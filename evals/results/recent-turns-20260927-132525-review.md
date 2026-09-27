# Review of the M1 pilot run `recent-turns-20260927-132525`

The pilot's answers read by hand on 2026-09-27, as ADR 0008 requires before any
figure is reported. The rows are `recent-turns-20260927-132525.jsonl` in this
directory: `RecentTurnsMemory` without a turn window, commit 972333c,
`openai/gpt-4o-2024-08-06`, the first ten questions of each type. The reading
files were written by `evals/write_run_reading.py`.

## Summary

- **17 evidence missing.** No evidence turn was in the context, and the model
  answered "I do not know." in every one of them.
- **2 context used, correct:** `b6019101` and `6aeb4375`, both with breakdown
  `later`, 6,271 and 1,708 tokens from the question.
- **1 context ignored:** `0f05491a`, breakdown `later`, 3,657 tokens from the
  question.

All three questions where the evidence was reached lie within 6,271 tokens of
the question; all 17 misses lie at least 10,052 tokens away. None of the three
had both evidence turns in the context, so `both` is untested.

No answer followed an instruction from a filler conversation: every miss
answered exactly "I do not know.", and the other three answered the question.

## Per question

Distance is the tokens of conversation between the newest evidence turn and
the question (ADR 0005).

| # | question | type | distance | reached | breakdown | verdict | reading |
|---|---|---|---:|---|---|---|---|
| 1 | c8c3f81d | SSU | 14,602 | no |  | no | evidence missing |
| 2 | ad7109d1 | SSU | 57,541 | no |  | no | evidence missing |
| 3 | 36580ce8 | SSU | 13,298 | no |  | no | evidence missing |
| 4 | 51a45a95 | SSU | 17,454 | no |  | no | evidence missing; see data notes |
| 5 | 86f00804 | SSU | 80,895 | no |  | no | evidence missing |
| 6 | 6b168ec8 | SSU | 33,139 | no |  | no | evidence missing |
| 7 | c14c00dd | SSU | 84,214 | no |  | no | evidence missing |
| 8 | 8ebdbe50 | SSU | 18,020 | no |  | no | evidence missing |
| 9 | 95bcc1c8 | SSU | 83,107 | no |  | no | evidence missing |
| 10 | 66f24dbb | SSU | 68,932 | no |  | no | evidence missing |
| 11 | 07741c45 | KU | 34,179 | no | neither | no | evidence missing |
| 12 | b6019101 | KU | 6,271 | yes | later | yes | context used, correct |
| 13 | 6071bd76 | KU | 55,921 | no | neither | no | evidence missing |
| 14 | a2f3aa27 | KU | 49,131 | no | neither | no | evidence missing; see data notes |
| 15 | c6853660 | KU | 79,725 | no | neither | no | evidence missing; see data notes |
| 16 | b01defab | KU | 10,052 | no | neither | no | evidence missing; see data notes |
| 17 | 0f05491a | KU | 3,657 | yes | later | no | context ignored |
| 18 | 6aeb4375 | KU | 1,708 | yes | later | yes | context used, correct |
| 19 | 06db6396 | KU | 34,746 | no | neither | no | evidence missing |
| 20 | 89941a94 | KU | 12,659 | no | neither | no | evidence missing; see data notes |

Every distance comes from `distance_tokens` in the rows.

## `0f05491a`: the context ignored

"How many stars do I need to reach the gold level on my Starbucks Rewards
app?" The later evidence turn, `answer_d6d2eba8_2:6`, was in the context and
says explicitly "120 stars, not 300". The gold answer, 120, is right. The model
answered 300, which is Starbucks' real earlier rule: it ignored the context in
favour of its training data. This is neither a retrieval error nor a data
error.

## Data notes

These do not affect the baseline, whose evidence was missing in all five. They
are to be checked in M2 and M3, where a strategy may reach the evidence.

- `51a45a95`: the marked evidence turn, `answer_d61669c7:4`, does not mention
  Target. The answer needs turn 2 of the same session and is an inference. A
  turn-based retrieval risks `reached=True` without the answer being in the
  context.
- `c6853660`: the later evidence turn says "thinking of changing to two cups";
  the gold answer says "you increased".
- `a2f3aa27`: the later evidence turn says "close to 1300"; the gold answer
  says 1300.
- `89941a94`: the question says "gravel bike"; the evidence says "hybrid bike".
- `b01defab`: both evidence turns were outside the context, but three messages
  from the later session, `answer_8c0712af_2:9` to `:11`, were in it and
  discuss the book's ending. The model still answered that it did not know.

## Against the hypotheses

H1 to H3 are the three hypotheses in `docs/vg-project.md`, in order.

H1 is confirmed: all three questions where the evidence was reached lie within
6.3k tokens of the question, all 17 misses at least 10k away, and every miss
was "I do not know". H2 and H3 are untested. H2 is settled in M2 by breakdown
`both` against correct; H3's cost is estimated from `history_tokens`.
`0f05491a` is a model error outside the hypotheses.
