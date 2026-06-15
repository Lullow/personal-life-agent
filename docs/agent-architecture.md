# Agent Architecture

This document explains the agent runtime that sits between the chat loop and the
service layer in Personal Life Agent.  The runtime was added after the initial
MVP to give the chat mode a structured, testable classification pipeline instead
of ad-hoc keyword checks.

Everything described here is fully implemented.  No cloud infrastructure,
background process, or external AI service is required.

---

## High-level flow

```
User input
  │
  ▼
CLI chat loop (commands.py)
  │  /help and /quit are handled here before anything else
  │
  ▼
ChatService.classify_intent()
  │  maps the message to a ChatIntent by delegating to AgentRouter
  │
  ▼
AgentRouter.route()
  │  classifies the message into an AgentDecision
  │  ├─ deterministic mode  (default)  — regex patterns, no network call
  │  └─ llm mode  (optional)  ─────── tries LLM first, falls back to deterministic
  │
  ▼
AgentDecision
  │  a structured value: intent, tool_name, action_type, requires_confirmation, …
  │
  ▼
AgentPolicy.validate_decision_safety()
  │  rejects unknown tools and unsafe write decisions, never lets an
  │  unregistered or confirmation-free mutation reach the runtime
  │
  ▼
AgentRuntime.handle_message()
  │  dispatches based on decision.tool_name
  │  ├─ read tools  ──► call service immediately, return RuntimeResponse(kind="display")
  │  ├─ query_saved_data ─► saved_data_query_service, return RuntimeResponse(kind="display")
  │  ├─ extract_items ──► return RuntimeResponse(kind="needs_confirmation")
  │  ├─ complete_activity ► return RuntimeResponse(kind="needs_confirmation")
  │  └─ unknown ──────────► return RuntimeResponse(kind="unknown")
  │
  ▼
Service layer  (planner_service, reminder_service, saved_data_query_service, …)
  │
  ▼
Repository layer  (life_agent/db/repositories.py)
  │
  ▼
SQLite  (data/life_agent.db, local file only)
```

The chat loop acts on the returned `RuntimeResponse`:

- `"display"` — print the text directly, no confirmation needed.
- `"needs_confirmation"` — show the proposal and ask `Save this? [y/N]` or
  `Mark this activity as completed? [y/N]` before touching the database.
- `"unknown"` — show a helpful fallback message with examples.

---

## Components

### AgentDecision  (`life_agent/agent/decisions.py`)

An `AgentDecision` is the normalised output of every routing step.  It is a
Pydantic model with these fields:

| Field | Type | Purpose |
|---|---|---|
| `intent` | `str` | Human-readable label for the routing result (e.g. `"show_today"`) |
| `tool_name` | `str \| None` | Which registered tool handles this decision |
| `action_type` | `"read" \| "write" \| "update" \| "delete" \| "clarify" \| "unknown"` | Used by policy to determine safety |
| `requires_confirmation` | `bool` | Whether the caller must ask the user before executing |
| `arguments` | `dict` | Free-form payload forwarded to the tool (e.g. `{"text": "..."}`) |
| `confidence` | `float \| None` | 0–1 confidence in the classification; validated at construction |
| `user_facing_message` | `str \| None` | Optional message the router wants shown to the user |

`AgentDecision.is_mutating` is a computed property that returns `True` for
`write`, `update`, and `delete` action types.

All mutating decisions must have `requires_confirmation=True` — this is
enforced by the policy layer, not just by convention.

---

### ToolRegistry  (`life_agent/agent/tools.py`)

The `ToolRegistry` is an in-memory catalogue of `ToolDefinition` objects.
Each `ToolDefinition` carries:

- `name` — unique string identifier.
- `description` — plain-text explanation used in LLM prompts.
- `action_type` — read / write / update / delete / clarify.
- `requires_confirmation` — boolean enforced by policy.
- `handler_name` — the function the runtime will call.

`build_default_tool_registry()` populates the registry with all current tools
(see [Current tools](#current-tools)).  The router and policy both receive the
same default registry, so an unregistered tool name can never slip through to
the runtime.

---

### AgentPolicy  (`life_agent/agent/policy.py`)

`validate_decision_safety(decision, registry)` enforces two rules:

1. **Unknown action type** (`"unknown"`) is always unsafe — the router returns
   a clarify decision instead.
2. **Mutating actions** (`write`, `update`, `delete`) must have
   `requires_confirmation=True`; if an LLM returns a mutating decision without
   this flag, the router rejects it and falls back to deterministic routing.
3. **Unregistered tool** — if `decision.tool_name` is not in the registry the
   decision is rejected.

`requires_confirmation(action_type)` is a pure helper that returns `True` for
`write`, `update`, and `delete`.

---

### AgentRouter  (`life_agent/agent/router.py`)

`AgentRouter.route(message) -> AgentDecision` is the main classification entry
point.  It operates in one of two modes (controlled by
`LIFE_AGENT_AGENT_ROUTER_MODE` env var, default `deterministic`):

#### Deterministic mode (default)

Pattern-matching in pure Python — no network call, no external dependency,
works fully offline.

Priority order inside `_route_deterministic`:

1. **Saved-data question patterns** (`_QUERY_PATTERNS`) — checked first to
   prevent question phrases from matching broader list patterns.
2. **Today / week / deadline / reminder list patterns** — phrases like
   "vad har jag idag" or "visa veckan".
3. **Completion phrases** — "jag har tränat klart", "träningen är klar".
4. **Planning / creation markers** — "jag ska", "påminn mig", "behöver",
   "måste", etc.
5. **Fallback** — unknown action, prompts the user for clarification.

#### LLM mode (optional)

Set `LIFE_AGENT_AGENT_ROUTER_MODE=llm`.  The router sends the message to the
configured LLM (same `LLMClient` used by the extraction service) with a
structured routing prompt, then:

1. Parses the JSON response into an `AgentDecision`.
2. Validates the decision against `AgentPolicy` and `ToolRegistry`.
3. **Falls back to deterministic routing** if the LLM is unavailable, returns
   invalid JSON, names an unknown tool, or produces an unsafe decision.

The fallback is unconditional: the runtime never receives a decision that has
not passed both the policy check and the tool registry lookup.

---

### AgentRuntime  (`life_agent/agent/runtime.py`)

`AgentRuntime.handle_message(message) -> RuntimeResponse` is the thin
dispatcher layer.

It calls `AgentRouter.route(message)`, inspects `decision.tool_name`, and
returns a `RuntimeResponse` without touching the database:

| `tool_name` | `RuntimeResponse.kind` | What happens |
|---|---|---|
| `list_today` | `"display"` | Calls `planner_service.get_today_agenda()` |
| `list_week` | `"display"` | Calls `planner_service.get_week_agenda()` |
| `list_deadlines` | `"display"` | Calls `planner_service.get_upcoming_deadlines()` |
| `list_reminders` | `"display"` | Calls `reminder_service.list_reminders()` |
| `query_saved_data` | `"display"` | Calls `saved_data_query_service.answer_saved_data_question()` |
| `extract_items` | `"needs_confirmation"` | Returns; the chat loop handles extraction + `Save this?` |
| `complete_activity` | `"needs_confirmation"` | Returns; the chat loop handles completion + `Mark as completed?` |
| anything else | `"unknown"` | Returns the fallback message |

The runtime itself never writes to the database.

---

## Current tools

| Tool | Action type | Confirmation required | Description |
|---|---|---|---|
| `list_today` | read | no | Show today's agenda |
| `list_week` | read | no | Show this week's agenda |
| `list_deadlines` | read | no | Show upcoming task deadlines |
| `list_reminders` | read | no | Show pending reminders |
| `list_activities` | read | no | Show logged activities |
| `extract_items` | read | no | Parse planning text into a structured preview (never saves) |
| `query_saved_data` | read | no | Answer questions about existing saved data (reminders, tasks, events, activities) |
| `ask_clarifying_question` | clarify | no | Return a clarification prompt to the user |
| `save_extracted_items` | write | **yes** | Persist an extraction result (only after user confirms) |
| `complete_activity` | update | **yes** | Mark a planned activity as completed (only after user confirms) |

`save_extracted_items` is never selected directly by the router — it is reached
only through the confirmation flow inside the CLI after the user answers `y`.

---

## Read vs write/update actions

**Read-only tools** can run immediately:

- `list_today`, `list_week`, `list_deadlines`, `list_reminders`
- `list_activities`
- `extract_items` (produces a preview; does not persist anything)
- `query_saved_data` (reads existing records; never writes)
- `ask_clarifying_question` (returns text only)

**Write and update tools** require explicit user confirmation:

- `save_extracted_items` — the user must answer `y` or `yes` to
  `Save this? [y/N]` before any record is created.
- `complete_activity` — the user must answer `y` or `yes` to
  `Mark this activity as completed? [y/N]` before the status is updated.

This rule is enforced at three independent layers:

1. `AgentDecision.requires_confirmation` must be `True` for all mutating decisions.
2. `AgentPolicy.validate_decision_safety` rejects mutating decisions that lack
   the flag.
3. `life_agent/agent/safety.py` — `assert_confirmed(confirmed)` raises
   `PermissionError` inside `save_confirmed_extraction` and `complete_activity`
   if they are reached without an explicit confirmation flag.

---

## Saved-data Q&A (`query_saved_data`)

`query_saved_data` is a read-only tool that answers simple questions about
records that already exist in the database.  It is handled by
`life_agent/services/saved_data_query_service.py`.

The service classifies the question into one of three patterns:

| Pattern | Example | What it does |
|---|---|---|
| Reminder lookup | "vilken tid ska du påminna mig om att handla mat" | Searches pending reminders for a matching title keyword |
| Planned tomorrow | "har jag något planerat imorgon" | Lists events, tasks, activities, and reminders for tomorrow |
| Training this week | "vad har jag för träningar den här veckan" | Lists gym activities within the current week |

If nothing matches or no records are found the service returns a clear "nothing
found" message.  The service never writes or modifies records.

---

## Why tools are separated from the LLM

The LLM (when enabled) acts only as a **classifier** — it picks a tool name and
fills in arguments.  It never calls tools directly.  Benefits:

- The same tool definitions are used in deterministic mode, so adding a new
  tool automatically exposes it to both routing paths.
- The `ToolRegistry` and `AgentPolicy` validate every decision before the
  runtime sees it, so a hallucinated or unsafe LLM output is rejected the same
  way an invalid deterministic decision would be.
- Tests use a `FakeLLMClient` that returns pre-written JSON — no real API key
  is needed and tests are deterministic.
- Disabling the LLM (or running without one) degrades gracefully: the
  deterministic router handles everything.

---

## Safety summary

| Principle | How it is enforced |
|---|---|
| Local-first storage | All data is in a local SQLite file; no cloud database |
| No write without confirmation | `AgentPolicy`, `AgentDecision.requires_confirmation`, `assert_confirmed()` |
| LLM output is validated | `AgentPolicy` checks every LLM decision; invalid output triggers fallback |
| Unknown decisions are safe | Unregistered tools and unknown action types always fall back to `"unknown"` |
| Deterministic fallback | Available in all modes; LLM mode falls back to it on any failure |
| Extraction is read-only | `extract` command and `extract_items` tool never persist anything |
