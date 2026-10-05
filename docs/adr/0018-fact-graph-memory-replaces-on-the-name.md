# 0018 — FactGraphMemory keeps timestamped facts in Neo4j and replaces on the name

Status: accepted
Date: 2026-10-05

## Context

The proposal for this project named a strategy of timestamped facts with
explicit overwrite, and the reply to it suggested adding a graph database or
another complementary data storage architecture. M1 to M3 built neither. M4
(`docs/vg-project.md`) builds both as one fourth strategy in the last week,
measured as a pilot (0019).

M3 left a question it could not answer. The consolidator read every evidence
turn, and by the reading in `docs/results.md` the requested value was still
missing from the notes in most questions: the notes are one text held to
S = 1000 tokens (0015), and what was said many sessions before the question
did not survive into them. A store of single facts with no cap, from which
the facts are chosen per question, differs from the notes in that respect.

What is already fixed constrains the rest: the 8000-token budget, counted
over the content of what is returned (0006, 0007); recalled messages shown
without dates (0008); recall and precision per turn (0009); how a summary
counts toward recall (0013); the strategy's clock (0014);
`gpt-4o-mini-2024-07-18` as the model that reads the histories, through
`chat_json` at temperature 0 in JSON mode (0010, 0015); a session the model
cannot handle skipped and counted (0016). `CLAUDE.md` adds that the Protocol
is the contract, that an outcome is never paraphrased, that memory writes to
its own store and never through `db/repositories.py`, and that a call outside
the turn must not be able to produce a tool call.

**The spike.** Before this record was written, `evals/spike_fact_graph.py`
extracted facts from the eight `knowledge-update` histories that no run
measures, the last 8 of the 69 in the list (0010): `5c40ec5b`, `6a1eabeb`,
`41698283`, `42ec0761`, `dfde3500`, `184da446`, `dad224aa` and `9ea5eabc`. No
question was answered and nothing was graded. It ran three rounds over the
same 374 sessions, one call per session, and no call failed in any round. The
replies are in `evals/results/spike/`.

- **Round one**, prompt `bc144a9f`: each session on its own, nothing
  replaced. 1,342 facts under 1,265 distinct pairs of subject and relation,
  21 of them in more than one session. By a hand reading of the eight
  questions, the value that changes kept its name between its two sessions in
  1 of the 8 histories. A rule that replaces on the name finds nothing to
  replace when each call names its facts alone.
- **Round two**, prompt `2cd15b7e`: the sessions in order, each call given
  the current facts under numbers and asked to name the numbers a new fact
  makes out of date. 937 facts, 8 replaced, and in none of the 8 did a fact
  from an evidence turn replace a fact from an evidence turn. By the hand
  reading 1 of the 8 was right, 1 restated the same value with more detail
  and 6 were wrong. But seeing the earlier facts the model reused their
  names: by the hand reading the changed value kept its name in 5 of the 8
  histories.
- **Round three**, prompt `8773bf87`: each call given the current facts and
  told that a fact with the subject and relation of an earlier one replaces
  it; the code replaces on exactly that. 973 facts, 74 replaced, 7 of them by
  the same value and 39 of them in one history. The names that replace most
  are general ones: `recent_activity` 18 times, `plan` 7, `upcoming_trip` 6.
  5 facts from an evidence turn were replaced, 1 of them by a fact from an
  evidence turn. By the hand reading, of the six histories where the old
  value was extracted at all, the new value replaced it in 2, in part in 2
  and not in 2. By the hand reading the changed value kept its name in 2 of
  the 8. Every one of the 973 facts has `user` as its subject.

The measure is the same in the three rounds. It is about the value the
question asks about, and a value that was not extracted, or only in part,
counts as not kept. The reading can be made again from
`evals/results/spike/reading.md`.

In all three rounds the value each of the eight questions asks for was
extracted from an evidence session. The extraction finds the facts; what does
not hold is the name.

`evals/verify_adr_0018.py` replays round three's saved replies without a
model call. It shows four weaknesses in the rule as round three ran it:

- A fact is a few words. Ranked with BM25 on its own text, the fact that
  holds the answer shares a word with the question in 6 of the 8 histories.
- 7 facts were replaced by a fact with the same value. In `9ea5eabc` that
  moved the fact holding the answer from its evidence session to a session
  without evidence.
- Of the 69 facts from evidence sessions, 5 were replaced with another value
  by a fact from a session without evidence.
- The turn the model names for a fact is not always the marked one: in 14 of
  the 16 evidence sessions at least one fact points at an evidence turn.

The eight histories are not measured, but they share sessions with histories
that are. By content, 54 of their 374 sessions also occur in one of the 122
measured histories, 14 of them in one of the pilot's 20 (0019). None of the
54 holds evidence, in the spike's history or in the measured one.

Neo4j 5.26.31 runs in a container on the author's machine, from the image
`neo4j:5.26.31` with digest
`sha256:d9cfe82983d27f5a75b3aaae8f316d04f9a698a3b7f6103a508f7caf8362f255`,
and is reached with the Python driver `neo4j`, version 6.3.1. Nothing under
`life_agent/` depends on either today, and the tests run offline.

## Decision

`FactGraphMemory` is a fourth implementation of `ConversationMemory`. The
Protocol is unchanged. The harness registers it as `fact-graph`.

**When, and by which model.** The strategy extracts in `end_session()`, once,
and only if at least one `kind="message"` record was written since the last
extraction. `write()` never extracts. The model is
`openai/gpt-4o-mini-2024-07-18` through OpenRouter, named by its dated id,
through the same `chat_json` as every other call: temperature 0, JSON mode.
The model id is written into every result row.

**What the call reads.** The system prompt below and one user message: the
facts that hold now, oldest first, one per line, or `(none)`; then the
session that just ended, every `kind="message"` record written since the last
extraction, in write order, numbered from 0. A `kind="outcome"` record never
enters the call. The system prompt is round three's, word for word:

```
You keep the assistant's memory of facts about the user. You are given the
facts so far and the transcript of one more conversation between the user
and the assistant, every turn numbered in brackets. List what the user says
in this conversation about themselves and about the people, places and
things in their life: what they have, like, do, plan and have done, with the
names, numbers, dates and places. Leave out general knowledge, the
assistant's advice, and what the user only asks about.
Each fact is one triple with the turn it comes from. subject: "user", or the
name of the person or thing the fact is about. relation: what is said about
the subject, as a short name in English, lower_snake_case (blood_type,
dentist_name, number_of_siblings). value: the value, as short as the
conversation allows, in the language of the conversation. turn: the number
of the turn.
A fact with the subject and relation of a fact so far replaces it. So when
the user gives a newer value for one of the facts so far, use exactly its
subject and relation; and give a fact about another person, thing or
occasion a relation of its own, one that says which: a second allergy is not
a newer value for the first. When the conversation gives two values for the
same thing, give only the current one. Reply with a JSON object:
{"facts": [{"subject": "...", "relation": "...", "value": "...", "turn": 0}]}.
With nothing to list, reply {"facts": []}.
```

The user message is:

```
Facts so far:
{subject} / {relation} = {value}
...

Conversation:
[0] user: {content}

[1] assistant: {content}

...
```

**What comes back.** One JSON object with a list `facts`. An entry is a fact
when its `subject`, `relation` and `value` are non-empty strings and its
`turn` is the number of a turn in the call; a `value` sent as a number is
taken as its text. Any other entry is dropped and counted. Nothing
dispatches on the reply.

**The replacement rule.** Two names are the same when they are equal after
`str.casefold()` with runs of whitespace made one space; nothing else is
normalised. The facts of one session are handled together, in the order of
the reply:

1. A fact with the subject, relation and value of a fact that holds, or of
   an earlier fact in the same reply, is not stored. Two values are the same
   by the rule for names. The older fact stands, with its time and where it
   came from, and no fact of this session replaces it.
2. Every other fact is stored. It replaces every fact from an earlier
   session that holds, has its subject and relation, and was not said again
   under 1. Two facts of one session never replace each other.

**A replaced fact is kept.** It is marked with the fact that replaced it and
with that fact's time. Nothing is deleted, so what held at an earlier time
can still be asked for.

**Time.** A fact's `at` is the strategy's clock when the extraction ran, as
0014 defines it: the largest `at` received in `write()`. It is never the time
of the turn. A fact holds at `T` when its `at <= T` and it is either not
replaced or replaced by a fact with `at > T`.

**Each fact is a record**: `kind="summary"`, `role="assistant"`, the content
`{subject} / {relation} = {value}`, the `session_id` of the session that
ended, `at` as above, and `id = f"fact:{session_id}:{n}"`, where `n` counts
the facts stored from that session, from 0. Its `derived_from` is the ids of
every `kind="message"` record the call read, which is the same meaning as in
0013: the call read them. The turn the model named is kept with the fact for
ranking and for display, and is not what `derived_from` rests on.

**Where the facts live.** In Neo4j 5.26.31, behind a small store interface
with a second implementation in the process. A run uses Neo4j; the tests and
the dry run use the one in the process, and need neither Docker nor a
network. A fact is an edge from a node for its subject to a node for its
value, typed by the relation and carrying the fact's id, relation, value,
session, turn, `at`, and what replaced it and when. Every replay writes under
a tag of its own and clears that tag first, so replays never see each
other's facts. The raw records stay in the process, as they do for the other
strategies. The driver is an optional dependency of its own, `graph`, in
`pyproject.toml`; the database listens on `127.0.0.1` only and its password
is read from the environment. Nothing goes through `db/repositories.py`.

**What `retrieve(query, at=T, budget_tokens=B)` returns.**

1. The facts that hold at `T` are ranked against `query` with the BM25 of
   0011: its terms, `k1`, `b` and `idf`, equal scores ordered with the fact
   stored later first. The text a fact is ranked on is its line followed by
   the content of the turn the model named for it. `N`, `n(t)` and `avgdl`
   are computed over those texts, line and turn together, for the facts that
   hold at `T` and no others.
2. Walking down the ranking, a fact is taken if the facts message with its
   line added counts at most F = 1000 tokens, and passed over if not; the
   walk goes on to the end. A fact that shares no term with the query is
   never taken.
3. The facts message is one assistant message: the lines of the facts taken,
   in the order they were stored, one per line. Only the line is shown, never
   the turn's text. No label, date, rank or score is shown.
4. The raw records with `at <= T` follow, filled backwards from the newest
   into `B` minus the tokens of the facts message, in the order they were
   written, as 0015 fills its window (0007).
5. `sources` is the ids of the facts shown, in the order shown, and then the
   raw ids. When no fact is taken there is no facts message, and the strategy
   returns what the baseline would.

A fact that has been replaced at `T` is not shown, marked or unmarked.

**Recall.** 0009 and 0013 apply unchanged. A fact's id matches no evidence, so
recall and precision count the window only, and every fact shown counts as
one recalled item. "Evidence consolidated" is computed as 0013 defines it,
with `C` the union of `derived_from` over the facts in `sources`.

**Failures.** As 0016. A call that returns `None`, or a reply without a list
`facts`, is tried twice more. If all three attempts fail the session is
skipped: no fact is stored, nothing is replaced, the turns stay in the store
as raw records, and the skip is counted. The strategy never raises on a
failed call.

A write to the store that fails, or a read from it, is the machine's failure
and not the model's. The strategy raises, the harness marks the question
`error`, and the question is run again before any figure is reported (0008).
The rerun clears the replay's tag first, so nothing half written is read.

**What the row records**, beyond what it records for the third row: the facts
message as the model saw it and its tokens; the number of messages in the
context, since `sources` no longer gives it; how many facts were stored, how
many are replaced at `T`, how many hold and how many are shown; how many
facts were not stored because they were said again; entries dropped;
sessions skipped; of the facts whose named turn is an evidence turn, how
many there are, how many are replaced at `T` and how many are shown; and the
replay's tag in Neo4j. The extraction calls are logged under `extract` and
are the strategy's cost; in the list-order replay of 0009 under
`extract-list-order`, which is not.

**What is fixed here.** The prompt, the user message, the replacement rule, F
and the ranking text are fixed before the strategy's first run. A dry run
shows the window's recall without a model call, so they are not changed after
it. One smoke test, one question per type, is made to see that the JSON
comes back in shape and that the graph is written; it changes nothing unless
the measurement is wrong, and then as a new record.

Considered and rejected:

- **Replacing on the name, each call on its own**, as round one ran. The
  changed value kept its name in 1 of 8 histories.
- **The model names what a fact replaces**, as round two ran. It did so 8
  times in 374 sessions, and no question's new value replaced its old one.
- **A narrower code rule**: replacing only where the name holds one fact
  before the session and the session gives one fact for it. On round three's
  replies that leaves 53 of the 74 replacements: it takes out 16 of the 18
  under `recent_activity` and leaves all 7 under `plan`.
- **Showing a replaced fact, marked as replaced.** It takes away the
  overwrite the strategy is there to test, and gives the answering model a
  signal the other strategies do not have (0008).
- **A fourth prompt.** Three were tried on the same eight histories; a
  further one would fit the prompt to them. The names also differ from run
  to run under one prompt.
- **Ranking a fact on its own line.** 6 of 8, above.
- **`derived_from` as the one turn the model names.** Recall's secondary
  figure would then rest on a pointer that misses in 2 of 16 evidence
  sessions.
- **Measuring with the store in the process and showing Neo4j.** The claim
  that a graph database was measured would not hold for the figures.
- **A graph without a database**, in NetworkX or in SQLite tables. The reply
  to the proposal suggested a graph database first. A graph held in the
  process is not a store, and tables are the kind of store the app already
  has, so neither is a complementary one.
- **Round two's prompt with the code's rule.** Replayed under the rule here,
  the numbers its model named left aside, round two's replies keep the name
  of the changed value in 5 of the 8 histories against 2, and 4 of the 69
  facts from evidence sessions are replaced with another value by a session
  without evidence against 5. The replay also showed that they replace more:
  85 facts against 67, 50 of them under `recent_activity` and 58 in one
  history, which is left with 38 facts that hold. The author set a bar for
  changing the prompt before the replay was run, and wrote it down after its
  result was seen: at least 4 of 8, and fewer than 4 of 69. The second was
  not met. The prompt that is kept meets neither. The bar was for a change,
  for two reasons.
  Round two's prompt cannot be used as it is: it asks the model for the
  numbers that the rule leaves aside, so either the model writes lists that
  nothing reads, or the prompt is edited into a fourth one that no call has
  seen. And the ground is thin: one run of each prompt on eight histories,
  where three of the changed values changed their name from one round to the
  next.
- **Facts in place of the raw turns.** Then the window would differ from the
  third row as well.
- **Dates in what is shown.** 0008 stands for every strategy.
- **A node per person.** A second Alex in one of the eight histories would
  be merged with the first on the name, and facts about the two would
  replace each other.

## Consequences

Two things differ from the third row on purpose, and they are what the
proposal named: a fact is written once and stands, in a store held to no
size, where the notes are one text rewritten after every session; and a fact
is replaced by a rule in the code, where the consolidator's prompt tells its
model to write the current value in place of the old one (0015). Other
things come with them and are not there on purpose: another prompt, triples
instead of prose, and a choice among the facts for each question where the
notes are shown whole. The pilot does not tell any of these apart. The model
that reads the sessions, the budget, the window's fill and the place of the
summary in the context are the same.

The rule replaces unrelated facts. Replayed over round three's replies as it
is stated here, 7 facts are not stored because they were said again, 966 are
stored and 67 are replaced; of the 69 facts from evidence sessions, 5 are
replaced with another value by a session without evidence. The record keeps
the rule and counts the harm: the row says how many facts were replaced and
whether a fact from an evidence turn was hidden when the question was asked.

With the prompt chosen, the overwrite found the changed value in 2 of the 8
spike histories. Where it misses, the old value and the new one both hold
and usually both are shown, without dates, and only the order of the lines
says which is newer: in `9ea5eabc`, `recent_family_trip = Hawaii` stands
next to `recent_trip = family trip to Paris`.

A question that asks for the earlier value loses its fact when the
replacement is right; one of the eight spike questions is of that kind. The
window can still hold the turn, and 0009's breakdown shows the case.

Ranked on its line and its turn, the fact holding the answer is among the
first five in all 8 histories and is shown in all 8. The facts message then
holds 69 to 88 of the 91 to 129 facts that hold when the question is asked,
which count 1,175 to 1,931 tokens in all. At this size the ranking decides
the margin, not the bulk: most of what holds is shown. On a history with many
more facts than these it would decide more.

The 8 of 8 for the ranking is measured on the same eight histories on which
the ranking text was chosen. It is not a test of that choice.

0011 has no stopword list, so once the turn's text is counted nearly every
fact shares a term with the question: 12 of the 899 facts that hold share
none, against 719 on the line alone. The rule that a fact sharing no term is
never taken removes almost nothing. What is shown is decided by F and by the
order of the ranking.

The spike had no `single-session-user` history: all eight are
`knowledge-update`. The pilot is the first time the strategy meets the other
type.

"Evidence consolidated" does not mean what it means for the third row. There
the last summary derives from every session, so the figure is 1 whenever the
consolidator ran. Here it says that an evidence turn's session gave at least
one fact that is shown. In the replay of the saved replies that is 15 of the
16 evidence turns. It does not say that the fact is the right one.

Precision falls by construction: every fact shown is one recalled item that
matches no evidence, 69 to 88 of them in the replay against one summary for
the third row. It is reported and not compared.

All the facts hang on `user`, so the graph is a star. What it has of
structure is in the chains of replaced values and in the times, and that is
what the presentation shows. It is a graph database used as a store of
timestamped edges, not a graph that is traversed.

The prompt allows a subject other than `user`, and the store makes a node
for each subject. If the model named a person, two people of one name would
share a node. In round three it never did. A value is a node by its text as
well, so two people named as values already share one: in `5c40ec5b`, the
friend Alex and the partner Alex. Retrieval reads the edges, so this changes
the drawing and not what is shown.

The list of facts given to each extraction call grows with the history: at
most 126 facts in the spike. That is small for a pilot and unbounded in an
agent.

The extraction turns fiction and exercises into facts about the user: 45 of
the 973 facts of round three have no word of their value in the user's turns
of their session, and 24 point at an assistant turn. Nothing in the rule
removes them.

The names are not reproducible. Three of the eight changed values kept their
name in round two and lost it in round three (`6a1eabeb`, `dfde3500` and
`9ea5eabc`). A second run of the same question can replace what the first
did not.

The figures in this record come from replies made under round three's rule,
replayed under the rule as stated here. The two differ in what happens to a
fact said again, which also changes the order of the facts given to the next
call. The first run under this record is the first time the model meets the
rule as written.

The prompt and the rule were shaped on histories that share 54 filler
sessions with measured ones. No evidence session, no question and no answer
of a measured history was seen while shaping them.

The prompt was shaped on English conversations and asks for relation names
in English. Swedish is untested, and the agent's language is Swedish.

Round three cost $0.2076 for the eight histories, about $0.026 a history, at
3,352 tokens in and 87 out per call. The three rounds cost $0.60 together.

A run needs Docker and Neo4j on the machine. The tests and the dry run do
not, and the app does not import the driver.

`CLAUDE.md` says no strategy persists anything yet. Under this record one
does, in its own store, and the sentence is corrected when the strategy is
built.

If OpenRouter withdraws the dated model before the pilot is finished, a new
record supersedes this one.
