# Demo

A short, reproducible walkthrough of the agent. It takes a few minutes and costs
a few cents in model calls.

Prerequisites: `pip install -e .`, and `.env` filled in with your
`LIFE_AGENT_LLM_*` values. See the [README](../README.md).

## 1. Start from a clean database

```bash
rm -f data/life_agent.db
python -m life_agent init
python -m life_agent chat
```

## 2. Plan a day in one sentence

```
You: Jag har möte på Odenplan kl 12 imorgon, behöver plugga machine learning,
     handla mat och träna på kvällen.
Agent: Jag har förberett fyra saker, vill du spara dem?

Proposed to save:

Events:
  [1] 2026-09-07 12:00 meeting - Möte på Odenplan (Odenplan)

Tasks:
  [1] - - study  - Plugga machine learning
  [2] - - errand - Handla mat

Activities:
  [1] - gym - - Träna

Will save 4 item(s); skipping 0 incomplete item(s).

Save this? [y/N] y
Saved 4 item(s):
  + task: Plugga machine learning
  + task: Handla mat
  + event: Möte på Odenplan
  + activity: Träna
```

One message, four items, sorted into three kinds. The list of what was saved is
generated from the database, not from what the agent said it did.

Answer anything other than `y`/`yes`/`j`/`ja` — including a bare Enter — and
nothing is written.

## 3. Ask about the day

```
You: Vad har jag på agendan imorgon?
Agent: Imorgon har du ett möte på Odenplan kl 12:00, och två saker att hinna med.

Tomorrow (2026-09-07):

  12:00  Möte på Odenplan  (Odenplan)

Any time:
  - Plugga machine learning
  - Handla mat
```

The day reads as a timeline, in the order it is lived. Things without a clock
time collect under **Any time** — that is where tasks live, since a task carries
only a due date.

The agent answers in words *and* prints the rows, so you can check it.

## 4. Follow up

```
You: och idag då?
Agent: Idag har du träning inplanerad.
```

The last ten turns are kept in memory, so "och idag då?" resolves without you
repeating yourself. That memory is per session and is gone when you quit; the
database is the long-term memory.

## 5. Correct something

```
You: flytta mötet imorgon till 13:00
Agent: Jag har förberett att flytta mötet till 13:00 imorgon. Vill du spara ändringen?

Matched: event: Möte på Odenplan (2026-09-07 12:00)

Move it to 2026-09-07 13:00? [y/N] y
Moved event: Möte på Odenplan to 2026-09-07 13:00
```

You describe the item; the application finds it and shows you exactly which row
matched before anything changes. If your description fits several things, it
lists them and asks which you meant.

`ta bort` works the same way.

## 6. Mark a session done

```
You: jag har tränat klart
Agent: Bra jobbat! Vill du att jag markerar det som klart?

Matched planned activity:
  planned gym - 2026-09-07 18:00 - Träna

Mark this activity as completed? [y/N] y
Completed: Träna
```

## 7. Look backwards

```
You: hur mycket har jag tränat den senaste veckan?
Agent: Du har tränat en gång den senaste veckan, ett pass på 60 minuter.

2026-08-31 -> 2026-09-07:

Mon 2026-09-07:
  18:00  Träna  (60 min, done)
```

## 8. Structured commands

The same data is reachable without talking, when typing is faster:

```bash
python -m life_agent add-task "Plugga machine learning" --due 2026-09-12 --priority high --category study
python -m life_agent tasks
python -m life_agent done 1

python -m life_agent add-event "Möte på Odenplan" --start "2026-09-07 12:00" --location "Odenplan"
python -m life_agent events

python -m life_agent activity "Gym rygg och biceps" --type gym --minutes 50
python -m life_agent activities

python -m life_agent add-reminder "Träning" --at "2026-09-07 09:00"
python -m life_agent reminders
python -m life_agent dismiss-reminder 1

python -m life_agent today
python -m life_agent week
python -m life_agent deadlines
```

Manual activity logs default to `completed`; ones the agent saves for a future
day are `planned`, which is what `complete` later looks for.

## 9. Run the tests

```bash
pytest                                  # offline, the model is faked
.venv/bin/python evals/agent_eval.py    # fifteen real sentences, calls the model
```

Neither touches `data/life_agent.db`.

## What to expect when it is wrong

It will be, sometimes. Useful things to know:

- It never writes without asking, so a misunderstanding costs you one `n`.
- If it proposes the wrong thing, say what was wrong in the next message rather
  than starting over — it has the conversation in front of it.
- If it says it could not reach the model, check `LIFE_AGENT_LLM_*` in `.env`.
  A malformed value looks exactly like a missing one.
- Model quality shows up as misclassification and as claiming saves that did not
  happen. See the comparison in [llm-first-pivot.md](llm-first-pivot.md).
