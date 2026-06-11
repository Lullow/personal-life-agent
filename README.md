# Personal Life Agent

A **local-first terminal assistant** for managing the small, recurring parts of
daily life — tasks, calendar events, activities, and reminders — with optional
natural language input in Swedish or English.

Everything runs on your machine. There are no cloud services, no external APIs,
and no accounts. Your data lives in a local SQLite file.

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

## What is intentionally not included

This MVP deliberately leaves out (see [docs/roadmap.md](docs/roadmap.md)):

- A real LLM provider — extraction currently uses a deterministic rule-based
  fallback, not a network API call.
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
```

For a full, reproducible walkthrough see [docs/demo.md](docs/demo.md).

## Safety principle

> **Natural language input never writes to the database without explicit confirmation.**

- `extract` is always read-only — it shows a structured preview and saves nothing.
- `add` and `complete` show a proposal and only persist changes after you answer
  `y` / `yes`. Pressing Enter or answering `n` / `no` cancels.
- This rule is enforced in code (`life_agent/agent/safety.py`), not just by
  convention.

## Privacy (local-first)

- All data is stored locally in SQLite at `data/life_agent.db` by default.
- No external APIs are called in this MVP.
- See [docs/privacy.md](docs/privacy.md) for details and a warning about not
  committing your database file.

## Testing

```bash
pytest -v
```

Tests use temporary databases and never touch your real `data/life_agent.db`.
See [docs/testing.md](docs/testing.md).

## Configuration

Settings are read from environment variables (optionally via a `.env` file):

| Variable    | Default               | Description                          |
|-------------|-----------------------|--------------------------------------|
| `APP_ENV`   | `development`         | Application environment              |
| `LOG_LEVEL` | `INFO`                | Logging level                        |
| `DB_PATH`   | `data/life_agent.db`  | Path to the local SQLite database    |

## Project structure

```
personal-life-agent/
├── life_agent/
│   ├── cli/             # Typer CLI commands and output formatters
│   ├── services/        # Task, event, activity, reminder, planner,
│   │                    #   extraction, confirmation, completion services
│   ├── db/              # SQLite connection, schema, repositories
│   ├── models/          # Pydantic domain models + shared enums
│   ├── schemas/         # Extraction / planner / confirmation schemas
│   ├── agent/           # Prompts and the safety rule
│   ├── llm/             # LLM client placeholder + structured-output parsing
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
