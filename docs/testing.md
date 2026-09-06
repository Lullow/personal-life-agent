# Testing

The project uses [pytest](https://docs.pytest.org/). Tests are fast,
deterministic, and never touch your real database — even though the product
itself is driven by a language model and is neither.

There are two suites, and keeping them apart is the point:

- **`pytest`** — offline. The model is faked, so what is tested is the machinery
  around it: that the registry rejects invented tools, that a write cannot pass
  itself off as a read, that nothing is saved without confirmation.
- **`evals/agent_eval.py`** — calls the real model, and is read with human eyes.
  Run it whenever you change a prompt.

There are no recorded model fixtures. A recording made against today's model
says nothing about the one you switch to tomorrow.

## How to run the tests

From the project root, with the virtual environment activated:

```bash
# Run everything
pytest

# Verbose output (one line per test)
pytest -v

# Run a single file
pytest tests/test_completion_service.py -v

# The eval — costs a few cents, needs LIFE_AGENT_LLM_* configured
.venv/bin/python evals/agent_eval.py
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

Two further isolations matter:

- `tests/conftest.py` neutralises the local `.env`, so a machine with real
  credentials configured behaves exactly like one without. Without this, whether
  a test passed would depend on whose laptop it ran on.
- Dates are made deterministic with an injectable `reference_date` on the
  completion service and the conversation agent, so tests assert exact
  timestamps without depending on the real current date.

`evals/agent_eval.py` seeds its own temporary database too, and pins the same
reference date, so the same sentence stays comparable between runs.

## What is tested

The suite covers each layer of the [architecture](architecture.md):

- **Models** — validation rules (non-empty titles, non-negative durations,
  event end-time ordering).
- **Database / repositories** — schema initialisation and CRUD for tasks,
  events, activities, and reminders, including status updates and round-trip
  serialization of dates/datetimes.
- **Services** — planner views and timelines, day and range retrieval, the
  confirmation flow (proposal counts, save/skip behaviour), the completion flow,
  and `edit_service` resolution (inflected descriptions, ambiguity, dropped
  guesses).
- **The agent** — `tests/test_conversation_agent.py` drives the loop with a fake
  client returning canned payloads: tool validation, the confirmation flags the
  registry supplies, conversation history, the second call on reads, and every
  degradation path.
- **CLI** — commands via Typer's `CliRunner`, including confirmation prompts
  (yes / `y` / no / Enter) and status display in `activities`.

## Safety-related tests

Several tests specifically protect the core safety rule that **natural language
input must not write without explicit confirmation**:

- A proposal writes nothing: after the agent prepares four items, the database
  is still empty.
- `save_extracted_items` is flagged `write` and `requires_confirmation` from the
  registry, whatever the model's own JSON claimed.
- A hallucinated tool name is not executed.
- `complete`, `reschedule_item`, and `delete_item` change nothing until
  confirmed.
- The underlying services raise `PermissionError` if a save, update, or delete
  is attempted without confirmation.

> The exact number of tests changes as the project grows; run `pytest -v` to see
> the current count and the full list.
