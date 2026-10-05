# 0019 — The fact graph is measured as a pilot, on 20 questions

Status: accepted
Date: 2026-10-05

## Context

0010 fixed N = 61 per type for three strategies, and that comparison, on 122
questions, is the result of the project (`docs/results.md`). 0018 adds a
fourth strategy in the last week. The project ends with a presentation on
Friday 9 October, and `docs/vg-project.md` gives the fourth strategy until
the evening of Wednesday 7 October to be measured and read, and cuts it
before anything the presentation needs.

The first ten questions of each type in `evals/longmemeval_questions.json`
are the 20 of the M1 pilot (0005, 0010). Every strategy has rows for them. In
the committed runs `RecentTurnsMemory` answered 0 of 10 `single-session-user`
and 3 of 10 `knowledge-update` questions correctly on them, `RetrievalMemory`
9 and 6, and `ConsolidatingMemory` 4 and 3.

The answering model is not deterministic at temperature 0. The M2 run of the
baseline agreed with the M1 pilot on 19 of the same 20 questions
(`docs/method.md`).

The answers of every run are read by hand before its figures are reported
(`docs/method.md`). Twenty answers can be read in the day the plan has for
it. 122 cannot.

Round three of the spike (0018) made 374 extraction calls for $0.2076. The 20
histories hold 962 sessions, and the list-order replay of 0009 on the ten
`knowledge-update` questions adds 473 more. In `RetrievalMemory`'s run an
answer cost $0.0204 a question and its grading $0.0004.

`docs/vg-project.md` puts the measurement at $26.90 when M3 closed, and the
spike cost $0.60 by its own count, against 0010's cap of $101.00. The
author read $32.14 of credits left on OpenRouter on 5 October, before the
spike.

## Decision

**The fourth strategy is measured on the 20 pilot questions**, the first ten
of each type, with `--strategy fact-graph --per-type 10`, under 0004–0009,
0013, 0014 and 0018. The rows are committed under `evals/results/`.

**It is called a pilot everywhere**: in the results, the method, the report
and the presentation. Its figures go into a table of their own, the four
strategies on the same 20 questions, where the other three are read from the
rows their committed runs have for those questions. It is never a row of the
main table. The table comes out of `evals/results_table.py`, so that
`--check` covers every figure in it.

**The list-order replay of 0009** is made on the ten `knowledge-update`
questions, which in this run is all of that type. Its extraction calls are
logged under their own label and are not the strategy's cost (0018).

**The answers are read by hand before any figure is reported**, as for M1 to
M3. For every wrong answer the reading says whether the value was in the
graph, whether it was shown, and whether the old value had been replaced or
both were held.

**What the pilot may say.** With ten questions per type one question moves a
share by 0.1, and a repeat of the same 20 questions changed one answer. A
difference of one or two questions between two rows is not a finding. The
pilot reports what happened on each question, with the counts 0018 logs, and
shows whether the mechanism works at all.

**All 122 questions are run only if the pilot is measured and read before
the stop on Wednesday and time is left.** That is then a run of its own under
the same records. It becomes a fourth row of the main table only if its
answers are read by hand before any figure from it is reported. The pilot's
table stays the pilot run's.

**If the pilot is not measured and read by Wednesday evening, the report says
that it was not made.** What is shown is then the graph of the spike, as what
it is: built, not measured.

The pilot is estimated at $1.21. Its two parts, each rounded, are $0.80 for
the extraction, the list-order replay included, and $0.42 for the answers
and their grading. All 122 are estimated at $6.07.
`evals/verify_adr_0018.py` recomputes both.

Considered and rejected:

- **All 122 at once.** The run fits the time and the money; reading 122
  answers by hand before Friday does not, and an unread row would break the
  method's own rule.
- **Another 20**, drawn at random or taken from the end of the lists. The
  first ten of each type are the ones the list's committed order gives, so
  they are not picked after any result, and every strategy already has rows
  for them. The eight unmeasured histories are the ones the prompt was shaped
  on (0018).
- **A row in the main table, marked with its N.** A share of 10 next to a
  share of 61 reads as the same kind of figure, and it is not.
- **Twenty `knowledge-update` questions and no `single-session-user`.** The
  strategy is about changed facts, but the question 0018 asks, whether a
  store without a cap keeps what the notes lost, is asked by both types.

## Consequences

The pilot cannot rank the fourth strategy against the other three. It can
show that a value was extracted, replaced and shown, or where that broke,
question by question.

The 20 questions have been used before: by the M1 pilot and by the smoke
tests of the third row. The fourth strategy's prompt was shaped on other
histories, which share 14 filler sessions with these 20 (0018).

The pilot's table sets a run of this week next to rows from runs made on 2
and 3 October. The answering model, the prompt and the grading are the same
(0008); the noise between two runs is in every cell.

The proposal named gold for what the assistant should believe at each
point in time. LongMemEval asks one question, after the last session, so the
pilot measures the last state only. What held at an earlier time is shown on
one example in the presentation and is not measured.

The money is not what limits the pilot: both estimates together are under a
tenth of what is left under the cap.
