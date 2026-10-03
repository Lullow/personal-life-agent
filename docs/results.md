# Results (draft)

Status: M2, two strategies. M3 adds `ConsolidatingMemory` as a third row.

Every figure here is printed by `evals/results_table.py` from the rows in
`evals/results/`, and `--check` finds each one in this file. Both runs were
made on commit `c242d35` with `openai/gpt-4o-2024-08-06`, 61 questions per
type, under ADRs 0004–0011. No call failed and nothing was over budget. The
answers were read by hand before these figures were written
(`evals/results/m2-runs-20261002-review.md`).

## The table

| | single-session-user | knowledge-update |
|---|---:|---:|
| `RecentTurnsMemory`, correct | 3 of 61 (0.05) | 9 of 61 (0.15) |
| `RetrievalMemory`, correct | 50 of 61 (0.82) | 47 of 61 (0.77) |
| `RecentTurnsMemory`, evidence reached | 6 of 61 | 11 of 61 |
| `RetrievalMemory`, evidence reached | 59 of 61 | 61 of 61 |
| `RecentTurnsMemory`, recall / precision | 0.098 / 0.0030 | 0.087 / 0.0048 |
| `RetrievalMemory`, recall / precision | 0.967 / 0.0236 | 0.986 / 0.0488 |
| `RecentTurnsMemory`, messages / tokens recalled | 39 / 7,809 | 39 / 7,751 |
| `RetrievalMemory`, messages / tokens recalled | 45 / 7,997 | 43 / 7,998 |
| `RecentTurnsMemory`, cost per question, counted / with framing | $0.0198 / $0.0203 | $0.0197 / $0.0201 |
| `RetrievalMemory`, cost per question, counted / with framing | $0.0204 / $0.0209 | $0.0204 / $0.0209 |

Correct is the share of answers the judge accepted (0008). Evidence reached
is the number of questions where at least one evidence turn was in the
context; recall and precision are per turn, averaged over questions (0009).
Messages and tokens are what one recall held, on average, against a budget of
8,000 tokens (0006, 0007). Cost is the answer call per question: counted by
the harness, and with the 4 tokens per message and 3 per call the provider
adds (0010). Grading is not included.

The `knowledge-update` breakdown of 0009, which of a question's two evidence
sessions reached the context, as questions and correct answers:

| | neither | earlier | later | both | not two sessions |
|---|---:|---:|---:|---:|---:|
| `RecentTurnsMemory` | 48, 2 | 0, 0 | 11, 7 | 0, 0 | 2 |
| `RetrievalMemory` | 0, 0 | 0, 0 | 1, 0 | 58, 45 | 2 |

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

**Cost does not separate the two rows.** Both fill the same budget, so the
answer call costs the same to within the framing: `RetrievalMemory` recalls
more and shorter messages, 45 against 39, which adds about 24 tokens per
call. The harness counts $5.01 for the two runs. What separates strategies on
cost is the calls a strategy adds beyond the answer, which neither of these
makes; that is M3's question.

## The secondary figures

- **Order sensitivity (0009).** `RecentTurnsMemory` depends on the replay
  order: in the list order of 0004 it reaches the evidence in 15
  `knowledge-update` questions instead of 11. `RetrievalMemory` does not: 61 of
  61 in both orders.
- **User turns only (0011).** With only the user turns indexed, the evidence
  reaches the context in 60 and 61 of 61 questions, against 59 and 61 with
  every turn indexed. The assistant's turns, 87% of the tokens, do not crowd
  the evidence out.

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
