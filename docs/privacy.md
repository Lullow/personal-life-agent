# Privacy

Your data is stored locally. **The model is not local.**

Personal Life Agent keeps everything it saves in a SQLite file on your machine,
with no accounts and no sync. But the agent is driven by a language model, and
since the pivot described in [llm-first-pivot.md](llm-first-pivot.md) that model
is not optional — it is what understands you. Every message you type is sent to
the provider you configured.

This document used to promise that nothing left your machine by default. That
promise is gone, and it is better to say so plainly than to leave the old
sentence standing.

## What leaves your machine

Every turn of `python -m life_agent chat` sends, to your configured endpoint:

- **the message you typed**, verbatim;
- **the last ten turns** of the conversation, so follow-up questions work;
- **the system prompt**, which contains today's date and the tool list;
- **on a question about your schedule, the rows that were retrieved.** When you
  ask "vad har jag imorgon?" the agent fetches that day and then sends it back
  to the model so it can answer in words rather than dumping a table. Your
  agenda for the days you ask about therefore leaves the machine too.

That last point is the one worth sitting with. The database file itself is never
uploaded, but its contents reach the provider in fragments, one question at a
time.

What is sent is subject to **your provider's** privacy and retention policy, not
this project's. If you are using OpenRouter or OpenAI, read theirs.

## What still never leaves

- The SQLite file, as a file. Nothing copies or syncs it.
- Anything you have not asked about. The agent sends the days you enquire about,
  not the whole database.
- Your API key, beyond the provider it authenticates you to.

There is no telemetry, no analytics, and no other network call of any kind. The
LLM client uses only the Python standard library, so installing this project
pulls in no provider SDK.

## The way back to fully local

`LLMClient` speaks only the OpenAI-compatible protocol, so pointing it at a
model running on your own machine is a change of one line:

```bash
LIFE_AGENT_LLM_BASE_URL=http://localhost:11434/v1   # Ollama, llama.cpp, vLLM …
```

At that point nothing leaves the machine again, and the privacy properties this
project started with are restored. That is the intended destination; a hosted
model is the way to get moving. Be aware that a weak local model classifies
badly — see the model comparison in [llm-first-pivot.md](llm-first-pivot.md).

## What is stored locally

Because this is a personal life assistant, the local database can contain
personal information that **you** enter:

- Task titles, descriptions, due dates, priorities, and categories.
- Calendar event titles, times, and locations (e.g. *"Möte på Odenplan"*).
- Activity logs — gym, run, walk, study sessions and durations.
- Reminders and their times.
- The wording of what you typed, to the extent the agent saved it as a title,
  description, or note.

This stays in `data/life_agent.db` unless you copy or share that file yourself.

## Do not commit your database

> ⚠️ **Never commit `data/life_agent.db` to Git.** It may contain personal
> information.

- The repository's `.gitignore` already excludes the `data/` directory, and
  `.env` with it.
- If you have previously committed a database file, remove it from version
  control:

  ```bash
  git rm --cached data/life_agent.db
  ```

- To start from a clean database locally, delete the file:

  ```bash
  rm -f data/life_agent.db
  python -m life_agent init
  ```

## Your API key

Keep it in a local `.env` file or your shell environment. **Never commit real
keys** — `.env.example` ships with placeholders only, and `.env` is ignored.

If a key is ever exposed — pasted into a chat, committed, shared in a screenshot
— rotate it at the provider rather than hoping. It takes a minute.

## Tests and your data

The test suite never reads or writes your real database: every test uses a
temporary path. It also never calls the network — the model is faked. Neither
does it read your `.env`, so a machine with credentials configured tests
identically to one without. See [testing.md](testing.md).

`evals/agent_eval.py` is the exception: it calls the real model on purpose. It
still uses a temporary database and never touches yours.
