# 0005 — Which questions are measured

Status: accepted
Date: 2026-09-26

## Context

The comparison uses two question types from LongMemEval_S:
`single-session-user` (find a fact) and `knowledge-update` (a fact that has
changed). The file pinned in 0004 holds 70 and 78 of them. M1 measures 10 per
type; the number for the full comparison is fixed after M1, from the measured
cost.

Every question that enters the table has to be chosen before any strategy has
been run on it. A selection made after seeing results can favour one strategy
without anyone deciding to. And the questions must be the same for every
strategy and every milestone, so that M2 and M3 add rows to M1's table rather
than start a new one.

Some questions cannot be measured fairly under the rules in 0004:

- **Abstention questions**, whose ids end in `_abs`: 6 of each type. The right
  answer is that the history does not say. They mark no evidence turns, so
  recall is undefined, and LongMemEval grades them with a different template.
- **Histories with a repeated session id**: `58bf7951`, `1e043500` and
  `001be529` (`single-session-user`), `18bc8abd` and `c7dc5443`
  (`knowledge-update`). In all five the repeat is a filler session, never
  evidence.
- **Evidence timed against the update it records**: `618f13b2`. "Four times"
  is dated 22:16 and "six times" 17:45 on the same day, and the answer is six.
  In clock order (0004) the update runs backwards. It is the only question of
  the two types whose evidence sessions come in a different order by time than
  in the list.

`2133c1b5`, whose updated value is timed hours after the question on the same
day, is measured: 0004 treats a question as asked at the end of its day.

## Decision

A question is **eligible** when it is one of the two types, is not an
abstention question, has no repeated session id, and has at least one evidence
turn, with every evidence session dated on or before the question's day and in
the same order by time as in the list. That leaves **61 `single-session-user`
and 69 `knowledge-update`** questions.

Within each type, eligible questions are ordered by
`sha256(question_id.encode()).hexdigest()`, ascending. **A run of N per type
takes the first N of each list.** The ordered lists are written once to
`evals/longmemeval_questions.json` and committed. They are generated only after
this record is committed, so the rule is fixed before anyone sees which
questions it picks. The harness must read that file and never recompute the
order during a run.

M1 takes the first 10 of each. When N grows, it grows by taking more of the
same list. Nothing is ever drawn again.

For every question the harness also logs how many tokens of conversation lie
between the newest evidence turn and the question. Questions are not filtered
on it. The distance is what "long-term", as `docs/vg-project.md` defines it,
is measured by. It also shows whether a small sample happens to sit near or
far from the evidence compared with the pool: that is reported, and is never a
reason to draw again.

Considered and rejected:

- **A seeded shuffle.** A seed is a number someone could change and try again.
  Ordering by a hash of the id leaves nothing to choose.
- **The first N in file order.** The file's order is whatever produced it, and
  nothing says it is unrelated to difficulty.
- **Picking by hand, or stratifying by where the evidence sits.** Either one is
  a choice made while looking at the questions, which is what this record
  exists to prevent.

## Consequences

The M1 pilot questions are part of the final set, so the baseline measured in
M1 is the first rows of the final table, not a separate experiment.

The pool caps the comparison at 61 and 69 questions. The tentative 30 per type
fits; anything above 61 does not.

The excluded questions are not a random sample of the dataset. Abstention is
a question type this comparison does not measure, and the other six are data
defects that have nothing to do with difficulty. The method section lists all
of them by id.

With 10 questions per type, one question moves an accuracy figure by ten
percentage points. M1's numbers are a pilot and have to be reported as one.

The question list is tied to the pinned file. A different revision of the
dataset means a new list and a new record.
