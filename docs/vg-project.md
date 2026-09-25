# The VG project and the agent project

The `personal-life-agent` repo holds two projects. Read this before proposing
larger work in the memory layer.

## Two projects, one repo

**The VG project** compares three conversation-memory strategies against each
other on LongMemEval: `RecentTurnsMemory`, `RetrievalMemory` and
`ConsolidatingMemory`. The comparison is what gets graded.

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
that has changed). Tentatively 30 questions per type; M1 fixes the number once
the cost per question is known.

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
- `RecordingLLMClient` measures the cost per question with a real tokenizer,
  and the number of questions per type is fixed from it.
- The harness rules are recorded as ADRs before the run: turns are numbered
  exactly as the dataset lists them, `ApproxTokenCounter` is refused, and
  `tokens_used` is reported per question, since the baseline's turn window
  binds before the budget does.
- The method section exists as a draft.

**M2 — two strategies compared (step 5, first half). Done by Friday
2 October.**

- `RetrievalMemory` is built. The order of its `messages` is decided and
  recorded before it is measured.
- `RecentTurnsMemory` and `RetrievalMemory` run on all questions: a table of
  two strategies × two types, with results and analysis in the report.
- This is a complete result on its own.

**M3 — three strategies (step 5, second half). Done by Tuesday 6 October.**

- `ConsolidatingMemory` is built. Before it is measured, two rules are
  recorded as ADRs: how a summary counts toward recall, and where the
  strategy's clock comes from during a replay.
- It runs on the same questions: the full table of three strategies × two
  types.
- Hard stop. If it is not measured by the end of Tuesday 6 October, the report
  covers M2 and states that M3 was not done.

**Step 7 — the report. Wednesday 7 to Friday 9 October.** No new code. The
report is finished here, not started: each milestone has already added its
part.

**Step 4 — persistence, timestamps and session ids, in memory's own store.**
After the deadline. Persistence is needed by the agent, not by the
measurement. Tentative until it is known whether the course requires it.

## Keeping on track

- Every milestone has an end date. A milestone that runs over is cut, not
  extended.
- Cut order: step 4 first, then the number of questions per type, then
  `ConsolidatingMemory`. M2 always stays.
- A measurement rule is decided and recorded as an ADR before the strategy it
  applies to is measured, so no method is tuned to its own result.
- Each milestone date is a checkpoint: compare progress with this plan, and
  cut by the order above if it lags.

## Scope rule

`life_agent` is a prototype under construction. New capabilities in the agent
are built only when they block the measurement. Everything else waits until
after the course.
