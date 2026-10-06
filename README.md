# Personal Life Agent

A conversational terminal assistant for the small, recurring parts of daily
life — tasks, calendar events, activities, and reminders. You talk to it in
Swedish or English, and it works out what you meant.

```
You: Jag har möte på Odenplan kl 12 imorgon, behöver plugga machine learning,
     handla mat och träna på kvällen.
Agent: Jag har förberett fyra saker, vill du spara dem?

Proposed to save:

Events:
  [1] 2026-09-07 12:00 meeting - Möte på Odenplan (Odenplan)

Tasks:
  [1] - - study  - Plugga machine learning
  [2] - - errand - Handla mat

Activities:
  [1] - gym - - Träna

Will save 4 item(s); skipping 0 incomplete item(s).

Save this? [y/N]
```

Your data lives in a local SQLite file with no accounts and no sync. The model
that reads your messages does not: see [docs/privacy.md](docs/privacy.md) for
exactly what leaves your machine, and how to move to a local model.

## The VG project: a comparison of memory strategies

The repo holds two projects. One is the agent described on this page. The
other is a course project that compares ways of giving such an agent a
memory, and it is the part that is graded. If you are here for that, this
section is the place to start.

**The question.** An assistant that is talked to for weeks cannot hand the
whole conversation to the model each time. At the same budget, 8,000 tokens
of recalled conversation per answer, which kinds of memory question does each
strategy answer, and at what cost?

**What was built.** One interface, `ConversationMemory` in
`life_agent/agent/memory.py`, with the strategies behind it, and a harness,
`evals/longmemeval.py`, that drives them without the agent. For each of 122
questions from the LongMemEval benchmark it replays a history of about 48
sessions into the strategy, asks the question, and has the answer graded.
Half the questions ask for a fact the user stated once, half for a fact the
user later changed.

**The result.** Correct answers per question type, and what the strategy's
model calls cost:

| | a fact stated once | a fact that changed | cost per question |
|---|---:|---:|---:|
| `RecentTurnsMemory`: the most recent turns, as the agent does today | 3 of 61 | 9 of 61 | $0.020 |
| `RetrievalMemory`: BM25 search over every turn | 50 of 61 | 47 of 61 | $0.020 |
| `ConsolidatingMemory`: a summary rewritten after every session | 14 of 61 | 20 of 61 | $0.085 |

Search answers about four questions in five and costs what the baseline
costs. The summary beats the baseline and not the search, at four times the
price: the model that writes it read every turn that holds an answer, and
most of the answers did not survive the rewriting. Of the three hypotheses
the project set out with, the first held, the second held in its first half
and not clearly in its second, and the third did not hold as stated.

A fourth strategy, `FactGraphMemory`, keeps timestamped facts in a graph
database, Neo4j, where a newer value replaces an older one. It was built in
the last week and measured as a pilot on 20 of the questions, of which it
answered 10 of 10 and 6 of 10. With ten questions per type that shows what
happened on those questions and does not rank it against the other three.

**The method.** Each rule of the measurement was written down as a decision
record before the strategy it applies to was measured, the answers of every
run were read by hand before a figure was reported, and a script recomputes
every figure in the report from the committed rows.

**Where to read, in this order.**

1. [docs/vg-project.md](docs/vg-project.md): the question and the hypotheses,
   the plan and how each milestone closed, and
   [where the project departs from its proposal](docs/vg-project.md#where-the-project-departs-from-its-proposal).
2. [docs/method.md](docs/method.md): how a history is replayed, what the
   budget covers, how answers are graded and how recall is counted.
3. [docs/results.md](docs/results.md): the full table, what it says about
   each hypothesis, the pilot, and the limitations.
4. [docs/adr/](docs/adr/): the decision records. 0004 to 0011 and 0013 to
   0019 are the rules of the measurement.
5. The code: `life_agent/agent/memory.py` holds the interface and the four
   strategies, `life_agent/agent/fact_store.py` the graph store,
   `evals/longmemeval.py` the harness, and `evals/results/` one row per
   question and run, next to the reviews of the hand readings.

Step 5 of [docs/demo.md](docs/demo.md) shows the problem in the agent itself:
it is told something it does not save, the chat is closed, and the fact is
gone.

**Check it.** Neither command calls a model:

```bash
pytest                                            # the four strategies and the agent, with a faked model
pip install -e '.[eval]'                          # the tokenizer the harness counts with
.venv/bin/python evals/results_table.py --check   # every figure in docs/results.md and in the table above
```

The check needs the network once, to download the tokenizer's vocabulary.
Measuring a strategy again calls the model and costs money: the commands are
at the top of `evals/longmemeval.py`.

## What it does

- **Understands ordinary sentences.** One message can produce several items;
  the agent sorts them into events, tasks, activities, and reminders itself.
- **Asks before it writes.** Everything is a proposal until you answer `y`.
- **Answers questions about what you saved.** "Vad har jag imorgon?", "hur
  mycket har jag tränat den senaste månaden?" — it fetches the days in question
  and answers in words.
- **Remembers the conversation.** "Och imorgon då?" works.
- **Changes its mind with you.** Move something to another time, or remove it.
- **Reads a day as a timeline**, in the order the day is lived, rather than as
  three lists grouped by row type.

## Requirements

- Python 3.11+
- Linux, or Windows 11 via WSL
- An OpenAI-compatible API endpoint and key. The agent cannot understand
  anything without one.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env      # then fill in the LIFE_AGENT_LLM_* values
python -m life_agent init # create the local SQLite database
```

Use a capable model. A weak one misclassifies and will occasionally tell you it
saved something it did not — there is a side-by-side comparison in
[docs/llm-first-pivot.md](docs/llm-first-pivot.md).

## Usage

```bash
python -m life_agent chat
```

That is the main way in. Everything below is the same data through structured
commands, for when you would rather type than talk:

| Area | Commands |
|------|----------|
| App info | `version`, `health`, `init` |
| Tasks | `add-task`, `tasks`, `done` |
| Events | `add-event`, `events` |
| Activities | `activity`, `activities` |
| Reminders | `add-reminder`, `reminders`, `dismiss-reminder` |
| Planner | `today`, `week`, `deadlines` |
| Natural language | `complete` — mark a planned activity done |
| Interactive | `chat` — the agent |

For a full walkthrough see [docs/demo.md](docs/demo.md).

## How the agent works

One model call per message, answering with JSON:

```json
{"tool": "list_day", "arguments": {"date": "2026-09-07"}, "reply": "Jag kollar imorgon åt dig."}
```

The model chooses; it never executes. Everything that decides what may happen
lives in code:

- **ToolRegistry** (`life_agent/agent/tools.py`) is the single source of truth
  for each tool's action type and whether it needs confirmation. A hallucinated
  tool name is a failed lookup, not an execution.
- **`action_type` and `requires_confirmation` are read from the registry**, not
  from the model's own JSON, so a write can never present itself as a read.
- **AgentPolicy** re-checks the assembled decision before anything runs.
- **The conversation loop never writes.** Mutating tools come back as
  `needs_confirmation` and the CLI asks you.
- **What you are told about a write comes from the database**, not from the
  model's prose. The model may claim whatever it likes; the line after a save is
  generated from the actual result.

Read questions take a second call: the first reply is composed before any data
exists, so the retrieved rows are handed back and the model answers from them.

Details in [docs/agent-architecture.md](docs/agent-architecture.md); the
reasoning behind the design, and what it replaced, in
[docs/llm-first-pivot.md](docs/llm-first-pivot.md).

## Safety principle

> **Natural language input never writes to the database without explicit confirmation.**

Enforced in code at three independent layers, not by convention:

1. A mutating `AgentDecision` must carry `requires_confirmation`.
2. `AgentPolicy.validate_decision_safety()` rejects one that does not, and any
   unregistered tool name.
3. `life_agent/agent/safety.py` raises `PermissionError` if a write is reached
   without confirmation. Only `y`/`yes`/`j`/`ja` counts as yes — a bare Enter
   is a refusal.

This holds for saving, completing, rescheduling, and deleting alike.

## Testing

```bash
pytest                          # fast, offline, no model involved
.venv/bin/python evals/agent_eval.py   # fifteen real sentences, calls the model
```

The suite fakes the model and uses temporary databases. The eval calls your
configured provider for real, costs a few cents, and is meant to be read with
your own eyes — run it whenever you change the prompt. See
[docs/testing.md](docs/testing.md).

## Configuration

Read from environment variables, or a `.env` file beside the project (copy
`.env.example`). A real environment variable always wins over the file.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Application environment |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DB_PATH` | `data/life_agent.db` | Path to the local SQLite database |
| `LIFE_AGENT_LLM_PROVIDER` | `openai_compatible` | Provider type |
| `LIFE_AGENT_LLM_BASE_URL` | _(unset)_ | OpenAI-compatible base URL |
| `LIFE_AGENT_LLM_API_KEY` | _(unset)_ | API key for the provider |
| `LIFE_AGENT_LLM_MODEL` | _(unset)_ | Model name to request |

The last three are required.

## Project structure

```
personal-life-agent/
├── life_agent/
│   ├── agent/           # The conversation loop, tool registry, policy, safety
│   ├── cli/             # Typer commands and output formatting
│   ├── services/        # Planner, confirmation, completion, edit, read views
│   ├── db/              # SQLite connection, schema, repositories
│   ├── models/          # Pydantic domain models + shared enums
│   ├── schemas/         # Extraction / planner / confirmation shapes
│   ├── llm/             # Dependency-free OpenAI-compatible client
│   ├── config.py        # Settings, including the .env reader
│   └── main.py          # Typer app entry point
├── evals/               # The agent's eval set, the LongMemEval harness and its result rows
├── tests/               # Pytest suite (temporary databases, faked model)
├── docs/
└── pyproject.toml
```

## Status

The agent handles planning, questions, corrections, and deletions, and the
confirmation chain covers every write path. Known gaps, in the order they bite:

- **Reminders do not remind.** There is no scheduler; they are rows you can ask
  about. This is the largest gap against the original idea.
- **The schema cannot express "tomorrow, time unknown"** for an activity, so the
  agent asks for a clock time rather than losing the day.
- Family sharing, meal suggestions, local events, and daily AI news remain
  ideas. See [docs/roadmap.md](docs/roadmap.md).

## License

Private / personal project.
