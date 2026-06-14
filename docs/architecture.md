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
- **Agent** (`life_agent/agent/`) — LLM prompt text and the safety rule.
- **LLM** (`life_agent/llm/`) — an optional OpenAI-compatible client (stdlib
  only) and JSON-to-schema parsing.

## CLI layer (`life_agent/cli/`)

- `commands.py` registers every Typer command (`init`, `add-task`, `today`,
  `extract`, `add`, `complete`, `chat`, …). Commands are thin: they parse
  arguments, call a service, and print results.
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
- `extraction_service.py` — converts free text into an `ExtractionResult`.
- `confirmation_service.py` — builds a proposal from an `ExtractionResult` and,
  only when confirmed, persists each item via the services above.
- `completion_service.py` — detects a completion phrase, finds the relevant
  planned activity, and (when confirmed) marks it completed.
- `chat_service.py` — deterministic intent classifier and response helpers for
  interactive chat mode (see [Chat mode](#chat-mode)).

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

## Extraction service

`extract_from_text(text, reference_date=None, llm_client=None, mode=None)`
chooses an extraction strategy and always returns an `ExtractionResult`:

1. **Mode selection.** An explicit `llm_client` (used in tests) forces LLM mode;
   otherwise the `mode` argument or `Settings.extraction_mode` decides. The
   default is `deterministic`, so the app works offline with no API key.
2. **LLM mode.** The configured `LLMClient.from_settings()` sends the system
   prompt plus a date-aware user prompt to an OpenAI-compatible
   `/chat/completions` endpoint and requests JSON only. The response is parsed
   and validated with `safe_parse_extraction_result`. If the client is disabled
   (missing base URL/API key/model), unreachable, or returns invalid JSON, the
   service **degrades to the deterministic extractor** and adds a short note to
   `questions` — it never raises.
3. **Deterministic mode.** A rule-based extractor recognises Swedish/English
   patterns: clock times (`kl 12`, `13:30`, `klockan 18`), relative dates and
   weekdays (`idag`, `imorgon`, `på fredag`), durations (`1h`, `45 min`),
   reminder triggers (`påminn`), task intent (`behöver`, `måste`, `kom ihåg`),
   event keywords (`möte`, `tandläkare`) with `på <Plats>` locations, and
   activity verbs (`träna`/`gymma` → gym).
4. Unclear or missing details become entries in `questions` rather than guesses,
   and `confidence` reflects how much was extracted.

The `LLMClient` is deliberately isolated and dependency-free (Python stdlib
`urllib`), so swapping providers — or installing the project without any LLM —
never affects the CLI, services, or database. Extraction is always
**read-only**; saving still goes through the confirmation flow below.

## Confirmation flow

The natural language `add` command never saves silently:

1. `extract_from_text` produces an `ExtractionResult`.
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

`python -m life_agent chat` starts a simple interactive loop. The chat service
classifies each message into an intent:

| Intent | Example phrases | Behaviour |
|--------|----------------|-----------|
| `/help` | `/help`, `help` | Print available commands |
| `/quit` | `/quit`, `/exit` | Exit the loop |
| TODAY | "vad har jag idag", "dagens plan" | Show today's agenda (read-only) |
| WEEK | "vad händer i veckan", "veckoplan" | Show week view (read-only) |
| DEADLINES | "visa deadlines" | Show upcoming deadlines (read-only) |
| REMINDERS | "visa påminnelser", "mina reminders" | Show pending reminders (read-only) |
| ADD_ITEMS | "jag ska träna…", "påminn mig…" | Extract, show proposal, ask `Save this? [y/N]` |
| COMPLETE | "jag har tränat klart" | Find planned activity, ask `Mark as completed? [y/N]` |
| UNKNOWN | anything else | Show helpful fallback with examples |

Classification is deterministic (regex-based, no LLM). Read-only intents
produce output immediately. Write intents go through the same confirmation flow
as the `add` and `complete` commands — the safety rule is always enforced.

The chat service has no long-term memory: each message is classified and handled
independently.

## Why small layers

- **Testability** — each layer can be tested in isolation with a temporary
  database, which is why the suite is fast and deterministic.
- **Incremental delivery** — every feature (models → DB → CLI → planner →
  extraction → confirmation → completion) was added as a focused layer without
  rewriting earlier ones.
- **Safety** — keeping persistence behind services and a single safety helper
  makes the "no write without confirmation" guarantee easy to enforce and audit.
- **Pluggable LLM** — because extraction returns a schema and the LLM client is
  isolated behind one interface, the optional OpenAI-compatible provider plugs
  in (and falls back) without changing the CLI, services, or database.
