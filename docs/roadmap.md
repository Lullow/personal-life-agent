# Roadmap

This document lists **future features** only.  The current system covers local
task/event/activity/reminder management, planner views (`today`, `week`,
`deadlines`), confirmed natural language input (`extract`, `add`, `complete`),
an interactive chat mode, and a structured agent runtime with optional LLM
routing and a read-only saved-data Q&A tool.

See [architecture.md](architecture.md) and
[agent-architecture.md](agent-architecture.md) for how the current system is
built and why external integrations can be added without rewriting existing
layers.

## Planned features

### Agent runtime and routing

- **Richer LLM routing** — improve the LLM routing prompt and decision parsing
  so the router handles more ambiguous phrases confidently.
- **Structured query result layer** — replace the ad-hoc string answers in
  `query_saved_data` with typed result objects that can be formatted
  consistently across chat, CLI, and a future web UI.
- **Response generation from grounded data** — use the LLM to compose
  human-readable summaries of query results rather than template strings, while
  keeping the data retrieval deterministic.
- **Better memory and preferences** — let the agent remember user preferences
  (e.g. preferred workout time, recurring errands) across sessions.

### Language and extraction

- **Better Swedish date/time parsing** — the extractor already covers relative
  dates (`idag`, `imorgon`), weekdays (`på måndag` … `på söndag`), times
  (`kl 9`, `kl 09:00`, `klockan 18`, bare `13:30`), and durations. Future work:
  date ranges, "om X dagar/veckor", part-of-day windows, and recurring phrasing.

### Reminders and planning

- **Reminder scheduler / notifications** — a background process or system
  integration that fires reminders at their scheduled time.
- **Recurring reminders** — repeat schedules (daily/weekly/custom).
- **Meal suggestions** — suggest meals based on stored preferences.
- **Local activity / event suggestions** — propose activities or events from
  context and history.

### Integrations

- **Google Calendar export/integration** — export events to and/or sync with
  Google Calendar.
- **AI news briefing** — an optional daily briefing.

### Interaction and platforms

- **Voice input** — capture notes and commands via speech.
- **Web UI** — a browser-based interface alongside the CLI; the agent runtime
  and services are already UI-agnostic and could serve a web frontend without
  changes to the core layers.
- **Mobile app** — a native or cross-platform mobile client.

### Collaboration

- **Family / partner sharing** — shared access for a partner or family member.

## Not planned for the near term

To keep the MVP focused and local-first, the following remain out of scope until
the features above are stable:

- Cloud database or remote sync.
- Push / email / background notifications and schedulers.
- Multi-user accounts and authentication.

Each roadmap item is intended to be added as a focused, well-tested step, the
same way the current MVP was built.
