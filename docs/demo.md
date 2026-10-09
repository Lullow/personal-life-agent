# Demo

A short, reproducible walkthrough of the agent. It takes a few minutes and costs
a few cents in model calls.

Prerequisites: `pip install -e .`, and `.env` filled in with your
`LIFE_AGENT_LLM_*` values. See the [README](../README.md).

## 1. Start from a clean database

```bash
export DB_PATH=data/demo.db
rm -f data/demo.db
python -m life_agent init
python -m life_agent chat
```

The demo runs against a database of its own, so whatever is in
`data/life_agent.db` is left alone. `unset DB_PATH` when you are done.

## 2. Plan a day in one sentence

```
You: Jag har möte på Odenplan kl 12 imorgon, behöver plugga machine learning,
     handla mat och träna kl 18.
Agent: Jag har förberett fyra saker, vill du spara dem?

Proposed to save:

Activities:
  [1] 2026-10-05 18:00 other - - Träna

Events:
  [1] 2026-10-05 12:00 meeting - Möte på Odenplan (Odenplan)

Tasks:
  [1] - - study - Plugga machine learning
  [2] - - errand - Handla mat

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
Agent: Du har ett möte på Odenplan kl 12:00 och träning kl 18:00.

Tomorrow (2026-10-05):

  12:00  Möte på Odenplan  (Odenplan)
  18:00  Träna
```

The day reads as a timeline, in the order it is lived. Things without a clock
time collect under **Any time** at the end — that is where a task shows up on
the day it is due, since a task carries only a due date. The two tasks above
have no due date, so they belong to no day; `python -m life_agent tasks` lists
them.

The agent answers in words *and* prints the rows, so you can check it.

## 4. Follow up

```
You: och idag då?
Agent: Det finns inget på agendan idag.

Today (2026-10-04):

Nothing on the agenda.
```

The last ten turns are kept in memory, so "och idag då?" resolves without you
repeating yourself. That memory is per session and is gone when you quit; the
database is the long-term memory.

## 5. Quit and come back

Tell it something that is not a thing to save, and leave:

```
You: Mina favoritlöparskor är Nike.
Agent: Nike är ett populärt val för löparskor! Har du haft dem länge?

You: /quit
Bye!
```

Start it again and ask:

```bash
python -m life_agent chat
```

```
You: Vilket märke är mina favoritlöparskor?
Agent: Jag har tyvärr ingen information om dina favoritlöparskor. Du kanske kan
       kolla i dina anteckningar eller fråga någon som känner dig väl.
```

The meeting and the training session are still in the database. The sentence
about the shoes held nothing to save, so it lived only in the conversation, and
the conversation ended with the process. What the agent is told but does not
save, it forgets. Which memory would have kept it, and at what cost, is what
the comparison in this repo measures: [vg-project.md](vg-project.md),
[results.md](results.md).

The steps below work from either session: they go by what is in the database.

## 6. Correct something

```
You: flytta mötet imorgon till 13:00
Agent: Jag har förberett att flytta mötet till kl 13:00 imorgon. Vill du göra det?

Matched: event: Möte på Odenplan (2026-10-05 12:00)

Move it to 2026-10-05 13:00? [y/N] y
Moved event: Möte på Odenplan to 2026-10-05 13:00
```

You describe the item; the application finds it and shows you exactly which row
matched before anything changes. If your description fits several things, it
lists them and asks which you meant.

`ta bort` works the same way.

## 7. Mark a session done

```
You: jag har tränat klart
Agent: Bra jobbat! Vill du markera träningen som klar?

Matched planned activity:
  planned other - 2026-10-05 18:00 - Träna

Mark this activity as completed? [y/N] y
Completed: Träna
```

## 8. Look backwards

```
You: hur mycket har jag tränat den senaste veckan?
Agent: Det finns ingen registrerad träning den senaste veckan.

2026-09-28 -> 2026-10-04:

Nothing scheduled.
```

The week it looks at ends today, and the session you just marked done is dated
tomorrow, so there is nothing in it yet.

## 9. Structured commands

The same data is reachable without talking, when typing is faster. With
`DB_PATH` still exported, these go to the demo database too:

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

## 10. Run the tests

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
