# Agent Architecture

The agent is one model call per message, plus a second call when the message
was a question about saved data. Everything that decides what may happen is
code. See [llm-first-pivot.md](llm-first-pivot.md) for why it is built this way
and what it replaced.

## The loop

```
your message
  │
  ├─ ConversationAgent.send()                    life_agent/agent/conversation.py
  │     history (last 10 turns) + system prompt
  │     └─► one call ──► {"tool": …, "arguments": {…}, "reply": "…"}
  │
  ├─ ToolRegistry.get(tool)                      unknown name → rejected, answered as chat
  ├─ AgentDecision built from the REGISTRY       action_type, requires_confirmation
  ├─ AgentPolicy.validate_decision_safety()      belt and braces
  │
  └─ dispatch
        read   → run it, then a second call to answer from the rows → "display"
        write  → propose it → "needs_confirmation" → the CLI asks you
        none   → "reply"
```

`AgentTurn` carries the outcome: `kind` is `"reply"`, `"display"`, or
`"needs_confirmation"`, and the CLI in `life_agent/cli/commands.py` does the
asking.

## The four guarantees

**1. The registry decides what a tool is, not the model.**

`action_type` and `requires_confirmation` are read from `ToolRegistry`, never
from the model's JSON. A model that labels `delete_item` as a harmless read
changes nothing: the registry says `delete`, and the confirmation prompt
appears anyway.

**2. A hallucinated tool is a failed lookup.**

The model never executes anything. It names a tool, and an unknown name simply
does not resolve — the turn degrades to conversation and the reply still
reaches you.

**3. The loop never writes.**

`ConversationAgent` has no write path. Mutating tools return
`needs_confirmation` with a resolved proposal, and only the CLI, after an
explicit `y`, calls a service that writes. Those services call
`assert_confirmed()` first and raise `PermissionError` otherwise.

**4. What you are told about a write comes from the database.**

The line printed after a save is generated from `ConfirmationSaveResult`, and
after an edit from the resolved row. The model's prose is never the record of
what happened — it is not trusted to be, and in practice it sometimes miscounts.

## Tools

| Tool | Action | Confirms | Arguments |
|---|---|---|---|
| `list_day` | read | no | `date` |
| `list_range` | read | no | `from`, `to` |
| `list_deadlines` | read | no | — |
| `list_reminders` | read | no | — |
| `save_extracted_items` | write | **yes** | `tasks`, `events`, `activities`, `reminders` |
| `complete_activity` | update | **yes** | `text` |
| `reschedule_item` | update | **yes** | `title`, `item_type`, `date`, `new_time` |
| `delete_item` | delete | **yes** | `title`, `item_type`, `date` |
| `ask_clarifying_question` | clarify | no | — |

There is deliberately **no tool that assumes a day**. `list_today` and
`list_week` used to exist, and while they did, "vad har jag imorgon?" kept being
answered with today's schedule. The agent must always name the date it means.

## Why reads take a second call

The reply is written in the same JSON as the tool call, so on a read it is
composed *before* any data exists. The model could fetch but never look. That
produced answers like "du har inget planerat" about a day it had not seen, and
whole-month dumps in response to "hur mycket har jag tränat?".

So a read turn calls again: the retrieved text is handed back with
`READ_ANSWER_SYSTEM_PROMPT`, and the model answers the actual question. The
rows are still printed underneath, so you can check it. If the second call
fails, the first reply stands and the data is unaffected.

Writes take one call. The extra cost is paid only where it buys something.

## How editing resolves without ids

The model never sees a database id. For `reschedule_item` and `delete_item` it
describes what the user meant — some words from the title, optionally a kind and
a day — and `life_agent/services/edit_service.py` resolves that to rows:

- Word matching compares **openings**, not substrings: the agent says
  "ryggpasset" and "lämningen" where the titles read "Träna rygg" and "Lämna
  grabben". Four shared leading characters bridge Swedish inflection without a
  stemmer.
- The kind and the day are treated as guesses. If narrowing by them finds
  nothing, they are dropped rather than reporting a findable row as missing.
- Only the best-scoring group survives, so a clear description resolves to one
  row and a vague one comes back as a list to choose from.
- An empty description matches nothing. Removing "everything" is not something
  the agent gets to propose.

The resolved row is always shown before you confirm, so a wrong match is caught
by a person.

## Degradation

Every failure lands somewhere sane, and none of them writes:

| Failure | Result |
|---|---|
| No model configured, or unreachable | A message saying so |
| Response is not JSON | Same |
| Tool name unknown | Answered as conversation, tool ignored |
| Arguments are not a valid `ExtractionResult` | Asks you to rephrase |
| Date argument will not parse | Asks which date, rather than assuming today |
| Nothing matches a description | Says so |
| Several things match | Lists them and asks |
| Second read call fails | The lead-in reply stands, data still printed |

The model also sometimes answers `{"delete_item": {…}}` instead of
`{"tool": "delete_item", "arguments": {…}}` — the right intent in the wrong
envelope. That is accepted when the key names a real tool, because the registry
still decides what the name is allowed to do.
