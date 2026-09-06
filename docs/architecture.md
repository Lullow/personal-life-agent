# Architecture

Personal Life Agent is built as a small set of clearly separated layers. Each
layer has one responsibility and depends only on the layers beneath it. This
keeps the code easy to read, test, and extend one feature at a time.

```
CLI (Typer)            life_agent/cli/
   │  parses arguments, prompts for confirmation, prints formatted output
   ▼
Services               life_agent/services/
   │  business logic; the only place that orchestrates models + repositories
   ▼
Repositories / DB      life_agent/db/
   │  SQLite access; converts rows <-> models
   ▼
SQLite database        data/life_agent.db
```

Supporting modules sit alongside these layers:

- **Models** (`life_agent/models/`) — Pydantic domain objects and shared enums.
- **Schemas** (`life_agent/schemas/`) — structured input/output shapes for
  extraction, planning, and confirmation.
- **Agent** (`life_agent/agent/`) — the conversation loop, AgentDecision schema,
  ToolRegistry, AgentPolicy, prompt text, and the safety rule. See
  [agent-architecture.md](agent-architecture.md) for a full walkthrough.
- **LLM** (`life_agent/llm/`) — a dependency-free OpenAI-compatible client
  (stdlib only) and JSON parsing.

## CLI layer (`life_agent/cli/`)

- `commands.py` registers every Typer command (`init`, `add-task`, `today`,
  `complete`, `chat`, …). Commands are thin: they parse arguments, call a
  service, and print results. `chat` is the agent loop and is where the
  confirmation prompts live.
- `formatters.py` turns models, agendas, extraction results, and proposals into
  readable terminal text. Keeping formatting here means services stay free of
  presentation concerns.
- Confirmation prompts (`Save this? [y/N]`, `Mark this activity as completed?
  [y/N]`) live in the CLI and delegate the yes/no decision to the safety helper.

## Services layer (`life_agent/services/`)

The services are the orchestration layer between the CLI and the database:

- `task_service.py`, `event_service.py`, `activity_service.py`,
  `reminder_service.py` — thin wrappers that build a model and call the matching
  repository function.
- `planner_service.py` — **read-only**. Builds the `today`, `week`, and
  `deadlines` views by loading tasks/events and sorting/grouping them. It never
  writes.
- `confirmation_service.py` — builds a proposal from an `ExtractionResult` and,
  only when confirmed, persists each item via the services above. The
  `ExtractionResult` is filled in by the model rather than by a parser.
- `completion_service.py` — finds the planned activity a completion phrase
  refers to and, when confirmed, marks it completed.
- `edit_service.py` — resolves a description of a saved item to actual rows, and
  reschedules or deletes one after confirmation.
- `read_service.py` — renders the read-only views the agent can ask for.

## Repository / database layer (`life_agent/db/`)

- `database.py` — opens a SQLite connection, creates the parent directory,
  enables WAL mode, and exposes `init_db()`.
- `schema.py` — `CREATE TABLE IF NOT EXISTS` definitions for `tasks`, `events`,
  `activities`, and `reminders`, plus `init_db()`.
- `repositories.py` — CRUD functions. This is the only layer that talks SQL. It
  converts between SQLite rows and Pydantic models, storing datetimes/dates as
  ISO-8601 strings and parsing them back on read.

Every repository function accepts an optional `db_path` so tests can point at a
temporary database.

## Models and schemas

- **Models** (`models/`): `Task`, `CalendarEvent`, `ActivityLog`, `Reminder`,
  plus `User`, `FamilyMember`, `MealPlan`, `Preference` for future use. Shared
  enums in `models/common.py` (`Priority`, `TaskStatus`, `TaskCategory`,
  `EventCategory`, `ActivityType`, `ActivityStatus`, `ReminderStatus`, …) keep
  values consistent across the codebase.
- **Schemas** (`schemas/`):
  - `extraction.py` — `ExtractedTask/Event/Activity/Reminder` and
    `ExtractionResult` (with `questions` and `confidence`).
  - `planner.py` — `TodayAgenda`, `WeekAgenda`, `DayPlan`, and generic agenda
    items.
  - `confirmation.py` — `ConfirmationProposal`, `ConfirmationSaveResult`,
    `SavedItemSummary`.

The distinction matters: **models** are persisted domain records; **schemas**
are transient shapes used at the boundaries (LLM output, planner output,
confirmation previews).

## Turning language into items

There is no parser. `ExtractionResult` — the same schema the confirmation flow
has always consumed — is filled in by the model as the `arguments` of the
`save_extracted_items` tool, and validated with Pydantic before anything is
proposed. Arguments that do not validate become a request to rephrase, not a
save.

Everything the deterministic extractor used to do with regexes for clock times,
weekdays, durations and locations is now the model's job, and the rules it works
to live in `life_agent/agent/prompts.py`. See
[llm-first-pivot.md](llm-first-pivot.md) for why that trade was made and what it
cost.

The `LLMClient` is deliberately isolated and dependency-free (Python stdlib
`urllib`), so swapping providers — including to a local model — never affects
the CLI, services, or database.

## Confirmation flow

Language never saves silently:

1. The model produces an `ExtractionResult` as tool arguments.
2. `build_confirmation_proposal` counts how many items are complete enough to
   save versus incomplete — without touching the database.
3. The CLI prints the proposal and asks `Save this? [y/N]`.
4. Only on an explicit `y`/`yes` does `save_confirmed_extraction` run. It
   converts each extracted item into a model and persists it, skipping
   incomplete items with a clear reason. Extracted activities are saved with
   status `planned`.

## Completion flow

The `complete` command marks a previously planned activity as done:

1. `is_completion_phrase` checks for phrases like *"Jag har tränat klart"* or
   *"träningen är klar"*.
2. `find_completion_candidate` looks for planned activities today first, then in
   a small yesterday–tomorrow window, optionally preferring the activity type
   hinted by the text.
3. The CLI shows the matched activity and asks `Mark this activity as completed?
   [y/N]`.
4. Only on confirmation does `complete_activity` update the status to
   `completed`.

## The safety rule

`life_agent/agent/safety.py` centralises one rule:

> Natural language input must not write to the database without explicit
> confirmation.

- `is_affirmative(answer)` treats only `y/yes/j/ja` as confirmation; everything
  else (including a bare Enter) is a refusal.
- `assert_confirmed(confirmed)` raises `PermissionError` if a save/update path is
  reached without confirmation. Both `save_confirmed_extraction` and
  `complete_activity` call it first, so the guarantee cannot be bypassed by
  accident.

## Chat mode

`python -m life_agent chat` is the agent. One model call per message decides
which tool to use, the registry decides what that tool is allowed to do, and
mutating tools stop at a confirmation prompt in the CLI. Questions about saved
data take a second call so the answer is grounded in the rows that came back.

The full walkthrough, the tool table, and the degradation matrix are in
[agent-architecture.md](agent-architecture.md).

## Why small layers

- **Testability** — each layer can be tested in isolation with a temporary
  database and a faked model, which is why the suite is fast and deterministic
  even though the product is not.
- **Incremental delivery** — every feature was added as a focused layer without
  rewriting earlier ones. It also survived the reversal: when the deterministic
  language layer was removed, the domain core underneath it did not move.
- **Safety** — keeping persistence behind services and a single safety helper
  makes the "no write without confirmation" guarantee easy to enforce and audit.
- **Pluggable LLM** — the client speaks only the OpenAI-compatible protocol
  behind one interface, so moving to a different provider, or to a model running
  on your own machine, is a base-URL change.
- **Extensible agent** — a new capability is a `ToolDefinition` in the registry,
  a dispatch branch, and a paragraph of prompt. Its action type and confirmation
  requirement are declared in one place and enforced everywhere.
