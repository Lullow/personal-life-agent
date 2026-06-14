# Personal Life Agent

A **local-first terminal assistant** for managing the small, recurring parts of
daily life — tasks, calendar events, activities, and reminders — with optional
natural language input in Swedish or English.

Everything runs on your machine by default. There are no accounts, and your data
lives in a local SQLite file. Natural language understanding uses a deterministic
offline extractor out of the box; an **optional** OpenAI-compatible LLM can be
enabled via configuration if you want it (see [LLM extraction](#optional-llm-extraction)).

## What problem it solves

Keeping track of "what do I need to do today, what's coming this week, what did I
plan to train, and when should I be reminded" usually means juggling several
apps. This project is a single, fast, keyboard-driven tool that:

- captures tasks, events, activities, and reminders from the command line,
- understands short natural language notes like
  *"Jag ska träna rygg och biceps kl 12 imorgon, träningen ska vara 1h och påminn mig kl 09."*,
- shows you a daily and weekly agenda, and
- always asks before saving anything that came from natural language.

## MVP scope

This MVP is intentionally focused and runs entirely offline:

- Structured CLI commands for tasks, events, activities, and reminders.
- A planner that builds today / week / deadline views from stored data.
- A deterministic natural language **extraction** preview (read-only).
- A natural language **add** command that proposes items and saves them only
  after explicit confirmation.
- A natural language **completion** flow to mark a planned activity as done.

## Features

| Area | Commands |
|------|----------|
| App info | `version`, `health`, `init` |
| Tasks | `add-task`, `tasks`, `done` |
| Events | `add-event`, `events` |
| Activities | `activity`, `activities` |
| Reminders | `add-reminder`, `reminders`, `dismiss-reminder` |
| Planner | `today`, `week`, `deadlines` |
| Natural language | `extract` (preview), `add` (confirm + save), `complete` (confirm + update) |
| Interactive | `chat` — conversational loop with routing to all of the above |

## What is intentionally not included

This MVP deliberately leaves out (see [docs/roadmap.md](docs/roadmap.md)):

- A bundled LLM dependency — LLM extraction is **optional and opt-in** via
  config; the default is a fully offline deterministic extractor.
- Google Calendar or any external integration.
- Cloud storage or a hosted database.
- Push, email, or background notifications / schedulers.
- A web or mobile app, voice input, and partner/family sharing.

## Requirements

- Python 3.11+
- WSL Ubuntu, Windows 11 (via WSL), or Linux

## Installation (WSL / Linux)

From the project root:

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package (editable)
pip install -e .
```

## Usage

```bash
# First-time setup: create the local SQLite database
python -m life_agent init

# Inspect available commands
python -m life_agent --help

# Tasks
python -m life_agent add-task "Plugga machine learning" --due 2026-06-15 --priority high --category study
python -m life_agent tasks
python -m life_agent done 1

# Events
python -m life_agent add-event "Möte på Odenplan" --start "2026-06-15 12:00" --location "Odenplan"
python -m life_agent events

# Activities (manual logs default to "completed")
python -m life_agent activity "Gym rygg och biceps" --type gym --minutes 50
python -m life_agent activities

# Reminders
python -m life_agent add-reminder "Träning" --at "2026-06-15 09:00"
python -m life_agent reminders
python -m life_agent dismiss-reminder 1

# Planner
python -m life_agent today
python -m life_agent week
python -m life_agent deadlines

# Natural language
python -m life_agent extract "Möte på Odenplan kl 14 imorgon"          # read-only preview
python -m life_agent add "Jag ska träna rygg och biceps kl 12 imorgon, träningen ska vara 1h och påminn mig kl 09."
python -m life_agent complete "Jag har tränat klart"

# Interactive chat mode
python -m life_agent chat
```

In chat mode you can type naturally — "vad har jag idag", plan items, or
complete activities — and the assistant routes your message to the right
service.  All the same safety rules apply: write operations always ask for
confirmation first.

For a full, reproducible walkthrough see [docs/demo.md](docs/demo.md).

## Safety principle

> **Natural language input never writes to the database without explicit confirmation.**

- `extract` is always read-only — it shows a structured preview and saves nothing.
- `add` and `complete` show a proposal and only persist changes after you answer
  `y` / `yes`. Pressing Enter or answering `n` / `no` cancels.
- `chat` mode applies the same rules: planning text asks `Save this? [y/N]`,
  and completion text asks `Mark this activity as completed? [y/N]`.
- This rule is enforced in code (`life_agent/agent/safety.py`), not just by
  convention.

## Privacy (local-first)

- All data is stored locally in SQLite at `data/life_agent.db` by default.
- No external APIs are called unless you explicitly enable LLM mode
  (`LIFE_AGENT_EXTRACTION_MODE=llm`). The default is fully offline.
- See [docs/privacy.md](docs/privacy.md) for details and a warning about not
  committing your database file.

## Testing

```bash
pytest -v
```

Tests use temporary databases and never touch your real `data/life_agent.db`.
See [docs/testing.md](docs/testing.md).

## Configuration

Settings are read from environment variables (optionally via a `.env` file —
copy `.env.example` to `.env`):

| Variable    | Default               | Description                          |
|-------------|-----------------------|--------------------------------------|
| `APP_ENV`   | `development`         | Application environment              |
| `LOG_LEVEL` | `INFO`                | Logging level                        |
| `DB_PATH`   | `data/life_agent.db`  | Path to the local SQLite database    |
| `LIFE_AGENT_EXTRACTION_MODE` | `deterministic` | `deterministic` (offline) or `llm`   |
| `LIFE_AGENT_LLM_PROVIDER`    | `openai_compatible` | Provider type for LLM mode    |
| `LIFE_AGENT_LLM_BASE_URL`    | _(unset)_           | OpenAI-compatible base URL    |
| `LIFE_AGENT_LLM_API_KEY`     | _(unset)_           | API key for the provider      |
| `LIFE_AGENT_LLM_MODEL`       | _(unset)_           | Model name to request         |

### Optional LLM extraction

By default the app uses a **deterministic, offline** extractor and never makes a
network call — no API key is required and everything works out of the box.

You can optionally route extraction through any **OpenAI-compatible** API
(OpenAI, OpenRouter, a local server, …). Enable it by setting:

```bash
export LIFE_AGENT_EXTRACTION_MODE=llm
export LIFE_AGENT_LLM_BASE_URL=https://api.openai.com/v1
export LIFE_AGENT_LLM_API_KEY=sk-your-key-here
export LIFE_AGENT_LLM_MODEL=gpt-4o-mini
```

How it behaves safely:

- The LLM is asked for **JSON only**, which is validated against the same
  `ExtractionResult` schema as the offline extractor.
- If the provider is unconfigured, unreachable, or returns invalid output, the
  app **falls back to the deterministic extractor** and prints a short note —
  it never crashes.
- `extract` stays **read-only**, and `add` still asks `Save this? [y/N]` before
  writing anything. LLM output is never saved without validation **and**
  confirmation.
- No LLM SDK is bundled; the client uses only the Python standard library, so
  installing this project never pulls in a provider dependency.

## Project structure

```
personal-life-agent/
├── life_agent/
│   ├── cli/             # Typer CLI commands and output formatters
│   ├── services/        # Task, event, activity, reminder, planner,
│   │                    #   extraction, confirmation, completion, chat services
│   ├── db/              # SQLite connection, schema, repositories
│   ├── models/          # Pydantic domain models + shared enums
│   ├── schemas/         # Extraction / planner / confirmation schemas
│   ├── agent/           # Prompts and the safety rule
│   ├── llm/             # Optional OpenAI-compatible client + JSON parsing
│   ├── config.py        # Environment-based settings
│   └── main.py          # Typer app entry point
├── tests/               # Pytest suite (uses temporary databases)
├── docs/                # Architecture, privacy, demo, roadmap, testing
├── pyproject.toml
└── README.md
```

## Project status and roadmap

The MVP is feature-complete for local task/event/activity/reminder management,
planning, and confirmed natural language input. Planned future work (real LLM
integration, calendar export, recurring reminders, and more) is tracked in
[docs/roadmap.md](docs/roadmap.md). Architecture is documented in
[docs/architecture.md](docs/architecture.md).

## License

Private / personal project.
