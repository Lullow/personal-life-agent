# Method (draft)

Status: draft, written in M2 on 2026-10-03; the rules for
`ConsolidatingMemory` added in M3 the same night, before its run; the
paragraphs on `FactGraphMemory` and its pilot added in M4 on 2026-10-05,
after the pilot run, from records fixed before it (0018, 0019). Every rule
below is fixed in an ADR before the strategy it applies to was measured; the
number in brackets names the record, and the figures are the ones those
records verify.

## The question and the comparison

At the same token budget, which kinds of memory question does each strategy
answer, and at what cost? Three strategies for a conversational assistant's
memory stand behind one interface, `ConversationMemory`, with three
operations: `write` a turn, `retrieve` context for a question within a token
budget, and `end_session`. A strategy decides for itself what to keep, what
to recall and when to consolidate; the harness never does it for it.

A fourth strategy, `FactGraphMemory`, was added in the last week. It stands
behind the same interface and is measured as a pilot on 20 questions, in a
table of its own; the comparison is the three (0018, 0019).

The assistant the memory serves is a Swedish household planner that answers
from its database rather than from memory, so the assistant is never in the
measured path. The harness, `evals/longmemeval.py`, drives the memory module
directly.

## The benchmark and the questions

The data is LongMemEval_S in the authors' cleaned version, pinned by sha256;
the harness refuses any other file (0004). Two question types are used, chosen
because they separate the hypotheses: `single-session-user`, where the user
stated a fact once, and `knowledge-update`, where the user stated a value and
later changed it. Each question comes with a history of about 48 sessions and
about 100,000 tokens, far more than the budget, and marks the turns that hold
the answer, which is what makes recall measurable.

**Which questions (0005).** A question is eligible when it is of one of the
two types, is not an abstention question, has no repeated session id, has at
least one evidence turn, and has its evidence sessions dated on or before the
question's day and in the same order by time as in the list. That leaves 61
`single-session-user` and 69 `knowledge-update` questions; the excluded ones
are listed by id in the record. Within each type the eligible questions are
ordered by the sha256 of their id, the order was committed before any
strategy ran, and a run takes the first N of each list. M1 was a pilot on the
first 10 of each type. N was then fixed at 61 per type from the estimated cost
of the whole comparison, consolidation included (0010), so the comparison uses
every eligible `single-session-user` question and leaves the last 8
`knowledge-update` questions unmeasured. Nothing is ever drawn again.

**Long-term, defined.** A fact is long-term when more conversation lies
between it and the question than fits in the budget. The harness logs that
distance in tokens for every question and reports whether a sample sits
nearer the evidence than the pool it came from; it never filters on it
(0005).

## Replaying a history (0004)

Every session is written to a fresh instance of the strategy, turn by turn, in
clock order: a stable sort on the full session timestamps, as LongMemEval's
own reader sorts them. Each turn becomes one record with its role and content
unchanged, its session's timestamp, and the id `session:turn`, derived from
position and never random, so that two strategies name the same turn the same
way (0001). `end_session` is called after every session. The harness raises if
two records would share an id.

The question is treated as asked at the end of its day: everything dated on
or before that day is written, and `retrieve` is called at 23:59 on the
question's day, with the same cutoff for every strategy. This is an
interpretation the dataset does not state. Its dates hold to the day but not
to the minute, and within a day the order of sessions follows the clock, which
is the least reliable part of the dates. The choice moves the baseline, since
the list order would put the evidence nearer the end more often, so recall is
also computed with each day replayed in list order and reported as a
secondary figure (0009).

The time cutoff in `retrieve` is enforced but not exercised by this dataset,
in which no session is dated after its question's day; the memory tests cover
it.

## Budget and tokens (0006)

Every token is counted with tiktoken's `o200k_base`, the tokenizer of the
answering model, for the budget and for cost alike. The budget is 8,000
tokens for every strategy and counts the content of the recalled messages and
nothing else: not the role framing, the system prompt or the question.

Cost is measured on the LLM client, not inside the memory module: a recording
client wraps every call and logs its label and its input and output tokens. A
strategy's cost for a question is the answer call plus any call the strategy
itself makes, such as consolidation; grading calls and failed attempts are the
measurement's cost, not the strategy's. The count is slightly below the bill:
the provider adds 4 tokens per message and 3 per call, measured against the
provider's own count before the pilot (0010), about 2% on a full answer call.
Since a strategy that recalls short turns sends more messages than one that
recalls long ones, the report gives cost both as counted and with that framing
added (0011).

## The strategies as measured

**`RecentTurnsMemory`** is the assistant's default: the most recent turns. In
the evaluation it runs without its turn window of 10 turns, which would bind
long before the budget and leave it about half the context the other
strategies get; its only limit is the budget, so the row means "the most
recent messages that fit in 8,000 tokens" (0007). On a long-term question its
recall is zero by construction, and a correct answer there is a guess or a
restatement of the fact in a later turn.

**`RetrievalMemory`** ranks every record against the question with BM25, a
lexical score over the words the two share, with Lucene's defaults
(`k1 = 1.2`, `b = 0.75`), no stemming and no stopword list, and with the
statistics taken over the records visible at the cutoff only (0011). Both the
user's and the assistant's turns are indexed. Recall fills the budget in rank
order, passing over a record that does not fit, and never exceeds it. The
recalled messages are returned in the order they were written, not by rank:
the model sees no dates, so order is the only thing that tells it which of two
values is newer, and rank order would decide the hypothesis about changed
facts by construction. The strategy makes no model call. Its parameters were
fixed before its first dry run, which shows recall for free and could
otherwise have been used to tune them. The row is reported as BM25 retrieval,
not retrieval in general: a question that words a fact differently from the
turn that states it can miss it. As a secondary figure, recall is also
computed with only the user's turns written, which is how LongMemEval's own
retrieval indexes turns.

**`ConsolidatingMemory`** keeps a rolling summary over a recent window. After
every session it makes one call to `gpt-4o-mini-2024-07-18`, the model 0010's
estimate assumed, with the notes so far and the session's turns as quoted
transcript, and the reply becomes the new notes (0015). The notes are held
to S = 1000 tokens: the prompt asks for 750 words, states the limit first and
forbids links and markdown; a reply over S is asked for once more with its
word count; a second reply over S is cut from the start, at a sentence
boundary, so the oldest notes go first, as the baseline's window forgets
(0015, 0017). A session the model fails three times, which in the smoke tests
was a reply that looped on one phrase or on whitespace until the JSON never
closed, is skipped: the notes stay as they were and the skip is counted (0016).
At recall the newest notes visible at the cutoff come first, as one assistant
turn, and the most recent raw turns that fit in the rest of the budget follow
in the order they were written; raw turns are kept after consolidation, so
without visible notes the strategy is the baseline (0015). The notes are
stamped with the latest time the strategy has been given, never the wall
clock, so they can neither leak past a cutoff nor be backdated (0014). Recall
and precision count the notes' id as one recalled item that matches no
evidence, so evidence that reached the model only through the notes counts
as missed; next to them the strategy reports *evidence consolidated*, the
share of evidence turns the consolidator read, from the flat list of turn
ids each summary derives from (0013). Both figures are computable without a
model, so the prompt, S and the cut rule were fixed before the strategy's
first dry run. The consolidation calls are the strategy's own cost, logged
under their own label and priced at the consolidator's rate; the list-order
replay of 0009 is made on the ten `knowledge-update` pilot questions only,
and its calls are not counted as the strategy's (0009, 0015). What the
consolidator wrote is kept in every row, since the strategy cannot be
replayed to the same text.

**`FactGraphMemory`** keeps single facts with their times in a graph
database and replaces a fact when a newer one has its name. After every
session it makes one call to `gpt-4o-mini-2024-07-18`, the model that also
consolidates, with the facts that hold so far and the session's turns,
numbered; the reply is a list of triples, subject, relation and value, each
with the turn it comes from (0018). A fact replaces the facts of earlier
sessions that hold under its subject and relation. The names are compared
after case folding, with runs of whitespace made one space, and nothing
else; the rule is in the code and not left to the model, which is told the
rule and never says what a fact replaces. A fact said again with the value
it already has is not stored, and the older one stands. A replaced fact is
kept, marked with what replaced it and when, and is never shown, so nothing
is deleted and what held at an earlier time can still be asked for. The
facts live in Neo4j 5.26.31, each as an edge from its subject to its value,
in a store held to no size, behind a small store interface; the tests and
the dry run use a store in the process. A fact is stamped with the
strategy's clock when the extraction ran, as the notes are, and never with
the time of its turn (0014); it holds at a cutoff when it was stored by
then and not replaced by then. A session the model fails three times is
skipped and counted (0016). At recall the facts that hold at the cutoff are
ranked against the question with the BM25 of 0011, each on its line
together with the text of the turn the model named for it. Walking down
the ranking, a fact is taken when the facts message with its line added
stays within F = 1000 tokens, and passed over when it does not. That
message comes first, as one assistant turn, with the lines in the order
they were stored and no date, rank, label or score; the most recent raw
turns that fit in the rest of the budget follow, as for
`ConsolidatingMemory`. Recall and precision count the window only, and
every fact shown counts as one recalled item that matches no evidence, so
precision falls by construction and is reported, not compared. *Evidence
consolidated* means less here than for the notes: that an evidence turn's
session gave at least one fact that is shown, not that the fact is the
right one (0013, 0018). The row also counts the facts stored, replaced,
held and shown, and of the facts that name an evidence turn how many were
replaced and how many shown, so that what the rule hides is counted next to
what it finds. The prompt and the rule were shaped, and the ranking text
chosen, on a spike over the eight `knowledge-update` histories that no run
measures, in three rounds without answers or grading; they and F were fixed
before the strategy's first run. The extraction calls are the strategy's
own cost under their own label; those of the list-order replay, here made
on all ten `knowledge-update` questions, are not (0009, 0018). The facts of
every replay are written out next to the run's rows, since an extraction
cannot be made again to the same names.

## The pilot (0019)

The fourth strategy is measured on the 20 questions of the M1 pilot, the
first ten of each type in the committed order, so they were not picked after
any result and every strategy has rows for them. Its figures stand in a table
of their own, the four strategies on the same 20 questions, where the other
three are read from the rows of their committed runs of 2 and 3 October. It
is never a row of the main table. With ten questions per type one question
moves a share by 0.1, and a repeat of the same 20 questions changed one
answer, so a difference of one or two questions between two rows is not a
finding. The pilot reports what happened on each question and whether the
mechanism works at all. Its answers were read by hand before any figure was
reported, and for every wrong answer the reading says whether the value was
in the graph, whether it was shown, and whether the old value had been
replaced or both were held.

That reading was not made as the earlier ones were. An AI assistant in chat
read all 20 answers first and sorted them, and its summary of the errors was
in the chat before the author read. The author then judged the seven
questions that need a judgement, the four errors and three others, one of
them together with the assistant, and went over the other thirteen against
the assistant's rows, which is a check of those rows and not a second
sorting. The notes were then checked against the rows, the facts the run
left and the dataset, and the review says where the rows differ from them.

## Answering and grading (0008)

The model receives the strategy's recalled messages unchanged as its own
earlier conversation, followed by one user message with the question's date
and the question, under a fixed system prompt that tells it to answer from
that conversation only and to say when it does not know. The model is
`openai/gpt-4o-2024-08-06` through OpenRouter, named by its dated id, at
temperature 0 and in JSON mode. The same model grades: it receives
LongMemEval's own grading template for the question type, filled with the
question, the reference answer and the model's answer, and an answer is
correct when it replies yes. A call that fails is tried twice more, a question
that still fails is run again before any figure is reported, and one that
fails even then is dropped from every strategy's figures, so that every row
rests on the same questions.

Three things follow. The history reaches the model as chat turns without
dates, unlike LongMemEval's reader, which gives one block of text with session
dates; comparisons with published LongMemEval figures are therefore
approximate. One model answers and grades its own answers, against a reference
answer, which limits what that can matter but is a limitation. And because the
history is the model's own conversation, an instruction in a filler session
is an instruction to it: the answers of every run are read by hand for that
before any figure is reported, and the reading is recorded in
`evals/results/`.

## Measures (0009)

- **Correct answers**, as a share per question type, each question counting
  once.
- **Whether the evidence reached the model.** Recall is the share of a
  question's evidence turns among the records the strategy returned, and
  precision the share of returned records that are evidence; both are per
  turn, using the dataset's marks as they are, and averaged over questions.
  Precision is bounded by the budget: with one or two evidence turns among
  about 40 recalled messages, a strategy that finds everything scores around
  0.03 to 0.05, and the figure shows how much of an equal budget goes to
  noise. The number of questions where any evidence turn reached the context
  is reported next to recall.
- **The `knowledge-update` breakdown.** Each question's two evidence sessions
  are split into the earlier and the later by replay order, and the harness
  logs which reached the context: neither, the earlier only, the later only,
  or both, against whether the answer was correct. It does not assume which
  value a question asks for, since some ask for the earlier one, and it was
  declared before any strategy was measured.
- **Cost**, in tokens and dollars per question, as counted and with framing,
  with each strategy's own calls under their own label.

Accuracy is reported together with the share of questions where the evidence
reached the context, so that a strategy's failures, where the evidence never
reached the model, are told apart from the model's, where it did and the
answer was still wrong.

## Keeping the comparison fair

Every measurement rule is recorded as an ADR before the strategy it applies to
is measured, and the question lists were committed before any run. A
committed record is reopened only by a finding that the measurement itself is
wrong, such as a record crossing the time cutoff or evidence that cannot be
reached, and then everything measured under it is measured again; every other
finding becomes a limitation. The answers of every run are read by hand
before its figures are reported. That reading is one reading made in
dialogue, not two independent ones: the author read every answer and gave a
judgement, an AI assistant in chat gave its own, and the categories are what
the two agreed on; the author's notes and the review written from them,
checked against the rows and the dataset, are both kept in `evals/results/`.
The pilot's reading went the other way round, the assistant first, and is
described under "The pilot".

## Limitations of the method, so far

- The answering model is not deterministic at temperature 0. The same context
  has given "I do not know" and then the right answer to one question, and a
  repeat of the pilot's 20 questions agreed with the pilot on 19. Every row
  carries that noise alike.
- With 61 questions per type, one question moves a share by 0.016, and a
  difference of a few questions between two rows is within chance.
- The dataset marks one turn per value. A fact restated in a later turn is
  not marked, so per-turn recall undercounts what reached the model in such
  cases; and in one question the marked turn does not itself hold the answer,
  so "evidence reached" can be true with the answer absent.
- Two pairs of measured `knowledge-update` questions share their evidence
  sessions, so the 61 are not 61 independent facts.
- The results hold for English conversations, one model and one budget; for
  the Swedish assistant they are an indication to be checked.
- The retrieval row is one lexical index. A dense index would miss less on
  paraphrase and was not measured.
- The consolidation model is a weaker one than the answering model, which
  confounds the third hypothesis (0010). It did not keep to the size it was
  asked for: the size is held by a second call and then by code, and a cut
  summary is one the model did not make (0015, 0017). At temperature 0 it
  sometimes loops instead of answering, and the session is then skipped
  (0016). The summaries are not reproducible between runs.
- The recall figure of `ConsolidatingMemory` measures its window only; what
  the notes carried is visible in accuracy and in *evidence consolidated*,
  not in recall (0013).
- The fourth strategy is a pilot on 20 questions that had been used before:
  by the M1 pilot, by the smoke tests of the third row and, for the first
  question of each type, by its own smoke test. It cannot rank the strategy
  against the other three (0019).
- Its prompt and rule were shaped on eight unmeasured histories that share
  54 filler sessions with measured ones, 14 of them with the pilot's 20. No
  evidence session, question or answer of a measured history was seen (0018).
- The rule replaces on the name, and the names are the extraction model's.
  They are not reproducible between runs; a changed value that gets a new
  name is not replaced, and unrelated facts under a general name replace each
  other. The rows count what was replaced, and the reading says where a
  changed value was not (0018, 0019).
- The fourth strategy differs from the third in more than what it is there
  to test: another prompt, triples instead of prose, and a choice among the
  facts for each question. The pilot does not tell these apart (0018).
- LongMemEval asks one question, after the last session, so the pilot
  measures the last state only. What held at an earlier time is kept in the
  graph and is not measured (0019).
- The graph is a store of timestamped edges, not a graph that is traversed:
  nearly every fact hangs on the user, all but 15 of the 2,381 the pilot
  stored (0018).
- The grading template for `knowledge-update` has no rule for an answer that
  holds only a part of the reference. In the pilot one such answer was
  accepted and one rejected; the verdicts stand as the judge gave them, and
  the review names the questions (0008).
- The pilot's hand reading was less independent than the earlier ones: the
  AI assistant read first, and the author judged seven of the 20 answers and
  checked the other thirteen against its rows.
