# The VG project and the agent project

The `personal-life-agent` repo holds two projects. Read this before proposing
larger work in the memory layer.

## Two projects, one repo

**The VG project** compares three conversation-memory strategies against each
other on LongMemEval: `RecentTurnsMemory`, `RetrievalMemory` and
`ConsolidatingMemory`. The comparison is what gets graded. A fourth strategy,
`FactGraphMemory`, was built in M4 and measured as a pilot in a table of its
own (0018, 0019); it is not a part of that comparison.

**The agent project** is the household planner itself — the `life_agent`
package, a Typer CLI. In the VG project it is the consumer of the memory layer
and the demo, not the thing being measured. The evaluation must run headless,
and the agent must never appear in the measured path (see "Memory layer" in
`CLAUDE.md`).

## Goal

**Question.** At the same token budget, which kinds of memory question does
each strategy answer, and at what cost?

**Hypotheses.**

- `RecentTurnsMemory` is the floor. It answers only questions whose evidence
  sits at the end of the history.
- `RetrievalMemory` finds old facts, but answers wrong more often when a fact
  has changed: it retrieves the old value and the new one without knowing
  which holds.
- `ConsolidatingMemory` handles changed facts better, because the summary
  replaces the old value. It loses detail and pays for extra calls.

**Selection.** Two question types from LongMemEval_S that separate the
hypotheses: `single-session-user` (find a fact) and `knowledge-update` (a fact
that has changed). M1 fixes the number per type, N, from the estimated total
cost of the comparison, consolidation included. N is at most 61, the number of
eligible `single-session-user` questions (0005).

**Measures.** Share of correct answers per type, retrieval precision and
recall, and tokens per answer.

**Long-term, defined.** A fact counts as long-term memory when it was stated
in an earlier session and more conversation lies between it and the question
than fits in the token budget. Distance is measured in conversation, not in
wall-clock time: LongMemEval histories come dated and are replayed in one
pass.

**Done when** a table of three strategies × two question types exists, and the
whole measurement has cost under 1000 SEK.

## Constraints

- Six weeks in total, ending Friday 9 October 2026.
- One developer.
- API calls are self-funded, and the total stays under 1000 SEK.

## Milestones

Each milestone ends in a result that could be handed in on its own, so running
out of time costs the last milestone rather than the whole comparison. Step
numbers from the original plan are kept, because `CLAUDE.md` refers to them.
Step 6, the full measurement, is no longer a step of its own: each milestone
measures every strategy built so far on all questions. Weekends are buffer,
not planned time.

**Steps 1–3 — `memory.py`, wiring it into the agent, the outcome contract.**
Done, on the branch `memory-layer`, all behaviour-preserving. The decisions
behind them are recorded in `docs/adr/`:

- 0001 — deterministic record ids instead of uuid4
- 0002 — the window truncates at retrieve, not at write
- 0003 — `ApproxTokenCounter` as the default, tiktoken injected in the eval

**M1 — the baseline, measured (step H). Done by Tuesday 29 September.**

- `evals/longmemeval.py` runs `RecentTurnsMemory` headless on 20 questions,
  10 of each type.
- `RecordingLLMClient` measures the cost per question with a real tokenizer.
  N per type is fixed from the estimated total cost of all three strategies,
  consolidation calls included, and is at most 61.
- The harness rules are recorded as ADRs before the run, 0004–0009: how a
  history is replayed, which questions are measured, how tokens are counted,
  the baseline filling the budget instead of keeping its turn window, how
  answers are produced and graded, and how precision and recall are computed.
  `ApproxTokenCounter` is refused, as 0003 already decided.
- The method section exists as a draft.

Closed at the checkpoint on Friday 2 October, three days late. The harness,
the pilot run, ADRs 0004–0009 and N (ADR 0010) are done. The method section is
not: `docs/method.md` holds one sentence. It is not finished before M2 starts;
the points each ADR requires are written alongside M2.

**M2 — two strategies compared (step 5, first half). Done by Friday
2 October.**

- `RetrievalMemory` is built. The order of its `messages` is decided and
  recorded before it is measured.
- `RecentTurnsMemory` and `RetrievalMemory` run on all questions: a table of
  two strategies × two types, with results and analysis in the report.
- This is a complete result on its own.

Closed at the checkpoint on Saturday 3 October, one day late. `RetrievalMemory`
is built under ADR 0011, both strategies ran on all 122 questions on 2 October,
the answers were read by hand on 3 October, and the table with its analysis is
in `docs/results.md`, every figure checked by `evals/results_table.py`. The
method section carried over from M1 is written. Whether M3 fits before its
hard stop is decided on Monday 5 October.

**M3 — three strategies (step 5, second half). Done by Tuesday 6 October.**

- `ConsolidatingMemory` is built. Before it is measured, three rules are
  recorded as ADRs: which model consolidates, how a summary counts toward
  recall, and where the strategy's clock comes from during a replay.
- It runs on the same questions: the full table of three strategies × two
  types.
- Hard stop. If it is not measured by the end of Tuesday 6 October, the report
  covers M2 and states that M3 was not done.

Closed at the checkpoint on Sunday 4 October, two days before the hard stop.
`ConsolidatingMemory` is built under ADRs 0015–0017 (0012 superseded after the
first smoke test) with 0013 and 0014; it ran on all 122 questions the night of
3–4 October, the answers were read by hand on 4 October, and the full table of
three strategies × two types with its analysis is in `docs/results.md`, every
figure checked by `evals/results_table.py`. The method section covers the
third strategy. Three rules were reopened before the strategy was measured,
each on a smoke test and each as a new record; nothing measured had to be
measured again. The gpt-4o check that 0010 set aside was not made. The
measurement has cost $26.90 so far, about 266 SEK at 0010's rate.

**M4 — a fourth strategy as a pilot, and the presentation. Monday 5 to
Friday 9 October.**

Added on Sunday 4 October, the day M3 closed, when the project was compared
with its proposal. The proposal named a strategy of timestamped facts with
explicit overwrite, and the reply to it suggested adding a graph database or
another complementary data storage architecture. Neither had been built. The
examination is a 30-minute presentation with screen sharing on Friday
9 October, so the presentation is prepared first and never waits for the
fourth strategy.

- `FactGraphMemory` is built: facts extracted from each session, kept with
  their times in Neo4j, a newer value replacing an older one. A spike on the
  eight histories no run measures comes first, to see what an extraction
  gives. Then its design and its scope are recorded as ADRs 0018 and 0019,
  before it is measured.
- It is measured as a pilot on the 20 pilot questions and reported in a table
  of its own, called a pilot wherever it appears. The comparison of three
  strategies on 122 questions stays the result of the project.

Three stops, each on an evening:

- **Monday 5 October.** The presentation can be given from what M1 to M3
  left: its order, the three questions it walks through and the screenshots
  to fall back on. If not, that work goes on into Tuesday and the rest of M4
  shrinks.
- **Tuesday 6 October.** The class, its tests and a smoke test are done. If
  not, no pilot is measured, and what is shown is the spike's graph as what
  it is: built, not measured.
- **Wednesday 7 October, hard stop.** The pilot is measured and its answers
  are read. If not, the report says that it was not made.

Cut order within M4: first the graph in the agent, below, then a run on all
122 questions, last the pilot. The presentation of M1 to M3 and the spike's
graph are never cut.

**An exception to the scope rule, for M4 only.** The fourth strategy may be
wired into the agent's chat, so that the presentation can show an edge being
replaced while the audience watches. The reason is the form of the
examination. The exception covers that wiring and nothing else. It is
optional, it is the first thing cut, and it is given up if it is not done in
three hours, with nothing of it committed half done. The default strategy
stays `RecentTurnsMemory`, and the agent never appears in the measured path.

The pilot closed at the checkpoint on Monday 5 October, two days before the
hard stop. `FactGraphMemory` is built under ADR 0018, after a spike of three
rounds on the eight histories no run measures. It ran as a pilot on the 20
pilot questions on 5 October under ADR 0019: 1,475 calls, none failed, no
session skipped, and 30 graphs in Neo4j, one for each of the 20 questions and
10 for the list-order replays of the `knowledge-update` questions. The
answers were read by hand on 5 October, and the pilot's table of four
strategies on the same 20 questions is in `docs/results.md`, every figure
checked by `evals/results_table.py`. The method section covers the fourth
strategy and the pilot.

Of the three stops, Monday's was met a day late, on Tuesday 6 October. The
demo (`docs/demo.md`) and the script that sets one question side by side
through every strategy were there from Sunday 4 October; the order of the
presentation, the three questions it walks through and the screenshots to
fall back on went into the repo as `docs/presentation.md` on the Tuesday,
after the pilot had closed. Monday went to the spike, the two records, the
class and the pilot instead, the reverse of the order the plan set.
Tuesday's stop was met a day early, on Monday 5 October, when the class, its
tests and the smoke test were done, and Wednesday's was met the same day.

The run on all 122 questions was not made and the graph in the agent was not
built: Tuesday and Wednesday go to the presentation, where the replaced edge
is shown in Neo4j itself. By the readings of the OpenRouter account the
spike cost $0.57, the smoke test $0.11 and the pilot run $1.15 ($0.60, $0.12
and $1.18 by the harness's count); with the $26.90 at the close of M3 the
measurement has cost $28.73 so far, about 284 SEK at 0010's rate.

**Step 7 — the presentation and a short report. Thursday 8 and Friday 9
October.** The examination is the presentation. The report lives in the repo,
is kept short, and says where the project departs from its proposal and why.
No new code is written on Thursday except fixes for what is shown. The report
is finished here, not started: each milestone has already added its part.

**Step 4 — persistence, timestamps and session ids, in memory's own store.**
After the deadline. Persistence is needed by the agent, not by the
measurement. Tentative until it is known whether the course requires it.

## Where the project departs from its proposal

The project was proposed on 10 September 2026 as a comparison of three memory
strategies: simple vector search as the baseline, timestamped facts with
explicit overwrite, and consolidation by a language model. They were to be
evaluated on a dataset written for the project, of sessions in which facts
change, with gold for what the assistant should believe at each point in
time, and measured on retrieval precision and recall, on how often an answer
rests on a stale value, on token cost and on latency. The proposal named the
evaluation method as its contribution. The reply accepted it and suggested
adding a graph database or another complementary data storage architecture.

| Proposed | As it stands |
|---|---|
| Three strategies compared | Three strategies compared on 122 questions, every answer read by hand, and a fourth measured as a pilot. Two of the three are not the ones proposed. |
| Vector search, as the baseline | BM25 search, as a strategy of its own. The baseline is the most recent turns. |
| Timestamped facts with explicit overwrite | Built as `FactGraphMemory` and measured as a pilot on 20 questions. |
| A graph database, from the reply | Neo4j holds the fourth strategy's facts in the measured run. |
| A dataset of its own, with gold at every point in time | LongMemEval, which asks one question per history, after its last session. |
| Precision and recall, stale answers, token cost | Reported in `docs/results.md`. |
| Latency | Not measured. |

**The baseline is the most recent turns, and the search is BM25.** The agent
already kept its last turns, so `RecentTurnsMemory` is the floor the others
are held against, and the search became a strategy of its own. 0010 assumed
an embedding index for it and 0011 rejected one: it needed three more rules,
each with its own check (how a message longer than the model's input limit is
embedded, how embedding tokens are counted, and what a cache may hide from
the cost), the dry run could no longer have computed recall offline, and M2
was already at its date. The money was not the reason: the $0.25 that 0010
set aside for embeddings was not spent. What it costs is in
`docs/method.md`: the row is one lexical index, and a dense index would miss
less on paraphrase and was not measured.

**The timestamped facts came last, as a pilot.** Neither that strategy nor a
graph database had been built when the project was compared with its
proposal on 4 October (M4, above). `FactGraphMemory` was then built with its
facts in Neo4j (0018) and measured on the 20 pilot questions. It is not a row
of the comparison: the run on all 122 questions fitted the time and the
money, but reading 122 more answers by hand before 9 October did not, and an
unread row would break the method's own rule (0019). Nearly all its facts
hang on the user, so the graph is a star: a store of timestamped edges and
not a graph that is traversed (0018).

**The dataset is LongMemEval.** The project's own dataset was meant to grow
while the agent was built during the term. That building did not happen as
planned, so the dataset hardly exists. LongMemEval is made for this task: its
`knowledge-update` questions are a value the user states and later changes,
with gold, which is what the project's own dataset was to hold; each comes
with a history of about 48 sessions and about 100,000 tokens, and the turns
that hold the answer are marked, which is what makes recall measurable. What
the change gave up is the gold at each point in time: LongMemEval asks one
question, after the last session, so only the last state is measured. In every strategy `retrieve(at=T)` leaves out what
was written after T, and `FactGraphMemory` keeps a replaced fact, so that
what held at an earlier time can still be asked for. That is shown on one
example in the presentation and is not measured (0019). The conversations
are English; for the Swedish assistant the results are an indication to be
checked.

**Stale answers are counted in the hand reading.** The harness records
whether the judge accepted an answer. Whether a wrong answer gave the older
value is sorted by hand when the answers are read, and `docs/results.md`
reports the counts.

**Latency was not measured.** No rule for timing was recorded among the
rules of the measurement (0004–0019), and no row records how long a call
took. Cost is reported in dollars, tokens and model calls per question.

**What stands** is the part the proposal named as its contribution, the
method: a rule is recorded before the strategy it applies to is measured,
the answers are read by hand before a figure is reported, and every figure
in the report is recomputed by a script (see "Keeping on track", below).

## Keeping on track

- Every milestone has an end date. A milestone that runs over is cut, not
  extended.
- Cut order: step 4 first, then the number of questions per type, then
  `ConsolidatingMemory`. M2 always stays.
- A measurement rule is decided and recorded as an ADR before the strategy it
  applies to is measured, so no method is tuned to its own result.
- A committed ADR is closed. A finding reopens it only if it shows the
  measurement is wrong — a bug in the harness, records crossing the time
  cutoff, evidence ids that do not match `sources`, a question whose answer
  cannot be reached — not because another choice would also be defensible.
  Then a new ADR supersedes the old one, and everything measured under it is
  measured again. Every other finding goes into the report as a limitation.
- Each milestone date is a checkpoint: compare progress with this plan, and
  cut by the order above if it lags.

## Scope rule

`life_agent` is a prototype under construction. New capabilities in the agent
are built only when they block the measurement. Everything else waits until
after the course.
