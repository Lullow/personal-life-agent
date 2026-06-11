# Privacy

Personal Life Agent is **local-first** by design. It is built to run entirely on
your own machine, with no accounts and no network dependencies in this MVP.

## Where your data lives

- All data is stored in a single local **SQLite** database.
- The default location is `data/life_agent.db` (configurable via the `DB_PATH`
  environment variable).
- The database is created on demand by `python -m life_agent init` and by
  the first command that needs it.

## What the MVP does *not* do

The current MVP intentionally has **no** external dependencies at runtime:

- **No external APIs.** Natural language extraction uses a deterministic,
  rule-based parser that runs locally. No request leaves your machine.
- **No real LLM provider.** The LLM client is a disabled placeholder; it never
  makes a network call.
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
