# 0009 — Retrieval precision and recall, per turn

Status: accepted
Date: 2026-09-26

## Context

`docs/vg-project.md` lists retrieval precision and recall among the measures.
They answer a different question than accuracy does: not whether the model got
it right, but whether the strategy put the evidence in front of it.

The pieces exist already. Record ids are deterministic (0001), every strategy
keeps everything it was given (0002), and 0004 defines the evidence for a
question as the ids of the turns the dataset marks `has_answer: true`.
`Retrieval.sources` names the records that reached the model.

How the dataset marks evidence differs between the two types. A
`single-session-user` question marks one turn in 59 of 61 questions, the user
stating the fact. A `knowledge-update` question marks two turns in two sessions
in 65 of 69: the turn where a value was first stated and the turn where it
changed.

Not every `knowledge-update` question asks for the new value. Some ask for the
earlier one, such as `e66b632c`: "What was my previous personal best time for
the charity 5K run?" Which evidence session holds the answer therefore cannot
be read off the dates.

0004 replays each day's sessions in clock order and records that the list
order would place the evidence differently. Which order is replayed changes
what a strategy that reads the end of the history can reach.

## Decision

For one question, with `E` the evidence ids and `R` the set of
`Retrieval.sources`:

- **recall** = |R ∩ E| / |E|
- **precision** = |R ∩ E| / |R|, and 0 when `R` is empty.

`E` is never empty: 0005 admits only questions with evidence.

Per question type, both are the mean over questions, each question counting
once.

**The dataset's marks are used as they are.** Nothing is marked or unmarked by
hand.

**One breakdown, for `knowledge-update` only.** Each question's two evidence
sessions are split into the earlier and the later by the replay order of 0004,
which also orders sessions that share a day, and the harness logs which of
them reached the context: neither, the earlier only, the later only, or both.
It is a session reaching the context when any of its evidence turns is in `R`.
These four groups are reported against whether the answer was correct. The 2
`knowledge-update` questions that do not have exactly two evidence sessions are
reported separately and are not part of the breakdown; they still count in
recall and precision. The breakdown does not assume which value the question
asks for, and it is declared here, before any strategy is measured, so that it
cannot be picked afterwards because it favours one.

**Order sensitivity, for every strategy.** Recall, and whether any evidence
reached the context, are also computed with the sessions replayed as 0004's
rejected list order describes — each day in list order, with `at` set to the
day — and nothing else changed. Only `knowledge-update` questions are
affected: in `single-session-user` the two orders are the same. The figures are
reported next to the primary ones. They are declared here, before either order
has been measured, so that the order cannot be chosen afterwards. A strategy
whose model calls during replay depend on the order, such as
`ConsolidatingMemory`, is replayed in the second order only on the
`knowledge-update` questions among the 20 pilot questions; the cost of those
calls is logged under a label of its own and is not counted as the strategy's.

`sources` are compared as the strategy returns them. How a summary's id
counts, given what it was derived from, is decided in M3, before
`ConsolidatingMemory` is measured.

Considered and rejected:

- **Recall of the later evidence session only**, as the recall of "the current
  value". It is wrong for every question that asks for the earlier value.
- **Recall per session**: counting a hit when any turn of an evidence session
  is recalled. It is kinder to a strategy that finds the right conversation
  but not the right turn. It was rejected because ids, `derived_from` and the
  dataset's marks are all per turn.
- **Pooling all questions into one fraction.** A question with three evidence
  turns would then weigh three times as much as one with one.

## Consequences

Precision is bounded by the budget. With one or two evidence turns and about
38 messages recalled, a strategy that finds everything and fills the budget
scores around 0.03 to 0.05. That is expected and is not a failure. Precision
mainly shows how much of an equal budget each strategy spends on noise.

On `knowledge-update`, recall rewards having both values in context, whatever
the question asks. Whether the model then used the right one shows up in the
breakdown and in accuracy, not in recall.

A strategy that overwrites an old value with a new one gains on questions
about the current value and loses on questions about the earlier one. The
breakdown is what makes that visible.

The order sensitivity costs nothing for a strategy that makes no model calls
while replaying. For `ConsolidatingMemory` it rests on the 10
`knowledge-update` pilot questions, enough to show the direction of the effect
but not its size.

With 10 questions per type in M1, one question moves a mean by 0.1.
