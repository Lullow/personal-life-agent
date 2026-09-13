# The VG project and the agent project

The `personal-life-agent` repo holds two projects. Read this before proposing
larger work in the memory layer.

## Two projects, one repo

**The VG project** compares three conversation-memory strategies against each
other on LongMemEval: `RecentTurnsMemory`, `RetrievalMemory` and
`ConsolidatingMemory`. The comparison is what gets graded.

**The agent project** is the household planner itself — the `life_agent`
package, a Typer CLI. In the VG project it is the consumer of the memory layer
and the demo, not the thing being measured. The evaluation runs headless, and
the agent never appears in the measured path (see "Memory layer" in
`CLAUDE.md`).

## Constraints

- Six weeks in total.
- One developer.
- API calls are self-funded, and the total stays under 1000 SEK.

## Step plan

Steps run in this order: 1–3, H, 4, 5, 6.

**Steps 1–3 — `memory.py`, wiring it into the agent, the outcome contract.**
Done, on the branch `memory-layer`, all behaviour-preserving. The decisions
behind them are recorded in `docs/adr/`:

- 0001 — deterministic record ids instead of uuid4
- 0002 — the window truncates at retrieve, not at write
- 0003 — `ApproxTokenCounter` as the default, tiktoken injected in the eval

**Step H — the harness, plus the baseline against 20 LongMemEval questions,
in memory.** Prioritised ahead of step 4. Persistence is needed by the agent,
not by the measurement, and the storage format should be decided after the
benchmark's data format has been seen.

**Step 4 — persistence, timestamps and session ids, in memory's own store.**

**Step 5 — `RetrievalMemory` and `ConsolidatingMemory`.** If time runs short,
`ConsolidatingMemory` is the first thing cut.

**Step 6 — full measurement, all strategies.**

## Scope rule

`life_agent` is a prototype under construction. New capabilities in the agent
are built only when they block the measurement. Everything else waits until
after the course.
