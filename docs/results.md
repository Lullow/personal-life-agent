# Results (draft)

Status: M3, three strategies, all answers read by hand.

Every figure here is printed by `evals/results_table.py` from the rows in
`evals/results/`, and `--check` finds each one in this file. The first two
runs were made on commit `c242d35` with `openai/gpt-4o-2024-08-06`, 61
questions per type, under ADRs 0004–0011; no call failed and nothing was over
budget, and the answers were read by hand before these figures were written
(`evals/results/m2-runs-20261002-review.md`). The third run was made on the
code of `fa2d293`, the night of 3–4 October, under ADRs 0013–0017 as well,
with `openai/gpt-4o-mini-2024-07-18` consolidating; its rows say
`fa2d293+dirty` because two untracked result files sat in the tree, not
because any code differed. No question errored and nothing was over budget;
91 consolidation calls failed, every one a reply that looped until its JSON
never closed, and 17 sessions were skipped for it (0016).

## The table

| | single-session-user | knowledge-update |
|---|---:|---:|
| `RecentTurnsMemory`, correct | 3 of 61 (0.05) | 9 of 61 (0.15) |
| `RetrievalMemory`, correct | 50 of 61 (0.82) | 47 of 61 (0.77) |
| `ConsolidatingMemory`, correct | 14 of 61 (0.23) | 20 of 61 (0.33) |
| `RecentTurnsMemory`, evidence reached | 6 of 61 | 11 of 61 |
| `RetrievalMemory`, evidence reached | 59 of 61 | 61 of 61 |
| `ConsolidatingMemory`, evidence reached | 6 of 61 | 10 of 61 |
| `RecentTurnsMemory`, recall / precision | 0.098 / 0.0030 | 0.087 / 0.0048 |
| `RetrievalMemory`, recall / precision | 0.967 / 0.0236 | 0.986 / 0.0488 |
| `ConsolidatingMemory`, recall / precision | 0.098 / 0.0034 | 0.079 / 0.0050 |
| `RecentTurnsMemory`, messages / tokens recalled | 39 / 7,809 | 39 / 7,751 |
| `RetrievalMemory`, messages / tokens recalled | 45 / 7,997 | 43 / 7,998 |
| `ConsolidatingMemory`, messages / tokens recalled | 36 / 7,791 | 36 / 7,776 |
| `RecentTurnsMemory`, cost per question, counted / with framing | $0.0198 / $0.0203 | $0.0197 / $0.0201 |
| `RetrievalMemory`, cost per question, counted / with framing | $0.0204 / $0.0209 | $0.0204 / $0.0209 |
| `ConsolidatingMemory`, cost per question, counted / with framing | $0.0847 / $0.0852 | $0.0846 / $0.0851 |

Correct is the share of answers the judge accepted (0008). Evidence reached
is the number of questions where at least one evidence turn was in the
context; recall and precision are per turn, averaged over questions (0009).
For `ConsolidatingMemory` both count its window only: the summary's id
matches no evidence (0013), so its recall is the baseline's with S tokens
less, and what the summary carried shows in accuracy and in the figures
below. Messages and tokens are what one recall held, on average, against a
budget of 8,000 tokens (0006, 0007); for the third row one of the messages is
the summary. Cost is the strategy's calls per question, each at its model's
price: the answer call, and for `ConsolidatingMemory` its consolidation calls
as well (0010, 0015); counted by the harness, and with the 4 tokens per
message and 3 per call the provider adds (0010). Grading is not included.

The `knowledge-update` breakdown of 0009, which of a question's two evidence
sessions reached the context, as questions and correct answers:

| | neither | earlier | later | both | not two sessions |
|---|---:|---:|---:|---:|---:|
| `RecentTurnsMemory` | 48, 2 | 0, 0 | 11, 7 | 0, 0 | 2 |
| `RetrievalMemory` | 0, 0 | 0, 0 | 1, 0 | 58, 45 | 2 |
| `ConsolidatingMemory` | 49, 12 | 0, 0 | 10, 8 | 0, 0 | 2 |

The third row's own figures (0013, 0015–0017):

| | single-session-user | knowledge-update |
|---|---:|---:|
| evidence consolidated, mean | 1.000 | 1.000 |
| evidence consolidated or reached | 61 of 61 | 61 of 61 |
| summary tokens, mean | 827 | 869 |
| consolidations: asked again / cut / skipped / all | 1376 / 1073 / 4 / 2963 | 1383 / 1088 / 13 / 2911 |
| consolidation per question: calls, tokens in / out | 71.1, 176,676 / 64,040 | 70.2, 176,381 / 63,941 |
| cost per question: answer + consolidation | $0.0198 + $0.0649 | $0.0198 + $0.0648 |

Evidence consolidated is the share of evidence turns the consolidator read,
from each summary's `derived_from`; the second breakdown counts a session as
reached when it was read or in the window:

| | neither | earlier | later | both | not two sessions |
|---|---:|---:|---:|---:|---:|
| `ConsolidatingMemory` | 0, 0 | 0, 0 | 0, 0 | 59, 20 | 2 |

## What the table says

At the same budget, `RetrievalMemory` answers about four questions in five
and `RecentTurnsMemory` about one in ten. The baseline's reach is its
distance: it sees the evidence only when less than the budget lies between the
evidence and the question, which is 6 and 11 of the 61 questions, and it
answers "I do not know" in 106 of its 122 answers, `RetrievalMemory` in 16.

**The first hypothesis holds.** `RecentTurnsMemory` answers only where the
evidence sits at the end of the history. Its two correct answers at recall 0
are not guesses: unmarked turns of the evidence session restate the fact.

**The second hypothesis holds in its first half and not clearly in its
second.** `RetrievalMemory` finds old facts: 50 of 61 against 3. On changed
facts it answers 47 of 61, three questions fewer, which is within what chance
would give at this size. The mechanism the hypothesis names does occur: in 6
of the 61 `knowledge-update` questions the model answered with the old value
while the new one was in the context. Of the strategy's 14 errors on that type,
6 are that, 5 are the model not finding the new value, 2 are wrong reasoning
from both values, and 1 had only the later turn in the context. With both
values in the context, 45 of 58 answers were right.

**Most of `RetrievalMemory`'s errors are the model's.** In 23 of its 25 wrong
answers the evidence was in the context. On `single-session-user`, 8 of the 9
such errors are "I do not know" with the answer stated verbatim in the
recalled turn, among about 45 messages. The strategy's own misses are two
lexical ones, where the question and the evidence share no word.

**Cost does not separate the first two rows.** Both fill the same budget, so
the answer call costs the same to within the framing: `RetrievalMemory`
recalls more and shorter messages, 45 against 39, which adds about 24 tokens
per call. The harness counts $5.01 for the two runs. What separates strategies
on cost is the calls a strategy adds beyond the answer, which neither of these
makes.

## What the third row says

The answers were read by hand before this section was written
(`evals/results/m3-runs-20261004-review.md`); the figures that come from the
reading say so.

**The third hypothesis does not hold as stated.** `ConsolidatingMemory`
answers 20 of 61 changed-fact questions against `RetrievalMemory`'s 47, and
14 of 61 single-fact questions against 50. It beats the baseline on both, 9
and 3. The mechanism the hypothesis names is real: by the reading, in every
one of its 20 correct `knowledge-update` answers the notes held the newer
value only, and in none both, so the summary does replace the old value.
What the hypothesis did not say is how little survives the replacing. The
consolidator read every evidence turn in every question, 61 of 61 in both
types, while the window alone reached 6 and 10; yet by the reading the
requested value was in the notes in only 28 of 122 questions, and in 82 of
the 88 errors it was not there at all. The "old value kept" box is empty,
because the old value was gone too. Where the question asks for the earlier
value, replacing is the error: three answers gave the newer one. "I do not
know" is the answer in 84 of 88 errors.

**The loss is bounded by distance.** Correct answers by the tokens of
conversation between the newest evidence and the question: 12 of 17 under
8,000, 13 of 26 from 8,000 to 20,000, 9 of 29 from 20,000 to 40,000, 0 of 28
from 40,000 to 70,000 and 0 of 22 beyond. Nothing stated more than about
twenty sessions before the question survived into the notes. The notes alone
account for 21 of the 34 correct answers, the window for 7, both for 5, and
one is a guess.

**It loses detail and pays for extra calls, as the hypothesis said.** The
cost per question is $0.085 against $0.020, four times the other rows: 71
consolidation calls per question, 176,000 tokens in and 64,000 out at the
consolidator's price, against one answer call. The harness counts $11.07 for
the run; OpenRouter billed $12.03, the difference the framing and the looping
replies that were paid for and thrown away. 0010's estimate of $7.06 assumed
one call per session; the second call and the loops are the rest.

**The size was held by code more than by the model.** The notes held 827 and
869 tokens on average, below the 1,000 they were held to, but the model kept
to 750 words in about half the sessions, a second call shortened a few more,
and the cut fell in 2,161 of 5,874 (0015, 0017); 17 sessions were skipped
after three looping replies (0016), none of them holding evidence. The second
call sometimes returned a fraction of the notes: in 78 consolidations in 67
questions a reply over 1,000 tokens was followed by one under 30% of its
size, and 19 questions ended with notes under 600 tokens, where 3 of 19
answers were right against 31 of 103 above. Two final notes end mid-sentence
where the model closed the JSON string at a quotation mark; the end of the
notes is then lost without being counted, and the harness cannot see how
often that happened in the intermediate notes. One set of notes collapsed to
62 tokens because the cut rule knows no Chinese full stop. Four of the 122
final notes are not in English.

## The secondary figures

- **Order sensitivity (0009).** `RecentTurnsMemory` depends on the replay
  order: in the list order of 0004 it reaches the evidence in 15
  `knowledge-update` questions instead of 11. `RetrievalMemory` does not: 61 of
  61 in both orders.
- **User turns only (0011).** With only the user turns indexed, the evidence
  reaches the context in 60 and 61 of 61 questions, against 59 and 61 with
  every turn indexed. The assistant's turns, 87% of the tokens, do not crowd
  the evidence out.
- **Order sensitivity of the third row (0009).** Replayed in list order on the
  ten `knowledge-update` pilot questions, `ConsolidatingMemory`'s window reached
  the evidence in 5 of 10, against 10 of 61 in clock order over the whole type;
  the summaries differ between the two replays as between any two runs.

## Limitations found in M2

- The answer model is not deterministic at temperature 0: the same context
  gave "I do not know" and then the right answer to `c8c3f81d`, and the new
  baseline run agrees with the pilot on 19 of 20 questions.
- Per-turn recall misses a fact restated in a turn the dataset does not mark,
  and `reached` can be true without the answer in the context (`51a45a95`).
- Two pairs of `knowledge-update` questions share their evidence sessions, so
  the 61 are not 61 independent facts.
- With 61 questions per type, one question moves a share by 0.016, and a
  difference of a few questions between rows is not a finding.

## Limitations found in M3

- The consolidator did not keep to the size it was asked for; the size was
  held by a second call and then by a cut that drops the oldest notes
  (0015, 0017). A cut summary is one the model did not make, and the cut fell
  in 2,161 of 5,874 consolidations.
- The second call sometimes returns a fraction of the notes: 78 collapses in
  67 questions; 5 questions ended with notes under 300 tokens, the smallest
  62.
- At temperature 0 the consolidator loops on some inputs, a phrase or
  whitespace repeated until the output runs out; 91 calls, 17 sessions skipped
  (0016). The loops are not deterministic: the same session passed in one run
  and failed in the next.
- The model sometimes closes the JSON string at a quotation mark; the end of
  the notes is lost without being counted. Two final notes show it; the rate
  in the intermediate notes is unknown, since successful replies were not
  kept raw.
- The cut rule's sentence ends are Latin punctuation; one Chinese set of
  notes collapsed to 62 tokens for it. Four final notes follow a filler
  session's language instead of English.
- The consolidation model is weaker than the answering model (0010); the
  gpt-4o check 0010 set aside was not made.
- The hand reading was one reading made in dialogue with an AI assistant, as
  for M1 and M2, and the notes are kept next to the review.
- The run's commit stamp carries `+dirty` from untracked result files.
