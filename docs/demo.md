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
python -m life_agent extract "Jag har möte på Odenplan kl 14 imorgon"
```

```
Extraction preview:

Events:
  [1] 2026-06-12 14:00 meeting - Möte (Odenplan)

Confidence: 0.55

Nothing was saved. This is a read-only preview.
```

## More phrases the extractor understands

The deterministic extractor handles common Swedish planning phrases, including
relative dates (`idag`, `imorgon`), weekdays (`på fredag` … `på söndag`), and
times (`kl 9`, `kl 09:00`, `klockan 18`, bare `13:30`). A few examples:

```bash
# Task with a due date (category inferred: study / errand)
python -m life_agent extract "Jag behöver plugga machine learning på fredag"
#   Tasks:
#     [1] 2026-06-12 medium study - Plugga machine learning

# Errand task
python -m life_agent extract "Jag måste handla mat imorgon"
#   Tasks:
#     [1] 2026-06-12 medium errand - Handla mat

# Reminder with date + time
python -m life_agent extract "Påminn mig att handla mat imorgon kl 10"
#   Reminders:
#     [1] 2026-06-12 10:00 - Handla mat

# Planned gym activity with duration
python -m life_agent extract "Jag ska gymma bröst och triceps idag kl 18 i 45 minuter"
#   Activities:
#     [1] 2026-06-11 18:00 gym 45min - Gymma bröst och triceps

# Appointment on a weekday
python -m life_agent extract "Jag ska till tandläkaren på fredag kl 10"
#   Events:
#     [1] 2026-06-12 10:00 health - Tandläkaren
```

Vague times such as *"på söndag kväll"* are **not** invented into an exact
timestamp; the extractor records a clarifying question instead. As always,
`extract` is read-only and `add` asks `Save this? [y/N]` before writing.

## Interactive chat mode

Instead of running individual commands, you can use `chat` for a conversational
loop that routes messages to the right service:

```bash
python -m life_agent chat
```

```
Hello! I am your personal life agent.
Type a message, or /help for available commands.

You: vad har jag idag
Today (2026-06-14):

Nothing on the agenda.

You: jag ska träna rygg och biceps kl 12 imorgon, träningen ska vara 1h och påminn mig kl 09
Proposed to save:
...
Save this? [y/N] y
Saved 2 item(s):
  + activity: Träna rygg och biceps
  + reminder: Påminnelse

You: jag har tränat klart
Matched planned activity:
  planned gym 60min 2026-06-15 12:00 - Träna rygg och biceps

Mark this activity as completed? [y/N] y
Completed: Träna rygg och biceps

You: /quit
Bye!
```

Type `/help` for a full list of phrases the chat mode recognises. The same
safety rules apply: planning text asks for confirmation before saving, and
completion text asks before updating.
