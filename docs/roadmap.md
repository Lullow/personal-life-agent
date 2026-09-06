# Roadmap

This document lists **future features** only.  The current system covers local
task/event/activity/reminder management, planner views (`today`, `week`,
`deadlines`), and a conversational agent that plans, answers questions about
saved data, reschedules, deletes, and completes — always behind an explicit
confirmation.

See [architecture.md](architecture.md) and
[agent-architecture.md](agent-architecture.md) for how the current system is
built and why external integrations can be added without rewriting existing
layers.

## Planned features

### The agent

- **A `facts` table** — one generic table with free text, a category, and a
  timestamp, for what does not fit the four typed tables: preferences, family
  routines, household observations. Not four more typed models; you cannot
  enumerate in advance what a household wants remembered.
- **A day and a time that are separate fields** — the schema cannot express
  "tomorrow, time unknown" for an activity, so the agent has to ask for a clock
  time it does not need.
- **A local model** — `LLMClient` speaks only the OpenAI-compatible protocol, so
  this is a base-URL change plus a model good enough to be trusted with it. It
  restores the privacy properties the project started with.

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
