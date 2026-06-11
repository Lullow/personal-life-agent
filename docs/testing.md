# Testing

The project uses [pytest](https://docs.pytest.org/). Tests are fast,
deterministic, and never touch your real database.

## How to run the tests

From the project root, with the virtual environment activated:

```bash
# Run everything
pytest

# Verbose output (one line per test)
pytest -v

# Run a single file
pytest tests/test_completion_service.py -v
```

Configuration lives in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`pythonpath = ["."]` lets the tests import `life_agent` without installing the
package first.

## Why tests use temporary databases

Every test that needs persistence points the app at a **temporary** SQLite file
instead of `data/life_agent.db`. This is done in two complementary ways:

- **Service / repository tests** pass an explicit `db_path` (created with
  `tempfile.TemporaryDirectory`) into repository and service functions.
- **CLI tests** set the `DB_PATH` environment variable to a path under pytest's
  `tmp_path` fixture and then call `python -m life_agent init`, so the whole
  command runs against an isolated database.

Benefits:

- Running `pytest` can never read or modify your real `data/life_agent.db`.
- Each test starts from a clean, known state, so results are deterministic.
- Tests do not depend on one another or on machine-specific data.

Because dates like *"imorgon"* must be deterministic, the extraction and
completion services accept an injectable `reference_date`, so tests assert exact
timestamps without depending on the real current date.

## What is tested

The suite covers each layer of the [architecture](architecture.md):

- **Models** — validation rules (non-empty titles, non-negative durations,
  event end-time ordering).
- **Database / repositories** — schema initialisation and CRUD for tasks,
  events, activities, and reminders, including status updates and round-trip
  serialization of dates/datetimes.
- **Services** — planner views (`today`, `week`, `deadlines`) sorting and
  filtering; extraction parsing; the confirmation flow (proposal counts,
  save/skip behavior); and the completion flow (phrase detection, candidate
  matching, confirmed status change).
- **CLI** — every command via Typer's `CliRunner`, including the confirmation
  prompts (yes / `y` / no / Enter), the read-only guarantee of `extract`, and
  status display in `activities`.

## Safety-related tests

Several tests specifically protect the core safety rule that **natural language
input must not write without explicit confirmation**:

- `extract` saves nothing.
- `add` saves only on `y`/`yes`; `n`/`no`/Enter save nothing.
- `complete` updates only on confirmation.
- The underlying services raise `PermissionError` if a save/update is attempted
  without confirmation.

> The exact number of tests changes as the project grows; run `pytest -v` to see
> the current count and the full list.
