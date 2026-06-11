# Demo

A clean, reproducible walkthrough starting from a fresh local database. It shows
the natural language `add` (with confirmation), listing activities and
reminders, the `complete` flow, and the planner views.

> Run these from the project root with your virtual environment activated
> (`source .venv/bin/activate`). When `add` and `complete` ask `[y/N]`, type
> `y` and press Enter.

## 1. Start from a clean database

```bash
rm -f data/life_agent.db
python -m life_agent init
```

```
Database initialised.
```

## 2. Add from natural language (confirm with `y`)

```bash
python -m life_agent add "Jag ska träna rygg och biceps kl 12 imorgon, träningen ska vara 1h och påminn mig kl 09."
```

You will see a proposal and a prompt. Type `y`:

```
Proposed to save:

Activities:
  [1] 2026-06-12 12:00 gym 60min - Träna rygg och biceps

Reminders:
  [1] 2026-06-12 09:00 - Påminnelse

Confidence: 0.55

Will save 2 item(s); skipping 0 incomplete item(s).

Save this? [y/N]: y
Saved 2 item(s):
  + activity: Träna rygg och biceps
  + reminder: Påminnelse
```

The activity is stored as **planned** (a future plan), not completed.

> Dates are relative to the day you run the command. *"imorgon"* (tomorrow) is
> resolved against today's date, so the exact timestamps in your output will
> differ from those shown here.

## 3. List what was saved

```bash
python -m life_agent activities
```

```
[1] planned gym 60min 2026-06-12 12:00 - Träna rygg och biceps
```

```bash
python -m life_agent reminders
```

```
#1 2026-06-12 09:00 pending general - Påminnelse
```

## 4. Complete the activity from natural language (confirm with `y`)

```bash
python -m life_agent complete "Jag har tränat klart"
```

```
Matched planned activity:
  planned gym 60min 2026-06-12 12:00 - Träna rygg och biceps

Mark this activity as completed? [y/N]: y
Completed: Träna rygg och biceps
```

## 5. Confirm the status changed

```bash
python -m life_agent activities
```

```
[1] completed gym 60min - Träna rygg och biceps
```

## 6. Planner views

```bash
python -m life_agent today
python -m life_agent week
```

```
Today (2026-06-11):

Nothing on the agenda.
```

```
Week 2026-06-11 -> 2026-06-17:

Nothing scheduled.
```

> The planner views summarize **events** and **tasks**. To see them populated,
> add a task or event, for example:
>
> ```bash
> python -m life_agent add-task "Plugga ML" --due 2026-06-12 --priority high --category study
> python -m life_agent add-event "Möte på Odenplan" --start "2026-06-12 14:00" --location "Odenplan"
> python -m life_agent week
> ```

## 7. Run the tests

```bash
pytest -v
```

All tests use temporary databases, so running them never touches your
`data/life_agent.db`.

## Try the read-only preview

`extract` shows what *would* be extracted and saves nothing:

```bash
python -m life_agent extract "Möte på Odenplan kl 14 imorgon"
```

```
Extraction preview:

Events:
  [1] 2026-06-12 14:00 - Möte på Odenplan

Confidence: 0.55

Nothing was saved. This is a read-only preview.
```
