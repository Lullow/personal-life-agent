# Roadmap

This document lists **future features** only. None of these are implemented in
the current MVP. The MVP today covers local task/event/activity/reminder
management, planner views (`today`, `week`, `deadlines`), and confirmed natural
language input (`extract`, `add`, `complete`).

See [architecture.md](architecture.md) for how the current system is built and
why a real LLM and external integrations can be added later without rewriting
existing layers.

## Planned features

### Language and extraction

- **Real LLM provider integration** — wire the `llm/client.py` placeholder to an
  actual model for more flexible extraction, keeping the deterministic
  rule-based extractor as an offline fallback.
- **Better Swedish date/time parsing** — the extractor already covers relative
  dates (`idag`, `imorgon`), weekdays (`på måndag` … `på söndag`), times
  (`kl 9`, `kl 09:00`, `klockan 18`, bare `13:30`), and durations. Future work:
  date ranges, "om X dagar/veckor", part-of-day windows, and recurring phrasing.

### Reminders and planning

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
- **Web app** — a browser-based interface alongside the CLI.
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
