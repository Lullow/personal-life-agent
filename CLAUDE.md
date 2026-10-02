# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## What this is

A conversational terminal assistant (Typer CLI) for tasks, calendar events,
activities, and reminders, spoken to in Swedish or English. Data lives in a
local SQLite file (`data/life_agent.db`); there are no accounts and no sync.

The agent is driven by a language model and does not work without one. That is
a deliberate reversal of how the project started — it used to be a deterministic
offline extractor with an optional LLM bolted on, and the reasoning behind the
change is in `docs/llm-first-pivot.md`. Read that before proposing anything that
adds pattern matching back.

This repo holds two projects: the graded memory-strategy comparison (the VG
project) and the agent that consumes it. `docs/vg-project.md` separates them —
read it before proposing larger work in the memory layer.

`docs/logg.md` is the author's lab journal, in Swedish. Do not read,
edit, or summarise it unless explicitly asked.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env               # fill in LIFE_AGENT_LLM_* — required
python -m life_agent init          # create the local SQLite database

# Tests — offline, the model is faked
pytest
pytest tests/test_conversation_agent.py -v
pytest tests/test_conversation_agent.py::TestEditFlows -v

# Eval — calls the real model, costs a few cents, read it with your eyes
.venv/bin/python evals/agent_eval.py

# LongMemEval harness — needs the eval extra and the pinned dataset in
# data/longmemeval/ (ADR 0004). Rows go to data/longmemeval/runs/.
pip install -e '.[eval]'
.venv/bin/python evals/longmemeval.py --dry-run     # offline: replay, recall, token counts
.venv/bin/python evals/longmemeval.py               # 10 per type; calls the model, costs money
.venv/bin/python evals/longmemeval.py --strategy retrieval --dry-run   # RetrievalMemory, offline
.venv/bin/python evals/verify_adr_numbers.py        # recompute every figure in ADRs 0004–0009
.venv/bin/python evals/verify_adr_0011.py           # the same for ADR 0011

# Run
python -m life_agent chat
```

There is no lint/format/type-check command configured in this repo (no
ruff/black/mypy config present) — don't invent one unless asked.

`pyproject.toml` sets `pythonpath = ["."]` for pytest, so tests import
`life_agent` without an editable install. Tests never touch the real
`data/life_agent.db`: service and repository tests pass an explicit `db_path`
into a temp dir, CLI tests set `DB_PATH` to a `tmp_path`. `tests/conftest.py`
neutralises the local `.env`, so a machine with credentials configured tests
identically to one without. Dates are made deterministic with an injectable
`reference_date`.

## Architecture

Layered, each layer depending only on the one beneath it:

```
CLI (Typer)         life_agent/cli/        — prompts for confirmation, prints output
Services            life_agent/services/   — business logic; the only orchestration layer
Repositories/DB     life_agent/db/         — SQLite access; rows <-> Pydantic models
SQLite              data/life_agent.db
```

Supporting modules: `models/` (persisted domain objects + shared enums),
`schemas/` (transient shapes for extraction/planner/confirmation boundaries),
`agent/` (the conversation loop, see below), `llm/` (dependency-free
OpenAI-compatible client using only `urllib`).

Architecture decisions are recorded as ADRs in `docs/adr/` — one numbered file
each, context / decision / consequences, never edited once written. Propose one
whenever a decision shapes code that has yet to be written, or rests on a
constraint the code cannot show. Format and the supersede rule:
`docs/adr/README.md`.

Every repository function accepts an optional `db_path`, which is how test
isolation and the `DB_PATH` env var both work. The list functions also accept
inclusive day bounds (`start`/`end`, or `due_from`/`due_to` for tasks).

### The one safety rule

> Natural language input must not write to the database without explicit
> user confirmation.

The memory layer is not an exception to this rule. It must persist natural
language to its own store, which is not the database the rule protects. Memory
has no write path to domain tables and is read-only into the prompt. No
strategy persists anything yet — `RecentTurnsMemory` keeps its records in a
list in the process — and persistence comes in step 4 (`docs/vg-project.md`).
See "Memory layer" below.

Enforced in code, not convention, at three independent layers:

1. `AgentDecision.requires_confirmation` must be `True` for any mutating
   (`write`/`update`/`delete`) decision.
2. `AgentPolicy.validate_decision_safety()` (`life_agent/agent/policy.py`)
   rejects mutating decisions lacking that flag, and any unregistered tool name.
3. `life_agent/agent/safety.py` — `assert_confirmed()` raises `PermissionError`
   if a write is reached without confirmation. `is_affirmative()` treats only
   `y/yes/j/ja` as yes; a bare Enter is a refusal.

A new write-capable tool must be registered with `requires_confirmation=True`
and routed through a confirmation flow, never called from the loop.

### The conversation loop

```
message → ConversationAgent.send()          life_agent/agent/conversation.py
  memory.retrieve(...) + system prompt → one call → {"tool", "arguments", "reply"}
  → ToolRegistry lookup → AgentDecision → AgentPolicy → dispatch → AgentTurn
```

The agent owns no message buffer; context comes from the memory Protocol — see
"Memory layer" below. Both calls that build a message list, the tool call in
`_ask_model` and the read answer in `_answer_from_data`, get it from
`retrieve(...)`, and `send()` writes the user message and the reply back through
`write()`. The default strategy is `RecentTurnsMemory` (`DEFAULT_HISTORY_TURNS`,
10 turns). After a save the CLI calls `record_outcome()`, and `end_session()`
when the chat closes.

Four things matter and are easy to break:

- **`action_type` and `requires_confirmation` come from `ToolRegistry`, never
  from the model's JSON.** This is what stops a write from presenting itself as
  a read. Do not "trust" the model's own labels for convenience.
- **The loop never writes.** Mutating tools return `kind="needs_confirmation"`
  and the CLI asks. `ConversationAgent` has no write path; keep it that way.
- **The truth line comes from the database.** What is printed after a save is
  generated from `ConfirmationSaveResult`, never from the model's `reply`. The
  model does sometimes claim things that did not happen.
- **Read turns take a second call.** The reply is composed before any data
  exists, so `_answer_from_data` hands the retrieved rows back and asks the
  model to answer. If it fails, the lead-in stands.

`AgentTurn.kind` is `"reply"`, `"display"`, or `"needs_confirmation"`.

There is no tool that assumes a day. `list_day` and `list_range` take explicit
dates; `list_today`/`list_week` were removed because while they existed,
"imorgon" kept being answered with today's schedule.

Full walkthrough with the tool table: `docs/agent-architecture.md`. Layer
details: `docs/architecture.md`.

### Editing saved items

The model never sees a database id. `reschedule_item` and `delete_item` pass a
description; `services/edit_service.py` resolves it to rows, comparing word
*openings* rather than substrings (the agent says "ryggpasset" where the title
reads "Träna rygg"). Kind and day are treated as guesses and dropped if
narrowing by them finds nothing. Several matches come back as a list to choose
from. The resolved row is shown before confirmation.

### Prompts

`life_agent/agent/prompts.py` holds both prompts. Most behaviour lives here
rather than in code, and most fixes belong here — that is the point of the
pivot. When changing a rule, run `evals/agent_eval.py` and read the replies;
several rules exist because a specific failure was observed, and a careless
rewording brings the failure back. In particular: the ban on `T00:00:00`, "save
only what is new", and "never ask for permission to save".

### Config

`life_agent/config.py` — `Settings` from env vars, falling back to a `.env`
file read by a small stdlib parser. A real environment variable always wins, and
`.env` is never merged into `os.environ`.

| Var | Default | Notes |
|---|---|---|
| `DB_PATH` | `data/life_agent.db` | |
| `LIFE_AGENT_LLM_BASE_URL` / `_API_KEY` / `_MODEL` | unset | **Required** |

Model choice matters more than it looks: a weak model misclassifies and claims
saves that did not happen. There is a measured comparison in the pivot doc.


## Memory layer

### The interface

**The interface is the contract.** If a change makes it harder to swap the
memory backend with one config line, the change is wrong, however clean it
looks.

`life_agent/agent/memory.py`

```python
@dataclass(frozen=True)
class MemoryRecord:
    id: str                   # deterministic: f"{session_id}:{turn_index}"
    role: Literal["user", "assistant"]
    content: str
    kind: Literal["message", "outcome", "summary"]
    at: datetime
    session_id: str
    derived_from: tuple[str, ...] = ()   # ids a summary ate; empty for raw turns

@dataclass(frozen=True)
class Retrieval:
    messages: list[dict[str, str]]   # ready for chat_json, current turn excluded
    sources: tuple[str, ...]         # record ids that reached the context
    tokens_used: int

class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...

class ConversationMemory(Protocol):
    def write(self, record: MemoryRecord) -> None: ...
    def retrieve(self, query: str, *, at: datetime,
                 budget_tokens: int) -> Retrieval: ...
    def end_session(self) -> None: ...
```

Three implementations, in this order. `RecentTurnsMemory` and
`RetrievalMemory` are built; the third comes in step 5 (`docs/vg-project.md`).

1. `RecentTurnsMemory` — **built.** The last N turns, windowed at retrieve. The
   agent's default, and the baseline.
2. `RetrievalMemory` — **built.** BM25 over everything, filling the budget in
   rank order and returning the messages in the order they were written, with
   no way to overwrite stale facts. **This is intentional** — it is what the
   baseline should fail at. Its rules, constants included, are fixed by ADR
   0011 and are not tuned to a result.
3. `ConsolidatingMemory` — **not built.** Rolling summary plus a recent window.

### Rules that hold across all implementations

**Time cutoff.** `retrieve(at=T)` must never surface records with `at > T`. The
evaluation replays histories step by step and asks what the memory should
believe at a point in time. A leak here silently invalidates every number.

A `kind="summary"` record carries the time consolidation *ran*, never the time
of the records it derives from. Backdating a summary walks it straight past the
cutoff and leaks the future into `retrieve(at=T)`.

**Outcomes survive.** A record with `kind="outcome"` is a fact read out of the
domain database, not a model utterance. It is preserved verbatim and is never
dropped, summarised, or paraphrased during consolidation. The database gets the
last word — that is load-bearing, not a detail.

**The strategy owns consolidation.** The agent never calls consolidation
directly. `write()` decides for itself whether it needs to consolidate;
`end_session()` marks the session boundary. If the agent triggers it, we are
comparing strategies under one policy instead of comparing the policies.

**Budgets are in tokens.** Not characters. Cost is a reported metric, and
characters-per-token differ between dense summaries and verbose raw turns —
especially in Swedish, where compounds tokenize badly.

**Ids are deterministic.** `f"{session_id}:{turn_index}"`, derived from
position, never random. Replaying one history twice, or across two strategies,
must produce the same ids — otherwise retrieval precision and recall are not
comparable between the things being compared.

### Boundaries

Memory persistence must write to its own store. **Never** through
`db/repositories.py`, never to a domain table. Memory is read-only into the
prompt and has no write path into domain data.

Consolidation's LLM call runs outside the turn and must never be able to
produce a tool call — the same discipline `READ_ANSWER_SYSTEM_PROMPT` already
has. `ConsolidatingMemory` is not built yet; it comes in step 5.

Tests are offline (`tests/conftest.py` neutralises `.env`). Any embedding-based
retrieval needs a deterministic fake embedder behind the same Protocol.

Cost must be measured **on the LLM client**, not inside the memory module. A
strategy that retrieves more context makes the answer call more expensive, and
a counter living inside the memory module cannot see that. The client that does
it is a `RecordingLLMClient` wrapping `AgentLLMClient` and logging each call
with a label ("consolidate", "answer", …): `life_agent/agent/recording.py`.

### Out of scope

Do not change `prompts.py` to suit the benchmark. This restriction is about
benchmark-driven changes only — prompt fixes for agent behaviour still belong
there, as described above.

The agent is a Swedish household planner that is deliberately forbidden from
answering from memory — it looks things up. LongMemEval measures an English
assistant answering from memory. These are different jobs.

The evaluation must therefore run **headless**: `evals/longmemeval.py` must
drive the memory module through a thin harness, not through
`ConversationAgent.send()`, and the agent must never appear in the measured
path. It reads its questions from `evals/longmemeval_questions.json` and its
replay rules from `evals/verify_adr_numbers.py`; ADRs 0004–0009 and 0011 are its
specification.
