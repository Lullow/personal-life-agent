# Method (draft)

Status: draft, written in M2 on 2026-10-03. M3 adds the rules for
`ConsolidatingMemory`. Every rule below is fixed in an ADR before the strategy
it applies to was measured; the number in brackets names the record, and the
figures are the ones those records verify.

## The question and the comparison

At the same token budget, which kinds of memory question does each strategy
answer, and at what cost? Three strategies for a conversational assistant's
memory stand behind one interface, `ConversationMemory`, with three
operations: `write` a turn, `retrieve` context for a question within a token
budget, and `end_session`. A strategy decides for itself what to keep, what
to recall and when to consolidate; the harness never does it for it. Two are
measured so far, `RecentTurnsMemory` and `RetrievalMemory`.

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

**`ConsolidatingMemory`** is not measured yet. Before it is, three rules are
recorded: which model consolidates, how a summary's id counts toward recall,
and where the strategy's clock comes from during a replay (0009, 0010).

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
before its figures are reported.

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
- The consolidation model, when M3 is measured, is a weaker one than the
  answering model, which confounds the third hypothesis (0010).
