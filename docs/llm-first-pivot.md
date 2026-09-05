# LLM-first pivot

**Status:** agreed 2026-09-05, not yet implemented.
**Applies to:** the `spike/llm-first` branch. `main` is preserved as-is.

This document records a design decision that reverses the governing principle
of the project. It is written down because the reasoning matters more than the
task list: the same drift can happen again.

## Why

The project exists to be a conversational assistant for everyday planning —
unstructured text in, a structured plan out. The architecture was built the
other way around: `CLAUDE.md` established that deterministic pattern matching
is the default and the LLM an optional add-on that every path "degrades
gracefully" back to. That is a defensible engineering choice — testable,
offline, free per message — but it is the opposite of the stated goal. The LLM
was never allowed to hold the wheel.

The cost showed up as a treadmill. `saved_data_query_service.py` grew five
hardcoded question types, each with its own pattern list and query function;
three of the five most recent commits on `main` add another one. Every question
the household might ask requires new code. That queue is as long as the Swedish
language.

Measured at the time of the decision: 5418 lines of source, 5813 lines of
tests, 549 tests passing. Roughly 1650 source lines — about 30% — are
hand-written natural language understanding.

A second symptom: no `.env` exists and no local model runtime is installed, so
every LLM path in the codebase (extraction, routing, saved-data responses,
conversation fallback) has only ever run against fake clients in tests. Nothing
real ever pulled the design toward working behaviour.

## What is kept

The domain core is sound and is reused unchanged:

- `db/` — repositories, schema, database access
- `models/` — task, event, activity, reminder, common
- `services/` — task, event, activity, reminder, planner
- `agent/tools.py` — the `ToolRegistry`
- `agent/policy.py` and `agent/safety.py` — the confirmation chain
- `llm/client.py`, `cli/formatters.py`
- `schemas/extraction.py`, `schemas/confirmation.py`
- Tests covering the confirmation chain and the repositories

The safety architecture is the most valuable part of the existing work. A tool
registry carrying `action_type` and `requires_confirmation`, a policy that
rejects unconfirmed mutations, and `assert_confirmed()` at the write boundary
are exactly what is needed once a language model is allowed to drive. Starting
over would mean rebuilding it, worse.

## What is removed

On the spike branch only:

- `services/extraction_service.py` — twenty regexes for Swedish time,
  date, duration and location
- `services/saved_data_query_service.py` — five hardcoded question types
- the deterministic mode of `agent/router.py`
- `chat_service.classify_intent` and the intent ladder in `cli/commands.py`
- `models/family.py`, `meal.py`, `preference.py`, `user.py` — defined,
  exported, never wired to a table or a service
- the pattern-matching tests covering the above

Tests are deleted together with the code they cover. A test asserting that a
regex matches "imorgon" has no value once no regex exists.

## The new loop

One LLM call per message. The model receives the message plus the last ten
turns and answers with JSON:

```json
{"tool": "...", "arguments": {...}, "reply": "..."}
```

`ToolRegistry` validates the tool name, so a hallucinated tool becomes a
rejected lookup rather than an execution. Writes flow through the existing
confirmation flow; the whole plan is confirmed once, and `ExtractionResult` is
the argument shape the model fills in.

JSON classification is chosen over native tool-calling because it works against
every OpenAI-compatible endpoint including weak local models, which matters
given the local-model goal below. The format lives behind one function in
`llm/` so it can be swapped later without touching the runtime.

Single call rather than classify-then-respond: two calls double latency and
cost, and latency is the scarce resource once the model runs on your own
machine.

### Trust is structural, not prompted

The model's `reply` is never the last word about a write. After a save the CLI
always prints the actual outcome from `ConfirmationSaveResult`, styled
distinctly from conversational text. The model may claim whatever it likes; the
truth line comes from the database.

This follows the existing principle: guarantees live in code, not in a politely
worded instruction to a language model. A prompt rule alone was acceptable
while the LLM was a fallback for unrecognised messages. It is not acceptable
once the model drives every interaction.

## Two kinds of memory

These are separate mechanisms and must not be conflated.

**Conversation history** — the last ten turns, held in memory, discarded when
the session ends. It exists so follow-up questions work ("och imorgon då?").

**Long-term history** — the SQLite database, which already carries `logged_at`
and `created_at` on every row and has been accumulating since June. Storage is
not the gap; retrieval is. The repositories expose `list_tasks()`,
`list_events()`, `list_activities()` with no date filtering, so the agent
cannot ask what happened in March. Adding `from`/`to` parameters and
registering parameterised read tools is the fix — and it is exactly what
`saved_data_query_service.py` was approximating one question type at a time.

Read access goes through registered tools, not model-generated SQL. SQL
generation is a write path in disguise and the one place where a hallucination
becomes destructive.

## Cloud now, local later

`LLMClient` speaks only the OpenAI-compatible protocol, so moving to a local
model is a base-URL change. Build against a hosted model to get moving; treat a
local model as the destination.

This has a consequence for `docs/privacy.md` and the README, which currently
promise that nothing leaves the machine by default. Once the model drives every
message, that promise needs rewriting to match reality until a local model is
in place.

## Testing

Two suites, kept apart:

- **Fake LLM client** returning canned tool calls. Fast, deterministic, no
  network. Proves the confirmation chain holds and that the registry rejects
  invented tools.
- **A manual eval set** of ten to twenty real Swedish sentences, run by hand
  when the prompt changes and read with human eyes.

No recorded fixtures. A recording made against today's model says nothing about
the model you switch to tomorrow.

## Order of work

1. Add `LIFE_AGENT_CONVERSATION_MODE` to `.env.example`
2. Commit the outstanding conversation-fallback work on `main`, green and
   complete — `main` becomes the preserved snapshot
3. Branch
4. **Prerequisite, manual:** obtain an API key and write `.env`
5. The JSON contract in `llm/client.py`
6. The minimal loop: message plus history, one call, registry validation,
   dispatch
7. Wire in the existing confirmation flow
8. Run the target sentence

## Definition of done for the spike

> "Jag har möte på Odenplan kl 12 imorgon, behöver plugga machine learning,
> handla mat och träna på kvällen."

Four correct items, with the right time, place and category. Time-box it to a
couple of evenings; failing inside that box is also an answer.

The point of the spike is to feel whether the idea carries before anything is
torn out. Building the read tools first would mean a week of mechanical work
before that question gets answered.

## Deliberately deferred

Everything below waits until the spike succeeds:

- date-range parameters on the repositories, and registered read tools
- a `facts` table for what does not fit the four tables — preferences, family
  routines, household observations
- family agenda, meals, local events, AI news

On the `facts` table: it should be one generic table with free text, a category
and a timestamp — not the four typed models that were sketched and abandoned.
Four typed models is the same mistake as five hardcoded question types in a
different shape. You cannot enumerate in advance what a household will want
remembered.
