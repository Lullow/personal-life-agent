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

Every repository function accepts an optional `db_path`, which is how test
isolation and the `DB_PATH` env var both work. The list functions also accept
inclusive day bounds (`start`/`end`, or `due_from`/`due_to` for tasks).

### The one safety rule

> Natural language input must not write to the database without explicit
> user confirmation.

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
  history (10 turns) + system prompt → one call → {"tool", "arguments", "reply"}
  → ToolRegistry lookup → AgentDecision → AgentPolicy → dispatch → AgentTurn
```

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
