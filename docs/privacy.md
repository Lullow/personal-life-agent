# Privacy

Personal Life Agent is **local-first** by design. It is built to run entirely on
your own machine, with no accounts and no network dependencies by default.

The only way any data leaves your machine is if **you** explicitly enable the
optional LLM extraction mode (see [Optional LLM mode](#optional-llm-mode)).

## Where your data lives

- All data is stored in a single local **SQLite** database.
- The default location is `data/life_agent.db` (configurable via the `DB_PATH`
  environment variable).
- The database is created on demand by `python -m life_agent init` and by
  the first command that needs it.

## What the MVP does *not* do

By default the app makes **no** network calls at runtime:

- **No external APIs by default.** Natural language extraction uses a
  deterministic, rule-based parser that runs locally. No request leaves your
  machine unless you opt in to LLM mode.
- **No LLM provider unless you enable one.** The OpenAI-compatible client is
  disabled until you set `LIFE_AGENT_EXTRACTION_MODE=llm` and the
  `LIFE_AGENT_LLM_*` variables.
- **No Google Calendar** (or any calendar) integration.
- **No partner / family sharing** and no multi-user accounts.
- **No cloud database** and no remote sync.
- **No push, email, or background notifications.** Reminders are stored records
  you view with `python -m life_agent reminders`; nothing is sent anywhere.

## What personal data may be stored locally

Because this is a personal life assistant, the local database can contain
personal information that **you** enter, such as:

- Task titles, descriptions, due dates, priorities, and categories.
- Calendar event titles, times, and locations (e.g. *"Möte på Odenplan"*).
- Activity logs (e.g. gym/run/walk/study sessions and durations).
- Reminders and their times.
- The raw natural language text you pass to `add`, `extract`, and `complete`,
  to the extent it is saved as item titles or notes.

This data stays in `data/life_agent.db` on your machine unless you copy or share
that file yourself.

## Optional LLM mode

LLM extraction is **off by default**. If you enable it
(`LIFE_AGENT_EXTRACTION_MODE=llm` plus the `LIFE_AGENT_LLM_*` variables), then:

- The raw text you pass to `extract`, `add`, and `complete` is sent to the
  OpenAI-compatible endpoint you configured, in order to extract structured
  items. That request leaves your machine and is subject to **that provider's**
  privacy and data-retention policies.
- Only the note text and a system prompt are sent — never your SQLite database.
- The request is skipped (and the app falls back to the offline extractor) if
  the provider is not fully configured or is unreachable.
- Keep your API key in a local `.env` file or your shell environment. **Never
  commit real keys** — `.env.example` ships with placeholders only.

If you want a guarantee that nothing ever leaves your machine, simply leave
`LIFE_AGENT_EXTRACTION_MODE` at its default (`deterministic`).

## Do not commit your database

> ⚠️ **Never commit `data/life_agent.db` to Git.** It may contain personal
> information.

- The repository's `.gitignore` already excludes the `data/` directory.
- If you have previously committed a database file, remove it from version
  control:

  ```bash
  git rm --cached data/life_agent.db
  ```

- To start from a clean database locally, simply delete the file:

  ```bash
  rm -f data/life_agent.db
  python -m life_agent init
  ```

## Tests and your data

The test suite never reads or writes your real database. Every test uses a
temporary database path, so running `pytest -v` cannot modify
`data/life_agent.db`. See [testing.md](testing.md).
