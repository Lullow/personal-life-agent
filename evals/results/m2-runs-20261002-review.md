# Review of the M2 runs `retrieval-20261002-193417` and `recent-turns-20261002-193902`

The answers of both M2 runs read by hand on 2026-10-03, as ADR 0008 requires
before any figure is reported. The rows are in this directory: `RetrievalMemory`
(ADR 0011) and `RecentTurnsMemory` without a turn window, commit c242d35,
`openai/gpt-4o-2024-08-06`, the first 61 questions of each type. The reading
files were written by `evals/write_run_reading.py`, split into the groups
below. The author read them and discussed the classification with an AI
assistant in chat; the classification was then checked against the rows and
the dataset, which is where the ids and quotations below come from.

## Figures

| | single-session-user | knowledge-update |
|---|---:|---:|
| `RetrievalMemory`, correct | 50 of 61 | 47 of 61 |
| `RecentTurnsMemory`, correct | 3 of 61 | 9 of 61 |
| `RetrievalMemory`, evidence reached | 59 of 61 | 61 of 61 |
| `RecentTurnsMemory`, evidence reached | 6 of 61 | 11 of 61 |

No call failed, every verdict was `yes` or `no`, and no recall was over budget,
so no question was run again. The harness counts $5.01 for the two runs.

## Summary

- **No answer followed an instruction from a filler conversation**, in either
  run. Every answer either answered the question or said that it did not know.
- **No grading error was found.** `50635ada` is correct but worded as an
  inference; both evidence turns were in its context.
- **`RetrievalMemory`'s 14 errors on `knowledge-update`:** 13 with both evidence
  turns in the context and 1 with the later only. Of the 13, **6 answered with
  the old value**, 5 did not find the new value, and 2 reasoned wrongly from
  values it had found.
- **`RetrievalMemory`'s 11 errors on `single-session-user`:** 9 with the
  evidence in the context, of which 8 answered "I do not know" and 1 is a data
  defect; 2 where the evidence never reached the context, both lexical misses.
- **`RecentTurnsMemory`'s 2 correct answers without evidence in the context**
  are not guesses: in both, other turns of the evidence session restate the
  fact and were in the context.

## `RetrievalMemory` on `knowledge-update`, both evidence turns in the context, wrong (13)

A: answered with the old value. B: did not find the new value. C: another
wrong answer. E: the evidence or the gold answer is unclear in the data.

| question | reading | note |
|---|---|---|
| `07741c45` | A | under the bed → shoe rack; answered "under your bed". The later turn is loosely worded (E?). |
| `6071bd76` | C | 6 oz → 5 oz per tablespoon; stated both values in the right order and concluded "more water". |
| `a2f3aa27` | B, E | 1250 → "close to 1300"; the new value is vague in the data. "I do not know." |
| `0f05491a` | B | 125 → 120; four numbers in the evidence (400, 125, 300, 120). "I do not know." |
| `c4ea545c` | B | 3 days → 4 times a week; saw only the old schedule and said there was nothing to compare with. Borderline A. |
| `69fee5aa` | A | 37 → 38; answered 37. The new value is never written out, it is 37 + 1. |
| `59524333` | A | 7:00 pm → 6:00 pm; answered 7:00 pm. |
| `7401057b` | B | one night → two. "I do not know." |
| `852ce960` | A | $350,000 → $400,000; answered $350,000. The later turn looks back rather than announcing a change (E?). |
| `1cea1afa` | B | 500 → 600. "I do not know." |
| `ba61f0b9` | A | 5 → 6 women; answered 5. |
| `f685340e` | C | weekly → every other week; put "every other week" as the earlier frequency and missed "weekly". |
| `4b24c848` | A | 3 → 5; answered 3. |

6 A, 5 B, 2 C. A preliminary sort made from the answers alone, before the
reading, had `6071bd76` as A, `c4ea545c` as unclear and `f685340e` as a possible
grading error; on reading the evidence, the classification above holds.

The fourteenth error, `0977f2af`, had only the later evidence turn in the
context. The question asks for the earlier value, and the turn that states it
shares almost no word with the question.

## `RetrievalMemory` on `single-session-user`, evidence in the context, wrong (9)

| question | reading | note |
|---|---|---|
| `51a45a95` | E | Answered "last Sunday from your email inbox". The marked turn, `answer_d61669c7:4`, does not mention Target; the turn that does, `answer_d61669c7:2`, was not in the context. `reached` is true here without the answer being in the context, as the pilot review warned. |
| `545bd2b5` | B | The evidence says "around 2 hours". |
| `60d45044` | B | The evidence says "my favorite Japanese short-grain rice". |
| `b86304ba` | B, E | The evidence says "flea market find", not "painting of a sunset". |
| `311778f1` | B | The evidence says "I think I spent 10 hours". |
| `6ade9755` | B | The evidence says "can't make it to Serenity Yoga". |
| `76d63226` | B | The evidence says "new Samsung 55-inch". |
| `1faac195` | B | The evidence says "my sister Emily in Denver". |
| `118b2229` | B | The evidence says "45 minutes each way". |

In seven of the eight B cases the answer stands verbatim in the evidence turn,
among about 45 recalled messages. These are the model's errors, not the
strategy's: the evidence was on the sheet.

The two misses where the evidence never reached the context are lexical, as
ADR 0011 says they would be: `75499fd8`, where the evidence turn shares no word
with the question ("Golden Retriever" against "breed" and "dog"), and
`25e5aa4f`, a paraphrase ("completed", "undergrad", "CS" against "complete",
"Bachelor's degree", "Computer Science"). In both, "I do not know" was the
reasonable answer.

## `RecentTurnsMemory`, correct without evidence in the context (2)

- `603deb26`: the evidence turns are `answer_8afdebac_1:4` and
  `answer_8afdebac_2:0`, neither in the context. Two later turns of the same
  session were, and both restate the fact: `answer_8afdebac_2:6` ("I've tried
  making it at home 10 times now since my friend Emma showed me how to make
  it") and `answer_8afdebac_2:10`.
- `b01defab`: other turns of the evidence session in the context discuss the
  book's ending, as the pilot's data notes said.

The dataset marks one turn per value, and a fact restated later in the same
session is not marked. Per-turn recall therefore undercounts what reached the
model in such cases, and a correct answer at recall 0 is not always a guess.

## Other notes from the skim of all answers

- `0f05491a`, `RecentTurnsMemory`: answered from training data (300 stars, 12
  months), as in the pilot.
- `853b0a1d`, `RecentTurnsMemory`: "I do not know" in other words, graded
  correctly as wrong.
- `a2f3aa27`, `c6853660`, `89941a94` and `b01defab` from the pilot's data
  notes: with the evidence in the context, `RetrievalMemory` answered
  `c6853660` and `89941a94` correctly, `a2f3aa27` with "I do not know", and
  `b01defab` correctly.

## Sister questions

Two pairs of measured `knowledge-update` questions share their evidence
sessions and differ in which value they ask for: `07741c44` ("Where do I
initially keep my old sneakers?", gold "under my bed") with `07741c45`
("currently", gold "in a shoe rack in my closet"), and `89941a93` with
`89941a94`. The haystacks differ. `RetrievalMemory` answered "under your bed"
to both of the first pair, right once and wrong once. The 61 questions are
therefore not 61 independent facts; the report states it. No
`single-session-user` pair shares evidence.

## Against the hypotheses

H1 to H3 are the three hypotheses in `docs/vg-project.md`, in order.

H1 holds: `RecentTurnsMemory` reaches the evidence in 6 and 11 of 61 questions
and answers 3 and 9 correctly; 106 of its 122 answers are "I do not know".

H2's first half holds: `RetrievalMemory` answers 50 of 61 `single-session-user`
questions against the baseline's 3. Its second half, that it answers wrong more
often when a fact has changed, has no clear support in the figures: 47 of 61
against 50 of 61 is a difference of three questions, within what one would
expect by chance at this size. The mechanism the hypothesis names does occur:
in 6 of 61 `knowledge-update` questions the model answered with the old value
with the new one in the context. It accounts for 6 of the 14 errors; 5 more are
the model not finding the new value, and in 2 it found both values and
reasoned wrongly. With both values in the context, 45 of 58 answers were right.

H3 is untested until M3.

## Limitations carried to the report

- The answer model is not deterministic at temperature 0. The two-question
  check `retrieval-20261002-193258` answered `c8c3f81d` with "I do not know";
  the full run, on the same context, answered Nike. Against the pilot, the new
  baseline run gives the same verdict on 19 of 20 questions, on identical
  context; `b01defab` changed from "I do not know" to correct.
- Per-turn recall misses restatements of a fact in unmarked turns.
- `reached` can be true without the answer in the context (`51a45a95`).
- Two pairs of `knowledge-update` questions share their evidence.
- The matching is lexical: 3 of 122 misses are paraphrases.
