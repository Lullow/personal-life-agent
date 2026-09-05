# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local-first terminal assistant (Typer CLI) for tasks, calendar events,
activities, and reminders, with optional natural language input in Swedish or
English. Data is stored in a local SQLite file (`data/life_agent.db`). No
accounts, no cloud storage. Natural language understanding defaults to a
deterministic offline extractor; an OpenAI-compatible LLM can optionally be
enabled via config for extraction, chat routing, saved-data responses, and
free-form conversation fallback — every LLM path degrades gracefully to a
deterministic fallback on any failure.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python -m life_agent init          # create the local SQLite database

# Run tests
pytest                             # or: .venv/bin/python -m pytest
pytest -v                          # verbose, one line per test
pytest tests/test_completion_service.py -v   # single file
pytest tests/test_completion_service.py::test_name -v   # single test

# Run the CLI
python -m life_agent --help
python -m life_agent chat          # interactive chat loop
```

There is no lint/format/type-check command configured in this repo (no
ruff/black/mypy config present) — don't invent one unless asked.

`pyproject.toml` sets `pythonpath = ["."]` for pytest, so tests import
`life_agent` without an editable install. Tests never touch the real
`data/life_agent.db`: service/repository tests pass an explicit `db_path`
into a temp dir, CLI tests set the `DB_PATH` env var to a `tmp_path`. Dates
like "imorgon" (tomorrow) are made deterministic via an injectable
`reference_date` parameter on extraction/completion services — use it instead
of relying on real "now" in tests.

## Architecture

Layered, each layer depends only on the one beneath it:

```
CLI (Typer)        life_agent/cli/        — parses args, prompts confirmation, prints output
Services            life_agent/services/   — business logic; only layer that orchestrates models + repositories
Repositories/DB     life_agent/db/         — SQLite access; converts rows <-> Pydantic models
SQLite              data/life_agent.db
```

Supporting modules: `models/` (persisted domain objects + shared enums),
`schemas/` (transient shapes for extraction/planner/confirmation
boundaries — not persisted), `agent/` (chat routing pipeline, see below),
`llm/` (optional dependency-free OpenAI-compatible client using only
`urllib`).

Every repository function accepts an optional `db_path`, which is how test
isolation and the `DB_PATH` env var both work.

### The one safety rule

> Natural language input must not write to the database without explicit
> user confirmation.

This is enforced in code, not convention, at three independent layers:
1. `AgentDecision.requires_confirmation` must be `True` for any mutating
   (`write`/`update`/`delete`) decision.
2. `AgentPolicy.validate_decision_safety()` (`life_agent/agent/policy.py`)
   rejects mutating decisions lacking that flag, and rejects any
   unregistered tool name.
3. `life_agent/agent/safety.py` — `assert_confirmed()` raises
   `PermissionError` if `save_confirmed_extraction` or `complete_activity`
   is ever reached without confirmation. `is_affirmative()` treats only
   `y/yes/j/ja` as yes; a bare Enter or anything else is a refusal.

When touching extraction, confirmation, completion, or the agent runtime,
preserve this chain — a new write-capable tool must be registered with
`requires_confirmation=True` and routed through the confirmation flow, never
called directly from the router.

### Chat / agent pipeline

`chat` mode routes every message through a structured pipeline instead of ad
hoc keyword checks:

```
CLI chat loop → ChatService.classify_intent() → AgentRouter.route()
  → AgentDecision → AgentPolicy.validate_decision_safety()
  → AgentRuntime.handle_message() → RuntimeResponse
```

- **AgentRouter** (`agent/router.py`) classifies text into an
  `AgentDecision`. Deterministic mode (default) is pure regex/pattern
  matching, offline. LLM mode (`LIFE_AGENT_AGENT_ROUTER_MODE=llm`) asks the
  configured LLM for a JSON decision, then validates it against
  `AgentPolicy`/`ToolRegistry` and **unconditionally falls back to
  deterministic routing** on any failure, invalid JSON, unknown tool, or
  unsafe (unconfirmed mutating) decision.
- **ToolRegistry** (`agent/tools.py`) is the single source of truth for
  every tool's `action_type` and `requires_confirmation`; both routing modes
  read from the same registry, so an unregistered tool can never reach the
  runtime.
- **AgentRuntime** (`agent/runtime.py`) dispatches by `tool_name` and never
  writes to the database itself. It returns one of three `RuntimeResponse`
  kinds: `"display"` (read-only, print immediately), `"needs_confirmation"`
  (CLI must ask `y/N` before the write/update proceeds), `"unknown"`
  (fallback help text).
- The LLM, when enabled, only ever acts as a **classifier** picking a tool
  name + arguments — it never calls tools directly, so a hallucinated tool
  name is caught by the registry lookup rather than executed.

Full walkthrough with the tool table: `docs/agent-architecture.md`. Layer
details: `docs/architecture.md`.

### Extraction

`extraction_service.extract_from_text()` always returns an
`ExtractionResult`, never raises. Mode is deterministic by default; LLM mode
degrades to the deterministic extractor (with a note in `questions`) on any
failure — missing config, unreachable endpoint, invalid JSON. Extraction
itself is always read-only regardless of mode; only the confirmation flow
(`confirmation_service.py`) persists, and only after explicit user
confirmation.

### Config

`life_agent/config.py` — `Settings` loaded from env vars (optionally via
`.env`, see `.env.example`). Key toggles, all default to the safe/offline
option:

| Var | Default | Values |
|---|---|---|
| `LIFE_AGENT_EXTRACTION_MODE` | `deterministic` | `deterministic` \| `llm` |
| `LIFE_AGENT_AGENT_ROUTER_MODE` | `deterministic` | `deterministic` \| `llm` |
| `LIFE_AGENT_SAVED_DATA_RESPONSE_MODE` | `template` | `template` \| `llm` |
| `LIFE_AGENT_CONVERSATION_MODE` | `off` | `off` \| `on` |
| `LIFE_AGENT_LLM_BASE_URL` / `_API_KEY` / `_MODEL` | unset | any OpenAI-compatible endpoint |

`LLMClient` (`life_agent/llm/client.py`) is enabled only when base URL, API
key, and model are all present; it's built via `LLMClient.from_settings()`
and used identically by extraction, routing, saved-data responses, and
conversation fallback. It's dependency-free (stdlib `urllib` only) so
installing the project never pulls in a provider SDK.
